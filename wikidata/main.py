#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from . import config
from .neo4j_io import Neo4jConnector
from .pipeline import map_keywords, write_csv

def main():
    # 1) Read JSON
    print(f"📥 Reading JSON from: {config.INPUT_JSON}")
    with open(config.INPUT_JSON, "r", encoding="utf-8") as f:
        records = json.load(f)

    # 2) Map first (without Neo4j by default)
    neo4j_conn = None
    if config.ENABLE_NEO4J_INGEST:
        print(f"🔗 Trying to connect to Neo4j at {config.NEO4J_URI}...")
        try:
            neo4j_conn = Neo4jConnector(config.NEO4J_URI, config.NEO4J_USER, config.NEO4J_PASSWORD)
            neo4j_conn.driver.verify_connectivity()
            print("✅ Connection to Neo4j successful.")
        except Exception as e:
            print(f"⚠️ Could not connect to Neo4j. Continuing without ingest. Details: {e}")
            neo4j_conn = None

    print(f"🔍 Processing {len(records)} records...")
    rows = map_keywords(records, neo4j_conn)  # if conn is None or toggle is False, NO ingestion

    # 3) Save CSV for review
    print(f"\n💾 Saving results to CSV: {config.OUTPUT_CSV}")
    write_csv(rows, config.OUTPUT_CSV)

    # 4) Close Neo4j if it was opened
    if neo4j_conn:
        neo4j_conn.close()
        print("✅ Neo4j connection closed.")

    print("🏁 Done.")

if __name__ == "__main__":
    main()
