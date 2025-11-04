# 🧠 Wikidata Enrichment Script

This project performs **keyword-to-Wikidata enrichment** using the HAL dataset.  
It retrieves candidate Wikidata entities based on keyword, title, and abstract similarity, applies fuzzy matching, and builds lineage paths for each matched QID.

---

## 📁 Project Structure

```
HALL-API-TEST-DB-MYSQL/
│
├── api/
│   └── data/
│       └── upec_sample200_keywords_domains.json
│
├── wikidata/
|   ├─ main.py
|   ├─ config.py
|   ├─ utils.py
|   ├─ wikidata_api.py
|   ├─ scoring.py
|   ├─ matchers.py
|   ├─ neo4j_io.py
|   ├─ pipeline.py
|   └─ requirements.txt
│
└── ...
```


---


pip install -r requirements.txtc


python -m wikidata.main