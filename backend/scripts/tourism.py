"""Fetch UAE travel-concern search interest from Google Trends.

Writes:
  data/travel_concerns.json

Higher index = more safety / warning / disruption searches about Dubai & the UAE.

    python backend/scripts/tourism.py
    python backend/scripts/tourism.py --refresh
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import warnings
from datetime import date
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUT_PATH = DATA_DIR / "travel_concerns.json"
KEYWORD_CSV = DATA_DIR / "travel_concerns_keywords_monthly.csv"

START_DATE = "2025-01-01"
GEO = ""  # worldwide; use "AE" / "GB" / etc. to restrict origin

KEYWORDS = [
    "Is Dubai safe",
    "Is UAE safe",
    "Is it safe to travel to Dubai",
    "Dubai travel warning",
    "UAE travel advice",
    "UAE travel advisory",
    "Dubai flights cancelled",
    "is Dubai airport open",
    "Dubai airspace",
    "cancel Dubai trip",
    "Dubai holiday refund",
]

SMOOTH_MONTHS = 3
INDEX_CAP = 500
MAX_ZERO_SHARE = 0.9


def pct_change(new, old):
    if old is None or new is None or pd.isna(old) or pd.isna(new) or old == 0:
        return None
    return round((new / old - 1) * 100, 1)


def clean(values):
    return [None if pd.isna(v) else round(float(v), 1) for v in values]


def fetch_weekly(pytrends, keyword: str, timeframe: str, retries: int = 5) -> pd.Series:
    for attempt in range(1, retries + 1):
        try:
            pytrends.build_payload([keyword], timeframe=timeframe, geo=GEO)
            df = pytrends.interest_over_time()
            if df.empty:
                raise ValueError("empty response")
            if "isPartial" in df.columns:
                df = df[~df["isPartial"].astype(bool)]
            return df[keyword].astype(float)
        except Exception:
            if attempt == retries:
                raise
            time.sleep(30 * attempt + random.uniform(0, 5))


def fetch_all() -> dict[str, pd.Series]:
    from pytrends.request import TrendReq

    pytrends = TrendReq(hl="en-US", tz=-240)
    timeframe = f"{START_DATE} {date.today().isoformat()}"
    series: dict[str, pd.Series] = {}
    for i, kw in enumerate(KEYWORDS):
        print(f"  fetching: {kw}")
        series[kw] = fetch_weekly(pytrends, kw, timeframe)
        if i < len(KEYWORDS) - 1:
            time.sleep(random.uniform(8, 15))
    return series


def build_results(series: dict[str, pd.Series]) -> tuple[dict, pd.DataFrame]:
    kept, left_out = {}, []
    for kw, s in series.items():
        if s.mean() == 0 or (s == 0).mean() > MAX_ZERO_SHARE:
            left_out.append(kw)
            continue
        kept[kw] = (s / s.mean() * 100).clip(upper=INDEX_CAP)
    if not kept:
        raise RuntimeError("No keyword had enough search volume to use.")

    weekly_end = max(s.index.max() for s in series.values()) + pd.Timedelta(days=6)
    monthly_kw = pd.DataFrame(kept).resample("MS").mean()

    monthly = monthly_kw.mean(axis=1)
    complete = [m for m in monthly.index if m + pd.offsets.MonthEnd(0) <= weekly_end]
    monthly = monthly / monthly.loc[complete].mean() * 100

    smooth = monthly.rolling(SMOOTH_MONTHS, min_periods=SMOOTH_MONTHS).mean()
    latest = complete[-1]
    prev = latest - pd.DateOffset(months=1)
    last_year = latest - pd.DateOffset(years=1)

    periods = [m.strftime("%Y-%m") for m in monthly.index]
    result = {
        "title": "UAE travel concerns",
        "latest_month": latest.strftime("%b %Y"),
        "latest_period": latest.strftime("%Y-%m"),
        "smooth_months": SMOOTH_MONTHS,
        "yoy": pct_change(smooth.get(latest), smooth.get(last_year)),
        "mom": pct_change(smooth.get(latest), smooth.get(prev)),
        "unit": (
            f"Search interest index "
            f"(average month, {complete[0]:%b %Y} to {latest:%b %Y} = 100)"
        ),
        "included": list(kept),
        "excluded": left_out,
        "series": [
            {
                "period": periods[i],
                "index": clean(monthly.values)[i],
                "smooth": clean(smooth.values)[i],
                "partial": m not in complete,
            }
            for i, m in enumerate(monthly.index)
        ],
    }
    return result, monthly_kw


def load_cache() -> dict | None:
    if not OUT_PATH.exists():
        return None
    try:
        return json.loads(OUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def main(refresh: bool = False) -> dict:
    if not refresh:
        cached = load_cache()
        if cached:
            print(f"Using cached travel concerns at {OUT_PATH}. Use --refresh to re-download.")
            return cached

    print("Fetching UAE travel-concern keywords from Google Trends ...")
    try:
        series = fetch_all()
        result, monthly_kw = build_results(series)
    except Exception as exc:
        cached = load_cache()
        if cached:
            print(f"WARNING: download failed ({exc}); using older cache.")
            return cached
        sys.exit(f"Could not fetch travel concerns: {exc}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result), encoding="utf-8")
    monthly_kw.round(1).to_csv(KEYWORD_CSV)
    print(f"Saved {OUT_PATH}")
    print(f"  latest {result['latest_month']}: MoM {result['mom']}% · YoY {result['yoy']}%")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch UAE travel-concern Trends data")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    main(refresh=args.refresh)
