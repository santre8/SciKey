# scripts/fill_missing_item_labels.py
"""
Rellena los labels faltantes de nodos :Item en Neo4j usando Wikidata.

Uso:
    (.venv) python scripts/fill_missing_item_labels.py
"""

import os
import time
import requests

import django
from neomodel import db


import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "neomovies.settings")
# scripts/fill_missing_item_labels.py
"""
Rellena los labels faltantes de nodos :Item en Neo4j usando Wikidata.

Uso:
    (.venv) python scripts/fill_missing_item_labels.py
"""

import os
import time
import requests

import django
from neomodel import db


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "neomovies.settings")
django.setup()

# ====== CONFIG ======
WIKIDATA_URL = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"


HEADERS = {
    "User-Agent": "SciKey-Graph/1.0 (Langara College student project; contact: tu_email@ejemplo.com)"
}

SLEEP_SECONDS = 0.2 


def get_missing_qids(limit: int | None = None):

    cypher = "MATCH (n:Item) WHERE n.label IS NULL RETURN n.qid AS qid"
    results, meta = db.cypher_query(cypher)
    qids = [row[0] for row in results if row[0]]
    if limit:
        qids = qids[:limit]
    return qids


def fetch_label_from_wikidata(qid: str) -> str | None:

    url = WIKIDATA_URL.format(qid=qid)
    resp = requests.get(url, headers=HEADERS, timeout=15)

    if resp.status_code == 403:
        raise RuntimeError(f"403 Forbidden for {url} (possible rate limit or User-Agent rejected)")

    resp.raise_for_status()
    data = resp.json()

    entity = data.get("entities", {}).get(qid)
    if not entity:
        return None

    labels = entity.get("labels", {})

    for lang in ("en", "fr", "es"):
        if lang in labels:
            return labels[lang]["value"]

    return None


def update_label_in_neo4j(qid: str, label: str) -> None:

    cypher = """
    MATCH (n:Item {qid: $qid})
    SET n.label = $label
    """
    db.cypher_query(cypher, {"qid": qid, "label": label})


def main():

    qids = get_missing_qids()
    total = len(qids)
    print(f"Found {total} Item nodes without label")

    for idx, qid in enumerate(qids, start=1):
        try:
            label = fetch_label_from_wikidata(qid)
        except Exception as e:
            print(f"[{idx}/{total}] {qid}: ERROR fetching from Wikidata -> {e}")

            continue

        if not label:
            print(f"[{idx}/{total}] {qid}: no label found in Wikidata")
            continue

        try:
            update_label_in_neo4j(qid, label)
        except Exception as e:
            print(f"[{idx}/{total}] {qid}: ERROR updating Neo4j -> {e}")
            continue

        print(f"[{idx}/{total}] {qid} -> {label}")
        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()
