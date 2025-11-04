#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from . import config
from .neo4j_io import Neo4jConnector
from .pipeline import map_keywords, write_csv

def main():
    # 1. Connect to Neo4j
    print(f"🔗 Trying to connect to Neo4j at {config.NEO4J_URI}...")
    try:
        neo4j_conn = Neo4jConnector(config.NEO4J_URI, config.NEO4J_USER, config.NEO4J_PASSWORD)
        neo4j_conn.driver.verify_connectivity()
        print("✅ Connection to Neo4j successful.")
    except Exception as e:
        print(f"❌ Error connecting to Neo4j. Details: {e}")
        return

    # 2. Read JSON file
    print(f"📥 Reading JSON from: {config.INPUT_JSON}")
    with open(config.INPUT_JSON, "r", encoding="utf-8") as f:
        records = json.load(f)

    print(f"🔍 Processing {len(records)} records and ingesting into Neo4j and CSV...")
    rows = map_keywords(records, neo4j_conn)

    # 3. Save results to CSV
    print(f"\n💾 Saving results to CSV: {config.OUTPUT_CSV}")
    write_csv(rows, config.OUTPUT_CSV)

    # 4. Close Neo4j connection
    neo4j_conn.close()
    print("✅ Process completed. Neo4j connection closed.")

if __name__ == "__main__":
    main()
