# neo4j-keywords Module – README
This module provides the Django + Neo4j explorer for the SciKey Knowledge Graph. It connects MySQL (HAL metadata) with Neo4j (Wikidata ontology), and exposes a web interface to search and visualize Document–Keyword–Item–Class relationships.

------------------------------------------------------------
1. Project Structure
------------------------------------------------------------

neo4j-keywords/
  manage.py
  movies/
    models.py          – Neo4j node models (Document, Keyword, Item, Class)
    mysql_models.py    – MySQL metadata models
    services.py        – Graph ingestion + D3 JSON builder
    views.py           – Search, graph API, metadata endpoints
    templates/
        home.html      – Homepage with stats + keywords
        index.html     – Graph explorer (D3.js)

------------------------------------------------------------
2. Environment Setup
------------------------------------------------------------

Create virtual environment:

Windows:
    py -3.11 -m venv .venv
    .\.venv\Scripts\Activate.ps1

macOS/Linux:
    python3 -m venv .venv
    source .venv/bin/activate

Install dependencies:
    pip install -r requirements.txt

If needed:
    pip install django
    pip install django_neomodel

------------------------------------------------------------
3. Neo4j Connection
------------------------------------------------------------

Set environment variable:

Windows:
    set NEO4J_BOLT_URL=bolt://neo4j:test@localhost:7687

macOS/Linux:
    export NEO4J_BOLT_URL=bolt://neo4j:test@localhost:7687

Ensure Neo4j is running and credentials match.

------------------------------------------------------------
4. Django Database (Admin DB)
------------------------------------------------------------

Run migrations:
    python manage.py migrate

Note: This database is only for Django admin. HAL metadata lives in MySQL; Wikidata graph lives in Neo4j.

------------------------------------------------------------
5. Running the Explorer
------------------------------------------------------------

From inside neo4j-keywords:

Windows:
    .\.venv\Scripts\Activate.ps1

Run server:
    python manage.py runserver

Open in browser:
    http://localhost:8000

------------------------------------------------------------
6. MySQL + Neo4j Integration
------------------------------------------------------------

MySQL tables (via mysql_models.py):
    Documents, Keywords, Authors, Journals, Organisms

Neo4j graph nodes (via models.py):
    Document (docid)
    Keyword (name)
    Item (qid, label)
    Class (qid, label)

Relationships:
    Document —CONTAINS_KEYWORD→ Keyword
    Keyword  —MAPS_TO→ Item
    Item     —INSTANCE_OF→ Class
    Item     —SUBCLASS_OF→ Item (ancestors)

------------------------------------------------------------
7. Graph Ingestion Workflow
------------------------------------------------------------

services.ingest_doc_graph(docid):
    - Executes optimized Cypher to fetch document subgraph
    - Upserts nodes into Neo4j via Neomodel
    - Extracts Item ancestors (P279)
    - Builds JSON for D3.js visualization
    - Caches results on disk

This function powers the /graph endpoint used in the UI.

------------------------------------------------------------
8. Search & API Endpoints
------------------------------------------------------------

/search?q=keyword
    - Searches MySQL Keywords table
    - Returns matching documents

/graph?docid=XXXX
    - Returns JSON graph for D3.js renderer

/doc-details?docid=XXXX
    - Returns document metadata:
        title, discipline, authors, journal, organisms, keywords, url_primary

------------------------------------------------------------
9. Example Cypher Queries
------------------------------------------------------------

All relationships for a document:
    MATCH (d:Document {id:"1006198"})-[:CONTAINS_KEYWORD]->(k)-[:MAPS_TO]->(i)
    MATCH path = (i)-[:SUBCLASS_OF*]->(a)
    RETURN path

Full subgraph:
    MATCH (n:Document {id:"1006198"})
    OPTIONAL MATCH (n)-[r1:CONTAINS_KEYWORD]->(k)
    OPTIONAL MATCH (k)-[r2:MAPS_TO]->(i)
    OPTIONAL MATCH (i)-[r3:INSTANCE_OF]->(c)
    OPTIONAL MATCH (i)-[r4:SUBCLASS_OF]->(p)
    RETURN n,r1,k,r2,i,r3,c,r4,p

------------------------------------------------------------
10. Admin Panel
------------------------------------------------------------

View Neo4j nodes in Django admin:
    http://localhost:8000/admin

------------------------------------------------------------
11. Summary
------------------------------------------------------------

This module:
    - Serves as SciKey’s visual exploration interface
    - Connects MySQL (HAL) + Neo4j (Wikidata ontology)
    - Provides search, graph visualization, and metadata lookup
    - Automatically builds and caches document subgraphs
    - Displays Document → Keyword → Item → Class hierarchy

It is the final interactive layer of the SciKey Knowledge Graph.

