from typing import Dict, List
from rapidfuzz import fuzz
from .utils import normalize_kw, tokenize, singularize_en
import math
from . import config
from pathlib import Path
import os
import csv
from .utils import tokenize, normalize_kw

_DEBUG_HEADER_WRITTEN = False


def _debug_log_score(row: list):
    """Append one debug row if DEBUG_SCORES is enabled."""
    global _DEBUG_HEADER_WRITTEN
    if not getattr(config, "DEBUG_SCORES", False):
        return
    path = getattr(config, "DEBUG_SCORES_PATH", Path("debug_scores.csv"))

    # --- NUEVO: borrar archivo si existe en la primera llamada ---
    if not hasattr(_debug_log_score, "_cleared"):
        if path.exists():
            os.remove(path)
        _debug_log_score._cleared = True
    write_header = (not path.exists()) and (not _DEBUG_HEADER_WRITTEN)

    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow([
                "kw_norm","qid","label","ctx_sim","lbl_sim","canon",
                "alias_exact_flag","penalty","exact_bonus","alias_bonus","total",
                "p31_ids","p101_ids","p31_cnt", "p101_cnt"     # ← NUEVO
            ])
            _DEBUG_HEADER_WRITTEN = True
        w.writerow(row)


def label_similarity(keyword: str, ent_like: Dict) -> float:
    """Max de similitud entre la keyword y (label o cualquiera de los aliases)."""
    kw = normalize_kw(keyword).lower()
    label = normalize_kw(ent_like.get("label") or "").lower()
    aliases = [normalize_kw(a).lower() for a in (ent_like.get("aliases") or [])]

    # Usa una métrica estricta sobre cadenas (ratio), no token_sort de todo el set.
    sims = [fuzz.ratio(kw, label)] + [fuzz.ratio(kw, a) for a in aliases]
    return float(max(sims))


def context_overlap(keyword: str, context: str, ent_like: Dict) -> int:
    ctx_tokens = set(tokenize(normalize_kw(context)))
    label = (ent_like.get("label") or "")
    desc = (ent_like.get("description") or "")
    aliases = " ".join(ent_like.get("aliases") or [])
    cand_tokens = set(tokenize(" ".join([label, desc, aliases])))
    return len(ctx_tokens & cand_tokens)

def _context_similarity(context: str, ent_like: Dict) -> float:
    """0..100: robust similarity between (title+abstract) and (label+desc+aliases)."""
    ctx = normalize_kw(context).lower()
    label = (ent_like.get("label") or "")
    desc = (ent_like.get("description") or "")
    aliases = " ".join(ent_like.get("aliases") or [])
    cand_text = normalize_kw(" ".join([label, desc, aliases])).lower()
    if not ctx or not cand_text:
        return 0.0
    return float(fuzz.token_set_ratio(ctx, cand_text))


   
def _canonicality_bonus(ent_like: Dict) -> float:
    """
    Bonus general de canonicidad:
    - Sitelinks domina (más Wikipedias = más canónico).
    - has_p279 ayuda (clases suelen tener P279).
    - Aliases aporta muy poco.
    - Claims NO aporta (0) para no sesgar por cantidad de statements.
    """
    sl = float(ent_like.get("__sitelinks", 0) or 0)
    has_p279 = 1.0 if ent_like.get("__has_p279") else 0.0
    alias_count = float(ent_like.get("__alias_count", 0) or 0)

    # Dar MUCHO peso a sitelinks, un poco a P279, casi nada a aliases, 0 a claims.
    sitelinks_term = 3.2 * math.log1p(sl)     # sube el peso de sitelinks
    structure_term = 2.0 * has_p279           # mantiene un empujón a clases
    alias_term = 0.01 * min(alias_count, 200) # muy suave
    claims_term = 0.0                          # <- SIN efecto de claims

    return sitelinks_term + structure_term + alias_term + claims_term

def total_score(keyword: str, context: str, ent_like: Dict, allow_exact_bonus: bool = True) -> float:
    # Exact match (hint)
    lbl = normalize_kw(ent_like.get("label") or "").lower()
    kw_norm = normalize_kw(keyword).lower()
    kw_sing = singularize_en(kw_norm).lower()
    exact = (lbl == kw_norm) or (lbl == kw_sing)
    exact_bonus = 1.0 if (allow_exact_bonus and exact) else 0.0

    # Similitudes
    ctx_sim = _context_similarity(context, ent_like)   # 0..100
    lbl_sim = label_similarity(keyword, ent_like)      # 0..100

        # Penalización por tokens extra en label (suavizada y condicional)
    kw_tokens = set(tokenize(kw_norm))
    lbl_tokens = set(tokenize(lbl))

    alias_exact_flag = bool(ent_like.get("__alias_exact"))
    # Acrónimo “corto” si tiene 2–5 letras, y (todo mayúsculas o vino como alias exacto)
    is_short_acronym = (2 <= len(kw_norm) <= 5) and kw_norm.isalpha() and (kw_norm.isupper() or alias_exact_flag)

    if is_short_acronym or alias_exact_flag:
        # No castigues expansions del acrónimo (“TEM” → “transmission electron microscopy”)
        penalty = 0.0
    else:
        extra_tokens = len([t for t in lbl_tokens if t not in kw_tokens])
        # Penaliza suave y capado (evita que gane “Tem” solo por ser corto)
        penalty = 3.0 * min(extra_tokens, 2)

    # **Nuevo**: bonus de canonicidad basado en sitelinks/estructura
    canon = _canonicality_bonus(ent_like)

    # **Nuevo**: bonus pequeño si el match exacto fue por alias
    alias_bonus = 1.0 if alias_exact_flag else 0.0

    # Pesos base
    ctx_w = 2.0
    lbl_w = 0.4
    canon_w = 3.0
    alias_w = 1.0
    exact_w = 1.0

    # Si es ACRÓNIMO: confiar menos en contexto textual y más en canonicidad
    if is_short_acronym:
        ctx_w = 1.3       # ↓ 1.1
        canon_w = 0.72    # ↑5
        alias_w = 2.0     # ↑ refuerza alias exacto del acrónimo
        exact_w = 1.0     # igual

    # ... luego compón el total usando estos pesos
    total = ctx_w * ctx_sim + lbl_w * lbl_sim + exact_w * exact_bonus + alias_w * alias_bonus + canon_w * canon - penalty

    p31_ids  = sorted(list(ent_like.get("__p31s", [])))
    p101_ids = sorted(list(ent_like.get("__p101s", [])))
    p31_cnt = len(p31_ids)
    p101_cnt = len(p101_ids)

    qid = ent_like.get("id", "")  # suele venir en el cand
    _debug_log_score([
        kw_norm,
        qid,
        lbl,
        round(ctx_sim, 1),
        round(lbl_sim, 1),
        round(canon, 1),
        bool(alias_exact_flag),
        round(penalty, 1),
        round(exact_bonus, 1),
        round(alias_bonus, 1),
        round(total, 1),
        ";".join(p31_ids),
        ";".join(p101_ids),
        p31_cnt,
        p101_cnt,
    ])

    ent_like["__ctx_sim"] = ctx_sim
    ent_like["__lbl_sim"] = lbl_sim

    ctx_tokens = set(tokenize(normalize_kw(context)))
    label_tokens = set(tokenize((ent_like.get("label") or "")))
    ent_like["__ctx_label_overlap"] = len(ctx_tokens & label_tokens)
    return total
