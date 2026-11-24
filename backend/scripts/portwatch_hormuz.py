"""Fetch Strait of Hormuz daily capacity from IMF PortWatch.

Writes:
  data/portwatch_hormuz.json

    python backend/scripts/portwatch_hormuz.py
    python backend/scripts/portwatch_hormuz.py --refresh
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CACHE_FILE = DATA_DIR / "portwatch_hormuz.json"
CACHE_MAX_AGE_H = 24

BASELINE_START = date(2025, 10, 1)
HORMUZ_ID = "chokepoint6"

ARC = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services"
DAILY = f"{ARC}/Daily_Chokepoints_Data/FeatureServer/0/query"


def get_json(url: str, tries: int = 3) -> dict:
    last: Exception | None = None
    for i in range(tries):
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0 (economic-recovery-dashboard)"})
            with urlopen(req, timeout=90) as response:
                return json.loads(response.read().decode("utf-8"))
        except (URLError, HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"request failed: {last}")


def fetch_all(where: str, out_fields: str, page: int = 500) -> list[dict]:
    out: list[dict] = []
    offset = 0
    while True:
        params = {
            "where": where,
            "outFields": out_fields,
            "f": "json",
            "returnGeometry": "false",
            "resultOffset": offset,
            "resultRecordCount": page,
            "orderByFields": "date ASC",
        }
        data = get_json(DAILY + "?" + urlencode(params))
        if "error" in data:
            raise RuntimeError(f"ArcGIS error: {data['error']}")
        feats = data.get("features", [])
        out.extend(f["attributes"] for f in feats)
        if not feats or not (data.get("exceededTransferLimit") or len(feats) >= page):
            break
        offset += len(feats)
    return out


def fetch_rows(out_fields: str) -> list[dict]:
    """Try date filters that ArcGIS accepts on this layer; fall back to portid-only."""
    y, m = BASELINE_START.year, BASELINE_START.month
    variants = [
        # year/month is the most reliable filter on Daily_Chokepoints_Data.
        f"portid='{HORMUZ_ID}' AND (year > {y} OR (year = {y} AND month >= {m}))",
        f"portid='{HORMUZ_ID}' AND date >= DATE '{BASELINE_START.isoformat()}'",
        f"portid='{HORMUZ_ID}'",
    ]
    last_err: Exception | None = None
    for where in variants:
        try:
            rows = fetch_all(where, out_fields)
            if rows:
                return rows
        except RuntimeError as exc:
            last_err = exc
    if last_err:
        raise last_err
    return []


def to_date(val: object) -> date | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val / 1000, tz=timezone.utc).date()
    s = str(val).strip()
    if s.isdigit():
        return datetime.fromtimestamp(int(s) / 1000, tz=timezone.utc).date()
    return date.fromisoformat(s[:10])


def fetch_hormuz() -> dict:
    print("Fetching Strait of Hormuz from PortWatch ...")
    rows = fetch_rows("date,portid,portname,n_total,capacity")
    daily: dict[str, dict] = {}
    for row in rows:
        day = to_date(row.get("date"))
        if day is None or day < BASELINE_START:
            continue
        daily[day.isoformat()] = {
            "n_total": float(row.get("n_total") or 0),
            "capacity": float(row.get("capacity") or 0),
        }
    if not daily:
        raise RuntimeError("no Strait of Hormuz rows returned")

    cache = {
        "fetched_at": time.time(),
        "portid": HORMUZ_ID,
        "name": "Strait of Hormuz",
        "daily": daily,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache), encoding="utf-8")
    print(f"Saved {len(daily)} days to {CACHE_FILE}")
    return cache


def load_cache() -> dict | None:
    if not CACHE_FILE.exists():
        return None
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def main(refresh: bool = False) -> dict:
    cache = load_cache()
    if cache and not refresh:
        age_h = (time.time() - cache.get("fetched_at", 0)) / 3600
        if age_h < CACHE_MAX_AGE_H:
            print(f"Using cached Hormuz data ({age_h:.1f} h old). Use --refresh to re-download.")
            return cache
    try:
        return fetch_hormuz()
    except Exception as exc:
        if cache:
            print(f"WARNING: download failed ({exc}); using older cache.")
            return cache
        sys.exit(f"\nCould not fetch Strait of Hormuz data: {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch PortWatch Strait of Hormuz data")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    result = main(refresh=args.refresh)
    print(f"Ready: {len(result.get('daily') or [])} daily rows")
