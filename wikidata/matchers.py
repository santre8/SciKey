from typing import Dict, List, Optional

from . import config
from .utils import normalize_kw, singularize_en
from .scoring import mode_aware_total_score
from .wikidata_api import (
    wbsearchentities, wbsearch_label_only, wbgetentities,
    get_p31_ids, _claim_ids, get_p101_ids
)

# ----------------------------------------------------------------------------- #
# ----------------------------------------------------------------------------- #
def _is_semantically_valid(entity: Dict) -> bool:
    if not entity:
        return False
    #claims = entity.get("claims", {})
    #has_p31 = bool(claims.get(config.P_INSTANCE_OF))
    #has_p279 = bool(claims.get(config.P_SUBCLASS_OF))
    has_desc = bool(entity.get("descriptions"))
    #has_alias = bool(entity.get("aliases"))
    #return (has_p31 or has_p279) and (has_desc or has_alias)
    return has_desc


def pick_exact_label_only(keyword: str) -> Optional[Dict]:
    """Atajo legacy; el flujo principal ya no lo usa."""
    kw_norm = normalize_kw(keyword)
    kw_sing = singularize_en(kw_norm)
    targets = {kw_norm, kw_sing}

    for lg in config.LANGS:
        hits = wbsearch_label_only(kw_sing, language=lg, limit=5) or \
               wbsearchentities(kw_sing, language=lg, limit=5)
        for h in hits or []:
            lbl = normalize_kw(h.get("label") or "")
            if lbl in targets:
                qid = h.get("id")
                ent = wbgetentities([qid]).get(qid, {})
                if not ent:
                    continue
                return {
                    "id": qid,
                    "label": h.get("label"),
                    "description": h.get("description"),
                    "aliases": h.get("aliases") or [],
                    "language": lg,
                    "label_similarity": 100.0,
                    "match_score": 0.0,
                    "__stage": "exact_label_legacy",
                }
    return None


# ------------------------------- MATCHER PRINCIPAL --------------------------- #

def pick_with_context_then_exact(keyword: str, context: str) -> Optional[Dict]:

    raw_keyword = keyword
    keyword = normalize_kw(keyword)
    context = normalize_kw(context)
    DISABLE_SEM_FILTER = getattr(config, "PURE_SCORE_DISABLE_SEMANTIC_FILTER", True)

    
    terms = [keyword]
    kw_sing = singularize_en(keyword)
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
                    "id": qid,
                    "label": h.get("label"),
                    "description": h.get("description"),
                    "aliases": h.get("aliases") or [],
                    "language": lg,
                })

    if not raw:
        return None

   
    ents = wbgetentities([c["id"] for c in raw])

    
    all_p31_ids, all_p279_ids = set(), set()
    for c in raw:
        ent = ents.get(c["id"], {})
        # P31
        for q in get_p31_ids(ent):
            all_p31_ids.add(q)
        # P279 
        for q in _claim_ids(ent, config.P_SUBCLASS_OF):
            all_p279_ids.add(q)

    p31_ents  = wbgetentities(list(all_p31_ids))  if all_p31_ids else {}
    p279_ents = wbgetentities(list(all_p279_ids)) if all_p279_ids else {}

    def _expand_p279_text(start_qids: set, max_depth: int, max_nodes: int) -> (str, set):
        """
        Expande P279 hacia ancestros hasta 'max_depth' niveles.
        Devuelve (texto_concatenado, conjunto_de_qids_visitados).
        100% genérico: no hace supuestos de dominio y usa solo P279.
        """
        texts, visited = [], set()
        
        frontier = set(q for q in (start_qids or set()) if q)

        depth = 0
        while frontier and depth < max_depth and len(visited) < max_nodes:
            
            batch = [q for q in frontier if q not in visited]
            if not batch:
                break

            
            ents_level = wbgetentities(batch) or {}

            
            for qid, ent in ents_level.items():
                visited.add(qid)
                if ent:
                    labs = " ".join([v["value"] for v in (ent.get("labels") or {}).values()])
                    desc = " ".join([v["value"] for v in (ent.get("descriptions") or {}).values()])
                    alias_lists = (ent.get("aliases") or {}).values()
                    aliases = " ".join([a["value"] for L in alias_lists for a in L])
                    txt = " ".join([labs, desc, aliases]).strip()
                    if txt:
                        texts.append(txt)

            
            next_frontier = set()
            for ent in ents_level.values():
                if not ent:
                    continue
                for parent in _claim_ids(ent, config.P_SUBCLASS_OF) or []:
                    if parent not in visited:
                        next_frontier.add(parent)

            frontier = next_frontier
            depth += 1

        joined = " ".join(texts).strip()
        limit = int(getattr(config, "P279_TEXT_MAXCHARS", 12000))
        return joined[:limit], visited


    def _text_of_entity(e: Dict) -> str:
        labs = " ".join([v["value"] for v in (e.get("labels") or {}).values()])
        desc = " ".join([v["value"] for v in (e.get("descriptions") or {}).values()])
        alias_lists = (e.get("aliases") or {}).values()
        aliases = " ".join([a["value"] for L in alias_lists for a in L])
        return " ".join([labs, desc, aliases]).strip()

    candidates: List[Dict] = []

    
    for c in raw:
        ent = ents.get(c["id"], {})

        
        alias_dict = (ent.get("aliases") or {})
        c["aliases"] = [a["value"] for lst in alias_dict.values() for a in lst]

        
        if not c.get("description"):
            descs = ent.get("descriptions") or {}
            c["description"] = " ".join(v["value"] for v in descs.values())

        
        if not DISABLE_SEM_FILTER and not _is_semantically_valid(ent):
            continue

        claims = ent.get("claims", {}) if ent else {}
        c["__sitelinks"]    = len(ent.get("sitelinks", {}) or {}) if ent else 0
        c["__alias_count"]  = sum(len(v) for v in (ent.get("aliases") or {}).values()) if ent else 0
        c["__claims_count"] = sum(len(v) for v in (claims or {}).values())
        c["__has_p279"]     = bool(claims.get(config.P_SUBCLASS_OF))

        # sets P31 / P279
        p31s  = get_p31_ids(ent) if ent else set()
        p279s = set(_claim_ids(ent, config.P_SUBCLASS_OF)) if ent else set()
        c["__p31s"]  = p31s
        c["__p279s"] = p279s
        c["__p101s"] = get_p101_ids(ent) if ent else set()

        # --- 
        if getattr(config, "ENABLE_P31_BLOCK", True):
            if p31s & config.DISALLOWED_P31:
                
                continue

        # 
        p31_texts= []
        for pid in p31s:
            pe = p31_ents.get(pid, {})
            if pe:
                p31_texts.append(_text_of_entity(pe))

        c["__p31_text"]  = " ".join(p31_texts)[:5000]
        

        #
        if getattr(config, "ENABLE_P279_PATHS", False) and p279s:
            p279_text, p279_all = _expand_p279_text(
                start_qids=p279s,
                max_depth=int(getattr(config, "P279_DEPTH", 5)),
                max_nodes=int(getattr(config, "P279_MAX_NODES", 300)),
            )
            c["__p279_text"] = p279_text
            c["__p279s"]     = p279_all
        else:
            
            p279_texts = []
            for pid in p279s:
                pe = p279_ents.get(pid, {})
                if pe:
                    p279_texts.append(_text_of_entity(pe))
            c["__p279_text"] = " ".join(p279_texts)[:5000]
            c["__p279s"]     = p279s
        
        score = mode_aware_total_score(keyword, context, c, raw_keyword=raw_keyword)


        type_bonus = 0.0
        if getattr(config, "ENABLE_PREFERRED_P31_BONUS", True):
            if p31s & config.PREFERRED_P31:
                type_bonus = float(getattr(config, "TYPE_BONUS", 30.0))

        c["match_score"] = score + type_bonus
        c["__type_bonus"] = type_bonus
        c["__stage"] = "mode_score"

        candidates.append(c)

    if not candidates:
        return None



    candidates.sort(key=lambda x: x["match_score"], reverse=True)
    top = candidates[0]

    MIN_TOTAL_SCORE = getattr(config, "MIN_TOTAL_SCORE", 8.0)
    if top["match_score"] < MIN_TOTAL_SCORE:
        return None 
    return top
