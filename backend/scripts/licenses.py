"""Fetch Abu Dhabi quarterly economic license counts from SCAD.

Outputs data/economic_licenses.csv with one row per indicator per quarter.
Unlike the FCSC scrapers this API is reachable with plain HTTP (no Playwright).
"""

import re
import sys
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests

BASE_URL = "https://scad.gov.ae/o/communication"
CATEGORY_ID = "3294941"
EMIRATE = "Abu Dhabi"
DEFAULT_FROM_YEAR = 2025

TARGETS = {
    "New Economic Licenses (Quarterly)": "total number of new economic licenses",
    "Renewed Economic Licenses (Quarterly)": "total number of renewed economic licenses",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://scad.gov.ae/",
}

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
OUT_DATA = DATA_DIR / "economic_licenses.csv"


def api_url(inner: str) -> str:
    return f"{BASE_URL}?url={quote(inner, safe='')}"


def get_json(session: requests.Session, inner: str):
    resp = session.get(api_url(inner), headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def iter_dicts(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from iter_dicts(value)
    elif isinstance(node, list):
        for item in node:
            yield from iter_dicts(item)


def iter_record_lists(node, path="$"):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from iter_record_lists(value, f"{path}.{key}")
    elif isinstance(node, list):
        if len(node) >= 2 and all(isinstance(item, dict) for item in node):
            yield path, node
        for index, value in enumerate(node):
            if isinstance(value, (dict, list)):
                yield from iter_record_lists(value, f"{path}[{index}]")


def match_target(record):
    for value in record.values():
        if isinstance(value, str):
            low = value.lower()
            for label, needle in TARGETS.items():
                if needle in low:
                    return label
    return None


def find_ids(session: requests.Session) -> dict[str, object]:
    inner = (
        "Statistics/GetClickhouseKeyStatisticsIndicatorsOverview"
        f"?CategoryID={CATEGORY_ID}&PageNumber=1&PageSize=100&lang=EN"
    )
    data = get_json(session, inner)
    found: dict[str, object] = {}
    for record in iter_dicts(data):
        label = match_target(record)
        if not label or label in found:
            continue
        candidate = None
        for key, value in record.items():
            if re.fullmatch(r"indicator_?id", key, re.I) and value not in (None, ""):
                candidate = value
                break
        if candidate is None:
            for key, value in record.items():
                if key.lower() == "id" and value not in (None, ""):
                    candidate = value
                    break
        if candidate is not None:
            found[label] = candidate
    return found


def label_for(data, fallback: str) -> str:
    for record in iter_dicts(data):
        label = match_target(record)
        if label:
            return label
    return fallback


def main(from_year: int = DEFAULT_FROM_YEAR) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Licenses from_year={from_year} (emirate={EMIRATE})")

    session = requests.Session()
    id_map = find_ids(session)
    if len(id_map) < len(TARGETS):
        print(f"Only found IDs for: {list(id_map)}", file=sys.stderr)
    if not id_map:
        raise SystemExit("No SCAD indicator IDs found.")

    rows = []
    for label, ind_id in id_map.items():
        inner = f"Statistics/GetClickhouseIndicatorDetail?indicatorId={ind_id}&lang=EN"
        try:
            data = get_json(session, inner)
        except (requests.RequestException, ValueError) as exc:
            print(f"ID {ind_id}: request failed: {exc}", file=sys.stderr)
            continue

        label = label_for(data, label)
        lists = list(iter_record_lists(data))
        data_lists = [(path, items) for path, items in lists if path.endswith("Data.Data")] or lists

        for _path, items in data_lists:
            for item in items:
                if "VALUE" not in item:
                    continue
                year = int(item["YEAR"]) if str(item.get("YEAR", "")).isdigit() else None
                if year is not None and year < from_year:
                    continue
                quarter = item.get("QUARTER_EN")
                rows.append(
                    {
                        "emirate": EMIRATE,
                        "indicator": label,
                        "indicator_id": ind_id,
                        "period": f"{year}-{quarter}" if year and quarter else item.get("Name"),
                        "year": item.get("YEAR"),
                        "quarter": quarter,
                        "period_start": item.get("OBS_DT"),
                        "value": item.get("VALUE"),
                    }
                )

    if not rows:
        raise SystemExit("No license rows produced.")

    df = pd.DataFrame(rows).sort_values(["indicator", "period_start"])
    df.to_csv(OUT_DATA, index=False)
    print(f"Saved {len(df)} rows to {OUT_DATA}")
    print(df.head())


if __name__ == "__main__":
    main()
