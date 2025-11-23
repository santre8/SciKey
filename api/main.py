import os, re, time, requests, pandas as pd
from urllib.parse import urlencode
from pathlib import Path

from api.apimodule import NEED_N, choose_url, consolidate_domains, consolidate_keywords, \
    fallback_text_match_for_discipline, fetch_page, hal_record_url, map_codes_to_discipline, savetojson

NEED_N = 20
FIELD ="Chemical Engineering"
FILE ="upec_chemical_20_n.json"

records, cursor = [], "*"

if __name__ == '__main__':
    """call api module"""
    # Crawl
    
    while len(records) < NEED_N:
        data = fetch_page(cursor)
        docs = data.get("response", {}).get("docs", [])
        if not docs: #si nohay documentos no hago nada
            break

        for d in docs: # cargo documentos del api
            # title/abstract/halId sometimes come as single-item lists
            for k in ["title_s", "abstract_s", "halId_s"]:
                v = d.get(k)
                if isinstance(v, list) and v:
                    d[k] = v[0]

            # consolidate metadata
            d["keywords_joined"] = consolidate_keywords(d)
            labels, codes = consolidate_domains(d)
            d["domain_labels"] = "; ".join(labels) if labels else ""
            d["domain_codes"] = "; ".join(codes) if codes else ""

            # build URL
            d["record_url"] = hal_record_url(d.get("halId_s"))
            d["url_primary"] = choose_url(d.get("linkExtUrl_s"), d.get("record_url"), d.get("files_s"))

            # must have keywords
            if not d["keywords_joined"]:
                continue

            # infer discipline (codes first, then text fallback)
            discipline = map_codes_to_discipline(codes, labels)
            if discipline is None:
                discipline = fallback_text_match_for_discipline(
                    [d.get("title_s"), d.get("abstract_s"), d.get("keywords_joined")]
                )
            if discipline is None:
                continue  # not one of your 5 buckets

            if discipline != FIELD:
                 continue

            d["discipline"] = discipline

            # keep only requested output columns
            records.append({
                # ---- DOCUMENT ----
                "docid": d.get("docid"),
                "halId_s": d.get("halId_s"),
                "title_s": d.get("title_s"),
                "abstract_s": d.get("abstract_s"),
                "domain_codes": d.get("domain_codes"),
                "discipline": d.get("discipline"),
                "url_primary": d.get("url_primary"),

                # ---- AUTHORS ----
                "authFirstName_s": d.get("authFirstName_s"),
                "authLastName_s": d.get("authLastName_s"),
                "authQuality_s": d.get("authQuality_s"),
                "authFullNameIdFormPerson_fs": d.get("authFullNameIdFormPerson_fs"),
                "authIdHasStructure_fs": d.get("authIdHasStructure_fs"),

                # ---- ORGANISMS ----
                "structIdName_fs": d.get("structIdName_fs"),
                "structName_s": d.get("structName_s"),

                # ---- JOURNAL ----
                "journalIssn_s": d.get("journalIssn_s"),
                "journalTitle_s": d.get("journalTitle_s"),

                # ---- IDENTIFIERS ----
                "doiId_s": d.get("doiId_s"),
                "isbn_id": d.get("isbn_id"),

                # ---- KEYWORDS ----
                "keyword_s": d.get("keyword_s"),
            })

            if len(records) >= NEED_N:
                break

        next_c = data.get("nextCursorMark")
        if not next_c or next_c == cursor:
            break
        cursor = next_c
        time.sleep(0.12)

    # ---------------------------------------------
    # ✅ Save results inside /api/data/
    # ---------------------------------------------
    df_sample = pd.DataFrame.from_records(records)
    print("Rows in sample:", len(df_sample))
    df_sample = df_sample.drop(columns=["domain_labels"], errors="ignore")

    # Define /api/data/ directory and file names
    BASE_DIR = Path(__file__).resolve().parent / "data"
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    json_path = BASE_DIR / FILE
   
    # Save to JSON (via your apimodule function)
    savetojson(df_sample, json_path.name)  # ✅ will save to /api/data/

  