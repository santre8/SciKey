import csv
import json
import re
from typing import Dict, List, Optional, Tuple, Set

from . import config
from .neo4j_io import Neo4jConnector, ingest_p279_hierarchy, ingest_document_map, ingest_p31_types
from .matchers import pick_with_context_then_exact
from .wikidata_api import (
    wbgetentities, extract_bnf_id, extract_label, is_disambiguation,
    get_p31_ids, expand_p279_paths, _claim_ids
)
from .wikidata_api import wbgetentities as _wbget  # explicit alias
from .wikidata_api import _claim_ids as claim_ids
from .wikidata_api import extract_label as get_label
from .wikidata_api import extract_bnf_id as get_bnf
from .wikidata_api import wbgetentities as fetch_entities
from .wikidata_api import _claim_ids as get_claim_ids
from .wikidata_api import wbgetentities as get_entities
from .wikidata_api import _claim_ids as claim_ids_util
from .wikidata_api import wbgetentities as entities_fetcher  # optional, just clarifies aliasing

def _split_keywords(raw: str) -> List[str]:
    """Split keywords separated by commas or semicolons."""
    return [k.strip() for k in re.split(r"[;,]", raw) if k.strip()]

def get_labels_for(qids: List[str], languages: List[str] = None) -> Dict[str, str]:
    """Lightweight version to retrieve labels for QIDs (used for CSV output)."""
    languages = languages or config.LANGS
    entities = _wbget(qids, languages)
    labels = {}
    for q, ent in entities.items():
        lab = None
        for lg in languages:
            if "labels" in ent and lg in ent["labels"]:
                lab = ent["labels"][lg]["value"]
                break
        labels[q] = lab or q
    return labels

def map_keywords(records: List[Dict], neo4j_conn: Neo4jConnector) -> List[Dict]:
    """Map HAL keywords to Wikidata QIDs, create Neo4j nodes, and prepare CSV rows."""
    rows = []
    seen_pairs = set()

    for rec in records:
        title = rec.get("title_s") or ""
        abstract = rec.get("abstract_s") or ""
        context = f"{title}. {abstract}"
        docid = rec.get("docid") or rec.get("halId_s") or ""

        keywords = rec.get("keyword_s") or []
        if not keywords and rec.get("keywords_joined"):
            keywords = _split_keywords(rec["keywords_joined"])

        print(f"\n--- Processing Document {docid} with {len(keywords)} keywords ---")

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

            # Try to find the best Wikidata match for the keyword
            cand = pick_with_context_then_exact(kw, context)

            if cand:
                ent = wbgetentities([cand["id"]]).get(cand["id"], {})
                if ent:
                    disambig = is_disambiguation(cand["id"], ent)
                    if not disambig:
                        qid = cand["id"]
                        label = get_label(ent)
                        bnf = get_bnf(ent) or ""
                        match_stage = cand.get("__stage", "context_or_exact")
                        best_sim = cand.get("label_similarity", 0.0)
                        best_score = cand.get("match_score", 0.0)

                        # P31 (instance of)
                        p31s_out = get_p31_ids(ent)
                        p31_labels = get_labels_for(list(p31s_out)) if p31s_out else {}
                        p31_labels_out = ";".join(p31_labels.get(x, x) for x in p31s_out)

                        # Neo4j: insert P31 relationships
                        if neo4j_conn and config.ENABLE_NEO4J_INGEST:
                            ingest_p31_types(neo4j_conn, qid, p31s_out, p31_labels)

                        # P279 (subclass of)
                        direct_p279 = claim_ids(ent, config.P_SUBCLASS_OF)
                        if direct_p279:
                            qid_paths = expand_p279_paths(
                                direct_p279,
                                config.MAX_LEVELS_LINEAGE,
                                config.LANGS
                            )

                            # Neo4j: insert P279 hierarchy
                            if neo4j_conn and config.ENABLE_NEO4J_INGEST:
                                ingest_p279_hierarchy(neo4j_conn, qid, label, qid_paths)

                            # CSV: collect subclass labels
                            for qpath in qid_paths:
                                labs = get_labels_for(qpath, config.LANGS)
                                p279_paths_labels.append(" > ".join(labs.get(q, q) for q in qpath))

                        # Neo4j: create Document–Keyword–Item mapping
                        if neo4j_conn and config.ENABLE_NEO4J_INGEST:
                            ingest_document_map(neo4j_conn, docid, kw, qid)

            # CSV (replicate for each P279 path; if no QID, create an empty row)
            paths = p279_paths_labels or [""] if qid else [""]
            for path_text in paths:
                rows.append({
                    "docid": docid, "title": title, "keyword": kw,
                    "wikidata_label": label, "wikidata_qid": qid,
                    "bnf_id": bnf, "p279_path": path_text,
                    "retry_source": match_stage, "match_stage": match_stage,
                    "is_disambiguation": "yes" if (cand and disambig) else "no",
                    "label_similarity": round(best_sim, 1), "match_score": round(best_score, 1),
                    "p31_types": ";".join(sorted(p31s_out)) if p31s_out else "",
                    "p31_label": p31_labels_out,
                })

    return rows

def write_csv(rows: List[Dict], out_path):
    """Write the mapping results to a CSV file."""
    fieldnames = [
        "docid", "title", "keyword", "wikidata_label", "wikidata_qid",
        "bnf_id", "p279_path", "retry_source", "match_stage", "is_disambiguation",
        "label_similarity", "match_score", "p31_types", "p31_label"
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
