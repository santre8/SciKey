from typing import Dict, List, Optional
import math

from . import config
from .utils import normalize_kw, singularize_en
from .scoring import label_similarity, total_score
from .wikidata_api import (
    wbsearchentities, wbsearch_label_only, wbgetentities,
    get_p31_ids, _claim_ids, get_p101_ids
)

# --- helpers -----------------------------------------------------------------

def _type_bonus_or_block(p31s: set) -> (bool, float):
    """
    Returns (block, bonus). If entity must be blocked due to P31, block=True.
    Otherwise, assign a preferred-type bonus if in PREFERRED_P31.
    """
    if p31s & config.DISALLOWED_P31:
        return True, 0.0
    bonus = 30.0 if (p31s & config.PREFERRED_P31) else 0.0
    return False, bonus


def _is_semantically_valid(entity: Dict) -> bool:
    """
    We consider an entity 'valid' if it:
    - has P31 or P279,
    - has descriptions or aliases (not an empty stub),
    - and is not a disambiguation page (covered by DISALLOWED_P31 if included).
    """
    if not entity:
        return False

    claims = entity.get("claims", {})
    has_p31 = bool(claims.get(config.P_INSTANCE_OF))
    has_p279 = bool(claims.get(config.P_SUBCLASS_OF))
    has_desc = bool(entity.get("descriptions"))
    has_alias = bool(entity.get("aliases"))
    return (has_p31 or has_p279) and (has_desc or has_alias)


# --- exact label-only shortcut -----------------------------------------------

def pick_exact_label_only(keyword: str) -> Optional[Dict]:
    """
    Fast-path: if any returned item has an exact label match for the keyword
    (including singularized), return it with a strong base score.
    """
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
                if not _is_semantically_valid(ent):
                    continue
                p31s = get_p31_ids(ent)
                block, type_bonus = _type_bonus_or_block(p31s)
                if block:
                    continue
                return {
                    "id": qid,
                    "label": h.get("label"),
                    "description": h.get("description"),
                    "aliases": h.get("aliases") or [],
                    "language": lg,
                    "label_similarity": 100.0,
                    "match_score": 50.0 + type_bonus,
                    "__p31s": p31s,
                    "__stage": "exact_label",
                }
    return None


# --- main matcher -------------------------------------------------------------

def pick_with_context_then_exact(keyword: str, context: str) -> Optional[Dict]:
    """
    Main strategy:
      1) Collect candidates from wbsearchentities/label_only for keyword and its singular.
      2) Fetch full entities in batch; compute neutral signals & similarities.
      3) Compute total_score() (which will also log debug if enabled).
      4) Safety-net: if we have exact label/alias matches, rank them with special rules:
         - non-short tokens: label-exact > alias-exact (+contextual/canonical tiebreakers)
         - short tokens (2–5 chars, acronyms): reduce context weight, demand minimal sitelinks,
           and use label-overlap + base_score before canonicality.
      5) If no safety-net match, fall back to best contextual candidate.
    """
    keyword = normalize_kw(keyword)
    context = normalize_kw(context)

    # collect search terms: original and singularized
    terms = [keyword]
    kw_sing = singularize_en(keyword)
    if kw_sing != keyword:
        terms.append(kw_sing)

    # 1) search
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
                    "id": qid,
                    "label": h.get("label"),
                    "description": h.get("description"),
                    "aliases": h.get("aliases") or [],
                    "language": lg
                })

    if not raw:
        return pick_exact_label_only(keyword)

    # 2) batch-fetch entities for candidates
    ents = wbgetentities([c["id"] for c in raw])

    # Build a batch of all P31 ids from candidates, to fetch once and reuse their text
    all_p31_ids = set()
    for c in raw:
        ent = ents.get(c["id"], {})
        for q in get_p31_ids(ent):
            all_p31_ids.add(q)

    p31_ents = wbgetentities(list(all_p31_ids)) if all_p31_ids else {}

    def _text_of_entity(e: Dict) -> str:
        # Concatenate label + descriptions + aliases across languages
        labs = " ".join([v["value"] for v in (e.get("labels") or {}).values()])
        desc = " ".join([v["value"] for v in (e.get("descriptions") or {}).values()])
        alias_lists = (e.get("aliases") or {}).values()
        aliases = " ".join([a["value"] for L in alias_lists for a in L])
        return " ".join([labs, desc, aliases]).strip()

    candidates: List[Dict] = []

    # 3) build enriched candidates and compute scores
    for c in raw:
        ent = ents.get(c["id"], {})
        if not _is_semantically_valid(ent):
            continue

        # P31 / P101 first, so scoring/debug can see them
        p31s = get_p31_ids(ent)
        p101s = get_p101_ids(ent)
        c["__p31s"] = p31s
        c["__p101s"] = p101s

        # Aggregate P31 text for fuzzy context scoring (done in scoring.py)
        p31_texts = []
        for pid in p31s:
            pe = p31_ents.get(pid, {})
            if pe:
                p31_texts.append(_text_of_entity(pe))
        c["__p31_text"] = " ".join(p31_texts)[:5000]

        # block/bonus by P31
        block, type_bonus = _type_bonus_or_block(p31s)
        if block:
            continue

        # neutral signals
        claims = ent.get("claims", {})
        c["__sitelinks"]    = len(ent.get("sitelinks", {}) or {})
        c["__alias_count"]  = sum(len(v) for v in (ent.get("aliases") or {}).values())
        c["__claims_count"] = sum(len(v) for v in (claims or {}).values())
        c["__has_p279"]     = bool(claims.get(config.P_SUBCLASS_OF))

        # similarities
        sim = label_similarity(keyword, c)

        # exactness flags (label vs alias)
        kw_norm = normalize_kw(keyword).lower()
        alias_list = [normalize_kw(a).lower() for a in (c.get("aliases") or [])]
        lbl_eq = normalize_kw(c.get("label") or "").lower() == kw_norm
        alias_eq = kw_norm in alias_list
        c["__lbl_exact"] = bool(lbl_eq)
        if alias_eq:
            c["__alias_exact"] = True
        elif lbl_eq:
            c["__alias_exact"] = False

        # score (base + type bonus)
        base_score = total_score(keyword, context, c, allow_exact_bonus=True)
        score = base_score + type_bonus

        c["label_similarity"] = sim
        c["match_score"] = score
        c["__base_score"] = base_score
        c["__type_bonus"] = type_bonus

        candidates.append(c)

    # 4) safety-net: prefer exact label/alias matches if any
    kw_norm = normalize_kw(keyword).lower()

    def _alias_list(ent_like: Dict) -> List[str]:
        return [normalize_kw(a).lower() for a in (ent_like.get("aliases") or [])]

    exact_pool: List[Dict] = []
    for cand in candidates:
        lbl_eq  = bool(cand.get("__lbl_exact"))
        alias_eq = bool(cand.get("__alias_exact"))
        if lbl_eq or alias_eq:
            exact_pool.append(cand)

    # if exact_pool:
    #     def _lang_rank(lg: str) -> int:
    #         return -config.LANGS.index(lg) if lg in config.LANGS else -99

    #     from .utils import tokenize
    #     # Treat 2–5 letters alphabetic tokens as acronyms even if lowercase
    #     is_short_token = (2 <= len(kw_norm) <= 5) and kw_norm.isalpha()

    #     # For short tokens, optionally demand minimal sitelinks to avoid niche items
    #     if is_short_token:
    #         min_sl = getattr(config, "MIN_SITELINKS_SHORT_TOKEN", 5)
    #         filtered = [c for c in exact_pool if c.get("__sitelinks", 0) >= min_sl]
    #         if filtered:
    #             exact_pool = filtered

    #     # For non-short tokens, if any label-exact exists, drop alias-only items
    #     # if not is_short_token:
    #     #     if any(c.get("__lbl_exact") for c in exact_pool):
    #     #         exact_pool = [c for c in exact_pool if c.get("__lbl_exact")]

    #     # context tokens
    #     ctx_tokens = set(tokenize(context))

    #     def _context_support(cand: Dict) -> int:
    #         label = cand.get("label") or ""
    #         desc  = cand.get("description") or ""
    #         cand_text = normalize_kw(f"{label} {desc}").lower()
    #         cand_tokens = set(tokenize(cand_text))
    #         cand_tokens.discard(kw_norm)
    #         return len(ctx_tokens & cand_tokens)

    #     # precompute tiebreakers
    #     for cand in exact_pool:
    #         cand["__ctx_support"] = _context_support(cand)
    #         sl = float(cand.get("__sitelinks", 0) or 0)
    #         has_p279 = 1.0 if cand.get("__has_p279") else 0.0
    #         alias_cnt = float(cand.get("__alias_count", 0) or 0)
    #         cand["__canon_rank"] = (3.2 * math.log1p(sl)) + (2.0 * has_p279) + (0.01 * min(alias_cnt, 200))

    #     def _exact_rank(c: Dict) -> int:
    #         # Non-short: label-exact > alias-exact
    #         if not is_short_token:
    #             return 2 if c.get("__lbl_exact") else (1 if c.get("__alias_exact") else 0)
    #         # Short: both count the same
    #         return 1 if (c.get("__lbl_exact") or c.get("__alias_exact")) else 0

    #     def _support_weight(cand: Dict) -> float:
    #         base = float(cand.get("__ctx_support", 0))
    #         return (0.5 * base) if is_short_token else base

    #     # Sorting priority
    #     if is_short_token:
    #         # Acronyms: 1) label-overlap (computed in scoring) 2) base score 3) ctx_sim 4) canonicality
    #         sort_key = lambda x: (
    #             _exact_rank(x),
    #             x.get("__ctx_label_overlap", 0.0),
    #             x.get("__base_score", x["match_score"]),
    #             x.get("__ctx_sim", 0.0),
    #             x.get("__canon_rank", 0.0),
    #             _support_weight(x),
    #             x.get("__type_bonus", 0.0),
    #             x.get("__sitelinks", 0),
    #             1 if x.get("__has_p279") else 0,
    #             x.get("__alias_count", 0),
    #             _lang_rank(x.get("language", "en")),
    #         )
    #     else:
    #         # Non-acronyms: label-exact first, then context, then full score, then canonical tiebreakers
    #         sort_key = lambda x: (
    #             _exact_rank(x),
    #             _support_weight(x),
    #             x["match_score"],
    #             x.get("__canon_rank", 0.0),
    #             x.get("__sitelinks", 0),
    #             1 if x.get("__has_p279") else 0,
    #             x.get("__alias_count", 0),
    #             _lang_rank(x.get("language", "en")),
    #         )

    #     exact_pool.sort(key=sort_key, reverse=True)
    #     top = exact_pool[0]

    #     # Optional "clear advantage" rule for acronyms: if #2 has much higher base_score, pick it
    #     if is_short_token and len(exact_pool) > 1:
    #         a, b = top, exact_pool[1]
    #         a_base = a.get("__base_score", a.get("match_score", 0.0))
    #         b_base = b.get("__base_score", b.get("match_score", 0.0))
    #         if b_base >= a_base + 0.5:
    #             top = b

    #     top["__stage"] = "exact_safety_net"
    #     return top

    # 5) fallback: pick best contextual candidate
    if candidates:
        def _lang_rank(lg: str) -> int:
            return -config.LANGS.index(lg) if lg in config.LANGS else -99

        candidates.sort(
            key=lambda x: (
                
                x["match_score"],
                x["label_similarity"],
                x.get("__sitelinks", 0),
                1 if x.get("__has_p279") else 0,
                
                x.get("__alias_count", 0),
                x.get("__claims_count", 0),
                _lang_rank(x.get("language", "en")),
            ),
            reverse=True,
        )

        top = candidates[0]
        if top["label_similarity"] >= config.MIN_LABEL_SIM and top["match_score"] >= config.MIN_TOTAL_SCORE:
            top["__stage"] = "context"
            return top

    # 6) last resort: exact label-only
    return pick_exact_label_only(keyword)
