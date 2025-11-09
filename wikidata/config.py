from pathlib import Path

# =============== INPUT / OUTPUT PATHS =================
INPUT_JSON = Path(r"C:\Users\sanda\Documents\Langara_College\DANA-4850-001-Capstone_Project\hall-api-test-db-mysql\api\data\upec_chemical_4.json")
OUTPUT_CSV = Path(r"C:\Users\sanda\Documents\Langara_College\DANA-4850-001-Capstone_Project\hall-api-test-db-mysql\wikidata\hal_field_audit_out\Wikidata_upec_chemical_20.csv")

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

#====================Neo4j================
ENABLE_NEO4J_INGEST = False  # <- set it to True only when you actually want to load into Neo4j

# =============== PERFORMANCE OPTIONS =================
ENABLE_P279_PATHS = False  # Set to True when you want to generate full subclass paths

# Properties and QIDs
P_INSTANCE_OF = "P31"
P_SUBCLASS_OF = "P279"
P_BNF_ID = "P268"
Q_DISAMBIGUATION = "Q4167410"
P_FIELD_OF_WORK = "P101"   # ← NUEVO

# P31 filters
DISALLOWED_P31 = {
    "Q13442814",  # scholarly article
    "Q571",       # book
    "Q1002697",   # written work
    "Q737498",    # document
    "Q47461344",  # written work (broad)
    "Q732577",    # publication
    #"Q5",         # human
    "Q215627",    # person
    "Q43229",     # organization
    "Q1656682",   # company
    "Q4830453",   # business
    "Q167037",      # corporation
    "Q17334923",  # research project
    "Q1371598",   # software
    "Q35127",     # website
    #"Q101352",    # university
    #"Q3918",      # educational institution
    "Q95074",     # award
    "Q4167410",   # Wikidata disambiguation page
    "Q4167836",   # Wikimedia category
    "Q24046192",   # academic journal article
    "Q41298",       # magazine
    "Q5633421",      #scientific journal
    "Q1980247",      #chapter
    
    # --- Media / entertainment (to avoid false positives) ---
    "Q169930",    # extended play (EP)
    "Q482994",    # album
    "Q7366",      # song
    "Q11424",     # film
    "Q15416",     # television series
    "Q21191270"     #television series episode

}

PREFERRED_P31  = { #"Q486972", #human settlement 
                   #"Q618123", #geographical feature
                   #"Q82794", #region
                   "Q16889133", # class
                   "Q151885", # concept 
                   "Q11173", # chemical compound
                   #"Q11862829", # academic discipline
                   #"Q7187", # gene
                   # "Q16521" #taxon 
                    }
# =============== DEBUG =================
DEBUG_SCORES = True
DEBUG_SCORES_PATH = Path(r"C:\Users\sanda\Documents\Langara_College\DANA-4850-001-Capstone_Project\hall-api-test-db-mysql\wikidata\debug_scores.csv")  # cambia la ruta si quieres

# --- Context similarity filters ---
STOPWORDS = {
    "the","and","of","in","on","for","with","by","from","to","at","as","is","are","was","were",
    "a","an","this","that","these","those","it","its","their","our"
}
MIN_TOKEN_LEN = 4   # ignora tokens cortos en el cálculo de contexto