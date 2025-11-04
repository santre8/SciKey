from typing import Dict, List, Optional, Tuple
import requests
from . import config
from .utils import normalize_kw, chunked, backoff_sleep

def _get(params: Dict, sleep_sec: float = 0.1) -> Dict:
    params = {**params, "format": "json"}
    for attempt in range(5):
        try:
            r = requests.get(config.WIKIDATA_API, params=params, headers=config.HEADERS, timeout=20)
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                raise RuntimeError(data["error"])
            # ritmo para no abusar del endpoint
            import time; time.sleep(sleep_sec)
            return data
        except Exception:
            if attempt == 4:
                raise
            backoff_sleep(attempt)
    return {}

def wbsearchentities(search: str, language: str = "en", limit: int = config.SEARCH_LIMIT) -> List[Dict]:
    search = normalize_kw(search)
    return _get({
        "action": "wbsearchentities",
        "search": search,
        "language": language,
        "uselang": language,
        "type": "item",
        "limit": limit,
        "strictlanguage": 0,
    }).get("search", [])

def wbsearch_label_only(search: str, language: str = "en", limit: int = config.SEARCH_LIMIT) -> List[Dict]:
    search = normalize_kw(search)
    return _get({
        "action": "wbsearchentities",
        "search": f"label:{search}",
        "language": language,
        "uselang": language,
        "type": "item",
        "limit": limit,
        "strictlanguage": 0,
    }).get("search", [])

def wbgetentities(ids: List[str], languages: List[str] = None) -> Dict:
    from .utils import chunked
    languages = languages or config.LANGS
    combined = {}
    for batch in chunked(list(ids), 50):
        data = _get({
            "action": "wbgetentities",
            "ids": "|".join(batch),
            "props": "labels|descriptions|aliases|claims",
            "languages": "|".join(languages),
            "languagefallback": 1,
        }, sleep_sec=0.05)
        combined.update(data.get("entities", {}))
    return combined

def _claim_ids(entity: Dict, pid: str) -> List[str]:
    out = []
    for cl in entity.get("claims", {}).get(pid, []):
        dv = cl.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        if isinstance(dv, dict) and dv.get("id"):
            out.append(dv["id"])
    return out

def get_p31_ids(entity: Dict) -> set:
    return set(_claim_ids(entity, config.P_INSTANCE_OF))

def expand_p279_paths(start_parents: List[str], max_levels: int, languages: List[str]) -> List[List[str]]:
    if not start_parents:
        return []
    paths = []
    frontier = [[p] for p in start_parents]
    for _ in range(max_levels - 1):
        new_frontier = []
        for path in frontier:
            current = path[-1]
            ent = wbgetentities([current], languages).get(current, {})
            parents = _claim_ids(ent, config.P_SUBCLASS_OF)
            if not parents:
                paths.append(path)
                continue
            for par in parents:
                new_frontier.append(path + [par])
        frontier = new_frontier or frontier
    for p in frontier:
        if p not in paths:
            paths.append(p)
    return paths

def extract_bnf_id(entity: Dict) -> Optional[str]:
    for cl in entity.get("claims", {}).get(config.P_BNF_ID, []):
        dv = cl.get("mainsnak", {}).get("datavalue", {})
        if dv.get("value"):
            return str(dv["value"])
    return None

def extract_label(entity: Dict, languages: List[str] = None) -> str:
    languages = languages or config.LANGS
    for lg in languages:
        if "labels" in entity and lg in entity["labels"]:
            return entity["labels"][lg]["value"]
    labs = entity.get("labels", {})
    if labs:
        return list(labs.values())[0]["value"]
    return ""

def is_disambiguation(qid: str, entity: Dict) -> bool:
    for cl in entity.get("claims", {}).get(config.P_INSTANCE_OF, []):
        v = cl.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        if v.get("id") == config.Q_DISAMBIGUATION:
            return True
    return False
