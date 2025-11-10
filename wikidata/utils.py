import re
import time
from typing import Dict, List, Iterable

_ws_re = re.compile(r"\s+", re.UNICODE)
_token_re = re.compile(r"[^\w\-]+")

# def normalize_kw(s: str) -> str:
#     if not s:
#         return ""
#     s = s.replace("\u00A0", " ").replace("\ufeff", "")
#     s = _ws_re.sub(" ", s.strip())
#     s = s.strip(";, ")
#     return s



def normalize_kw(s: str) -> str:
    """
    Normaliza texto para comparación semántica:
    - Convierte todo a minúsculas, EXCEPTO tokens que son
      acrónimos técnicos de 2–5 letras en mayúsculas (e.g., TEM, CVD, XRD, DNA).
    - Elimina signos de puntuación y separadores.
    """
    if not s:
        return ""
    
    tokens = re.findall(r"[A-Za-z0-9\-\+]+", s)
    normalized = []
    for t in tokens:
        # Si el token es todo mayúsculas, alfabético, y de 2–5 letras → conserva
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
    # intento 0..4 → 0.5, 1.0, 1.5, 2.0, 2.5
    time.sleep(0.5 * (attempt + 1))
