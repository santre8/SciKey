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

# ====== Dominio HAL (por LABEL; se resuelve a QIDs en wikidata_api) ======
DOMAIN_CFG_LABELS = {
    "Physics": {
        "p31_whitelist_labels": ["scientific concept", "physical quantity", "physical law", "phenomenon", "academic discipline"],
        "p279_root_labels": ["physics", "mechanics", "fluid mechanics"]
    },
    "Engineering Sciences": {
        "p31_whitelist_labels": ["engineering concept", "technology", "method", "process", "academic discipline"],
        "p279_root_labels": ["engineering", "civil engineering", "mechanical engineering", "chemical engineering"]
    },
    "Mechanics": {
        "p31_whitelist_labels": ["scientific concept", "physical quantity", "phenomenon", "method", "model"],
        "p279_root_labels": ["mechanics"]
    },
    "Fluid mechanics": {
        "p31_whitelist_labels": ["scientific concept", "physical quantity", "phenomenon", "method", "model"],
        "p279_root_labels": ["fluid mechanics", "fluid dynamics"]
    },
}

# Mapeo de cadenas → buckets HAL
_HAL_DOMAIN_BUCKETS_MAP = {
    "physics": "Physics",
    "engineering sciences": "Engineering Sciences",
    "mechanics": "Mechanics",
    "fluid mechanics": "Fluid mechanics",
    "fluids mechanics": "Fluid mechanics",
}

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
def extract_hal_buckets(rec: Dict) -> List[str]:
    """Extrae buckets de dominio desde el campo 'en_domainAllCodeLabel_fs' del JSON HAL."""
    out = set()
    for raw in rec.get("en_domainAllCodeLabel_fs", []) or []:
        part = raw
        if "FacetSep_" in raw:
            part = raw.split("FacetSep_", 1)[1]
        for seg in re.split(r"[\/>]", part):
            seg_clean = re.sub(r"\[[^\]]*\]", "", seg).strip().lower()
            if not seg_clean:
                continue
            for key, bucket in _HAL_DOMAIN_BUCKETS_MAP.items():
                if key in seg_clean:
                    out.add(bucket)
    return sorted(out)

def merge_domain_cfg_for_buckets(buckets: List[str]) -> Dict[str, Set[str]]:
    """Une whitelists P31 y raíces P279 de los buckets HAL presentes en el record."""
    if not buckets or not DOMAIN_CFG_QIDS:
        return {"p31_whitelist": set(), "p279_roots": set()}
    wl, roots = set(), set()
    for b in buckets:
        c = DOMAIN_CFG_QIDS.get(b)
        if not c:
            continue
        wl |= c["p31_whitelist"]
        roots |= c["p279_roots"]
    return {"p31_whitelist": wl, "p279_roots": roots}
