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
        rel_manager.connect(node)

def _add_node(nodes_dict: dict, node_id: str, label: str, title: str | None = None, extra: dict | None = None):
    """Idempotente: agrega si no existe."""
    if node_id is None:
        return
    if node_id not in nodes_dict:
        payload = {
            "id": node_id,
            "label": label,     # usado por la clase CSS en index.html
            "title": title or node_id,  # tooltip en D3
        }
        if extra:
            payload.update(extra)
        nodes_dict[node_id] = payload

def ingest_doc_graph(docid: str) -> dict:
    """
    Lee el subgrafo del Document(id=$docid), upserta en Django/Neomodel
    y construye el JSON de D3: {"nodes": [...], "links": [...], "stats": {...}}.
    """
    rows, _ = db.cypher_query(CYPHER, {"docid": str(docid)})

    # Upsert mínimo del Document propio (para admin / queries via neomodel)
    doc = _get_or_create_document(docid)

    # Acumuladores para D3
    nodes = {}
    links = []

    # Stats útiles para debug
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

    # Nodo raíz: Document
    _add_node(nodes, docid, "Document", title=f"Document {docid}")

    for (n, k, i, c, parent) in rows:
        # ---- Keyword ----
        kw_id = None
        if k is not None:
            k_props = dict(k)
            kw_name = k_props.get("name")
            kw = _get_or_create_keyword(kw_name)
            if kw:
                kw_id = kw.name
                _add_node(nodes, kw_id, "Keyword", title=f"Keyword: {kw_id}")
                # link Document -> Keyword
                links.append({"source": docid, "target": kw_id, "type": "CONTAINS_KEYWORD"})
                _connect_once(doc.keywords, kw)
                stats["keywords_linked"] += 1
                stats["keywords_seen"].add(kw_id)

        # ---- Item (MAPS_TO) ----
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
                    title=f"Item {item.qid} ({item.label})" if item.label else f"Item {item.qid}",
                    extra={"caption": item.label or item.qid},
                )
                stats["items_seen"].add(item.qid)
                if kw_id:
                    links.append({"source": kw_id, "target": item.qid, "type": "MAPS_TO"})
                    _connect_once(Keyword.nodes.get(name=kw_id).maps_to, item)
                    stats["maps_to_linked"] += 1

        # ---- Class (INSTANCE_OF) ----
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
                    title=f"Class {klass.qid} ({klass.label})" if klass.label else f"Class {klass.qid}",
                    extra={"caption": klass.label or klass.qid},
                )
                links.append({"source": item_id, "target": klass.qid, "type": "INSTANCE_OF"})
                _connect_once(Item.nodes.get(qid=item_id).instance_of, klass)
                stats["classes_seen"].add(klass.qid)
                stats["instance_of_linked"] += 1

        # ---- SUBCLASS_OF (Item -> parent Item) ----
        if item_id and parent is not None:
            p_props = dict(parent)
            parent_qid = p_props.get("qid")
            parent_label = p_props.get("label")
            parent_item = _get_or_create_item(parent_qid, label=parent_label)
            if parent_item:
                _add_node(
                    nodes,
                    parent_item.qid,
                    "Item",
                    title=f"Item {parent_item.qid} ({parent_item.label})" if parent_item.label else f"Item {parent_item.qid}",
                    extra={"caption": parent_item.label or parent_item.qid},
                )
                links.append({"source": item_id, "target": parent_item.qid, "type": "SUBCLASS_OF"})
                _connect_once(Item.nodes.get(qid=item_id).ancestors, parent_item)
                stats["subclass_of_linked"] += 1

    # sets -> listas para JSON
    stats["keywords_seen"] = sorted(stats["keywords_seen"])
    stats["items_seen"] = sorted(stats["items_seen"])
    stats["classes_seen"] = sorted(stats["classes_seen"])

    return {
        "nodes": list(nodes.values()),
        "links": links,
        "stats": stats,
    }
