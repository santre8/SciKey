from typing import Dict, List, Optional
from . import config
from .utils import normalize_kw, singularize_en
from .scoring import label_similarity, total_score
from .wikidata_api import (
    wbsearchentities, wbsearch_label_only, wbgetentities,
    get_p31_ids, _claim_ids, get_p101_ids
)
from .utils import normalize_kw
import math

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
                if not _is_semantically_valid(ent):
                    continue
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
            if not _is_semantically_valid(ent):
                continue
            p31s = get_p31_ids(ent)
            p101s = get_p101_ids(ent)   # ← NUEVO

            c["__p31s"] = p31s
            c["__p101s"] = p101s   # ← NUEVO
            
            block, type_bonus = _type_bonus_or_block(p31s)
            if block:
                continue

            # 1) señales neutrales primero (para que las use el score)
            claims = ent.get("claims", {})
            c["__sitelinks"]    = len(ent.get("sitelinks", {}) or {})
            c["__alias_count"]  = sum(len(v) for v in (ent.get("aliases") or {}).values())
            c["__claims_count"] = sum(len(v) for v in (claims or {}).values())
            c["__has_p279"]     = bool(claims.get(config.P_SUBCLASS_OF))

            # 2) similitudes
            sim = label_similarity(keyword, c)

            # 2b) detect alias exact BEFORE scoring (needed for alias bonus)
            kw_norm = normalize_kw(keyword).lower()
            alias_list = [normalize_kw(a).lower() for a in (c.get("aliases") or [])]
            lbl_eq = normalize_kw(c.get("label") or "").lower() == kw_norm
            alias_eq = kw_norm in alias_list

            c["__lbl_exact"] = bool(lbl_eq)
            if alias_eq:
                c["__alias_exact"] = True
            elif lbl_eq:
                c["__alias_exact"] = False

            # 3) score (incluye canonicalidad) + bonus por tipo si aplica
            base_score = total_score(keyword, context, c, allow_exact_bonus=True)
            score = base_score + type_bonus

            c["label_similarity"] = sim
            c["match_score"] = score
            c["__base_score"] = base_score
            c["__type_bonus"] = type_bonus

            candidates.append(c)

        # #DEBUG-----------
        # if keyword.lower().strip() == "tem":
        #     print(f"[DBG] candidates built: {len(candidates)}")
        #     for cand in candidates:
        #         alias_list = [normalize_kw(a).lower() for a in (cand.get('aliases') or [])]
        #         print(f"    {cand['id']} | label='{cand.get('label')}' | alias_exact={'tem' in alias_list} | sitelinks={cand.get('__sitelinks',0)}")


        # ===== SAFETY-NET: priorizar coincidencia EXACTA (label o alias) si existe =====
        # ===== SAFETY-NET: priorizar coincidencia EXACTA (label o alias) si existe =====
        kw_norm = normalize_kw(keyword).lower()

        def _alias_list(ent_like: Dict) -> List[str]:
            return [normalize_kw(a).lower() for a in (ent_like.get("aliases") or [])]

        exact_pool = []
        for cand in candidates:
            lbl_eq  = bool(cand.get("__lbl_exact"))
            alias_eq = bool(cand.get("__alias_exact"))
            if lbl_eq or alias_eq:
                exact_pool.append(cand)

        if exact_pool:
            def _lang_rank(lg: str) -> int:
                return -config.LANGS.index(lg) if lg in config.LANGS else -99

            from .utils import tokenize
            # Tratar tokens cortos (2–5 letras) como acrónimos aunque vengan en minúsculas
            is_short_token = (2 <= len(kw_norm) <= 5) and kw_norm.isalpha()

            # --- Filtro de canonicidad mínima (genérico) para tokens cortos ---
            if is_short_token:
                filtered = [c for c in exact_pool if c.get("__sitelinks", 0) >= 5]
                if filtered:
                    exact_pool = filtered  # si nadie pasa el umbral, seguimos con todos

            if not is_short_token:
                # Si hay al menos un label exacto, ignora candidatos que solo sean alias exacto
                if any(c.get("__lbl_exact") for c in exact_pool):
                    exact_pool = [c for c in exact_pool if c.get("__lbl_exact")]
            # Tokens del contexto (title + abstract ya normalizado arriba)
            ctx_tokens = set(tokenize(context))

            def _context_support(cand: Dict) -> int:
                label = cand.get("label") or ""
                desc  = cand.get("description") or ""
                cand_text = normalize_kw(f"{label} {desc}").lower()
                cand_tokens = set(tokenize(cand_text))
                cand_tokens.discard(kw_norm)
                return len(ctx_tokens & cand_tokens)

            # Precálculo
            for cand in exact_pool:
                cand["__ctx_support"] = _context_support(cand)
                # canonicidad simple (no dependemos de scoring._canonicality_bonus)
                sl = float(cand.get("__sitelinks", 0) or 0)
                has_p279 = 1.0 if cand.get("__has_p279") else 0.0
                alias_cnt = float(cand.get("__alias_count", 0) or 0)
                cand["__canon_rank"] = (3.2 * math.log1p(sl)) + (2.0 * has_p279) + (0.01 * min(alias_cnt, 200))
            def _exact_rank(c):
                # Para NO cortos: label exact > alias exact
                if not is_short_token:
                    return 2 if c.get("__lbl_exact") else (1 if c.get("__alias_exact") else 0)
                # Para cortos: ambos valen igual
                return 1 if (c.get("__lbl_exact") or c.get("__alias_exact")) else 0

            # Peso de apoyo contextual: NORMAL vs ACRÓNIMO
            # Nota: antes se duplicaba para acrónimos; ahora lo reducimos para evitar sesgo a nicho.
            def _support_weight(cand: Dict) -> float:
                base = float(cand.get("__ctx_support", 0))
                return (0.5 * base) if is_short_token else base  # ↓ menos peso si es acrónimo

            # Orden:
            # 1) alias exacto
            # 2) si es acrónimo → canonicidad primero; si no → contexto primero
            # 3) match_score
            # 4) sitelinks / P279 / alias_count / idioma (por si acaso)
            if is_short_token:
                # Acrónimos: 1) solapamiento con LABEL 2) canonicidad 3) score base (sin type_bonus)
                sort_key = lambda x: (
                    _exact_rank(x),
                    x.get("__ctx_label_overlap", 0),            # ← fuerte: label en contexto
                    x.get("__base_score", x["match_score"]),    # ← desempate
                    x.get("__ctx_sim", 0.0),  
                    x.get("__canon_rank", 0.0),                 # ← TEM (microscopy) suele ganar aquí
                    
                    _support_weight(x),                         # (débil)
                    x.get("__type_bonus", 0.0),
                    x.get("__sitelinks", 0),
                    1 if x.get("__has_p279") else 0,
                    x.get("__alias_count", 0),
                    _lang_rank(x.get("language", "en")),
                )
            else:
                sort_key = lambda x: (
                    _exact_rank(x), 
                    _support_weight(x),
                    x["match_score"],               # aquí el score completo (incluye type_bonus)
                    x.get("__canon_rank", 0.0),
                    x.get("__sitelinks", 0),
                    1 if x.get("__has_p279") else 0,
                    x.get("__alias_count", 0),
                    _lang_rank(x.get("language", "en")),
                )

            
            # --- DEBUG opcional para inspeccionar ---
            if keyword.lower().strip() == "cvd":
                print("\n--- [DEBUG] SAFETY-NET SORTED CANDIDATES ---")
                for c in exact_pool[:10]:
                    print(
                        f"QID: {c['id']:<9} | Label: {c['label']:<35} | "
                        f"Alias_exact: {c.get('__alias_exact', False)} | "
                        f"Ctx_support: {c.get('__ctx_support', 0)} | "
                        f"Score: {c['match_score']:.1f} | "
                        f"Sitelinks: {c.get('__sitelinks',0)} | "
                        f"P279: {c.get('__has_p279')} | "
                        f"Aliases: {c.get('__alias_count',0)}"
                    )
                print("-------------------------------------------------\n")

            exact_pool.sort(key=sort_key, reverse=True)
            top = exact_pool[0]
            top["__stage"] = "exact_safety_net"
            return top
        # ===== FIN SAFETY-NET =====

        if candidates:
           
            def _lang_rank(lg: str) -> int:
                return -config.LANGS.index(lg) if lg in config.LANGS else -99

            candidates.sort(
                key=lambda x: (
                    x["label_similarity"],
                    x.get("__sitelinks", 0),
                    1 if x.get("__has_p279") else 0,
                    x["match_score"],
                    x.get("__alias_count", 0),
                    x.get("__claims_count", 0),
                    _lang_rank(x.get("language", "en")),
                ),
                reverse=True,
            )

            # --- DEBUG: visualizar top resultados para TEM ---
            if keyword.lower().strip() == "CVD":
                print("\n--- TOP after sort (score includes sitelinks) ---")
                for c in candidates[:5]:
                    print(
                        f"QID: {c['id']:<9} | Label: {c['label']:<35} | "
                        f"Score: {c['match_score']:.1f} | Sim(lbl): {c['label_similarity']:.1f} | "
                        f"Sitelinks: {c.get('__sitelinks',0)} | P279: {c.get('__has_p279')} | "
                        f"Aliases: {c.get('__alias_count',0)} | Claims: {c.get('__claims_count',0)}"
                    )
                print("-------------------------------------------------\n")
            # --- FIN DEBUG ---
            top = candidates[0]
            if top["label_similarity"] >= config.MIN_LABEL_SIM and top["match_score"] >= config.MIN_TOTAL_SCORE:
                top["__stage"] = "context"
                return top

    return pick_exact_label_only(keyword)

def _is_semantically_valid(entity: Dict) -> bool:
    """
    We consider an entity 'valid' if it:
    - has a P31 or P279 property (some type or superclass), and
    - includes either a description or aliases (indicating it’s not an empty stub),
    - and is not a disambiguation page (already covered by DISALLOWED_P31 if included).
    """
    if not entity:
        return False

    claims = entity.get("claims", {})
    has_p31 = bool(claims.get(config.P_INSTANCE_OF))
    has_p279 = bool(claims.get(config.P_SUBCLASS_OF))
    has_desc = bool(entity.get("descriptions"))
    has_alias = bool(entity.get("aliases"))
    return (has_p31 or has_p279) and (has_desc or has_alias)

