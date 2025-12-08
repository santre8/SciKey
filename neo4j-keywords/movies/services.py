# app: movies/services.py
from neomodel import db
from .models import Document, Keyword, Item, Class

from pathlib import Path
import json
import os
from typing import Dict, List, Optional

# =============== CACHE (OPTION 2) =====================
BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "graph_cache"
CACHE_DIR.mkdir(exist_ok=True)


# =============== CYPHER (OPTION 1) ====================
#  - Neo4j computes:
#       * ancestors: all Items reachable through SUBCLASS_OF*1..10
#       * subclassRels: ALL SUBCLASS_OF relationships between i and those ancestors
#
#  This avoids reconstructing paths in Python and greatly reduces processing time.
CYPHER = """
MATCH (n:Document {id: $docid})
OPTIONAL MATCH (n)-[:CONTAINS_KEYWORD]->(k:Keyword)
OPTIONAL MATCH (k)-[:MAPS_TO]->(i:Item)
OPTIONAL MATCH (i)-[:INSTANCE_OF]->(c:Class)
OPTIONAL MATCH p = (i)-[:SUBCLASS_OF*1..10]->(ancestor:Item)
WITH n, k, i, c, collect(DISTINCT ancestor) AS ancestors
OPTIONAL MATCH (a:Item)-[r:SUBCLASS_OF]->(b:Item)
WHERE (a IN ancestors OR b IN ancestors OR a = i OR b = i)
WITH n, k, i, c, ancestors, collect(DISTINCT r) AS subclassRels
RETURN n, k, i, c, ancestors, subclassRels
"""


# =============== HELPERS NEO4J/NEOMODEL ================

def _get_or_create_document(docid: str) -> Document:
    doc = Document.nodes.get_or_none(docid=docid)
    if not doc:
        doc = Document(docid=docid).save()
    return doc


def _get_or_create_keyword(name: Optional[str]) -> Optional[Keyword]:
    if not name:
        return None
    kw = Keyword.nodes.get_or_none(name=name)
    if not kw:
        kw = Keyword(name=name).save()
    return kw


def _get_or_create_item(qid: Optional[str], label: Optional[str] = None) -> Optional[Item]:
    if not qid:
        return None
    it = Item.nodes.get_or_none(qid=qid)
    if not it:
        it = Item(qid=qid, label=label).save()
    else:
        if label and (not it.label or it.label != label):
            it.label = label
            it.save()
    return it


def _get_or_create_class(qid: Optional[str], label: Optional[str] = None) -> Optional[Class]:
    if not qid:
        return None
    cl = Class.nodes.get_or_none(qid=qid)
    if not cl:
        cl = Class(qid=qid, label=label).save()
    else:
        if label and (not cl.label or cl.label != label):
            cl.label = label
            cl.save()
    return cl


def _connect_once(rel_manager, node):
    """Connect only if the relationship does not already exist."""
    if node is None:
        return
    try:
        if not rel_manager.is_connected(node):
            rel_manager.connect(node)
    except AttributeError:
        # para relaciones simples de neomodel
        rel_manager.connect(node)


def _add_node(
    nodes_dict: Dict[str, Dict],
    node_id: str,
    label: str,
    title: Optional[str] = None,
    extra: Optional[Dict] = None,
):
    """Idempotent: adds the node only if it doesn't already exist."""
    if not node_id:
        return
    if node_id not in nodes_dict:
        payload = {
            "id": node_id,
            "label": label,              # clase CSS en index.html
            "title": title or node_id,   # tooltip en D3
        }
        if extra:
            payload.update(extra)
        nodes_dict[node_id] = payload


def _add_link(
    links: List[Dict],
    links_seen: set,
    source: Optional[str],
    target: Optional[str],
    rel_type: str,
):
    """Add an edge only if it is not duplicated."""
    if not source or not target:
        return
    key = (source, target, rel_type)
    if key in links_seen:
        return
    links.append({"source": source, "target": target, "type": rel_type})
    links_seen.add(key)


# =============== MAIN FUNCTION =====================

def ingest_doc_graph(docid, focus_keyword=None) -> dict:
    """
    Reads the subgraph of Document(id=$docid), upserts into Django/Neomodel,
    and builds the D3 JSON: {"nodes": [...], "links": [...], "stats": {...}}.

    Includes:
      - OPTION 1: Optimized Cypher for SUBCLASS_OF
      - OPTION 2: Disk cache per docid
    """

    # ---------- 1) CACHE: if it exists, return it immediately----------
    cache_file = CACHE_DIR / f"{docid}.json"
    if cache_file.exists():
        with cache_file.open("r", encoding="utf-8") as f:
            return json.load(f)

    # ---------- 2) Execute Cypher----------
    rows, _ = db.cypher_query(CYPHER, {"docid": str(docid)})

    doc = _get_or_create_document(docid)

    nodes: Dict[str, Dict] = {}
    links: List[Dict] = []
    links_seen: set = set()

    stats = {
        "document": docid,
        "keywords_linked": 0,
        "maps_to_linked": 0,
        "instance_of_linked": 0,
        "subclass_of_linked": 0,
        "keywords_seen": set(),
        "items_seen": set(),
        "classes_seen": set(),
        "rows": len(rows),
    }


    _add_node(nodes, docid, "Document", title=f"Document {docid}")


    for (n, k, i, c, ancestors, subclass_rels) in rows:
        # --- Keyword ---
        kw_id = None
        if k is not None:
            k_props = dict(k)
            kw_name = k_props.get("name")
            kw = _get_or_create_keyword(kw_name)
            if kw:
                kw_id = kw.name
                _add_node(nodes, kw_id, "Keyword", title=f"Keyword: {kw_id}")
                _add_link(links, links_seen, docid, kw_id, "CONTAINS_KEYWORD")
                _connect_once(doc.keywords, kw)
                stats["keywords_linked"] += 1
                stats["keywords_seen"].add(kw_id)

        # --- Item (MAPS_TO) ---
        item_id = None
        if i is not None:
            i_props = dict(i)
            item_id = i_props.get("qid")
            item_label = i_props.get("label")
            item = _get_or_create_item(item_id, label=item_label)
            if item:
                _add_node(
                    nodes,
                    item.qid,
                    "Item",
                    title=(
                        f"Item {item.qid} ({item.label})"
                        if item.label
                        else f"Item {item.qid}"
                    ),
                    extra={"caption": item.label or item.qid},
                )
                stats["items_seen"].add(item.qid)
                if kw_id:
                    _add_link(links, links_seen, kw_id, item.qid, "MAPS_TO")
                    _connect_once(Keyword.nodes.get(name=kw_id).maps_to, item)
                    stats["maps_to_linked"] += 1

        # --- Class (INSTANCE_OF) ---
        if item_id and c is not None:
            c_props = dict(c)
            class_qid = c_props.get("qid")
            class_label = c_props.get("label")
            klass = _get_or_create_class(class_qid, label=class_label)
            if klass:
                _add_node(
                    nodes,
                    klass.qid,
                    "Class",
                    title=(
                        f"Class {klass.qid} ({klass.label})"
                        if klass.label
                        else f"Class {klass.qid}"
                    ),
                    extra={"caption": klass.label or klass.qid},
                )
                _add_link(links, links_seen, item_id, klass.qid, "INSTANCE_OF")
                _connect_once(Item.nodes.get(qid=item_id).instance_of, klass)
                stats["classes_seen"].add(klass.qid)
                stats["instance_of_linked"] += 1

        # --- SUBCLASS_OF: ancestors + relationships (already computed in Cypher) ---
        # 1) ancestor nodes
        if ancestors:
            for anc in ancestors:
                if anc is None:
                    continue
                props = dict(anc)
                qid = props.get("qid")
                label = props.get("label")
                item = _get_or_create_item(qid, label=label)
                if not item:
                    continue
                _add_node(
                    nodes,
                    item.qid,
                    "Item",
                    title=(
                        f"Item {item.qid} ({item.label})"
                        if item.label
                        else f"Item {item.qid}"
                    ),
                    extra={"caption": item.label or item.qid},
                )
                stats["items_seen"].add(item.qid)

        # 2) SUBCLASS_OF edges (simple relationships, not full paths)
        if subclass_rels:
            for rel in subclass_rels:
                if rel is None:
                    continue
                start_qid = dict(rel.start_node).get("qid")
                end_qid = dict(rel.end_node).get("qid")
                if not start_qid or not end_qid:
                    continue

                _add_link(links, links_seen, start_qid, end_qid, "SUBCLASS_OF")

                
                start_item = Item.nodes.get_or_none(qid=start_qid)
                end_item = Item.nodes.get_or_none(qid=end_qid)
                if start_item and end_item:
                    _connect_once(start_item.ancestors, end_item)

                stats["subclass_of_linked"] += 1

    # ---------- 3) Convert sets -> lists for JSON serialization ----------
    stats["keywords_seen"] = sorted(stats["keywords_seen"])
    stats["items_seen"] = sorted(stats["items_seen"])
    stats["classes_seen"] = sorted(stats["classes_seen"])

    result = {
        "nodes": list(nodes.values()),
        "links": links,
        "stats": stats,
    }

    # ---------- 4) Save to cache and return ----------
    with cache_file.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)

    return result
