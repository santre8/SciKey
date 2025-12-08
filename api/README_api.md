# HAL Preprocessing Module (`api/`)

The `api` module is the **first stage** of the SciKey pipeline.  
It extracts, filters, normalizes, and enriches scientific records from the **HAL** API, producing clean datasets ready for downstream ETL, MySQL loading.

---

## 1. Folder Structure

```
api/
│
├── apimodule.py       # Core HAL crawler + preprocessing utilities
├── main.py            # Example pipeline that calls apimodule
└── data/              # Output JSON files generated automatically
```

---

## 2. Overview

The module implements a robust data-fetching and preprocessing workflow:

1. Query HAL’s REST API using cursor-based pagination  
2. Filter documents by metadata (language, keywords, domain codes, inferred discipline)  
3. Clean and consolidate raw HAL fields  
4. Infer the academic discipline using domain code mapping + keyword fallback  
5. Export the final dataset to JSON/CSV/XLSX  

This ensures a consistent and reproducible extraction stage for the SciKey project.

---

## 3. Core Components

### `apimodule.py` 

Handles all low-level processing:

- HAL API request construction  
- Cursor pagination (`fetch_page()`)  
- Field extraction and normalization  
- Keyword consolidation  
- Domain code processing  
- Discipline inference via:
  - Regex-based domain patterns  
  - Keyword-based fallback classification  
- Primary URL selection  
- Data export utilities (JSON)

### `main.py` – Example Extraction Pipeline

A practical implementation of the entire pipeline.  
It:

- Fetches HAL pages  
- Normalizes metadata  
- Filters by the selected discipline  
- Stops after reaching `NEED_N` documents  
- Saves output to `api/data/<filename>.json`

Configurable parameters:

```python
NEED_N = 40
FIELD = "Civil Engineering"
FILE = "upec_civil_20_n.json"
```

---

## 4. Installation

Install required dependencies:

```bash
pip install requests pandas xlsxwriter
```

---

## 5. How to Run the Pipeline

From the project root:

```bash
cd api
python -m api.main
```

All output files will be saved inside:

```
api/data/
```

The folder is created automatically if missing.

---

## 6. Output Files

The module supports three formats:

### **JSON (default)**  
Stored in:

```
api/data/<filename>.json
```


---

## 7. HAL API Settings

The module queries:

```
https://api.archives-ouvertes.fr/search/<portal>/
```

Filters applied:

- English-language documents  
- Documents containing keywords  
- Domain code classification  
- Discipline inference (codes → text fallback)

Pagination uses `cursorMark` for stable and efficient crawling.

---

## 8. Discipline Classification Logic

This module currently detects five disciplines:

- Chemical Engineering  
- Civil Engineering  
- Computer Science  
- Political Science  
- Marketing  

Classification uses two stages:

1. **Domain Code Matching** via regex  
2. **Fallback Keyword Matching** on:
   - Title  
   - Abstract  
   - Consolidated keywords  

Only documents belonging to one of these disciplines are included.

---

## 9. Customizing the Extraction

### Number of documents:
```python
NEED_N = 150
```

### Target discipline:
```python
FIELD = "Chemical Engineering"
```

### Output filename:
```python
FILE = "chemical_eng_output.json"
```

### Add new disciplines:
Extend the code and keyword mappings in `apimodule.py`.

---

## 10. Error Handling

The module includes:

- 30-second request timeout  
- Cursor repetition detection to stop crawling  
- Skips records without keywords  
- A short delay (`0.12s`) to prevent API throttling  

---

