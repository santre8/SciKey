from typing import Dict, List, Optional
from . import config
from .utils import normalize_kw, singularize_en
from .scoring import label_similarity, total_score
from .wikidata_api import (
    wbsearchentities, wbsearch_label_only, wbgetentities,
    get_p31_ids
)

def _type_bonus_or_block(p31s: set) -> (bool, float):
    if p31s & config.DISALLOWED_P31:
        return True, 0.0
    bonus = 30.0 if (p31s & config.PREFERRED_P31) else 0.0
    return False, bonus

def pick_exact_label_only(keyword: str) -> Optional[Dict]:
    kw_norm = normalize_kw(keyword).lower()
    kw_sing = singularize_en(kw_norm).lower()
    targets = {kw_norm, kw_sing}
    for lg in config.LANGS:
        hits = wbsearch_label_only(kw_sing, language=lg, limit=5) or \
               wbsearchentities(kw_sing, language=lg, limit=5)
        for h in hits:
            lbl = normalize_kw(h.get("label") or "").lower()
            if lbl in targets:
                qid = h.get("id")
                ent = wbgetentities([qid]).get(qid, {})
                p31s = get_p31_ids(ent)
                block, type_bonus = _type_bonus_or_block(p31s)
                if block:
                    continue
                return {
                    "id": qid, "label": h.get("label"),
                    "description": h.get("description"),
                    "aliases": h.get("aliases") or [],
                    "language": lg,
                    "label_similarity": 100.0,
                    "match_score": 50.0 + type_bonus,
                    "__p31s": p31s, "__stage": "exact_label",
                }
    return None

def pick_with_context_then_exact(keyword: str, context: str) -> Optional[Dict]:
    keyword = normalize_kw(keyword); context = normalize_kw(context)
    terms = [keyword]; kw_sing = singularize_en(keyword)
    if kw_sing != keyword:
        terms.append(kw_sing)

    raw, seen = [], set()
    for term in terms:
        for lg in config.LANGS:
            hits = wbsearchentities(term, language=lg, limit=config.SEARCH_LIMIT) or \
                   wbsearch_label_only(term, language=lg, limit=config.SEARCH_LIMIT)
            for h in hits or []:
                qid = h.get("id")
                if not qid or qid in seen:
                    continue
                seen.add(qid)
                raw.append({
                    "id": qid, "label": h.get("label"),
                    "description": h.get("description"),
                    "aliases": h.get("aliases") or [],
                    "language": lg
                })

    if raw:
        ents = wbgetentities([c["id"] for c in raw])
        candidates = []
        for c in raw:
            ent = ents.get(c["id"], {})
            p31s = get_p31_ids(ent)
            block, type_bonus = _type_bonus_or_block(p31s)
            if block:
                continue
            sim = label_similarity(keyword, c)
            score = total_score(keyword, context, c, allow_exact_bonus=True) + type_bonus
            c["label_similarity"] = sim
            c["match_score"] = score
            c["__p31s"] = p31s
            candidates.append(c)

        if candidates:
            # order: score, similarity, preference of defined languages
            candidates.sort(
                key=lambda c: (
                    c["match_score"],
                    c["label_similarity"],
                    -config.LANGS.index(c.get("language", "en")) if c.get("language", "en") in config.LANGS else -99
                ),
                reverse=True,
            )
            top = candidates[0]
            if top["label_similarity"] >= config.MIN_LABEL_SIM and top["match_score"] >= config.MIN_TOTAL_SCORE:
                top["__stage"] = "context"
                return top

    return pick_exact_label_only(keyword)
