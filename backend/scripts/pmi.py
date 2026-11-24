"""Scrape UAE Manufacturing PMI from Trading Economics news pages.

Appends any new months into data/uae_pmi.csv. Existing months are kept;
conflicting values are reported but not overwritten.
"""

import re
import time
import urllib.robotparser
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://tradingeconomics.com/united-arab-emirates/manufacturing-pmi"
NEWS_PATH = "/united-arab-emirates/manufacturing-pmi/news/"
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DB_PATH = DATA_DIR / "uae_pmi.csv"
DEFAULT_START = "2026-01"
MAX_NEWS_PAGES = 25
DELAY_SECONDS = 3
HEADERS = {"User-Agent": "Mozilla/5.0 (personal research script)"}

MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
MONTH_NUM = {name: index + 1 for index, name in enumerate(MONTHS)}
MONTH_RE = "|".join(MONTHS)
NUM = r"(\d{2}(?:\.\d{1,2})?)"
VALUE_RE = re.compile(
    rf"\b{NUM}\s+(?:points\s+)?in\s+({MONTH_RE})(?:\s+(?:of\s+)?(\d{{4}}))?"
)


def allowed_by_robots(url: str) -> bool:
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url("https://tradingeconomics.com/robots.txt")
    try:
        parser.read()
        return parser.can_fetch(HEADERS["User-Agent"], url)
    except Exception:
        return False


def fetch(url: str) -> str | None:
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        print(f"  ! failed: {url} ({exc})")
        return None


def extract_values(text: str):
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text):
        if "PMI" not in sentence:
            continue
        ref = None
        for value, month_name, year in VALUE_RE.findall(sentence):
            month = MONTH_NUM[month_name]
            number = float(value)
            if not 30 <= number <= 70:
                continue
            if year:
                y = int(year)
                ref = ref or (y, month)
            elif ref:
                y = ref[0] - 1 if month > ref[1] else ref[0]
            else:
                continue
            out.append((pd.Period(year=y, month=month, freq="M"), number))
    return out


def news_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for anchor in soup.find_all("a", href=True):
        if NEWS_PATH in anchor["href"]:
            full = urljoin(BASE_URL, anchor["href"])
            if full not in links:
                links.append(full)
    return links[:MAX_NEWS_PAGES]


def load_db() -> pd.DataFrame:
    if DB_PATH.exists():
        df = pd.read_csv(DB_PATH, dtype={"month": str})
        for col in ("source_url", "retrieved_at"):
            if col not in df:
                df[col] = ""
        return df
    return pd.DataFrame(columns=["month", "pmi", "source_url", "retrieved_at"])


def main(start_month: str = DEFAULT_START) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    start = pd.Period(start_month, freq="M")
    print(f"PMI start_month={start_month}")

    if not allowed_by_robots(BASE_URL):
        raise SystemExit("robots.txt disallows (or could not confirm) access. Stopping.")

    db = load_db()
    known = dict(zip(db["month"], db["pmi"]))
    now = datetime.now(UTC).isoformat(timespec="seconds")

    main_html = fetch(BASE_URL)
    if not main_html:
        raise SystemExit("Could not fetch main page.")

    pages_html = {BASE_URL: main_html}
    for url in news_links(main_html):
        time.sleep(DELAY_SECONDS)
        html = fetch(url)
        if html:
            pages_html[url] = html

    new_rows, conflicts = [], []
    for url, html in pages_html.items():
        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        for period, value in extract_values(text):
            if period < start:
                continue
            key = str(period)
            if key in known:
                if abs(float(known[key]) - value) > 0.05:
                    conflicts.append((key, known[key], value, url))
                continue
            known[key] = value
            new_rows.append(
                {
                    "month": key,
                    "pmi": value,
                    "source_url": url,
                    "retrieved_at": now,
                }
            )

    if new_rows:
        db = pd.concat([db, pd.DataFrame(new_rows)], ignore_index=True)
    db = db.sort_values("month").reset_index(drop=True)
    db.to_csv(DB_PATH, index=False)

    print(f"Added {len(new_rows)} new month(s):")
    for row in new_rows:
        print(f"  {row['month']}: {row['pmi']}")
    for key, old, new, url in conflicts:
        print(f"CONFLICT {key}: stored {old} vs found {new} ({url}). Check manually.")

    if not db.empty:
        expected = pd.period_range(start, pd.Period(db["month"].max(), freq="M"), freq="M")
        missing = [str(period) for period in expected if str(period) not in set(db["month"])]
        if missing:
            print("Gaps in history (add manually to data/uae_pmi.csv):", ", ".join(missing))
    print(f"\n{DB_PATH} now holds {len(db)} months.")


if __name__ == "__main__":
    main()
