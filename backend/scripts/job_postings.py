"""Collect monthly UAE job-posting counts from jobdatafeeds.com.

Writes data/job_postings_monthly.csv (Jan 2026 onwards by default).
"""

from io import StringIO
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

URL = "https://jobdatafeeds.com/data/countries/ae"
DEFAULT_START = "2026-01"
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
OUT_DATA = DATA_DIR / "job_postings_monthly.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_html(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def parse_monthly_table(html: str) -> pd.DataFrame:
    soup = BeautifulSoup(html, "html.parser")

    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if "month" in headers and any("new jobs" in header for header in headers):
            df = pd.read_html(StringIO(str(table)))[0]
            break
    else:
        raise RuntimeError(
            "Monthly table not found. The page layout may have changed "
            "or the content is rendered with JavaScript."
        )

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    for col in ("new_jobs", "sources"):
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(",", "", regex=False), errors="coerce"
        ).astype("Int64")

    df["month"] = df["month"].astype(str).str.strip()
    return df


def main(start_month: str = DEFAULT_START) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Job postings start_month={start_month}")

    try:
        html = fetch_html(URL)
        df = parse_monthly_table(html)
    except Exception as exc:
        raise SystemExit(f"Error: {exc}") from exc

    df = df[df["month"] >= start_month].sort_values("month").reset_index(drop=True)
    df.insert(0, "country_code", "AE")

    df.to_csv(OUT_DATA, index=False)
    print(f"Saved {len(df)} rows to {OUT_DATA}")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
