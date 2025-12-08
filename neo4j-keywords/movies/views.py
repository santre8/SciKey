from django.http import JsonResponse
from django.shortcuts import render
from .models import Document
from .services import ingest_doc_graph
from neomodel import db
from .mysql_models import (
    Documents,
    Keywords as MysqlKeywords,
    Keywords,
    Authors,
    Journals,
    DocumentOrganisms,
    Organisms,
)
from django.views.decorators.http import require_GET


def home(request):

    keywords = (
        MysqlKeywords.objects
        .exclude(keyword_s__isnull=True)
        .exclude(keyword_s__exact="")
        .values_list("keyword_s", flat=True)
        .distinct()[:10]
    )


    doc_count = Documents.objects.count()


    rows, _ = db.cypher_query("""
        MATCH (k:Keyword)-[:MAPS_TO]->(:Item)
        RETURN count(DISTINCT k) AS kw_count
    """)
    mapped_kw_count = rows[0][0] if rows and rows[0] else 0

    context = {
        "keywords": keywords,
        "doc_count": doc_count,
        "mapped_kw_count": mapped_kw_count,
    }
    return render(request, "home.html", context)


def movies_index(request):
    documents = Document.nodes.all()
    return render(request, "index.html", {"movies": documents})

def graph(request):
    docid = request.GET.get("docid", "1006198")
    keyword = request.GET.get("kw")
    graph_payload = ingest_doc_graph(docid)
    return JsonResponse(graph_payload)

def search(request):

    q = request.GET.get("q", "").strip()
    if not q:
        return JsonResponse([], safe=False)


    doc_ids = (
        Keywords.objects
        .filter(keyword_s__icontains=q)
        .values_list("doc_id", flat=True)
        .distinct()
    )

    if not doc_ids:
        return JsonResponse([], safe=False)


    docs = (
        Documents.objects
        .filter(doc_id__in=list(doc_ids))
        .values("doc_id", "title", "discipline")
    )

    results = [
        {
            "id": str(d["doc_id"]),
            "title": d["title"] or "",
            "discipline": d["discipline"] or "",
        }
        for d in docs
    ]

    return JsonResponse(results, safe=False)





def movie_by_title(request, title):
    pass

def mysql_documents_list(request):

    docs = Documents.objects.all().order_by("doc_id")[:200] 

    return render(request, "mysql_documents_list.html", {
        "docs": docs,
    })

def combined_documents(request):

    graph_docs = list(Document.nodes.all())
    mysql_docs = {
        str(d.doc_id): d
        for d in Documents.objects.all()
    }

    items = []
    for g in graph_docs:
        extra = mysql_docs.get(g.docid)
        items.append({
            "graph": g,
            "sql": extra,
        })

    return render(request, "combined_documents.html", {
        "items": items,
    })

@require_GET
def doc_details(request):

    docid = request.GET.get("docid")
    if not docid:
        return JsonResponse({"error": "missing docid"}, status=400)

    try:
        doc_id = int(docid)
    except ValueError:
        return JsonResponse({"error": "invalid docid"}, status=400)

    doc = Documents.objects.filter(doc_id=doc_id).values(
        "doc_id", "title", "discipline", "url_primary"
    ).first()

    if not doc:
        return JsonResponse({"error": "not found"}, status=404)

    # Autores
    authors_qs = Authors.objects.filter(doc_id=doc_id).values(
        "authfirstname_s", "authlastname_s"
    )
    authors = []
    for a in authors_qs:
        name = f"{a['authfirstname_s'] or ''} {a['authlastname_s'] or ''}".strip()
        if name:
            authors.append(name)

 
    journal = Journals.objects.filter(doc_id=doc_id).values(
        "journaltitle_s", "journalissn_s"
    ).first()


    org_ids = DocumentOrganisms.objects.filter(doc_id=doc_id).values_list(
        "hal_structure_id", flat=True
    )
    organisms = list(
        Organisms.objects.filter(hal_structure_id__in=list(org_ids))
        .values_list("structidname_fs", flat=True)
    )

    # Keywords
    keywords = list(
        Keywords.objects.filter(doc_id=doc_id)
        .exclude(keyword_s__isnull=True)
        .exclude(keyword_s__exact="")
        .values_list("keyword_s", flat=True)
    )

    payload = {
        "doc_id": doc["doc_id"],
        "title": doc["title"] or "",
        "discipline": doc["discipline"] or "",
        "url_primary": doc["url_primary"] or "",
        "authors": authors,
        "journal": {
            "title": journal["journaltitle_s"] if journal else "",
            "issn": journal["journalissn_s"] if journal else "",
        },
        "organisms": organisms,
        "keywords": keywords,
    }
    return JsonResponse(payload)