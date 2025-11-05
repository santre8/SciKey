from django.http import JsonResponse
from django.shortcuts import render
from .models import Document
from .services import ingest_doc_graph

def movies_index(request):
    documents = Document.nodes.all()
    return render(request, "index.html", {"movies": documents})


def graph(request):
    docid = request.GET.get("docid", "1006198")
    stats = ingest_doc_graph(docid)
    return JsonResponse(stats)



def search(request):
    # pass
    try:
        q = request.GET["q"]
    except KeyError:
        return JsonResponse([])

    documents = documents = Document.nodes.filter(docid__icontains=q)
    return JsonResponse(
        [
            {
                "id": doc.docid,
             
            }
            for doc in documents
        ],
        safe=False,
    )


# def serialize_cast(person, job, rel=None):
#     return {
#         "id": person.element_id,
#         "name": person.name,
#         "job": job,
#         "role": rel.roles if rel else None,
#     }


def movie_by_title(request, title):
    pass
#     movie = Movie.nodes.get(title=title)
#     cast = []

#     for person in movie.directors:
#         cast.append(serialize_cast(person, "directed"))

#     for person in movie.writters:
#         cast.append(serialize_cast(person, "wrote"))

#     for person in movie.producers:
#         cast.append(serialize_cast(person, "produced"))

#     for person in movie.reviewers:
#         cast.append(serialize_cast(person, "reviewed"))

#     for person in movie.actors:
#         rel = movie.actors.relationship(person)
#         cast.append(serialize_cast(person, "acted", rel))

#     return JsonResponse(
#         {
#             "id": movie.element_id,
#             "title": movie.title,
#             "tagline": movie.tagline,
#             "released": movie.released,
#             "label": "movie",
#             "cast": cast,
#         }
#     )
