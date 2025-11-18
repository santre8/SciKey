from typing import Dict
from rapidfuzz import fuzz
from pathlib import Path
import math
import os
import csv

from . import config
from .utils import normalize_kw, tokenize, singularize_en

_DEBUG_HEADER_WRITTEN = False

# ----------------------------- Debug CSV (clásico) ----------------------------

def _debug_log_score(row: list) -> None:
    """Append one debug row if DEBUG_SCORES is enabled."""
    global _DEBUG_HEADER_WRITTEN
    if not getattr(config, "DEBUG_SCORES", False):
        return

    path = getattr(config, "DEBUG_SCORES_PATH", Path("debug_scores.csv"))

    if not hasattr(_debug_log_score, "_cleared"):
        if path.exists():
            os.remove(path)
        _debug_log_score._cleared = True

    write_header = (not path.exists()) and (not _DEBUG_HEADER_WRITTEN)

    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow([
                "kw_norm", "qid", "label",
                "ctx_sim", "lbl_sim", "canon",
                "alias_exact_flag", "penalty", "exact_bonus", "alias_bonus",
                "total",
                "p31_ids", "p101_ids", "p31_cnt", "p101_cnt",
                "p31_fuzzy_ctx"
            ])
            _DEBUG_HEADER_WRITTEN = True
        w.writerow(row)

# ======================= DEBUG: mode-aware total score ========================

def _debug_log_mode_score(row: list) -> None:
    if not getattr(config, "DEBUG_SCORES", False):
        return
    path = getattr(config, "DEBUG_SCORES_MODE_PATH", Path("debug_scores_mode.csv"))
    if not hasattr(_debug_log_mode_score, "_cleared"):
        if path.exists():
            os.remove(path)
        _debug_log_mode_score._cleared = True
    write_header = not path.exists()
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow([
                "kw","qid","label","mode",
                # señales crudas
                "exact_label","exact_alias",
                "ctx","sl_log1p","p31_cnt","p279_cnt","ctx_p31","ctx_p279","alias_inv",
                # pesos aplicados
                "w_ctx","w_sl","w_p31","w_p279","w_ctx_p31","w_ctx_p279","w_alias_inv",
                # bonus exactitud
                "bonus_label","bonus_alias",
                # total final
                "total"
            ])
        w.writerow(row)

# ----------------------------- Similarities ----------------------------------

def label_similarity(keyword: str, ent_like: Dict) -> float:
    """Strict char-level similarity between keyword and (label or any alias)."""
    kw = normalize_kw(keyword)
    label = normalize_kw(ent_like.get("label") or "")
    aliases = [normalize_kw(a) for a in (ent_like.get("aliases") or [])]
    sims = [fuzz.ratio(kw, label)] + [fuzz.ratio(kw, a) for a in aliases]
    return float(max(sims))

def _context_similarity(context: str, ent_like: Dict) -> float:
    """
    0..100: overlap direccional de tokens filtrados:
      100 * |tokens_context ∩ tokens_candidato| / |tokens_context|
    """
    ctx = normalize_kw(context)
    label = ent_like.get("label") or ""
    desc = ent_like.get("description") or ""
    aliases = " ".join(ent_like.get("aliases") or [])
    cand_text = normalize_kw(" ".join([label, desc, aliases]))
    if not ctx or not cand_text:
        return 0.0

    sw = set(getattr(config, "STOPWORDS", set()))
    min_len = int(getattr(config, "MIN_TOKEN_LEN", 4))

    def _filtered_tokens(s: str) -> set:
        toks = tokenize(s)
        out = {t for t in toks if ((len(t) >= min_len or t.isupper()) and t not in sw)}
        return out if out else set(toks)

    A = _filtered_tokens(ctx)
    B = _filtered_tokens(cand_text)
    if not A or not B:
        return 0.0

    overlap = len(A & B)
    return 100.0 * overlap / max(1, len(A))

def _context_similarity_full(context: str, ent_like: Dict) -> float:
    """0..100: overlap usando label+desc+aliases (sin filtros especiales)."""
    from .utils import tokenize
    A = set(tokenize(normalize_kw(context)))
    label = ent_like.get("label") or ""
    desc  = ent_like.get("description") or ""
    aliases = " ".join(ent_like.get("aliases") or [])
    B = set(tokenize(normalize_kw(f"{label} {desc} {aliases}")))
    if not A or not B:
        return 0.0
    return 100.0 * len(A & B) / max(1, len(A))

def _fuzzy_ctx(textA: str, textB: str) -> float:
    """0..100: token_set_ratio con manejo de vacíos."""
    a = normalize_kw(textA or "")
    b = normalize_kw(textB or "")
    if not a or not b:
        return 0.0
    return float(fuzz.token_set_ratio(a, b))

def _p31_fuzzy_context(context: str, ent_like: Dict) -> float:
    ctx = normalize_kw(context)
    p31_text = normalize_kw(ent_like.get("__p31_text") or "")
    if not ctx or not p31_text:
        return 0.0
    return float(fuzz.token_set_ratio(ctx, p31_text))

# ----------------------------- Canonicality ----------------------------------

def _canonicality_bonus(ent_like: Dict) -> float:
    sl = float(ent_like.get("__sitelinks", 0) or 0)
    has_p279 = 1.0 if ent_like.get("__has_p279") else 0.0
    alias_count = float(ent_like.get("__alias_count", 0) or 0)
    sitelinks_term = 3.2 * math.log1p(sl)
    structure_term = 2.0 * has_p279
    alias_term = 0.01 * min(alias_count, 200)
    return sitelinks_term + structure_term + alias_term

# ----------------------------- Total score (histórico) -----------------------

def total_score(keyword: str, context: str, ent_like: Dict, allow_exact_bonus: bool = True) -> float:
    lbl = normalize_kw(ent_like.get("label") or "")
    kw_norm = normalize_kw(keyword)
    kw_sing = singularize_en(kw_norm)
    exact = (lbl == kw_norm) or (lbl == kw_sing)
    exact_bonus = 1.0 if (allow_exact_bonus and exact) else 0.0

    ctx_sim = _context_similarity(context, ent_like)   # 0..100
    lbl_sim = label_similarity(keyword, ent_like)      # 0..100

    kw_tokens = set(tokenize(kw_norm))
    lbl_tokens = set(tokenize(lbl))
    alias_exact_flag = bool(ent_like.get("__alias_exact"))
    is_short_acronym = (2 <= len(kw_norm) <= 5) and kw_norm.isalpha() and (kw_norm.isupper() or alias_exact_flag)

    if is_short_acronym or alias_exact_flag:
        penalty = 0.0
    else:
        extra_tokens = len([t for t in lbl_tokens if t not in kw_tokens])
        penalty = 0 * min(extra_tokens, 2)  # desactivado

    canon = _canonicality_bonus(ent_like)
    alias_bonus = 1.0 if alias_exact_flag else 0.0
    p31_fuzzy_ctx = _p31_fuzzy_context(context, ent_like)

    p31_ids  = sorted(list(ent_like.get("__p31s", [])))
    p101_ids = sorted(list(ent_like.get("__p101s", [])))
    p31_cnt = len(p31_ids)
    p101_cnt = len(p101_ids)

    ctx_w = 2.0
    lbl_w = 0.4
    canon_w = 3.0
    alias_w = 50.0
    exact_w = 1.0
    p31_fuzzy_w = 2.5
    p31_w = 1.0

    if is_short_acronym:
        ctx_w = 2.0; canon_w = 2.0; alias_w = 50.0; p31_fuzzy_w = 4; p31_w = 1.0

    total = (
        ctx_w * ctx_sim +
        lbl_w * lbl_sim +
        exact_w * exact_bonus +
        alias_w * alias_bonus +
        canon_w * canon +
        p31_fuzzy_w * (p31_fuzzy_ctx / 100.0) +
        p31_w * p31_cnt -
        penalty
    )

    qid = ent_like.get("id", "")
    _debug_log_score([
        kw_norm, qid, lbl,
        round(ctx_sim, 1), round(lbl_sim, 1), round(canon, 1),
        bool(alias_exact_flag), round(penalty, 1), round(exact_bonus, 1), round(alias_bonus, 1),
        round(total, 1),
        ";".join(p31_ids), ";".join(p101_ids), p31_cnt, p101_cnt,
        round(p31_fuzzy_ctx, 1)
    ])

    ent_like["__ctx_sim"] = ctx_sim
    ent_like["__lbl_sim"] = lbl_sim
    ctx_tokens = set(tokenize(normalize_kw(context)))
    label_tokens = set(tokenize(ent_like.get("label") or ""))
    ent_like["__ctx_label_overlap"] = len(ctx_tokens & label_tokens)

    return total

# ------------------------- Mode-aware total score (nuevo) --------------------

def mode_aware_total_score(keyword: str, context: str, ent_like: Dict) -> float:
    """
    total = bonus(label_exact) + bonus(alias_exact)
          + w_ctx(mode)      * ctx_sim
          + w_sl(mode)       * log1p(sitelinks)
          + w_p31(mode)      * (#P31)
          + w_p279(mode)     * (#P279)
          + w_ctx_p31(mode)  * (ctx vs P31_text)/100
          + w_ctx_p279(mode) * (ctx vs P279_text)/100
    """
    kw = normalize_kw(keyword)
    lbl = normalize_kw(ent_like.get("label") or "")
    aliases_norm = [normalize_kw(a) for a in (ent_like.get("aliases") or [])]

    exact_label = 1.0 if (lbl == kw or lbl == singularize_en(kw)) else 0.0
    exact_alias = 1.0 if (kw in aliases_norm) else 0.0

    # modo
    if exact_label:
        mode = "label"
    elif exact_alias:
        mode = "alias"
    else:
        mode = "none"

    W = config.WEIGHTS_MODE.get(mode, config.WEIGHTS_MODE["none"])

    # señales
    ctx_sim  = _context_similarity_full(context, ent_like)               # 0..100
    sl_log1p = math.log1p(float(ent_like.get("__sitelinks", 0) or 0))
    p31_cnt  = float(len(ent_like.get("__p31s", set()) or set()))
    p279_cnt = float(len(ent_like.get("__p279s", set()) or set()))
    ctx_p31  = _fuzzy_ctx(context, ent_like.get("__p31_text") or "")     # 0..100
    ctx_p279 = _fuzzy_ctx(context, ent_like.get("__p279_text") or "")    # 0..100

    
    # ---- NUEVO: alias-count inverso (más alto cuando hay pocos aliases) ----
    alias_cnt = float(ent_like.get("__alias_count", 0) or 0)

    # Score inverso: 1 alias => 1.0 ; 3 aliases => 0.5 ; 10 aliases => 0.25 ; etc.
    alias_inverse = 1.0 / (1.0 + alias_cnt / 2.0)

    # Opcional: redondea para debug
    alias_inverse = round(alias_inverse, 3)

    # bonus
    bonus_label = getattr(config, "EXACT_BONUS_LABEL", 20.0) * exact_label
    bonus_alias = getattr(config, "EXACT_BONUS_ALIAS", 15.0) * exact_alias

    total = (
        bonus_label + bonus_alias
        + W["ctx"]      * ctx_sim
        + W["sl"]       * sl_log1p
        + W["p31"]      * p31_cnt
        + W["p279"]     * p279_cnt
        + W["ctx_p31"]  * (ctx_p31 / 100.0)
        + W["ctx_p279"] * (ctx_p279 / 100.0)
        + W.get("alias_inv", 0.0) * alias_inverse     # ← NUEVO
    )

    _debug_log_mode_score([
        keyword, ent_like.get("id",""), ent_like.get("label") or "", mode,
        int(exact_label), int(exact_alias),
        round(ctx_sim,1), round(sl_log1p,2), round(p31_cnt,1), round(p279_cnt,1), round(ctx_p31,1), round(ctx_p279,1),round(alias_inverse, 3),
        W["ctx"], W["sl"], W["p31"], W["p279"], W["ctx_p31"], W["ctx_p279"], W.get("alias_inv", 0.0),
        round(bonus_label,2), round(bonus_alias,2),
        round(total,2)
    ])

    ent_like["__mode_score"] = total
    return total
