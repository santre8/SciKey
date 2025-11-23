# Import necessary libraries
import os
from sqlalchemy import create_engine
import pandas as pd

# ---- Connection config (override with env vars if you like) ----
MYSQL_USER = os.getenv("MYSQL_USER", "citizix_user")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "An0thrS3crt")
MYSQL_DB = os.getenv("MYSQL_DATABASE", "scikey")

# If your Python runs on the host machine:
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "5362"))

# If your Python runs in another container on the same docker-compose network,
# set these env vars instead:
#   MYSQL_HOST=db
#   MYSQL_PORT=3306

DB_URL = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
    f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
)

engine = create_engine(DB_URL, pool_pre_ping=True, future=True)

def get_engine():
    """Devuelve el engine global de SQLAlchemy."""
    return engine

def load_data(df, table_name, if_exists="append"):
    engine = get_engine()

    # If it comes empty, do nothing.
    if df is None or df.empty:
        print(f"[load_data] DataFrame for {table_name} is empty, skipping.")
        return

    # ----------------- DOCUMENTS: avoid duplicate doc_ids -----------------
    if table_name == "documents":
        if "doc_id" in df.columns:
            # Remove duplicates within the batch itself
            df = df.drop_duplicates(subset=["doc_id"])

        with engine.begin() as conn:
            try:
                existing = pd.read_sql("SELECT doc_id FROM documents", conn)
                if not existing.empty:
                    already = set(existing["doc_id"])
                    before = len(df)
                    df = df[~df["doc_id"].isin(already)]
                    after = len(df)
                    print(
                        f"[documents] {before - after} rows skipped "
                        f"(already in DB), {after} new rows to insert."
                    )
            except Exception as e:
                # The first attempt may fail if the table does not exist.
                print(f"[documents] Could not check existing IDs: {e}")

            if df.empty:
                print("[documents] No new documents to insert, skipping.")
                return

            df.to_sql(
                name=table_name,
                con=conn,
                if_exists=if_exists,
                index=False,
                chunksize=1000,
                method="multi"
            )

    # ----------------- ORGANISMS: avoid duplicate hal_structure_id -------
    elif table_name == "organisms":
        if "hal_structure_id" in df.columns:
            df = df.drop_duplicates(subset=["hal_structure_id"])

        with engine.begin() as conn:
            try:
                existing = pd.read_sql(
                    "SELECT hal_structure_id FROM organisms",
                    conn
                )
                if not existing.empty:
                    already = set(existing["hal_structure_id"])
                    before = len(df)
                    df = df[~df["hal_structure_id"].isin(already)]
                    after = len(df)
                    print(
                        f"[organisms] {before - after} rows skipped "
                        f"(already in DB), {after} new rows to insert."
                    )
            except Exception as e:
                print(f"[organisms] Could not check existing IDs: {e}")

            if df.empty:
                print("[organisms] No new organisms to insert, skipping.")
                return

            df.to_sql(
                name=table_name,
                con=conn,
                if_exists=if_exists,
                index=False,
                chunksize=1000,
                method="multi"
            )

    # ----------------- REST OF TABLES ------------------------------------
    else:
        with engine.begin() as conn:
            df.to_sql(
                name=table_name,
                con=conn,
                if_exists=if_exists,
                index=False,
                chunksize=1000,
                method="multi"
            )

    print(f"Data successfully written to MySQL: {table_name}")

