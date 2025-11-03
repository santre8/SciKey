#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
from pathlib import Path
from typing import Dict, List, Set

import utils as U
import wikidata_api as W
from neo4j_io import Neo4jConnector, ingest_p31_types, ingest_p279_hierarchy, ingest_document_map

def map_keywords(records: List[Dict], neo4j_conn: Neo4jConnector) -> List[Dict]:
    rows = []
    seen_pairs = set()

    for rec in records:
        title = rec.get("title_s") or ""
        abstract = rec.get("abstract_s") or ""
        context = f"{title}. {abstract}".strip(". ")
        docid = rec.get("docid") or rec.get("halId_s") or ""

        # HAL → buckets → cfg
        hal_buckets = U.extract_hal_buckets(rec)
        domain_cfg = U.merge_domain_cfg_for_buckets(hal_buckets)

        # keywords
        keywords = rec.get("keyword_s") or []
        if not keywords and rec.get("keywords_joined"):
            raw = rec["keywords_joined"]
            keywords = [k.strip() for k in re.split(r"[;,]", raw) if k.strip()]

        print(f"\n--- Doc {docid} | {len(keywords)} keywords | HAL: {hal_buckets} ---")

        for kw in keywords:
            if (docid, kw) in seen_pairs:
                continue
            seen_pairs.add((docid, kw))

            qid = label = bnf = ""
            disambig = False
            match_stage = "none"
            best_sim = 0.0
            best_score = 0.0
            p31s_out: Set[str] = set()
            p31_labels_out = ""
            p279_paths_labels: List[str] = []
            domain_bonus_val = 0
            domain_hits = ""

            cand = W.pick_with_context_then_exact(kw, context, domain_cfg=domain_cfg)

            if cand:
                ent = W.wbgetentities([cand["id"]]).get(cand["id"], {})
                if ent:
                    disambig = W.is_disambiguation(cand["id"], ent)
                    if not disambig:
                        qid = cand["id"]
                        label = W.extract_label(ent)
                        bnf = W.extract_bnf_id(ent) or ""
                        match_stage = cand.get("__stage", "context_or_exact")
                        best_sim = cand.get("label_similarity", 0.0)
                        best_score = cand.get("match_score", 0.0)
                        domain_bonus_val = cand.get("__domain_bonus", 0)
                        domain_hits = ";".join(cand.get("__domain_hits", []))

                        # P31
                        p31s_out = W.get_p31_ids(ent)
                        p31_labels = W.get_labels_for(list(p31s_out)) if p31s_out else {}
                        p31_labels_out = ";".join(p31_labels.get(x, x) for x in p31s_out)

                        # Ingesta Neo4j: P31
                        ingest_p31_types(neo4j_conn, qid, p31s_out, p31_labels)

                        # P279*
                        direct_p279 = W._claim_ids(ent, U.P_SUBCLASS_OF)
                        if direct_p279:
                            qid_paths = W.expand_p279_paths(direct_p279, U.MAX_LEVELS_LINEAGE, U.LANGS)

                            all_p279_qids = set()
                            for qpath in qid_paths:
                                all_p279_qids.update(qpath)
                            p279_labels_map = W.get_labels_for(list(all_p279_qids), U.LANGS)

                            # Ingesta Neo4j: jerarquía
                            ingest_p279_hierarchy(neo4j_conn, qid, label, qid_paths, p279_labels_map)

                            # CSV: rutas legibles
                            for qpath in qid_paths:
                                p279_paths_labels.append(" > ".join(p279_labels_map.get(q, q) for q in qpath))

                        # Neo4j: doc-keyword-item
                        ingest_document_map(neo4j_conn, docid, kw, qid)

            paths = p279_paths_labels or [""] if qid else [""]

            for path_text in paths:
                rows.append({
                    "docid": docid, "title": title, "keyword": kw,
                    "wikidata_label": label, "wikidata_qid": qid,
                    "bnf_id": bnf, "p279_path": path_text,
                    "retry_source": match_stage, "match_stage": match_stage,
                    "is_disambiguation": "yes" if (cand and disambig) else "no",
                    "label_similarity": round(best_sim, 1),
                    "match_score": round(best_score, 1),
                    "p31_types": ";".join(sorted(p31s_out)) if p31s_out else "",
                    "p31_label": p31_labels_out,
                    "hal_domains": "|".join(hal_buckets),
                    "domain_bonus": domain_bonus_val,
                    "domain_hits": domain_hits,
                })

    return rows

# ==================== MAIN ====================
import re  # requerido aquí (split de keywords)

def main():
    # 1) Conexión a Neo4j
    print(f"🔗 Conectando a Neo4j en {U.NEO4J_URI} ...")
    try:
        uri_to_connect = U.NEO4J_URI.replace("localhost", "127.0.0.1")
        neo4j_conn = Neo4jConnector(uri_to_connect, U.NEO4J_USER, U.NEO4J_PASSWORD)
        neo4j_conn.driver.verify_connectivity()
        print("✅ Conexión con Neo4j OK.")
    except Exception as e:
        print(f"❌ Error al conectar a Neo4j: {e}")
        return

    # 2) Construir sets P31 (disallowed/preferred) a QIDs y guardarlos en utils
    disallowed, preferred = W.build_p31_type_sets()
    U.set_disallowed_preferred(disallowed, preferred)
    print(f"✅ DISALLOWED_P31: {len(U.DISALLOWED_P31)} | PREFERRED_P31: {len(U.PREFERRED_P31)}")

    # 3) Construir cfg de dominio HAL (whitelist P31 + raíces P279) y guardarlo en utils
    domain_cfg_qids = W.build_domain_cfg_qids()
    U.set_domain_cfg_qids(domain_cfg_qids)
    print("✅ Roots/whitelists de dominio resueltas a QIDs.")

    # 4) Leer JSON
    print(f"📥 Leyendo JSON: {U.INPUT_JSON}")
    with open(U.INPUT_JSON, "r", encoding="utf-8") as f:
        records = json.load(f)

    # 5) Procesar y escribir CSV
    print(f"🔍 Procesando {len(records)} records...")
    rows = map_keywords(records, neo4j_conn)

    fieldnames = [
        "docid", "title", "keyword", "wikidata_label", "wikidata_qid",
        "bnf_id", "p279_path", "retry_source", "match_stage", "is_disambiguation",
        "label_similarity", "match_score", "p31_types", "p31_label",
        "hal_domains", "domain_bonus", "domain_hits"
    ]

    U.OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    print(f"💾 Guardando CSV en: {U.OUTPUT_CSV}")
    with open(U.OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    neo4j_conn.close()
    print("✅ Proceso finalizado. Conexión a Neo4j cerrada.")

if __name__ == "__main__":
    main()
