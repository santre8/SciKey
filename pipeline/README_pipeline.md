# README_pipeline.md
## SciKey ETL Pipeline (`python -m pipeline.main`)

The **pipeline module** implements the second stage of the SciKey workflow.  
After the HAL extraction step produces a cleaned JSON dataset, this pipeline:

1. Loads the sample dataset  
2. Normalizes all fields into relational tables  
3. Avoids duplicates intelligently  
4. Writes everything into the MySQL SciKey database

This pipeline turns semi-structured HAL records into a fully structured relational schema ready for analytics, Neo4j enrichment, or downstream machine learning.

---

## 1. Pipeline Structure

```
pipeline/
│
├── main.py          # Orchestrates the normalization + load process
├── load.py          # Low-level MySQL loader with dedup logic
└── __init__.py
```

---

## 2. What the Pipeline Does

Running:

```
python -m pipeline.main
```

performs the following sequence:

### **1. Load the extracted JSON dataset**
The file comes from the `api` module, e.g.:

```
api/data/upec_civil_20_n.json
```

It loads the file into a Pandas DataFrame.

---

### **2. Normalize the data into relational tables**

`main.py` contains multiple `normalize_*()` functions that reshape raw HAL data into clean schema-aligned tables:

| Function | Output Table | Description |
|---------|--------------|-------------|
| `normalize_documents()` | `documents` | Core metadata (doc_id, title, discipline, primary URL) |
| `normalize_authors()` | `authors` | One row per author per document |
| `normalize_keywords()` | `keywords` | Explodes keyword lists |
| `normalize_identifiers()` | `identifiers` | DOI, ISBN, HAL IDs |
| `normalize_organisms()` | `organisms` | Extracts and deduplicates HAL structure IDs |
| `normalize_document_organisms()` | `document_organisms` | Links documents ↔ organisms |
| `normalize_journals()` | `journals` | Journal ISSN and titles |
| `normalize_author_organisms()` | `author_organisms` | Maps authors ↔ organisms (via HAL’s encoded IDs) |

All transformations are deterministic and safe for repeated runs.

---

### **3. Load the data into MySQL**

The loader (`load.py`) includes safety features:

- Skips duplicate `doc_id` values  
- Skips duplicate `hal_structure_id` for organisms  
- Uses efficient `to_sql(method="multi")` batch inserts  
- Creates the engine using environment variables (or defaults)

The loader writes to these tables:

- `documents`  
- `authors`  
- `keywords`  
- `identifiers`  
- `organisms`  
- `document_organisms`  
- `author_organisms`  
- `journals`

---

## 3. How to Run the Pipeline

### **Prerequisites**

1. MySQL must be running (Docker or local).  
2. Database credentials must match those in `load.py`.

Defaults (for local dev):

```
user: citizix_user
pwd: An0thrS3crt
db: scikey
host: 127.0.0.1
port: 5362
```

---

### **Execute the pipeline**

From the project root:

```bash
python -m pipeline.main
```

You should see logs like:

```
Rows in sample: 40
[documents] 0 rows skipped (already in DB), 40 new rows inserted.
[keywords] Data successfully written to MySQL: keywords
...
```

---

## 4. Configuration: Selecting Which Dataset to Load

In `pipeline/main.py` the dataset is configured here:

```python
data_path = os.path.join(
    os.path.dirname(__file__), '..', 'api', 'data', 'upec_civil_20_n.json'
)
```

To switch datasets, change the filename:

```python
# upec_chemical_20_n.json
# upec_computer_20_n.json
# upec_political_20_n.json
# upec_marketing_20_n.json
# upec_civil_20_n.json
```

---

## 5. Schema Overview

The pipeline writes to these tables:

```
documents(doc_id, halId_s, title, abstract, discipline, domain_codes, url_primary)
authors(doc_id, author_index, authFirstName_s, authLastName_s, authQuality_s)
keywords(doc_id, keyword_s)
identifiers(doc_id, doiId_s, halId_s, isbn)
organisms(hal_structure_id, structIdName_fs)
document_organisms(doc_id, hal_structure_id)
author_organisms(doc_id, author_index, hal_structure_id)
journals(doc_id, journalIssn_s, journalTitle_s)
```

---
