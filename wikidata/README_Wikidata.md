# Wikidata Enrichment Module (`wikidata/`)
Run with:
python -m wikidata.main

This module enriches HAL keywords by mapping them to Wikidata entities using a multi-stage ranking and semantic evaluation pipeline. It performs candidate retrieval, context-aware scoring, P31/P279 semantic validation, hierarchical expansion, and optional Neo4j ingestion. The result is a structured and semantically rich representation of scientific keywords.

------------------------------------------------------------
1. Overview
------------------------------------------------------------

The goal of this module is to convert the free-text keywords extracted from HAL documents into structured Wikidata QIDs. This enables downstream tasks such as:
- Knowledge graph construction
- Keyword disambiguation
- Scientific domain analysis
- Entity-centric search and visualization

The system performs:
1. Preprocessing of keywords and text context
2. Wikidata search using several strategies
3. Entity fetching with claims and metadata
4. Scoring and ranking of candidate entities
5. Hierarchy extraction (P279)
6. P31 semantic typing
7. Writing of results to CSV
8. Optional ingestion into Neo4j

------------------------------------------------------------
2. Folder Structure
------------------------------------------------------------

wikidata/
    main.py             - Orchestration script for the full pipeline
    config.py           - All configuration values for API, Neo4j, scoring
    utils.py            - Text normalization, tokenization, helpers
    scoring.py          - Scoring logic (context, label, canonicality, P31/P279)
    matchers.py         - Core matching algorithm using scoring
    wikidata_api.py     - Thin wrapper around Wikidata API endpoints
    pipeline.py         - Keyword mapping, row generation, Neo4j calls
    neo4j_io.py         - Functions for inserting data into Neo4j
    total_score_v5.py   - Logistic regression scoring extension
    requirements.txt    - Python dependency list

------------------------------------------------------------
3. Full Processing Pipeline
------------------------------------------------------------

3.1 Input
The module reads HAL records from a JSON file defined in config.INPUT_JSON.  
Each record typically contains:
- docid
- title
- abstract
- keywords

A context string is created by concatenating title and abstract.

3.2 Keyword Normalization
Keyword normalization uses functions from utils.py:
- normalize_kw: lowercasing, acronym handling, dash/plus retention
- tokenize: clean token extraction
- singularize_en: heuristic singularization for English nouns

These functions ensure consistency when comparing keywords with Wikidata labels or descriptions.

3.3 Candidate Retrieval
The module queries Wikidata using:
- wbsearchentities
- wbsearch_label_only
- wbgetentities

Candidates are retrieved in multiple languages (en, fr) as configured.

Each candidate includes:
- label
- description
- aliases
- sitelinks
- claims such as P31, P279, P101

3.4 Semantic Filtering
Candidates can be filtered by:
- P31 class restrictions (DISALLOWED_P31)
- Presence of descriptions
- Optional semantic rules controlled via config

This step ensures that the model avoids matching irrelevant concepts such as songs, artworks, organizations, or fictional characters.

3.5 Scoring System
The ranking system in scoring.py is responsible for computing match quality. It includes:

A. Label similarity  
Uses strict fuzzy matching between normalized keyword and label/aliases.

B. Context similarity  
Compares document context to entity text fields using token overlap and fuzzy comparison.

C. Canonicality  
Penalizes items with low structural importance and rewards:
- High sitelink count
- Presence of P279 hierarchy
- Alias variety

D. P31 and P279 information  
The system checks:
- Instance-of classes (P31)
- Subclass-of chains (P279)
- Expanded semantic context for matching

E. Mode-aware scoring  
Different weights are applied depending on whether the keyword exactly matches the label, an alias, or neither.

3.6 Hierarchy Expansion
If P279 subclass relations exist, the system expands them up to a configurable depth.  
Each path is converted into readable lineage strings recorded in the output CSV.

3.7 Neo4j Ingestion
If enabled (ENABLE_NEO4J_INGEST = True), the script:
- Creates or updates Item, Class, Keyword, and Document nodes
- Inserts INSTANCE_OF (P31) edges
- Inserts SUBCLASS_OF (P279) edges
- Connects Document → Keyword → Item mappings

This turns the SciKey dataset into a navigable knowledge graph.

3.8 CSV Output
The final CSV contains:
- Document ID
- Keyword
- Wikidata QID
- Matched label
- BNF ID, if available
- P279 hierarchy
- P31 types and labels
- Scoring information
- Disambiguation flags

------------------------------------------------------------
4. How to Run
------------------------------------------------------------

Install dependencies:
pip install -r wikidata/requirements.txt

Run the module:
python -m wikidata.main

The script will:
- Load the HAL JSON
- Attempt to connect to Neo4j
- Process each record
- Generate the output CSV
- Optionally ingest into Neo4j

------------------------------------------------------------
5. Output Files
------------------------------------------------------------

The module produces:
- A cleaned CSV mapping keywords to Wikidata entities
- Neo4j graph data (if enabled)
- Optional debug CSV files if DEBUG_SCORES or related flags are active

Debug files contain:
- Context similarity breakdown
- Label similarity tokens
- Overlap metrics
- Scoring contributions from each feature

------------------------------------------------------------
6. Integration with the Full SciKey Pipeline
------------------------------------------------------------

The Wikidata module typically follows the API extraction stage.  
A standard execution sequence is:

1. Extract HAL metadata and keywords:
   python -m api.main

2. Loaded into MySQL
    python -m pipeline.main

3. Enrich keywords with Wikidata:
   python -m wikidata.main

After this, the enriched data may be:
- Explored in Neo4j
- Webpage

------------------------------------------------------------
7. Notes and Recommendations
------------------------------------------------------------

- The scoring parameters in config.py can be tuned for different domains.
- Subclass expansion can be expensive; reduce P279_DEPTH for faster runs.
- Disable Neo4j ingestion during debugging to increase throughput.
- Use debug CSV files to inspect why specific matches were chosen.

