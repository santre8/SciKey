# create a command-line runnable pipeline
# from etl.extract import extract_data
# from etl.transform import clean_data, transform_data
# import etl.load as load

import yaml
import os
import time
import pandas as pd
from sqlalchemy import create_engine

# import pipeline configuration
# with open('config.yaml', 'r') as file:
#     config_data = yaml.safe_load(file)


# ====== Normalizers to your schema ======
from pipeline.load import load_data
import re

def clean_structure_name(text):

    if not isinstance(text, str):
        return text
    # Elimina '12345_FacetSep_'
    cleaned = re.sub(r"^\d+_FacetSep_", "", text)
    return cleaned.strip()

def normalize_documents(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame({
        "doc_id": pd.to_numeric(df.get("docid"), errors="coerce"),
        "halId_s": df.get("halId_s"),
        "title": df.get("title_s"),
        "abstract": df.get("abstract_s"),
        "discipline": df.get("discipline"),
        "domain_codes": df.get("domain_codes"),
        "url_primary": df.get("url_primary"),
    })
    out = out.dropna(subset=["doc_id"])
    return out.drop_duplicates(subset=["doc_id"])

def _as_list(v):
    if isinstance(v, list):
        return v
    if pd.isna(v):
        return []
    return [v]

def normalize_authors(df: pd.DataFrame) -> pd.DataFrame:
    base_doc = pd.to_numeric(df.get("docid"), errors="coerce")

    fn = df.get("authFirstName_s").apply(_as_list)
    ln = df.get("authLastName_s").apply(_as_list)
    qual = df.get("authQuality_s").apply(_as_list)

    rows = []
    for doc, fns, lns, quals in zip(base_doc, fn, ln, qual):
        if pd.isna(doc):
            continue
        n = max(len(fns), len(lns), len(quals))
        if n == 0:
            continue

        fns += [""] * (n - len(fns))
        lns += [""] * (n - len(lns))
        quals += [""] * (n - len(quals))

        for i in range(n):
            rows.append({
                "doc_id": int(doc),
                "author_index": i+1,
                "authFirstName_s": fns[i] or None,
                "authLastName_s": lns[i] or None,
                "authQuality_s": quals[i] or None,
            })

    return pd.DataFrame(rows)


def normalize_keywords(df: pd.DataFrame) -> pd.DataFrame:
    base_doc = pd.to_numeric(df.get("docid"), errors="coerce")
    kw = df.get("keyword_s").apply(_as_list)

    rows = []
    for doc, kws in zip(base_doc, kw):
        if pd.isna(doc):
            continue
        for k in kws:
            if not k:
                continue
            rows.append({
                "doc_id": int(doc),
                "keyword_s": k
            })
    return pd.DataFrame(rows)

def normalize_identifiers(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame({
        "doc_id": pd.to_numeric(df.get("docid"), errors="coerce"),
        "doiId_s": df.get("doiId_s"),
        "halId_s": df.get("halId_s"),
        "isbn": df.get("isbn_id"),   
    })
    out = out.dropna(subset=["doc_id"])
    return out.drop_duplicates(subset=["doc_id", "doiId_s", "isbn"])

def normalize_organisms(df: pd.DataFrame) -> pd.DataFrame:

    col = df.get("structIdName_fs")

    
    if col is None:
        return pd.DataFrame(columns=["hal_structure_id", "structIdName_fs"])

    rows = []

    
    for items in col.apply(_as_list):
        for item in items:
            if not isinstance(item, str):
                continue

            # item: '390741_FacetSep_TCM'
            parts = item.split("_", 1)
            try:
                struct_id = int(parts[0])   # 390741
            except ValueError:
                continue

            
            clean_name = clean_structure_name(item)  

            rows.append({
                "hal_structure_id": struct_id,
                "structIdName_fs": clean_name
            })

    if not rows:
        return pd.DataFrame(columns=["hal_structure_id", "structIdName_fs"])

    out = pd.DataFrame(rows)
    
    return out.drop_duplicates(subset=["hal_structure_id"])

def normalize_document_organisms(df: pd.DataFrame) -> pd.DataFrame:
    base_doc = pd.to_numeric(df.get("docid"), errors="coerce")
    col = df.get("structIdName_fs")

    def to_list(v):
        if isinstance(v, list):
            return v
        if pd.isna(v):
            return []
        return [v]

    rows = []
    for doc, items in zip(base_doc, col.apply(to_list)):
        if pd.isna(doc):
            continue
        for item in items:
            if not isinstance(item, str):
                continue
            parts = item.split("_", 1)
            try:
                struct_id = int(parts[0])
            except ValueError:
                continue
            rows.append({
                "doc_id": int(doc),
                "hal_structure_id": struct_id
            })

    out = pd.DataFrame(rows)
    return out.drop_duplicates()

def normalize_journals(df: pd.DataFrame) -> pd.DataFrame:

    if "journalIssn_s" not in df.columns and "journalTitle_s" not in df.columns:
        
        return pd.DataFrame(columns=["doc_id", "journalIssn_s", "journalTitle_s"])

    jdf = df[["docid", "journalIssn_s", "journalTitle_s"]].copy()

    
    jdf = jdf.rename(columns={"docid": "doc_id"})

    
    jdf = jdf.dropna(subset=["journalIssn_s", "journalTitle_s"], how="all")

    return jdf

def build_author_index_map(df: pd.DataFrame) -> dict:

    mapping = {}

    col = df.get("authFullNameIdFormPerson_fs")
    if col is None:
        return mapping

    for doc_id, items in zip(df["docid"], col.fillna("").apply(_as_list)):
        for idx, entry in enumerate(items, start=1):
            
            if "_FacetSep_" not in entry:
                continue
            full_name, person_id = entry.split("_FacetSep_", 1)
            person_id = person_id.strip()
            mapping[(int(doc_id), person_id)] = idx

    return mapping

def normalize_author_organisms(df: pd.DataFrame) -> pd.DataFrame:

    col = df.get("authIdHasStructure_fs")
    if col is None:
        return pd.DataFrame(columns=["doc_id", "author_index", "hal_structure_id"])

    
    idx_map = build_author_index_map(df)

    rows = []

    for doc_id, items in zip(df["docid"], col.fillna("").apply(_as_list)):
        doc_id = int(doc_id)
        for entry in items:
            if not isinstance(entry, str):
                continue

            
            if "_JoinSep_" not in entry:
                continue

            left, right = entry.split("_JoinSep_", 1)

            
            person_part = left.split("_FacetSep_", 1)[0]  
            person_id = person_part.strip()

            
            try:
                struct_id_str = right.split("_", 1)[0]
                hal_structure_id = int(struct_id_str)
            except Exception:
                continue

            author_index = idx_map.get((doc_id, person_id))
            if author_index is None:
                
                continue

            rows.append({
                "doc_id": doc_id,
                "author_index": author_index,
                "hal_structure_id": hal_structure_id,
            })

    if not rows:
        return pd.DataFrame(columns=["doc_id", "author_index", "hal_structure_id"])

    ao = pd.DataFrame(rows).drop_duplicates()
    return ao


# ====== Your crawler glue: build df_sample (using your existing code) ======

def crawl_to_df_sample():
    # ---- paste your crawling loop here ----
    # For demo, we assume you already produced df_sample
    # from your script with `records` and `pd.DataFrame.from_records(records)`
    # If you're reading your sample JSON file:
    # df_sample = pd.read_json("sample.json")
    raise NotImplementedError("Replace with your existing crawl code that returns df_sample")

def run_pipeline(df_sample: pd.DataFrame):
    df_sample = df_sample.copy()

    docs_df = normalize_documents(df_sample)
    auth_df = normalize_authors(df_sample)
    kw_df = normalize_keywords(df_sample)
    id_df = normalize_identifiers(df_sample)
    org_df = normalize_organisms(df_sample)
    doc_org_df = normalize_document_organisms(df_sample)
    journals_df = normalize_journals(df_sample)
    author_org_df = normalize_author_organisms(df_sample)
    doc_org_df = normalize_document_organisms(df_sample)
    
    load_data(docs_df, "documents", if_exists="append")
    load_data(auth_df, "authors", if_exists="append")
    load_data(kw_df, "keywords", if_exists="append")
    load_data(id_df, "identifiers", if_exists="append")
    load_data(org_df, "organisms", if_exists="append")
    load_data(doc_org_df, "document_organisms", if_exists="append")
    load_data(journals_df, "journals", if_exists="append")
    load_data(author_org_df, "author_organisms", if_exists="append")
    load_data(doc_org_df, "document_organisms", if_exists="append")

if __name__ == "__main__":
    # If you’re using your in-memory 'records' from the code you pasted:
    # Just import them or read from the JSON you saved with savetojson(...)
    # Example using the JSON you showed in the message:
    import json
    data_path= os.path.join(os.path.dirname(__file__), '..', 'api', 'data','upec_civil_20_n.json')
    #upec_chemical_20_n.json
    #upec_computer_20_n.json
    #upec_political_20_n.json
    #upec_marketing_20_n.json
    #upec_civil_20_n.json
    with open(data_path, "r", encoding="utf-8") as f:
        sample_list = json.load(f)
    df_sample = pd.DataFrame(sample_list)

    print("Rows in sample:", len(df_sample))
    run_pipeline(df_sample)