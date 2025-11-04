from pathlib import Path

# =============== INPUT / OUTPUT PATHS =================
INPUT_JSON = Path(r"C:\Users\sanda\Documents\Langara_College\DANA-4850-001-Capstone_Project\hall-api-test-db-mysql\api\data\upec_chemical_20_5.json")
OUTPUT_CSV = Path(r"C:\Users\sanda\Documents\Langara_College\DANA-4850-001-Capstone_Project\hall-api-test-db-mysql\wikidata\hal_field_audit_out\Wikidata_upec_chemical_20_5.csv")

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

# Properties and QIDs
P_INSTANCE_OF = "P31"
P_SUBCLASS_OF = "P279"
P_BNF_ID = "P268"
Q_DISAMBIGUATION = "Q4167410"

# P31 filters
DISALLOWED_P31 = { "Q13442814", "Q571", "Q1002697", "Q737498", "Q732577", "Q47461344" }
PREFERRED_P31  = { "Q486972", "Q618123", "Q82794", "Q16889133", "Q151885", "Q11173", "Q11862829", "Q7187", "Q16521" }
