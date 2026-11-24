"""Fetch UAE monthly crude oil production from the EIA Open Data API v2.

Writes:
  data/eia_uae_raw.csv              — full EIA response rows
  data/oil_production_monthly.csv  — clean production series for the dashboard

Requires EIA_API_KEY in .env.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

BASE = "https://api.eia.gov/v2/international"
COUNTRY = "ARE"
PRODUCT = "57"  # crude oil including lease condensate
UNIT = "TBPD"  # thousand barrels per day
DEFAULT_START = "2025-01"
PAGE = 5000
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
RAW_PATH = DATA_DIR / "eia_uae_raw.csv"
OUT_PATH = DATA_DIR / "oil_production_monthly.csv"
SOURCE = "EIA Open Data"


def api_key() -> str:
    key = os.getenv("EIA_API_KEY")
    if not key:
        sys.exit("Add EIA_API_KEY to your .env file first.")
    return key


def get(path: str, params) -> dict:
    response = requests.get(f"{BASE}/{path}", params=params, timeout=60)
    if response.status_code in (400, 403):
        sys.exit(f"{response.status_code} from EIA: {response.text[:300]}")
    response.raise_for_status()
    return response.json()["response"]


def activity_ids(key: str) -> dict[str, str]:
    resp = get("facet/activityId", {"api_key": key})
    return {facet["name"].lower(): facet["id"] for facet in resp["facets"]}


def fetch(key: str, activity_id: str, start: str, frequency: str = "monthly") -> list[dict]:
    params = [
        ("api_key", key),
        ("frequency", frequency),
        ("data[]", "value"),
        ("facets[countryRegionId][]", COUNTRY),
        ("facets[productId][]", PRODUCT),
        ("facets[activityId][]", activity_id),
        ("facets[unit][]", UNIT),
        ("start", start),
        ("sort[0][column]", "period"),
        ("sort[0][direction]", "asc"),
        ("length", PAGE),
    ]
    rows: list[dict] = []
    offset = 0
    while True:
        resp = get("data", params + [("offset", offset)])
        rows += resp["data"]
        offset += PAGE
        if offset >= int(resp["total"]):
            return rows


def to_clean(raw: pd.DataFrame) -> pd.DataFrame:
    production = raw[raw["activity"].str.lower() == "production"].copy()
    production["value"] = pd.to_numeric(production["value"], errors="coerce")
    production = production.dropna(subset=["period", "value"])
    production = production.sort_values("period").drop_duplicates("period", keep="last")
    return pd.DataFrame(
        {
            "period": production["period"].astype(str),
            "production": production["value"].astype(float).round(1),
            "unit": UNIT,
            "source": SOURCE,
        }
    ).reset_index(drop=True)


def merge_clean(existing: pd.DataFrame | None, incoming: pd.DataFrame) -> pd.DataFrame:
    if existing is None or existing.empty:
        return incoming
    combined = pd.concat([existing, incoming], ignore_index=True)
    combined = combined.sort_values("period").drop_duplicates("period", keep="last")
    return combined.reset_index(drop=True)


def main(start_month: str = DEFAULT_START) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Oil production start_month={start_month}")

    key = api_key()
    acts = activity_ids(key)
    print("EIA activity types:", ", ".join(sorted(acts)))

    production_id = next(
        (act_id for name, act_id in acts.items() if name.startswith("production")),
        "1",
    )
    export_id = next((act_id for name, act_id in acts.items() if "export" in name), None)

    frames: list[pd.DataFrame] = []
    for label, act_id in (("production", production_id), ("exports", export_id)):
        if act_id is None:
            print(f"No '{label}' activity found in EIA's list.")
            continue
        rows = fetch(key, act_id, start=start_month)
        print(f"{label}: {len(rows)} monthly rows")
        if not rows:
            continue
        frame = pd.DataFrame(rows)
        frame["activity"] = label
        frames.append(frame)

    if not frames:
        sys.exit("No data returned from EIA.")

    raw = pd.concat(frames, ignore_index=True)
    raw["value"] = pd.to_numeric(raw["value"], errors="coerce")

    if RAW_PATH.exists():
        previous_raw = pd.read_csv(RAW_PATH)
        raw = (
            pd.concat([previous_raw, raw], ignore_index=True)
            .drop_duplicates(
                subset=["period", "activityId", "productId", "countryRegionId", "unit"],
                keep="last",
            )
            .sort_values(["activity", "period"])
            .reset_index(drop=True)
        )
    raw.to_csv(RAW_PATH, index=False)
    print(f"Saved raw rows to {RAW_PATH}")

    existing = pd.read_csv(OUT_PATH) if OUT_PATH.exists() else None
    clean = merge_clean(existing, to_clean(raw))
    # Keep rows from the requested start onwards in the clean file for incremental sync,
    # but never drop older history already stored locally.
    clean.to_csv(OUT_PATH, index=False)
    print(f"Saved {len(clean)} production months to {OUT_PATH}")
    print(clean.tail(6).to_string(index=False))


if __name__ == "__main__":
    main()
