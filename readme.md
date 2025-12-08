# SciKey

SciKey is a complete pipeline that ingests scientific records from **HAL**, enriches them using **Wikidata**, and stores the results in **Neo4j** to power an interactive graph explorer (Django front/back).  
This repository includes the full stack: API services, ETL pipeline, MySQL storage, Neo4j database, and orchestration via Docker.

---

## What’s Inside

### **api/**
Python service (FastAPI) that:
- Fetches records from **HAL**
- Normalizes fields  
- Outputs clean **JSON** for downstream processing  

---

### **database-image/**
Contains the Docker image and initialization scripts used to create the **MySQL** database.

### **mysql-data/**
Local volume where MySQL stores its generated data.

---

### **neo4j-keywords/**
Django front/back application that:
- Connects to **Neo4j**
- Queries the knowledge graph  
- Renders interactive visualizations and filters  

---

### **neo4j-scripts/**
Cypher scripts for:
- Index creation  
- Constraints  
- Data cleanup  
- Batch inserts  

---

### **wikidata/**
ETL worker that:
- Reads the JSON produced by the API  
- Queries **Wikidata** entities  
- Computes mappings and similarity scores  
- Inserts enriched nodes and relationships into Neo4j  

---

## How to Run

### **1. Go to the folder containing `docker-compose.yml`**

```sh
./docker-compose up -d
```

### **2. Clean up (optional, for rebuilds)**

```sh
docker compose down --rmi all --volumes
docker rm -f mysql-container-scikey && docker rmi scikey-mysql-db
```

### **3. Verify Neo4j is running**

```sh
docker ps --filter name=neo4j
```


## Recommended Tools (Optional)

- Visual Studio Code – Suggested IDE for browsing and editing the project
- DBeaver – To explore MySQL and Neo4j
- Docker Desktop – To manage containers