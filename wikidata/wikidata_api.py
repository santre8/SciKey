#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import requests
from typing import Dict, List, Optional, Tuple, Set
from rapidfuzz import fuzz

import utils as U

# ====== CACHES ======
_QID_CACHE_BY_LABEL: Dict[Tuple[str, str], str] = {}   # (label_lower, lang)->qid
_LABELS_CACHE_BY_QID: Dict[str, str] = {}
_ANCESTOR_CACHE: Dict[str, Set[str]] = {}

# ====== HTTP base ======
def _get(params: Dict, sleep_sec: float = 0.1) -> Dict:
    params = {**params, "format": "json"}
    for attempt in range(5):
        try:
            r = requests.get(U.WIKIDATA_API, params=params, headers=U.HEADERS, timeout=20)
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

def wbsearchentities(search: str, language: str = "en", limit: int = U.SEARCH_LIMIT) -> List[Dict]:
    search = U.normalize_kw(search)
    return _get({
        "action": "wbsearchentities", "search": search, "language": language,
        "uselang": language, "type": "item", "limit": limit, "strictlanguage": 0
    }).get("search", [])

def wbsearch_label_only(search: str, language: str = "en", limit: int = U.SEARCH_LIMIT) -> List[Dict]:
    search = U.normalize_kw(search)
    return _get({
        "action": "wbsearchentities", "search": f"label:{search}", "language": language,
        "uselang": language, "type": "item", "limit": limit, "strictlanguage": 0
    }).get("search", [])

def chunked(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]

def wbgetentities(ids: List[str], languages: List[str] = U.LANGS) -> Dict:
    combined = {}
    ids = [x for x in ids if x]
    for batch in chunked(list(ids), 50):
        data = _get({
            "action": "wbgetentities", "ids": "|".join(batch),
            "props": "labels|descriptions|aliases|claims",
            "languages": "|".join(languages), "languagefallback": 1
        }, sleep_sec=0.05)
        combined.update(data.get("entities", {}))
    return combined

def get_labels_for(qids: List[str], languages: List[str] = U.LANGS) -> Dict[str, str]:
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

# ====== claims ======
def _claim_ids(entity: Dict, pid: str) -> List[str]:
    out = []
    for cl in entity.get("claims", {}).get(pid, []):
        dv = cl.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        if isinstance(dv, dict) and dv.get("id"):
            out.append(dv["id"])
    return out

def get_p31_ids(entity: Dict) -> Set[str]:
    return set(_claim_ids(entity, U.P_INSTANCE_OF))

def extract_bnf_id(entity: Dict) -> Optional[str]:
    for cl in entity.get("claims", {}).get(U.P_BNF_ID, []):
        dv = cl.get("mainsnak", {}).get("datavalue", {})
        if dv.get("value"):
            return str(dv.get("value"))
    return None

def extract_label(entity: Dict, languages: List[str] = U.LANGS) -> str:
    for lg in languages:
        if "labels" in entity and lg in entity["labels"]:
            return entity["labels"][lg]["value"]
    labs = entity.get("labels", {})
    if labs:
        return list(labs.values())[0]["value"]
    return ""

def is_disambiguation(qid: str, entity: Dict) -> bool:
    for cl in entity.get("claims", {}).get(U.P_INSTANCE_OF, []):
        v = cl.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        if v.get("id") == U.Q_DISAMBIGUATION:
            return True
    return False

# ====== label ↔ qid ======
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

def resolve_labels_to_qids(labels: List[str], language: str = "en") -> Set[str]:
    qids = set()
    for lab in labels:
        q = resolve_label_to_qid(lab, language=language)
        if q and q.startswith("Q"):
            qids.add(q)
    return qids

# ====== P31 sets y dominio ======
def build_p31_type_sets():
    dis_q = resolve_labels_to_qids(U.DISALLOWED_P31_LABELS, language="en")
    pref_q = resolve_labels_to_qids(U.PREFERRED_P31_LABELS, language="en")
    return dis_q, pref_q

def build_domain_cfg_qids() -> Dict[str, Dict[str, Set[str]]]:
    cfg_by_qid = {}
    for bucket, cfg in U.DOMAIN_CFG_LABELS.items():
        p31_whitelist_q = resolve_labels_to_qids(cfg["p31_whitelist_labels"], language="en")
        roots_q = resolve_labels_to_qids(cfg["p279_root_labels"], language="en")
        cfg_by_qid[bucket] = {"p31_whitelist": p31_whitelist_q, "p279_roots": roots_q}
    return cfg_by_qid

# ====== árboles P279* ======
def get_ancestors_p279_cached(qid: str, max_levels: int = 6) -> Set[str]:
    if qid in _ANCESTOR_CACHE:
        return _ANCESTOR_CACHE[qid]
    visited, frontier = set(), [qid]
    levels = 0
    while frontier and levels < max_levels:
        nxt = []
        for cur in frontier:
            ent = wbgetentities([cur]).get(cur, {})
            parents = _claim_ids(ent, U.P_SUBCLASS_OF)
            for p in parents:
                if p not in visited:
                    visited.add(p)
                    nxt.append(p)
        frontier = nxt
        levels += 1
    _ANCESTOR_CACHE[qid] = visited
    return visited

def reaches_any_root(qid: str, root_qids: Set[str]) -> bool:
    if not qid or not root_qids:
        return False
    ancestors = get_ancestors_p279_cached(qid, max_levels=6)
    return bool(ancestors & root_qids)

def expand_p279_paths(start_parents: List[str], max_levels: int, languages: List[str]) -> List[List[str]]:
    """Expande rutas P279 (subclass of) hasta una profundidad máxima."""
    if not start_parents:
        return []
    paths = []
    frontier = [[p] for p in start_parents]
    for _ in range(max_levels - 1):
        new_frontier = []
        for path in frontier:
            current = path[-1]
            ent = wbgetentities([current], languages).get(current, {})
            parents = _claim_ids(ent, U.P_SUBCLASS_OF)
            if not parents:
                paths.append(path)
                continue
            for par in parents:
                if par not in path:
                    new_frontier.append(path + [par])
        frontier = new_frontier or frontier
    for p in frontier:
        if p not in paths:
            paths.append(p)
    return paths

# ====== scoring ======
def best_label_and_aliases_str(ent_like: Dict) -> str:
    label = ent_like.get("label") or ""
    aliases = " ".join(ent_like.get("aliases") or [])
    return f"{label} {aliases}".strip()

def label_similarity(keyword: str, ent_like: Dict) -> float:
    target = best_label_and_aliases_str(ent_like)
    return float(fuzz.token_sort_ratio(U.normalize_kw(keyword), U.normalize_kw(target)))

def context_overlap(keyword: str, context: str, ent_like: Dict) -> int:
    ctx_tokens = set(U.tokenize(U.normalize_kw(context)))
    label = (ent_like.get("label") or "")
    desc = (ent_like.get("description") or "")
    raw_aliases = " ".join(ent_like.get("aliases") or [])
    candidate_context_str = " ".join([label, desc, raw_aliases])
    all_candidate_tokens = U.tokenize(candidate_context_str)
    keyword_tokens = set(U.tokenize(U.normalize_kw(keyword)))
    cand_tokens = set(token for token in all_candidate_tokens if token not in keyword_tokens)
    return len(ctx_tokens & cand_tokens)

def total_score(keyword: str, context: str, ent_like: Dict, allow_exact_bonus: bool = True) -> float:
    lbl = U.normalize_kw(ent_like.get("label") or "").lower()
    kw_norm = U.normalize_kw(keyword).lower()
    kw_sing = U.singularize_en(kw_norm).lower()
    exact = (lbl == kw_norm) or (lbl == kw_sing)
    exact_bonus = 50.0 if (allow_exact_bonus and exact) else 0.0
    return exact_bonus + context_overlap(keyword, context, ent_like) + 0.6 * label_similarity(keyword, ent_like)

# ====== bonus/bloqueos por tipos ======
def domain_bonus_for_candidate(cand_qid: str, cand_p31s: Set[str], domain_cfg: Dict[str, Set[str]]) -> Tuple[int, List[str]]:
    bonus = 0
    hits: List[str] = []
    p31_hit = cand_p31s & domain_cfg.get("p31_whitelist", set())
    if p31_hit:
        bonus += 12
        hits.extend(list(p31_hit))
    try:
        if reaches_any_root(cand_qid, domain_cfg.get("p279_roots", set())):
            bonus += 15
            hits.append("P279*→root")
    except Exception:
        pass
    return bonus, hits

def type_bonus_or_block(p31s: Set[str]) -> Tuple[bool, float]:
    if p31s & U.DISALLOWED_P31:
        return True, 0.0
    bonus = 30.0 if (p31s & U.PREFERRED_P31) else 0.0
    return False, bonus

# ====== selección de candidato ======
def pick_exact_label_only(keyword: str) -> Optional[Dict]:
    kw_norm = U.normalize_kw(keyword).lower()
    kw_sing = U.singularize_en(kw_norm).lower()
    targets = {kw_norm, kw_sing}
    for lg in U.LANGS:
        hits = wbsearch_label_only(kw_sing, language=lg, limit=5) or wbsearchentities(kw_sing, language=lg, limit=5)
        for h in hits:
            lbl = U.normalize_kw(h.get("label") or "").lower()
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

def pick_with_context_then_exact(keyword: str, context: str, domain_cfg: Optional[Dict[str, Set[str]]] = None) -> Optional[Dict]:
    keyword = U.normalize_kw(keyword)
    context = U.normalize_kw(context)

    terms = [keyword]
    kw_sing = U.singularize_en(keyword)
    if kw_sing != keyword:
        terms.append(kw_sing)

    raw, seen = [], set()
    for term in terms:
        for lg in U.LANGS:
            for hit in wbsearchentities(term, language=lg, limit=U.SEARCH_LIMIT) or wbsearch_label_only(term, language=lg, limit=U.SEARCH_LIMIT):
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
                               -U.LANGS.index(c.get("language", "en")) if c.get("language", "en") in U.LANGS else -99),
                reverse=True,
            )
            top = candidates[0]
            if top["label_similarity"] >= U.MIN_LABEL_SIM and top["match_score"] >= U.MIN_TOTAL_SCORE:
                top["__stage"] = "context"
                return top

    return pick_exact_label_only(keyword)
