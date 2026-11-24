"""Fetch Abu Dhabi employed-residents growth rates from SCAD.

Source: Labour Force KSI indicator 8585
https://scad.gov.ae/labor-force?ThemeID=224&tab=KSI&IndicatorID=8585

Outputs data/employment_growth.csv with one row per gender per quarter.
Same SCAD HTTP pattern as licenses.py (no Playwright).
"""

import re
import sys
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests

BASE_URL = "https://scad.gov.ae/o/communication"
# ThemeID from the labour-force KSI page.
CATEGORY_ID = "224"
INDICATOR_ID = "8585"
EMIRATE = "Abu Dhabi"
DEFAULT_FROM_YEAR = 2025

TARGET_LABEL = (
    "Growth Rate of Employed Residents in the Emirate of Abu Dhabi by Gender "
    "(Current Quarter Compared to Same Quarter of Previous Year) - Quarterly"
)
# Require "by gender" so we do not pick the sibling age-group indicator (8587).
TARGET_NEEDLE = "growth rate of employed residents in the emirate of abu dhabi by gender"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": (
        "https://scad.gov.ae/labor-force?ThemeID=224&tab=KSI&IndicatorID=8585"
    ),
}

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
OUT_DATA = DATA_DIR / "employment_growth.csv"


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


def match_target(record) -> bool:
    for value in record.values():
        if isinstance(value, str) and TARGET_NEEDLE in value.lower():
            return True
    return False


def find_indicator_id(session: requests.Session) -> str:
    """Resolve the indicator id from the labour KSI overview; fall back to known id."""
    inner = (
        "Statistics/GetClickhouseKeyStatisticsIndicatorsOverview"
        f"?CategoryID={CATEGORY_ID}&PageNumber=1&PageSize=100&lang=EN"
    )
    data = get_json(session, inner)
    for record in iter_dicts(data):
        if not match_target(record):
            continue
        for key, value in record.items():
            if re.fullmatch(r"indicator_?id", key, re.I) and value not in (None, ""):
                return str(value)
        if record.get("id") not in (None, ""):
            return str(record["id"])
    print(
        f"Overview did not resolve indicator id; using known id {INDICATOR_ID}",
        file=sys.stderr,
    )
    return INDICATOR_ID


def extract_rows(data, ind_id: str, label: str, from_year: int) -> list[dict]:
    lists = list(iter_record_lists(data))
    data_lists = [(path, items) for path, items in lists if path.endswith("Data.Data")] or lists
    rows = []
    for _path, items in data_lists:
        for item in items:
            if "VALUE" not in item:
                continue
            year = int(item["YEAR"]) if str(item.get("YEAR", "")).isdigit() else None
            if year is not None and year < from_year:
                continue
            quarter = item.get("QUARTER_EN")
            gender = item.get("GENDER_EN")
            if not gender:
                continue
            rows.append(
                {
                    "emirate": EMIRATE,
                    "indicator": label,
                    "indicator_id": ind_id,
                    "gender": gender,
                    "period": f"{year}-{quarter}" if year and quarter else item.get("Name"),
                    "year": item.get("YEAR"),
                    "quarter": quarter,
                    "period_start": item.get("OBS_DT"),
                    "value": item.get("VALUE"),
                    "unit": "Percentage (%)",
                }
            )
    return rows


def title_for(data) -> str:
    for record in iter_dicts(data):
        title = record.get("component_title") or record.get("componentTitle")
        if isinstance(title, str) and TARGET_NEEDLE in title.lower():
            return title
    return TARGET_LABEL


def main(from_year: int = DEFAULT_FROM_YEAR) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Employment growth from_year={from_year} (emirate={EMIRATE})")

    session = requests.Session()
    ind_id = find_indicator_id(session)
    inner = f"Statistics/GetClickhouseIndicatorDetail?indicatorId={ind_id}&lang=EN"
    try:
        data = get_json(session, inner)
    except (requests.RequestException, ValueError) as exc:
        raise SystemExit(f"ID {ind_id}: request failed: {exc}") from exc

    if not data.get("IsSuccess"):
        raise SystemExit(f"SCAD returned unsuccessful response for id {ind_id}")

    label = title_for(data)
    rows = extract_rows(data, ind_id, label, from_year)

    if not rows:
        raise SystemExit("No employment-growth rows produced.")

    df = pd.DataFrame(rows).drop_duplicates(
        subset=["emirate", "indicator_id", "gender", "period_start"],
        keep="last",
    )
    df = df.sort_values(["period_start", "gender"])
    df.to_csv(OUT_DATA, index=False)
    print(f"Saved {len(df)} rows to {OUT_DATA}")
    print(df[["period", "gender", "value"]].to_string(index=False))


if __name__ == "__main__":
    main()
