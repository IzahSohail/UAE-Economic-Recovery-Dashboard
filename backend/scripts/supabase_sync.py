import os
import re
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# csv stem -> unique key columns (sanitized / lowercase names as stored in Postgres)
TABLES: dict[str, list[str]] = {
    "gdp_quarterly": [
        "ref_area",
        "freq",
        "unit_measure",
        "source_detail",
        "measure",
        "quarter",
        "qgdp_sys",
        "qgdp_unit",
        "time_period",
    ],
    "gdp_metadata_columns": ["column_id"],
    "trade_sect_mth": [
        "ref_area",
        "freq",
        "unit_measure",
        "source_detail",
        "measure",
        "trade_type",
        "hs_section",
        "hs_chapter",
        "country",
        "time_period",
    ],
    "metadata_columns": ["column_id"],
    "cpi_monthly": [
        "time_period",
        "measure",
        "unit_measure",
        "ref_area",
        "freq",
        "cpi_div",
        "source_detail",
    ],
    "cpi_metadata_columns": ["column_id"],
    "economic_licenses": ["emirate", "indicator_id", "period_start"],
    "employment_growth": ["emirate", "indicator_id", "gender", "period_start"],
    "uae_pmi": ["month"],
    "job_postings_monthly": ["country_code", "month"],
    "oil_production_monthly": ["period"],
}


def _sanitize(name: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", name.lower())


def _pg_type(dtype) -> str:
    if pd.api.types.is_float_dtype(dtype):
        return "double precision"
    if pd.api.types.is_integer_dtype(dtype):
        return "bigint"
    return "text"


def _table_exists(conn: psycopg.Connection, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (table,))
        return cur.fetchone()[0] is not None


def _count(conn: psycopg.Connection, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f'SELECT count(*) FROM "{table}"')
        return cur.fetchone()[0]


def ensure_table(
    conn: psycopg.Connection, table: str, df: pd.DataFrame, key_columns: list[str]
) -> None:
    columns_sql = ", ".join(f'"{_sanitize(c)}" {_pg_type(df[c].dtype)}' for c in df.columns)
    key_sql = ", ".join(f'"{c}"' for c in key_columns)

    with conn.cursor() as cur:
        if not _table_exists(conn, table):
            cur.execute(
                f'CREATE TABLE "{table}" ('
                f"{columns_sql}, "
                f'CONSTRAINT "{table}_unique_key" UNIQUE ({key_sql})'
                ")"
            )
            conn.commit()
            return

        # Existing table: fix the unique key and remove any duplicates first.
        cur.execute(f'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "{table}_unique_key"')
        same_key = " AND ".join(
            f'(a."{c}" IS NOT DISTINCT FROM b."{c}")' for c in key_columns
        )
        cur.execute(
            f'DELETE FROM "{table}" a USING "{table}" b '
            f"WHERE a.ctid < b.ctid AND {same_key}"
        )
        deleted = cur.rowcount
        cur.execute(
            f'ALTER TABLE "{table}" ADD CONSTRAINT "{table}_unique_key" UNIQUE ({key_sql})'
        )
    conn.commit()
    if deleted:
        print(f'  removed {deleted} duplicate rows from "{table}"')


def upsert_dataframe(conn: psycopg.Connection, table: str, df: pd.DataFrame) -> None:
    columns = [_sanitize(c) for c in df.columns]
    col_sql = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    rows = [tuple(None if pd.isna(v) else v for v in row) for row in df.itertuples(index=False)]

    with conn.cursor() as cur:
        cur.executemany(
            f'INSERT INTO "{table}" ({col_sql}) VALUES ({placeholders}) '
            f'ON CONFLICT ON CONSTRAINT "{table}_unique_key" DO NOTHING',
            rows,
        )
    conn.commit()


def sync_csv(conn: psycopg.Connection, csv_stem: str, key_columns: list[str]) -> None:
    csv_path = DATA_DIR / f"{csv_stem}.csv"
    if not csv_path.exists():
        print(f"Skipping {csv_stem}: {csv_path} not found")
        return

    df = pd.read_csv(csv_path)
    # CSV headers are uppercase; keys are lowercase Postgres names.
    df.columns = [_sanitize(c) for c in df.columns]
    table = _sanitize(csv_stem)

    ensure_table(conn, table, df, key_columns)
    before = _count(conn, table)
    upsert_dataframe(conn, table, df)
    after = _count(conn, table)

    print(
        f'{csv_path.name}: {len(df)} rows read, {after - before} new rows inserted into "{table}"'
    )


def latest_period(conn: psycopg.Connection, table: str, expression: str) -> str | None:
    """Return the latest period already stored, or None if the table is empty/missing."""
    if not _table_exists(conn, table):
        return None
    with conn.cursor() as cur:
        cur.execute(f'SELECT max({expression}) FROM "{table}"')
        value = cur.fetchone()[0]
    return str(value) if value is not None else None


def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    with psycopg.connect(database_url) as conn:
        for csv_stem, key_columns in TABLES.items():
            sync_csv(conn, csv_stem, key_columns)


if __name__ == "__main__":
    main()
