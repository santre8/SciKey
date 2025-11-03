#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

# ==================== RUTAS Y CONFIG ====================
# Ajusta tus rutas aquí:
INPUT_JSON = Path(r"C:\Users\sanda\Documents\Langara_College\DANA-4850-001-Capstone_Project\hall-api-test-db-mysql\api\data\upec_chemical_20.json")
OUTPUT_CSV = Path(r"C:\Users\sanda\Documents\Langara_College\DANA-4850-001-Capstone_Project\hall-api-test-db-mysql\wikidata\hal_field_audit_out\Wikidata_upec_chemical_20.csv")

# Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "your_password")  # <-- ¡Actualiza!

# Wikidata
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
HEADERS = {"User-Agent": "Keyword2Wikidata/1.3 (contact: your-email@example.com)"}

# Propiedades y QIDs
P_INSTANCE_OF = "P31"
P_SUBCLASS_OF = "P279"
P_BNF_ID = "P268"
Q_DISAMBIGUATION = "Q4167410"

# Idiomas / límites / umbrales
LANGS = ["en", "fr"]
MIN_LABEL_SIM = 70
MIN_TOTAL_SCORE = 30
MAX_LEVELS_LINEAGE = 5
SEARCH_LIMIT = 50

# ====== P31 config (por LABEL) ======
DISALLOWED_P31_LABELS = [
    # Wikimedia / contenedores
    "Wikimedia disambiguation page", "Wikimedia category", "Wikimedia template", "Wikimedia list article",
    # Obras
    "scholarly article", "academic journal", "book", "thesis", "conference paper", "report", "magazine", "newspaper", "patent",
    # Entidades no temáticas
    "organization", "company", "university", "human", "person", "award", "software", "website",
    # Lugares/eventos (si no quieres mapear geográficos)
    "country", "city", "human settlement", "building", "event",
]

PREFERRED_P31_LABELS = [
    # Conocimiento/ciencia
    "scientific concept", "academic discipline", "theory", "model", "method", "technique", "process", "phenomenon",
    "property", "quantity",
    # Física
    "physical quantity", "physical law", "physical constant",
    # Química
    "chemical compound", "chemical substance", "chemical process",
    # Computación / matemáticas
    "algorithm", "data structure", "computing concept", "mathematical object",
    # Bio (si aplica en tu corpus)
    "biological process", "disease",
]




# ====== Caches/globals compartidos entre módulos ======
DISALLOWED_P31: Set[str] = set()
PREFERRED_P31: Set[str] = set()
DOMAIN_CFG_QIDS: Dict[str, Dict[str, Set[str]]] = {}  # {"Physics": {"p31_whitelist": set(...), "p279_roots": set(...)}}

def set_disallowed_preferred(disallowed: Set[str], preferred: Set[str]) -> None:
    global DISALLOWED_P31, PREFERRED_P31
    DISALLOWED_P31 = set(disallowed or set())
    PREFERRED_P31 = set(preferred or set())

def set_domain_cfg_qids(cfg: Dict[str, Dict[str, Set[str]]]) -> None:
    global DOMAIN_CFG_QIDS
    DOMAIN_CFG_QIDS = cfg or {}

# ==================== HELPERS TEXTO ====================
_ws_re = re.compile(r"\s+", re.UNICODE)
_token_re = re.compile(r"[^\w\-]+")

def normalize_kw(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\u00A0", " ").replace("\ufeff", "")
    s = _ws_re.sub(" ", s.strip()).strip(";, ")
    return s

def tokenize(text: str) -> List[str]:
    return [t for t in _token_re.split((text or "").lower()) if t]

def singularize_en(word: str) -> str:
    w = normalize_kw(word)
    wl = w.lower()
    if len(w) > 3 and wl.endswith("ies"): return w[:-3] + "y"
    if len(w) > 3 and wl.endswith("ses"): return w[:-2]
    if len(w) > 2 and wl.endswith("s") and not wl.endswith("ss"): return w[:-1]
    return w

# ==================== HAL DOMAINS ====================

# ==================== DOMINIOS (GENÉRICO) ====================
_DOM_LABEL_CLEAN_RE = re.compile(r"\[[^\]]*\]")  # quita corchetes tipo [physics]
_DOM_SPLIT_RE = re.compile(r"[\/>]+")

def _clean_domain_piece(seg: str) -> str:
    """Limpia un segmento de dominio (sin corchetes, sin basura, trim)."""
    s = seg or ""
    s = _DOM_LABEL_CLEAN_RE.sub("", s)   # remove [ ... ]
    s = _ws_re.sub(" ", s.strip(" >/|,"))  # normaliza espacios
    return s

def extract_domain_labels(rec: Dict) -> List[str]:
    """
    Extrae *labels de dominio* tal como vienen en el JSON (sin mapear a buckets).
    Lee el campo 'en_domainAllCodeLabel_fs' y devuelve una lista única (ordenada).
    """
    out = set()
    dom_list = rec.get("en_domainAllCodeLabel_fs") or []
    for raw in dom_list:
        part = raw.split("FacetSep_", 1)[1] if isinstance(raw, str) and "FacetSep_" in raw else raw
        if not part:
            continue
        # dividir por / o >
        for seg in _DOM_SPLIT_RE.split(part):
            seg_clean = _clean_domain_piece(seg)
            if seg_clean:
                out.add(seg_clean)
    return sorted(out)

