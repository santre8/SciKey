from typing import Dict, List
from rapidfuzz import fuzz
from .utils import normalize_kw, tokenize, singularize_en

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

def total_score(keyword: str, context: str, ent_like: Dict, allow_exact_bonus: bool = True) -> float:
    # — Exact match used only as a “small hint”
    lbl = normalize_kw(ent_like.get("label") or "").lower()
    kw_norm = normalize_kw(keyword).lower()
    kw_sing = singularize_en(kw_norm).lower()
    exact = (lbl == kw_norm) or (lbl == kw_sing)
    exact_bonus = 8.0 if (allow_exact_bonus and exact) else 0.0  # ↓ reduced from 50 → 8

    # — Weighting: context > label
    ctx_sim = _context_similarity(context, ent_like)          # 0..100
    lbl_sim = label_similarity(keyword, ent_like)             # 0..100

    # — Final score (adjust if needed)
    return 1.6 * ctx_sim + 0.6 * lbl_sim + exact_bonus