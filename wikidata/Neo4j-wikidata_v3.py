#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
import re
import time
from typing import Dict, List, Optional, Tuple
from pathlib import Path

import requests
from rapidfuzz import fuzz
# Importación corregida
from neo4j import GraphDatabase, Driver, WRITE_ACCESS

# =============== CONFIG & CONSTANTS =================
INPUT_JSON = Path(r"C:\Users\sanda\Documents\Langara_College\DANA-4850-001-Capstone_Project\hall-api-test-db-mysql\api\data\upec_chemical_20.json")
OUTPUT_CSV = Path(r"C:\Users\sanda\Documents\Langara_College\DANA-4850-001-Capstone_Project\hall-api-test-db-mysql\wikidata\hal_field_audit_out\Wikidata_upec_chemical_20.csv")

# Neo4j CONFIG
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "your_password"  # ¡ACTUALIZA ESTA LÍNEA!

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
HEADERS = {"User-Agent": "Keyword2Wikidata/1.3 (contact: your-email@example.com)"}

# Propiedades de Wikidata
P_INSTANCE_OF = "P31"
P_SUBCLASS_OF = "P279"
P_BNF_ID = "P268"
Q_DISAMBIGUATION = "Q4167410"

# Idiomas y umbrales
LANGS = ["en", "fr"]
MIN_LABEL_SIM = 70
MIN_TOTAL_SCORE = 30
MAX_LEVELS_LINEAGE = 5
SEARCH_LIMIT = 50

# ====== P31 config (por LABEL; se resuelve a QIDs al inicio) ======
DISALLOWED_P31_LABELS = [
    # Contenido/obras/espacios Wikimedia
    "Wikimedia disambiguation page",
    "Wikimedia category",
    "Wikimedia template",
    "Wikimedia list article",

    # Obras/publicaciones
    "scholarly article",
    "academic journal",
    "book",
    "thesis",
    "conference paper",
    "report",
    "magazine",
    "newspaper",
    "patent",

    # Entidades no-temáticas frecuentes
    "organization",
    "company",
    "university",
    "human",
    "person",
    "award",
    "software",      # quítalo si SÍ quieres mapear software como concepto
    "website",

    # Lugares/eventos (quítalos si SÍ mapeas lugares)
    "country",
    "city",
    "human settlement",
    "building",
    "event",
]

PREFERRED_P31_LABELS = [
    # Genéricos de conocimiento/ciencia
    "scientific concept",
    "academic discipline",
    "theory",
    "model",
    "method",
    "technique",
    "process",
    "phenomenon",
    "property",
    "quantity",

    # Física / Mecánica / Fluidos
    "physical quantity",
    "physical law",
    "physical constant",

    # Química / Materiales
    "chemical compound",
    "chemical substance",
    "chemical process",

    # Computación / Matemáticas (por si aparecen)
    "algorithm",
    "data structure",
    "computing concept",
    "mathematical object",

    # Bio (usa sólo si te aparece bio en el corpus)
    "biological process",
    "disease",
]

# ====== Dominio HAL → configuración semántica (por LABEL; se resuelve a QIDs) ======
DOMAIN_CFG_LABELS = {
    "Physics": {
        "p31_whitelist_labels": [
            "scientific concept", "physical quantity", "physical law", "phenomenon", "academic discipline"
        ],
        "p279_root_labels": ["physics", "mechanics", "fluid mechanics"]
    },
    "Engineering Sciences": {
        "p31_whitelist_labels": [
            "engineering concept", "technology", "method", "process", "academic discipline"
        ],
        "p279_root_labels": ["engineering", "civil engineering", "mechanical engineering", "chemical engineering"]
    },
    "Mechanics": {
        "p31_whitelist_labels": ["scientific concept", "physical quantity", "phenomenon", "method", "model"],
        "p279_root_labels": ["mechanics"]
    },
    "Fluid mechanics": {
        "p31_whitelist_labels": ["scientific concept", "physical quantity", "phenomenon", "method", "model"],
        "p279_root_labels": ["fluid mechanics", "fluid dynamics"]
    },
}

# Mapeo de ocurrencias de cadenas en HAL → buckets semánticos
_HAL_DOMAIN_BUCKETS_MAP = {
    "physics": "Physics",
    "engineering sciences": "Engineering Sciences",
    "mechanics": "Mechanics",
    "fluid mechanics": "Fluid mechanics",
    "fluids mechanics": "Fluid mechanics",  # variante observada
}

# ====== Caches en memoria ======
_QID_CACHE_BY_LABEL: Dict[Tuple[str, str], str] = {}   # (label_lower, lang)->qid
_LABELS_CACHE_BY_QID: Dict[str, str] = {}              # qid->label (no imprescindible aquí)
_ANCESTOR_CACHE: Dict[str, set] = {}                   # qid->set(ancestros P279)

# Estos dos se completan en runtime:
DISALLOWED_P31: set = set()
PREFERRED_P31: set = set()
DOMAIN_CFG_QIDS: Optional[Dict[str, Dict[str, set]]] = None


# =============== NEO4J CONNECTOR =================
class Neo4jConnector:
    def __init__(self, uri, user, password):
        self.driver: Driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def run_query(self, query: str, parameters: Optional[Dict] = None):
        with self.driver.session(default_access_mode=WRITE_ACCESS) as session:
            try:
                result = session.execute_write(self._execute_query, query, parameters)
                return result
            except Exception as e:
                print(f"Error al ejecutar Cypher: {e}\nConsulta: {query}\nParámetros: {parameters}")
                return None

    @staticmethod
    def _execute_query(tx, query, parameters):
        return tx.run(query, parameters).consume()


# =============== NEO4J INGESTION LOGIC =================
def ingest_p279_hierarchy(connector: Neo4jConnector, entity_qid: str, entity_label: str,
                          qid_paths: List[List[str]], labels_map: Dict[str, str]):
    """Guarda la entidad y rutas P279 con labels."""
    connector.run_query("""
        MERGE (e:Item {qid: $qid})
        SET e.label = $label
    """, {"qid": entity_qid, "label": entity_label})

    for path in qid_paths:
        current_child_qid = entity_qid
        for parent_qid in path:
            if parent_qid == current_child_qid:
                continue
            parent_label = labels_map.get(parent_qid, parent_qid)
            connector.run_query("""
                MERGE (child:Item {qid: $child_qid})
                MERGE (parent:Item {qid: $parent_qid})
                SET parent.label = $parent_label
                MERGE (child)-[:SUBCLASS_OF]->(parent)
            """, {
                "child_qid": current_child_qid,
                "parent_qid": parent_qid,
                "parent_label": parent_label
            })
            current_child_qid = parent_qid

    print(f"   -> [Neo4j] Item {entity_qid} ingresado con {len(qid_paths)} rutas P279.")


def ingest_document_map(connector: Neo4jConnector, docid: str, keyword: str, qid: str):
    connector.run_query("""
        MERGE (d:Document {id: $docid})
        MERGE (k:Keyword {name: $keyword})
        MERGE (q:Item {qid: $qid})
        MERGE (d)-[:CONTAINS_KEYWORD]->(k)
        MERGE (k)-[:MAPS_TO]->(q)
    """, {"docid": docid, "keyword": keyword, "qid": qid})


def ingest_p31_types(connector: Neo4jConnector, entity_qid: str, p31_ids: set, p31_labels: Dict[str, str]):
    for p31_qid in p31_ids:
        label = p31_labels.get(p31_qid, p31_qid)
        connector.run_query("""
            MERGE (item:Item {qid: $item_qid})
            MERGE (type:Class {qid: $type_qid})
            SET type.label = $type_label
            MERGE (item)-[:INSTANCE_OF]->(type)
        """, {"item_qid": entity_qid, "type_qid": p31_qid, "type_label": label})


# =============== Funciones Helper =================
_ws_re = re.compile(r"\s+", re.UNICODE)
_token_re = re.compile(r"[^\w\-]+")

def normalize_kw(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\u00A0", " ").replace("\ufeff", "")
    s = _ws_re.sub(" ", s.strip())
    s = s.strip(";, ")
    return s

def tokenize(text: str) -> List[str]:
    return [t for t in _token_re.split((text or "").lower()) if t]

def singularize_en(word: str) -> str:
    w = normalize_kw(word)
    wl = w.lower()
    if len(w) > 3 and wl.endswith("ies"): return w[:-3] + "y"
    if len(w) > 3 and wl.endswith("ses"): return w[:-2]
    if len(w) > 2 and wl.endswith("s") and not wl.endswith("ss"): return w[:-1]
    return w

def _get(params: Dict, sleep_sec: float = 0.1) -> Dict:
    params = {**params, "format": "json"}
    for attempt in range(5):
        try:
            r = requests.get(WIKIDATA_API, params=params, headers=HEADERS, timeout=20)
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                raise RuntimeError(data["error"])
            time.sleep(sleep_sec)
            return data
        except Exception:
            if attempt == 4:
                raise
            time.sleep(0.5 * (attempt + 1))
    return {}

def wbsearchentities(search: str, language: str = "en", limit: int = SEARCH_LIMIT) -> List[Dict]:
    search = normalize_kw(search)
    return _get({
        "action": "wbsearchentities", "search": search, "language": language,
        "uselang": language, "type": "item", "limit": limit, "strictlanguage": 0
    }).get("search", [])

def wbsearch_label_only(search: str, language: str = "en", limit: int = SEARCH_LIMIT) -> List[Dict]:
    search = normalize_kw(search)
    return _get({
        "action": "wbsearchentities", "search": f"label:{search}", "language": language,
        "uselang": language, "type": "item", "limit": limit, "strictlanguage": 0
    }).get("search", [])

def chunked(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]

def wbgetentities(ids: List[str], languages: List[str] = LANGS) -> Dict:
    combined = {}
    for batch in chunked(list(ids), 50):
        data = _get({
            "action": "wbgetentities", "ids": "|".join(batch),
            "props": "labels|descriptions|aliases|claims",
            "languages": "|".join(languages), "languagefallback": 1
        }, sleep_sec=0.05)
        combined.update(data.get("entities", {}))
    return combined

def get_labels_for(qids: List[str], languages: List[str] = LANGS) -> Dict[str, str]:
    if not qids:
        return {}
    entities = wbgetentities(qids, languages)
    labels = {}
    for q, ent in entities.items():
        lab = None
        for lg in languages:
            if "labels" in ent and lg in ent["labels"]:
                lab = ent["labels"][lg]["value"]
                break
        labels[q] = lab or q
    return labels

def best_label_and_aliases_str(ent_like: Dict) -> str:
    label = ent_like.get("label") or ""
    aliases = " ".join(ent_like.get("aliases") or [])
    return f"{label} {aliases}".strip()

def label_similarity(keyword: str, ent_like: Dict) -> float:
    target = best_label_and_aliases_str(ent_like)
    return float(fuzz.token_sort_ratio(normalize_kw(keyword), normalize_kw(target)))

def context_overlap(keyword: str, context: str, ent_like: Dict) -> int:
    ctx_tokens = set(tokenize(normalize_kw(context)))
    label = (ent_like.get("label") or "")
    desc = (ent_like.get("description") or "")
    raw_aliases = " ".join(ent_like.get("aliases") or [])
    candidate_context_str = " ".join([label, desc, raw_aliases])
    all_candidate_tokens = tokenize(candidate_context_str)
    keyword_tokens = set(tokenize(normalize_kw(keyword)))
    cand_tokens = set(token for token in all_candidate_tokens if token not in keyword_tokens)
    return len(ctx_tokens & cand_tokens)

def total_score(keyword: str, context: str, ent_like: Dict, allow_exact_bonus: bool = True) -> float:
    lbl = normalize_kw(ent_like.get("label") or "").lower()
    kw_norm = normalize_kw(keyword).lower()
    kw_sing = singularize_en(kw_norm).lower()
    exact = (lbl == kw_norm) or (lbl == kw_sing)
    exact_bonus = 50.0 if (allow_exact_bonus and exact) else 0.0
    return exact_bonus + context_overlap(keyword, context, ent_like) + 0.6 * label_similarity(keyword, ent_like)

def _claim_ids(entity: Dict, pid: str) -> List[str]:
    out = []
    for cl in entity.get("claims", {}).get(pid, []):
        dv = cl.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        if isinstance(dv, dict) and dv.get("id"):
            out.append(dv["id"])
    return out

def get_p31_ids(entity: Dict) -> set:
    return set(_claim_ids(entity, P_INSTANCE_OF))

# ====== Resolución de labels → QIDs y construcción de sets ======
def resolve_label_to_qid(label: str, language: str = "en") -> Optional[str]:
    key = (label.lower(), language)
    if key in _QID_CACHE_BY_LABEL:
        return _QID_CACHE_BY_LABEL[key]
    hits = wbsearchentities(label, language=language, limit=5)
    if not hits:
        hits = wbsearch_label_only(label, language=language, limit=5)
    for h in hits or []:
        qid = h.get("id")
        if qid:
            _QID_CACHE_BY_LABEL[key] = qid
            return qid
    return None

def resolve_labels_to_qids(labels: List[str], language: str = "en") -> set:
    qids = set()
    for lab in labels:
        q = resolve_label_to_qid(lab, language=language)
        if q and q.startswith("Q"):
            qids.add(q)
    return qids

def build_p31_type_sets():
    dis_q = resolve_labels_to_qids(DISALLOWED_P31_LABELS, language="en")
    pref_q = resolve_labels_to_qids(PREFERRED_P31_LABELS, language="en")
    return dis_q, pref_q

# ====== HAL domains → buckets y cfg por QID ======
def build_domain_cfg_qids() -> Dict[str, Dict[str, set]]:
    cfg_by_qid = {}
    for bucket, cfg in DOMAIN_CFG_LABELS.items():
        p31_whitelist_q = resolve_labels_to_qids(cfg["p31_whitelist_labels"], language="en")
        roots_q = resolve_labels_to_qids(cfg["p279_root_labels"], language="en")
        cfg_by_qid[bucket] = {"p31_whitelist": p31_whitelist_q, "p279_roots": roots_q}
    return cfg_by_qid

def extract_hal_buckets(rec: Dict) -> List[str]:
    out = set()
    for raw in rec.get("en_domainAllCodeLabel_fs", []) or []:
        part = raw
        if "FacetSep_" in raw:
            part = raw.split("FacetSep_", 1)[1]
        for seg in re.split(r"[\/>]", part):
            seg_clean = re.sub(r"\[[^\]]*\]", "", seg).strip().lower()
            if not seg_clean:
                continue
            for key, bucket in _HAL_DOMAIN_BUCKETS_MAP.items():
                if key in seg_clean:
                    out.add(bucket)
    return sorted(out)

def merge_domain_cfg_for_buckets(buckets: List[str]) -> Dict[str, set]:
    if not buckets or not DOMAIN_CFG_QIDS:
        return {"p31_whitelist": set(), "p279_roots": set()}
    wl, roots = set(), set()
    for b in buckets:
        c = DOMAIN_CFG_QIDS.get(b)
        if not c:
            continue
        wl |= c["p31_whitelist"]
        roots |= c["p279_roots"]
    return {"p31_whitelist": wl, "p279_roots": roots}

# ====== Ancestros P279* con cache y verificación de raíces ======
def get_ancestors_p279_cached(qid: str, max_levels: int = 6) -> set:
    if qid in _ANCESTOR_CACHE:
        return _ANCESTOR_CACHE[qid]
    visited, frontier = set(), [qid]
    levels = 0
    while frontier and levels < max_levels:
        nxt = []
        for cur in frontier:
            ent = wbgetentities([cur]).get(cur, {})
            parents = _claim_ids(ent, P_SUBCLASS_OF)
            for p in parents:
                if p not in visited:
                    visited.add(p)
                    nxt.append(p)
        frontier = nxt
        levels += 1
    _ANCESTOR_CACHE[qid] = visited
    return visited

def reaches_any_root(qid: str, root_qids: set) -> bool:
    if not qid or not root_qids:
        return False
    ancestors = get_ancestors_p279_cached(qid, max_levels=6)
    return bool(ancestors & root_qids)

# ====== Bonus por dominio (P31 whitelist + P279→raíces) ======
def domain_bonus_for_candidate(cand_qid: str, cand_p31s: set, domain_cfg: Dict[str, set]) -> Tuple[int, List[str]]:
    bonus = 0
    hits = []
    p31_hit = cand_p31s & domain_cfg["p31_whitelist"]
    if p31_hit:
        bonus += 12
        hits.extend(list(p31_hit))
    try:
        if reaches_any_root(cand_qid, domain_cfg["p279_roots"]):
            bonus += 15
            hits.append("P279*→root")
    except Exception:
        pass
    return bonus, hits

# ====== Reglas P31 (block/bonus) ======
def type_bonus_or_block(p31s: set) -> Tuple[bool, float]:
    if p31s & DISALLOWED_P31:
        return True, 0.0
    bonus = 30.0 if (p31s & PREFERRED_P31) else 0.0
    return False, bonus

# ====== Expansión de jerarquías P279 (subclass of) ======
def expand_p279_paths(start_parents: List[str], max_levels: int, languages: List[str]) -> List[List[str]]:
    """
    Expande rutas P279 (subclass of) hasta una profundidad máxima.
    Retorna una lista de listas de QIDs, donde cada sublista es una ruta padre→ancestro.
    """
    if not start_parents:
        return []

    paths = []
    frontier = [[p] for p in start_parents]

    for _ in range(max_levels - 1):
        new_frontier = []
        for path in frontier:
            current = path[-1]
            ent = wbgetentities([current], languages).get(current, {})
            parents = _claim_ids(ent, P_SUBCLASS_OF)
            if not parents:
                # Si no tiene más padres, conserva la ruta actual
                paths.append(path)
                continue
            for par in parents:
                # Evita bucles o repeticiones dentro de la ruta
                if par not in path:
                    new_frontier.append(path + [par])
        frontier = new_frontier or frontier

    # Agrega todas las rutas finales si aún no están incluidas
    for p in frontier:
        if p not in paths:
            paths.append(p)

    return paths


# ====== Lógica de disambiguación y extracción ======
def is_disambiguation(qid: str, entity: Dict) -> bool:
    for cl in entity.get("claims", {}).get(P_INSTANCE_OF, []):
        v = cl.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        if v.get("id") == Q_DISAMBIGUATION:
            return True
    return False

def extract_bnf_id(entity: Dict) -> Optional[str]:
    for cl in entity.get("claims", {}).get(P_BNF_ID, []):
        dv = cl.get("mainsnak", {}).get("datavalue", {})
        if dv.get("value"):
            return str(dv.get("value"))
    return None

def extract_label(entity: Dict, languages: List[str] = LANGS) -> str:
    for lg in languages:
        if "labels" in entity and lg in entity["labels"]:
            return entity["labels"][lg]["value"]
    labs = entity.get("labels", {})
    if labs:
        return list(labs.values())[0]["value"]
    return ""

# ====== Búsqueda y ranking con dominio HAL ======
def pick_exact_label_only(keyword: str) -> Optional[Dict]:
    kw_norm = normalize_kw(keyword).lower()
    kw_sing = singularize_en(kw_norm).lower()
    targets = {kw_norm, kw_sing}
    for lg in LANGS:
        hits = wbsearch_label_only(kw_sing, language=lg, limit=5) or wbsearchentities(kw_sing, language=lg, limit=5)
        for h in hits:
            lbl = normalize_kw(h.get("label") or "").lower()
            if lbl in targets:
                qid = h.get("id")
                ent = wbgetentities([qid]).get(qid, {})
                p31s = get_p31_ids(ent)
                block, type_bonus = type_bonus_or_block(p31s)
                if block:
                    continue
                return {
                    "id": qid, "label": h.get("label"), "description": h.get("description"),
                    "aliases": h.get("aliases") or [], "language": lg, "label_similarity": 100.0,
                    "match_score": 50.0 + type_bonus, "__p31s": p31s, "__stage": "exact_label",
                    "__domain_bonus": 0, "__domain_hits": []
                }
    return None

def pick_with_context_then_exact(keyword: str, context: str, domain_cfg: Optional[Dict[str, set]] = None) -> Optional[Dict]:
    keyword = normalize_kw(keyword)
    context = normalize_kw(context)
    terms = [keyword]
    kw_sing = singularize_en(keyword)
    if kw_sing != keyword:
        terms.append(kw_sing)

    raw, seen = [], set()
    for term in terms:
        for lg in LANGS:
            for hit in wbsearchentities(term, language=lg, limit=SEARCH_LIMIT) or wbsearch_label_only(term, language=lg, limit=SEARCH_LIMIT):
                qid = hit.get("id")
                if not qid or qid in seen:
                    continue
                seen.add(qid)
                raw.append({
                    "id": qid, "label": hit.get("label"), "description": hit.get("description"),
                    "aliases": hit.get("aliases") or [], "language": lg
                })

    if raw:
        ents = wbgetentities([c["id"] for c in raw])
        candidates = []
        for c in raw:
            ent = ents.get(c["id"], {})
            p31s = get_p31_ids(ent)
            block, type_bonus = type_bonus_or_block(p31s)
            if block:
                continue
            sim = label_similarity(keyword, c)
            score = total_score(keyword, context, c, allow_exact_bonus=True) + type_bonus

            dom_bonus, dom_hits = (0, [])
            if domain_cfg:
                dom_bonus, dom_hits = domain_bonus_for_candidate(c["id"], p31s, domain_cfg)
                score += dom_bonus

            c["__p31s"] = p31s
            c["__domain_bonus"] = dom_bonus
            c["__domain_hits"] = dom_hits
            c["label_similarity"] = sim
            c["match_score"] = score
            candidates.append(c)

        if candidates:
            candidates.sort(
                key=lambda c: (c["match_score"], c["label_similarity"],
                               -LANGS.index(c.get("language", "en")) if c.get("language", "en") in LANGS else -99),
                reverse=True,
            )
            top = candidates[0]
            if top["label_similarity"] >= MIN_LABEL_SIM and top["match_score"] >= MIN_TOTAL_SCORE:
                top["__stage"] = "context"
                return top

    return pick_exact_label_only(keyword)


# =============== Pipeline con Neo4j =================
def map_keywords(records: List[Dict], neo4j_conn: Neo4jConnector) -> List[Dict]:
    rows = []
    seen_pairs = set()

    for rec in records:
        title = rec.get("title_s") or ""
        abstract = rec.get("abstract_s") or ""
        context = f"{title}. {abstract}"
        docid = rec.get("docid") or rec.get("halId_s") or ""

        # dominios HAL → buckets → cfg combinada
        hal_buckets = extract_hal_buckets(rec)
        domain_cfg = merge_domain_cfg_for_buckets(hal_buckets)

        keywords = rec.get("keyword_s") or []
        if not keywords and rec.get("keywords_joined"):
            raw = rec["keywords_joined"]
            keywords = [k.strip() for k in re.split(r"[;,]", raw) if k.strip()]

        print(f"\n--- Procesando Documento {docid} con {len(keywords)} keywords | HAL: {hal_buckets} ---")

        for kw in keywords:
            if (docid, kw) in seen_pairs:
                continue
            seen_pairs.add((docid, kw))

            qid = label = bnf = ""
            disambig = False
            match_stage = "none"
            best_sim = 0.0
            best_score = 0.0
            p31s_out = set()
            p31_labels_out = ""
            p279_paths_labels: List[str] = []
            domain_bonus_val = 0
            domain_hits = ""

            cand = pick_with_context_then_exact(kw, context, domain_cfg=domain_cfg)

            if cand:
                ent = wbgetentities([cand["id"]]).get(cand["id"], {})
                if ent:
                    disambig = is_disambiguation(cand["id"], ent)
                    if not disambig:
                        qid = cand["id"]
                        label = extract_label(ent)
                        bnf = extract_bnf_id(ent) or ""
                        match_stage = cand.get("__stage", "context_or_exact")
                        best_sim = cand.get("label_similarity", 0.0)
                        best_score = cand.get("match_score", 0.0)
                        domain_bonus_val = cand.get("__domain_bonus", 0)
                        domain_hits = ";".join(cand.get("__domain_hits", []))

                        # P31
                        p31s_out = get_p31_ids(ent)
                        p31_labels = get_labels_for(list(p31s_out)) if p31s_out else {}
                        p31_labels_out = ";".join(p31_labels.get(x, x) for x in p31s_out)

                        # Neo4j: P31
                        ingest_p31_types(neo4j_conn, qid, p31s_out, p31_labels)

                        # P279
                        direct_p279 = _claim_ids(ent, P_SUBCLASS_OF)
                        if direct_p279:
                            qid_paths = expand_p279_paths(direct_p279, MAX_LEVELS_LINEAGE, LANGS)

                            all_p279_qids = set()
                            for qpath in qid_paths:
                                all_p279_qids.update(qpath)
                            p279_labels_map = get_labels_for(list(all_p279_qids), LANGS)

                            # Neo4j: P279 (Jerarquía)
                            ingest_p279_hierarchy(neo4j_conn, qid, label, qid_paths, p279_labels_map)

                            # CSV: rutas legibles
                            for qpath in qid_paths:
                                p279_paths_labels.append(" > ".join(p279_labels_map.get(q, q) for q in qpath))

                        # Neo4j: mapeo documento-keyword-item
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
                    # auditoría por dominio HAL
                    "hal_domains": "|".join(hal_buckets),
                    "domain_bonus": domain_bonus_val,
                    "domain_hits": domain_hits,
                })

    return rows


# =============== Main =================
def main():
    print(f"🔗 Intentando conectar a Neo4j en {NEO4J_URI}...")
    try:
        uri_to_connect = NEO4J_URI.replace("localhost", "127.0.0.1")
        neo4j_conn = Neo4jConnector(uri_to_connect, NEO4J_USER, NEO4J_PASSWORD)
        neo4j_conn.driver.verify_connectivity()
        print("✅ Conexión con Neo4j exitosa.")
    except Exception as e:
        print(f"❌ Error al conectar a Neo4j. Verifica tus credenciales y si el servicio está corriendo. Detalle: {e}")
        return

    # 1) Resolver roots/whitelists de dominio a QIDs
    global DOMAIN_CFG_QIDS
    DOMAIN_CFG_QIDS = build_domain_cfg_qids()
    print("✅ Roots/whitelists de dominio resueltas a QIDs.")

    # 2) Construir sets P31 disallow/prefer a partir de labels
    global DISALLOWED_P31, PREFERRED_P31
    DISALLOWED_P31, PREFERRED_P31 = build_p31_type_sets()
    print(f"✅ DISALLOWED_P31: {len(DISALLOWED_P31)} tipos | PREFERRED_P31: {len(PREFERRED_P31)} tipos")

    print(f"📥 Leyendo JSON de: {INPUT_JSON}")
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        records = json.load(f)

    print(f"🔍 Procesando {len(records)} records e ingresando en Neo4j y CSV...")
    rows = map_keywords(records, neo4j_conn)

    fieldnames = [
        "docid", "title", "keyword", "wikidata_label", "wikidata_qid",
        "bnf_id", "p279_path", "retry_source", "match_stage", "is_disambiguation",
        "label_similarity", "match_score", "p31_types", "p31_label",
        "hal_domains", "domain_bonus", "domain_hits"
    ]
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    print(f"\n💾 Guardando resultados en CSV: {OUTPUT_CSV}")
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    neo4j_conn.close()
    print("✅ Proceso finalizado. Conexión a Neo4j cerrada.")


if __name__ == "__main__":
    main()
