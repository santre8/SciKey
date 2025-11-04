#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from . import config
from .neo4j_io import Neo4jConnector
from .pipeline import map_keywords, write_csv

def main():
    # 1. Conectar Neo4j
    print(f"🔗 Intentando conectar a Neo4j en {config.NEO4J_URI}...")
    try:
        neo4j_conn = Neo4jConnector(config.NEO4J_URI, config.NEO4J_USER, config.NEO4J_PASSWORD)
        neo4j_conn.driver.verify_connectivity()
        print("✅ Conexión con Neo4j exitosa.")
    except Exception as e:
        print(f"❌ Error al conectar a Neo4j. Detalle: {e}")
        return

    # 2. Leer JSON
    print(f"📥 Leyendo JSON de: {config.INPUT_JSON}")
    with open(config.INPUT_JSON, "r", encoding="utf-8") as f:
        records = json.load(f)

    print(f"🔍 Procesando {len(records)} records e ingresando en Neo4j y CSV...")
    rows = map_keywords(records, neo4j_conn)

    # 3. Guardar CSV
    print(f"\n💾 Guardando resultados en CSV: {config.OUTPUT_CSV}")
    write_csv(rows, config.OUTPUT_CSV)

    # 4. Cerrar conexión
    neo4j_conn.close()
    print("✅ Proceso finalizado. Conexión a Neo4j cerrada.")

if __name__ == "__main__":
    main()
