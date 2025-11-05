# app: movies/services.py
from neomodel import db
from .models import Document, Keyword, Item, Class

CYPHER = """
MATCH (n:Document)
WHERE n.id = $docid
OPTIONAL MATCH (n)-[r1:CONTAINS_KEYWORD]->(k:Keyword)
OPTIONAL MATCH (k)-[r2:MAPS_TO]->(i:Item)
OPTIONAL MATCH (i)-[r3:INSTANCE_OF]->(c:Class)
OPTIONAL MATCH (i)-[r4:SUBCLASS_OF]->(parent:Item)
RETURN n, k, i, c, parent
"""

def _get_or_create_document(docid: str) -> Document:
    # Your model maps property 'docid' -> db_property='id'
    doc = Document.nodes.get_or_none(docid=docid)
    if not doc:
        doc = Document(docid=docid).save()
    return doc

def _get_or_create_keyword(name: str | None) -> Keyword | None:
    if not name:
        return None
    kw = Keyword.nodes.get_or_none(name=name)
    if not kw:
        kw = Keyword(name=name).save()
    return kw

def _get_or_create_item(qid: str | None, label: str | None = None) -> Item | None:
    if not qid:
        return None
    it = Item.nodes.get_or_none(qid=qid)
    if not it:
        it = Item(qid=qid, label=label).save()
    else:
        # Backfill label if missing or different
        if label and (not it.label or it.label != label):
            it.label = label
            it.save()
    return it

def _get_or_create_class(qid: str | None, label: str | None = None) -> Class | None:
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
    """Connect only if not already connected."""
    if node is None:
        return
    try:
        if not rel_manager.is_connected(node):
            rel_manager.connect(node)
    except AttributeError:
        # For safety in case rel_manager doesn't expose is_connected
        rel_manager.connect(node)

def ingest_doc_graph(docid: str) -> dict:
    """
    Pulls the Cypher rows for a document id (Neo4j property `id`) and upserts:
    - Document (movies.Document with docid)
    - Keyword by name
    - Item by qid (+ label)
    - Class by qid (+ label)
    - Relationships: CONTAINS_KEYWORD, MAPS_TO, INSTANCE_OF, SUBCLASS_OF
    """
    rows, _ = db.cypher_query(CYPHER, {"docid": str(docid)})

    doc = _get_or_create_document(docid)
    stats = {
        "document": docid,
        "keywords_linked": 0,
        "maps_to_linked": 0,
        "instance_of_linked": 0,
        "subclass_of_linked": 0,
        "keywords_seen": set(),
        "items_seen": set(),
        "classes_seen": set(),
    }

    for (n, k, i, c, parent) in rows:
        # n is the Document node from Neo4j (not used directly; we rely on our doc instance)

        # ---- Keyword ----
        kw = None
        if k is not None:
            k_props = dict(k)
            kw = _get_or_create_keyword(k_props.get("name"))
            if kw:
                # Document -[:CONTAINS_KEYWORD]-> Keyword
                _connect_once(doc.keywords, kw)
                stats["keywords_seen"].add(kw.name)
                stats["keywords_linked"] += 1

        # ---- Item (maps_to) ----
        item = None
        if i is not None:
            i_props = dict(i)
            item = _get_or_create_item(
                qid=i_props.get("qid"),
                label=i_props.get("label"),
            )
            if item:
                stats["items_seen"].add(item.qid)
                # Keyword -[:MAPS_TO]-> Item (only if we had a keyword in this row)
                if kw:
                    _connect_once(kw.maps_to, item)
                    stats["maps_to_linked"] += 1

        # ---- Class (instance_of) ----
        if item is not None and c is not None:
            c_props = dict(c)
            klass = _get_or_create_class(
                qid=c_props.get("qid"),
                label=c_props.get("label"),
            )
            if klass:
                stats["classes_seen"].add(klass.qid)
                # Item -[:INSTANCE_OF]-> Class
                _connect_once(item.instance_of, klass)
                stats["instance_of_linked"] += 1

        # ---- SUBCLASS_OF (Item -> parent Item) ----
        if item is not None and parent is not None:
            p_props = dict(parent)
            parent_item = _get_or_create_item(
                qid=p_props.get("qid"),
                label=p_props.get("label"),  # may be None in your sample; ok
            )
            if parent_item:
                # Item -[:SUBCLASS_OF]-> Parent Item
                _connect_once(item.ancestors, parent_item)
                stats["subclass_of_linked"] += 1

    # Make sets JSON-friendly
    stats["keywords_seen"] = sorted(stats["keywords_seen"])
    stats["items_seen"] = sorted(stats["items_seen"])
    stats["classes_seen"] = sorted(stats["classes_seen"])
    return stats
