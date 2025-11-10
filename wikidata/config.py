from pathlib import Path

# =============== INPUT / OUTPUT PATHS =================
INPUT_JSON = Path(r"C:\Users\sanda\Documents\Langara_College\DANA-4850-001-Capstone_Project\hall-api-test-db-mysql\api\data\upec_political_20.json")
OUTPUT_CSV = Path(r"C:\Users\sanda\Documents\Langara_College\DANA-4850-001-Capstone_Project\hall-api-test-db-mysql\wikidata\hal_field_audit_out\Wikidata_upec_political_20.csv")

# =============== NEO4J CONFIGURATION =================
NEO4J_URI = "bolt://127.0.0.1:7687"
NEO4J_USER = "neo4j"          # CHANGE THIS
NEO4J_PASSWORD = "test"       # CHANGE THIS

# =============== WIKIDATA / HTTP =================
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
HEADERS = {"User-Agent": "Keyword2Wikidata/1.2 (contact: your-email@example.com)"}

# =============== LOGIC CONSTANTS =================
LANGS = ["en", "fr"]
MIN_LABEL_SIM = 70
MIN_TOTAL_SCORE = 30
MAX_LEVELS_LINEAGE = 5
SEARCH_LIMIT = 50

#==================== Neo4j =======================
ENABLE_NEO4J_INGEST = False  # Ponlo True solo cuando quieras cargar a Neo4j

# =============== PERFORMANCE OPTIONS =================
ENABLE_P279_PATHS = False  # True si quieres expandir jerarquías P279 (más lento)

# ================== Properties y QIDs =================
P_INSTANCE_OF = "P31"
P_SUBCLASS_OF = "P279"
P_BNF_ID = "P268"
Q_DISAMBIGUATION = "Q4167410"
P_FIELD_OF_WORK = "P101"

# =============== P31 filters (solo para otros flujos) ===============
DISALLOWED_P31 = {
    "Q13442814","Q571","Q1002697","Q737498","Q47461344","Q732577",
    # "Q5",
    "Q215627","Q43229","Q1656682","Q4830453","Q167037","Q17334923",
    "Q1371598","Q35127",
    # "Q101352","Q3918",
    "Q95074","Q4167410","Q4167836","Q24046192","Q41298","Q5633421","Q1980247",
    "Q169930","Q482994","Q7366","Q11424","Q15416","Q21191270",
    "Q187685", #doctoral thesis
    "Q43305660", #United States patent
    "Q1907875", #master's thesis
    "Q7725634", #literary work
    "Q3331189", #version, edition or translation
}

PREFERRED_P31  = {
    "Q16889133",  # class
    "Q151885",    # concept
    "Q11173",     # chemical compound
    # "Q11862829", # academic discipline
    # "Q7187",     # gene
    # "Q16521"     # taxon
}

# ================== DEBUG ==================
DEBUG_SCORES = True
DEBUG_SCORES_PATH = Path(
    r"C:\Users\sanda\Documents\Langara_College\DANA-4850-001-Capstone_Project\hall-api-test-db-mysql\wikidata\debug_scores.csv"
)
DEBUG_SCORES_MODE_PATH = Path(
    r"C:\Users\sanda\Documents\Langara_College\DANA-4850-001-Capstone_Project\hall-api-test-db-mysql\wikidata\debug_scores_mode.csv"
)

# --- Context similarity filters ---
STOPWORDS = {
    "the","and","of","in","on","for","with","by","from","to","at","as","is","are","was","were",
    "a","an","this","that","these","those","it","its","their","our"
}
MIN_TOKEN_LEN = 4

# ================== Mode-aware scoring ==================
# Bono por exactitud
EXACT_BONUS_LABEL = 20.0   # término por label exacto
EXACT_BONUS_ALIAS = 15.0   # término por alias exacto

# Pesos por modo para: contexto (ctx), sitelinks (sl), P31 (p31), P279 (p279),
# contexto vs P31 (ctx_p31) y contexto vs P279 (ctx_p279).
WEIGHTS_MODE = {
    "label": { "ctx": 3.0, "sl": 4.0, "p31": 2.0, "p279": 1.5, "ctx_p31": 2.2, "ctx_p279": 2.0, "alias_inv": 4.0 },
    "alias": { "ctx": 3.0, "sl": 4.0, "p31": 1.6, "p279": 1.0, "ctx_p31": 1.8, "ctx_p279": 1.5, "alias_inv": 8.0, }, #"sl": 0.6, "alias_inv": 4.0,
    "none":  { "ctx": 1.2, "sl": 0.5, "p31": 0.8, "p279": 0.6, "ctx_p31": 1.0, "ctx_p279": 0.8, "alias_inv": 3.0, },
}

# Filtro semántico suave del matcher (si True, se evalúa TODO; si False, descarta stubs)
PURE_SCORE_DISABLE_SEMANTIC_FILTER = True

# === Controles de filtrado / bonus por tipo ===
ENABLE_P31_BLOCK = True              # descarta candidatos cuyo P31 ∈ DISALLOWED_P31
ENABLE_PREFERRED_P31_BONUS = True    # suma bonus si P31 ∈ PREFERRED_P31
TYPE_BONUS = 30.0                    # tamaño del bonus por tipo preferido

# (Opcional) filtra stubs sin P31/P279/desc/alias:
PURE_SCORE_DISABLE_SEMANTIC_FILTER = False

# =============== PERFORMANCE / P279 EXPANSION =================
ENABLE_P279_PATHS   = True   # activa la expansión jerárquica de P279
P279_DEPTH          = 2      # niveles hacia arriba (subclass-of)
P279_MAX_NODES      = 300    # techo de nodos acumulados para evitar explosiones
P279_TEXT_MAXCHARS  = 12000  # recorte de texto concatenado para similitud
