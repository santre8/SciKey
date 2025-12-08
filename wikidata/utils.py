import re
import time
from typing import Dict, List, Iterable

_ws_re = re.compile(r"\s+", re.UNICODE)
_token_re = re.compile(r"[^\w\-]+")




def normalize_kw(s: str) -> str:

    if not s:
        return ""
    
    tokens = re.findall(r"[A-Za-z0-9\-\+]+", s)
    normalized = []
    for t in tokens:
        
        if t.isalpha() and t.isupper() and 2 <= len(t) <= 5:
            normalized.append(t)
        else:
            normalized.append(t.lower())
    return " ".join(normalized)


def tokenize(text: str) -> List[str]:
    return [t for t in _token_re.split((text or "")) if t]

def singularize_en(word: str) -> str:
    w = normalize_kw(word)
    wl = w.lower()
    if len(w) > 3 and wl.endswith("ies"): return w[:-3] + "y"
    if len(w) > 3 and wl.endswith("ses"): return w[:-2]
    if len(w) > 2 and wl.endswith("s") and not wl.endswith("ss"): return w[:-1]
    return w

def chunked(seq: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(seq), size):
        yield seq[i:i + size]

def backoff_sleep(attempt: int):
    
    time.sleep(0.5 * (attempt + 1))
