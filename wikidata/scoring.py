from typing import Dict
from rapidfuzz import fuzz
from pathlib import Path
import math
import os
import csv

from . import config
from .utils import normalize_kw, tokenize, singularize_en

_DEBUG_HEADER_WRITTEN = False


# ----------------------------- Debug CSV logger ------------------------------

def _debug_log_score(row: list) -> None:
    """Append one debug row if DEBUG_SCORES is enabled."""
    global _DEBUG_HEADER_WRITTEN
    if not getattr(config, "DEBUG_SCORES", False):
        return

    path = getattr(config, "DEBUG_SCORES_PATH", Path("debug_scores.csv"))

    # Clear the file only on the first write of this run
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
                "p31_fuzzy_ctx"  # ← new fuzzy P31↔context subscore (0..100)
            ])
            _DEBUG_HEADER_WRITTEN = True
        w.writerow(row)


# ----------------------------- Similarities ----------------------------------

def label_similarity(keyword: str, ent_like: Dict) -> float:
    """Strict char-level similarity between keyword and (label or any alias)."""
    kw = normalize_kw(keyword).lower()
    label = normalize_kw(ent_like.get("label") or "").lower()
    aliases = [normalize_kw(a).lower() for a in (ent_like.get("aliases") or [])]
    sims = [fuzz.ratio(kw, label)] + [fuzz.ratio(kw, a) for a in aliases]
    return float(max(sims))


def _context_similarity(context: str, ent_like: Dict) -> float:
    """
    0..100: overlap direccional de tokens filtrados:
      score = 100 * |tokens_context ∩ tokens_candidato| / |tokens_context|
    Evita inflar coincidencias por palabras genéricas.
    """
    ctx = normalize_kw(context).lower()
    label = ent_like.get("label") or ""
    desc = ent_like.get("description") or ""
    aliases = " ".join(ent_like.get("aliases") or [])
    cand_text = normalize_kw(" ".join([label, desc, aliases])).lower()
    if not ctx or not cand_text:
        return 0.0

    sw = set(getattr(config, "STOPWORDS", set()))
    min_len = int(getattr(config, "MIN_TOKEN_LEN", 4))

    def _filtered_tokens(s: str) -> set:
        toks = tokenize(s)
        # conserva tokens técnicos en mayúsculas o alfabéticos cortos (TEM, DNA, CFD)
        out = {
            t for t in toks
            if (
                (len(t) >= min_len or t.isupper())
                and t not in sw
            )
        }
        # fallback: si quedó vacío, usa los tokens originales
        return out if out else set(toks)

    A = _filtered_tokens(ctx)
    B = _filtered_tokens(cand_text)
    if not A or not B:
        return 0.0

    overlap = len(A & B)
    return 100.0 * overlap / max(1, len(A))


def _p31_fuzzy_context(context: str, ent_like: Dict) -> float:
    """
    0..100: token_set similarity between (title+abstract) and the concatenated
    text of the entity's P31 types (labels + descriptions + aliases).
    Requires matchers.py to set ent_like["__p31_text"].
    """
    ctx = normalize_kw(context).lower()
    p31_text = normalize_kw(ent_like.get("__p31_text") or "").lower()
    if not ctx or not p31_text:
        return 0.0
    return float(fuzz.token_set_ratio(ctx, p31_text))


# ----------------------------- Canonicality ----------------------------------

def _canonicality_bonus(ent_like: Dict) -> float:
    """
    Canonicality bonus:
      - sitelinks: strong weight (more Wikipedias = more canonical)
      - P279 presence: medium bump (classes often have P279)
      - aliases: tiny bump
      - claims: 0 (avoid statement-count bias)
    """
    sl = float(ent_like.get("__sitelinks", 0) or 0)
    has_p279 = 1.0 if ent_like.get("__has_p279") else 0.0
    alias_count = float(ent_like.get("__alias_count", 0) or 0)

    sitelinks_term = 3.2 * math.log1p(sl)
    structure_term = 2.0 * has_p279
    alias_term = 0.01 * min(alias_count, 200)
    claims_term = 0.0

    return sitelinks_term + structure_term + alias_term + claims_term


# ----------------------------- Total score -----------------------------------

def total_score(keyword: str, context: str, ent_like: Dict, allow_exact_bonus: bool = True) -> float:
    # Normalize and exact-match hint (label-only, or its singular)
    lbl = normalize_kw(ent_like.get("label") or "").lower()
    kw_norm = normalize_kw(keyword).lower()
    kw_sing = singularize_en(kw_norm).lower()
    exact = (lbl == kw_norm) or (lbl == kw_sing)
    exact_bonus = 1.0 if (allow_exact_bonus and exact) else 0.0

    # Text similarities
    ctx_sim = _context_similarity(context, ent_like)   # 0..100
    lbl_sim = label_similarity(keyword, ent_like)      # 0..100

    # Token penalty (avoid short label bias), but not for acronyms/alias-exact
    kw_tokens = set(tokenize(kw_norm))
    lbl_tokens = set(tokenize(lbl))
    alias_exact_flag = bool(ent_like.get("__alias_exact"))
    is_short_acronym = (2 <= len(kw_norm) <= 5) and kw_norm.isalpha() and (kw_norm.isupper() or alias_exact_flag)

    if is_short_acronym or alias_exact_flag:
        penalty = 0.0
    else:
        extra_tokens = len([t for t in lbl_tokens if t not in kw_tokens])
        penalty = 0 * min(extra_tokens, 2)

    # Canonicality and alias bonus
    canon = _canonicality_bonus(ent_like)
    alias_bonus = 1.0 if alias_exact_flag else 0.0

    # Fuzzy P31↔context (0..100)
    p31_fuzzy_ctx = _p31_fuzzy_context(context, ent_like)

    # ---- Debug row ----
    p31_ids  = sorted(list(ent_like.get("__p31s", [])))
    p101_ids = sorted(list(ent_like.get("__p101s", [])))
    p31_cnt = len(p31_ids)
    p101_cnt = len(p101_ids)

    # Base weights
    ctx_w = 2.0
    lbl_w = 0.4
    canon_w = 3.0
    alias_w = 50.0
    exact_w = 1.0
    p31_fuzzy_w = 2.5  # gentle but meaningful
    p31_w = 1.0

    # Acronyms: rely a bit less on generic context, slightly more on canonicality/P31
    if is_short_acronym:
        ctx_w = 2.0
        canon_w = 2.0
        alias_w = 50.0
        p31_fuzzy_w = 4
        p31_w = 1.0

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
        round(p31_fuzzy_ctx, 1)
    ])

    # Expose signals for safety-net sorting in matchers.py
    ent_like["__ctx_sim"] = ctx_sim
    ent_like["__lbl_sim"] = lbl_sim
    ctx_tokens = set(tokenize(normalize_kw(context)))
    label_tokens = set(tokenize(ent_like.get("label") or ""))
    ent_like["__ctx_label_overlap"] = len(ctx_tokens & label_tokens)

    return total
