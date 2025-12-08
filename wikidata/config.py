from pathlib import Path

# =============== INPUT / OUTPUT PATHS =================
INPUT_JSON = Path(r"C:\Users\sanda\Documents\Langara_College\DANA-4850-001-Capstone_Project\hall-api-test-db-mysql\api\data\upec_n.json")
OUTPUT_CSV = Path(r"C:\Users\sanda\Documents\Langara_College\DANA-4850-001-Capstone_Project\hall-api-test-db-mysql\wikidata\hal_field_audit_out\Wikidata_upec_n_v3.csv")

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
MIN_TOTAL_SCORE = -9999
MAX_LEVELS_LINEAGE = 6
SEARCH_LIMIT = 50

#==================== Neo4j =======================
ENABLE_NEO4J_INGEST = True  

# =============== PERFORMANCE OPTIONS =================
ENABLE_P279_PATHS = True  

# ================== Properties y QIDs =================
P_INSTANCE_OF = "P31"
P_SUBCLASS_OF = "P279"
P_BNF_ID = "P268"
Q_DISAMBIGUATION = "Q4167410"
P_FIELD_OF_WORK = "P101"

# =============== P31 filters ===============
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
    "Q1114461", #video game character
    "Q15632617", #fictional human
    "Q1569167", #comics character
    "Q58632367", #scholarly conference abstract
    "Q1298668", #research grant;
    "Q54875403", #science project
    "Q30612", #clinical trial
    "Q15781350", #final project report
    "Q134556", #single
    "Q30612", #clinical trial
    "Q1266946", #thesis
    "Q7889", #video game
    "Q230788", #grant
    "Q2668072", #collection
    "Q476068", #Act of Congress in the United States
    "Q21198342", #manga series  
    "Q483242", #laboratory 
    "Q23927052", # conference paper
    "Q3099732", #technical report
    "Q13433827", #encyclopedia article
    "Q105543609", #musical work/composition;
    "Q7302866", #audio track
    "Q111475835", #bachelor's with honors thesis
    "Q5398426", #television series
    "Q215380", #musical group;musical duo
    "Q9212979", #musical duo
    "Q14946528", #music genre;
    "Q188451",#conflation
    "Q10904438",#Twelve Vassals
    "Q836688", #ancient Chinese state
    "Q1093580", #Chinese family name
    "Q191067", #article
    "Q281643", #musical trio
    "Q641066", #girl band
    "Q1760610", #comic book
    "Q867242", #comics anthology
    "Q3305213", #painting
    "Q100532807", #Irish Statutory Instrument
    "Q212971", #Request for Comments
    "Q202866", #animated film
    "Q202444", #Vietnamese middle name
    "Q431289", #brand


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
    r"C:\Users\sanda\Documents\Langara_College\DANA-4850-001-Capstone_Project\hall-api-test-db-mysql\wikidata\debug_scores_v3.csv"
)
DEBUG_SCORES_MODE_PATH = Path(
    r"C:\Users\sanda\Documents\Langara_College\DANA-4850-001-Capstone_Project\hall-api-test-db-mysql\wikidata\debug_scores_mode_upec_n_v3.csv"
)

# --- Context similarity filters ---
STOPWORDS = {
    "the", "and", "of", "in", "on", "at", "for", "with", "by", "from", "to",
    "as", "is", "are", "was", "were", "be", "been", "being",
    "a", "an", "this", "that", "these", "those", "it", "its", "their", "our",
    "such", "many", "various", "several", "within", "between", "across",
    "through", "throughout", "overall", "including", "based", "related",
    "according", "further", "however", "also", "often", "generally",
    "mainly", "mostly", "nearly", "usually", "already",
    "may", "might", "can", "could", "should", "would",
    "used", "using", "use", "make", "made",
    "per", "via", "over", "under", "towards", "onto", "into", "out"
}
MIN_TOKEN_LEN = 2

# ================== Mode-aware scoring ==================

EXACT_BONUS_LABEL = 4.71283719812918   
EXACT_BONUS_ALIAS = 3.62412709435424  


WEIGHTS_MODE = {
    "label": { "ctx": 0.0543224825527197, "sl": 0.528106969082633, "p31": 0.195429005395847, "p279": -0.128992085884209, "ctx_p31": -0.0194360330503352, "ctx_p279": 0.0569351710003201, "alias_inv": 0.524144976653911},
    "alias": { "ctx": 0.0543224825527197, "sl": 0.528106969082633, "p31": 0.195429005395847, "p279": -0.128992085884209, "ctx_p31": -0.0194360330503352, "ctx_p279": 0.0569351710003201, "alias_inv": 0.524144976653911, }, #"sl": 0.6, "alias_inv": 4.0,
    "none":  { "ctx": 0.0543224825527197, "sl": 0.528106969082633, "p31": 0.195429005395847, "p279": -0.128992085884209, "ctx_p31": -0.0194360330503352, "ctx_p279": 0.0569351710003201, "alias_inv": 0.524144976653911, },
}


PURE_SCORE_DISABLE_SEMANTIC_FILTER = True


ENABLE_P31_BLOCK = True              
ENABLE_PREFERRED_P31_BONUS = True    
TYPE_BONUS = 0.0                    


PURE_SCORE_DISABLE_SEMANTIC_FILTER = False

# =============== PERFORMANCE / P279 EXPANSION =================
P279_DEPTH          = 1      
P279_MAX_NODES      = 300    
P279_TEXT_MAXCHARS  = 12000  


