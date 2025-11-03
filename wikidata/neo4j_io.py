#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Dict, List, Optional
from neo4j import GraphDatabase, Driver, WRITE_ACCESS

class Neo4jConnector:
    def __init__(self, uri: str, user: str, password: str):
        self.driver: Driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        if self.driver:
            self.driver.close()

    def run_query(self, query: str, parameters: Optional[Dict] = None):
        with self.driver.session(default_access_mode=WRITE_ACCESS) as session:
            try:
                result = session.execute_write(self._execute_query, query, parameters or {})
                return result
            except Exception as e:
                print(f"[Neo4j] Error al ejecutar Cypher: {e}\nConsulta: {query}\nParámetros: {parameters}")
                return None

    @staticmethod
    def _execute_query(tx, query, parameters):
        return tx.run(query, parameters).consume()

def ingest_p279_hierarchy(connector: Neo4jConnector, entity_qid: str, entity_label: str,
                          qid_paths: List[List[str]], labels_map: Dict[str, str]):
    """Guarda la entidad y rutas P279* con labels."""
    connector.run_query("""
        MERGE (e:Item {qid: $qid})
        SET e.label = $label
    """, {"qid": entity_qid, "label": entity_label})

    for path in qid_paths:
        current_child_qid = entity_qid
        for parent_qid in path:
            if parent_qid == current_child_qid:
                continue
            parent_label = labels_map.get(parent_qid, parent_qid)
            connector.run_query("""
                MERGE (child:Item {qid: $child_qid})
                MERGE (parent:Item {qid: $parent_qid})
                SET parent.label = $parent_label
                MERGE (child)-[:SUBCLASS_OF]->(parent)
            """, {
                "child_qid": current_child_qid,
                "parent_qid": parent_qid,
                "parent_label": parent_label
            })
            current_child_qid = parent_qid

def ingest_document_map(connector: Neo4jConnector, docid: str, keyword: str, qid: str):
    connector.run_query("""
        MERGE (d:Document {id: $docid})
        MERGE (k:Keyword {name: $keyword})
        MERGE (q:Item {qid: $qid})
        MERGE (d)-[:CONTAINS_KEYWORD]->(k)
        MERGE (k)-[:MAPS_TO]->(q)
    """, {"docid": docid, "keyword": keyword, "qid": qid})

def ingest_p31_types(connector: Neo4jConnector, entity_qid: str, p31_ids: set, p31_labels: Dict[str, str]):
    for p31_qid in p31_ids:
        label = p31_labels.get(p31_qid, p31_qid)
        connector.run_query("""
            MERGE (item:Item {qid: $item_qid})
            MERGE (type:Class {qid: $type_qid})
            SET type.label = $type_label
            MERGE (item)-[:INSTANCE_OF]->(type)
        """, {"item_qid": entity_qid, "type_qid": p31_qid, "type_label": label})
