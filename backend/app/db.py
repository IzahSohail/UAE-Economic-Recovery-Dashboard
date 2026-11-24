"""Read access to the data: Supabase Postgres if DATABASE_URL is set, else data/*.csv."""

import os
import re
import sqlite3
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL")


def _load_csvs() -> sqlite3.Connection:
    """In-memory copy of data/*.csv with the same table and column names as Supabase."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    for path in (ROOT / "data").glob("*.csv"):
        df = pd.read_csv(path)
        df.columns = [re.sub(r"[^a-z0-9_]", "_", c.lower()) for c in df.columns]
        df.to_sql(path.stem, conn, index=False)
    return conn


# Without Supabase credentials the API serves the CSVs the scripts wrote to data/.
LOCAL_DB = None if DATABASE_URL else _load_csvs()


def fetch_all(query: str) -> list[dict]:
    if LOCAL_DB is not None:
        return [dict(row) for row in LOCAL_DB.execute(query)]
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        return conn.execute(query).fetchall()
