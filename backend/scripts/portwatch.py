"""Fetch UAE port activity from IMF PortWatch (ArcGIS).

Writes:
  data/portwatch_cache.json  — daily port calls / import / export + port metadata

Used by GET /api/ports (see backend/app/portwatch.py) in the trade section.

    python backend/scripts/portwatch.py
    python backend/scripts/portwatch.py --refresh
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CACHE_FILE = DATA_DIR / "portwatch_cache.json"
CACHE_MAX_AGE_H = 24

BASELINE_START = date(2025, 10, 1)

ARC = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services"
PORTS_DB = f"{ARC}/PortWatch_ports_database/FeatureServer/0/query"
# Daily_Trade_Data was retired; Daily_Ports_Data is the current port-level series.
DAILY = f"{ARC}/Daily_Ports_Data/FeatureServer/0/query"

# display, aliases, emirate, fallback lat/lon, note
WANTED = [
    ("Jebel Ali", ["jebel ali"], "Dubai", 25.0118, 55.0610, "Jebel Ali Port"),
    ("Dubai", ["dubai", "port rashid", "mina rashid"], "Dubai", 25.2720, 55.2760, "Mina Rashid / Port Rashid"),
    ("Khalifa Port", ["khalifa port", "khalifa"], "Abu Dhabi", 24.8000, 54.6500, "Khalifa Port"),
    ("Abu Dhabi", ["abu dhabi", "zayed port", "mina zayed"], "Abu Dhabi", 24.5200, 54.3800, "Zayed Port (Mina Zayed)"),
    ("Jabal Az Zannah-Ruways", ["jabal az zannah ruways", "ruways", "ruwais"], "Abu Dhabi", 24.1100, 52.7300, "Ruwais"),
    ("Jebel Dhanna", ["jebel dhanna", "jabal dhanna"], "Abu Dhabi", 24.1900, 52.6000, "Oil export terminal"),
    ("Das Island", ["das island"], "Abu Dhabi", 25.1500, 52.8700, "Offshore oil & LNG terminal"),
    ("Zirku Island", ["zirku island", "zirku"], "Abu Dhabi", 24.8700, 53.0700, "Offshore oil export terminal"),
    ("Sharjah", ["sharjah", "port khalid"], "Sharjah", 25.3600, 55.3800, "Port Khalid"),
    (
        "Al Hamriyah LPG Terminal",
        ["al hamriyah lpg terminal", "hamriyah lpg terminal", "hamriyah lpg"],
        "Sharjah",
        25.4750,
        55.4650,
        "LPG terminal, Hamriyah",
    ),
    ("Khor Fakkan", ["khor fakkan"], "Sharjah", 25.3430, 56.3560, "Gulf of Oman container port"),
    ("Ajman", ["ajman"], "Ajman", 25.4100, 55.4400, "Ajman Port"),
    (
        "Umm al Qaiwain",
        ["umm al qaiwain", "umm al quwain", "umm al qawain"],
        "Umm Al Quwain",
        25.5950,
        55.5900,
        "Ahmed Bin Rashid Port",
    ),
    ("Mina Saqr", ["mina saqr", "mina saqr port"], "Ras Al Khaimah", 25.9800, 56.0400, "Ras Al Khaimah"),
    ("Fujairah", ["fujairah"], "Fujairah", 25.1667, 56.3667, "Bunkering & oil hub"),
]


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


def fetch_all(base: str, where: str, out_fields: str = "*", page: int = 500) -> list[dict]:
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
        }
        data = get_json(base + "?" + urlencode(params))
        if "error" in data:
            raise RuntimeError(f"ArcGIS error: {data['error']}")
        feats = data.get("features", [])
        out.extend(f["attributes"] for f in feats)
        if not feats or not (data.get("exceededTransferLimit") or len(feats) >= page):
            break
        offset += len(feats)
    return out


def lower_keys(d: dict) -> dict:
    return {str(k).lower(): v for k, v in d.items()}


def norm(s: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def to_date(val: object) -> date | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val / 1000, tz=timezone.utc).date()
    s = str(val).strip()
    if s.isdigit():
        return datetime.fromtimestamp(int(s) / 1000, tz=timezone.utc).date()
    return date.fromisoformat(s[:10])


def fetch_ports_db() -> list[dict]:
    fields = (
        "portid,portname,country,ISO3,lat,lon,"
        "industry_top1,industry_top2,industry_top3,"
        "share_country_maritime_import,share_country_maritime_export"
    )
    rows = fetch_all(PORTS_DB, "ISO3='ARE'", out_fields=fields)
    if not rows:
        rows = fetch_all(PORTS_DB, "country LIKE '%Emirates%'", out_fields=fields)
    if not rows:
        rows = [
            r
            for r in fetch_all(PORTS_DB, "1=1", out_fields=fields)
            if str(lower_keys(r).get("iso3", "")).upper() == "ARE"
        ]
    return [lower_keys(r) for r in rows]


def match_ports(db_rows: list[dict]) -> list[tuple]:
    matched, used = [], set()
    for disp, aliases, emirate, flat, flon, note in WANTED:
        al = [norm(a) for a in aliases]
        cand = [r for r in db_rows if r["portid"] not in used and norm(r.get("portname", "")) in al]
        if not cand:
            cand = [
                r
                for r in db_rows
                if r["portid"] not in used
                and any(
                    a in norm(r.get("portname", "")) or norm(r.get("portname", "")) in a
                    for a in al
                    if len(norm(r.get("portname", ""))) > 3
                )
            ]
        if cand:
            row = cand[0]
            used.add(row["portid"])
            matched.append((disp, emirate, flat, flon, note, row))
        else:
            print(f"  ! not found in PortWatch database: {disp}")
    extra = [r.get("portname") for r in db_rows if r["portid"] not in used]
    if extra:
        print("  (other UAE ports in PortWatch not on your list: " + ", ".join(map(str, extra)) + ")")
    return matched


def fetch_daily(portid: object) -> dict[str, list[float]]:
    pid = str(portid).replace("'", "").strip()
    fields = "date,portid,portcalls,import,export"
    variants = [
        f"portid='{pid}' AND date >= timestamp '{BASELINE_START.isoformat()} 00:00:00'",
        f"UPPER(portid)='{pid.upper()}' AND date >= timestamp '{BASELINE_START.isoformat()} 00:00:00'",
        f"portid='{pid}'",
    ]
    rows: list[dict] = []
    err: Exception | None = None
    for where in variants:
        try:
            rows = fetch_all(DAILY, where, out_fields=fields)
            if rows:
                break
        except RuntimeError as exc:
            err = exc
    if not rows and err:
        raise err

    daily: dict[str, list[float]] = {}
    for row in map(lower_keys, rows):
        if row.get("date") is None:
            continue
        day = to_date(row["date"])
        if day is None or day < BASELINE_START:
            continue
        daily[day.isoformat()] = [
            float(row.get("portcalls") or 0),
            float(row.get("import") or 0),
            float(row.get("export") or 0),
        ]
    return daily


def load_cache() -> dict | None:
    if not CACHE_FILE.exists():
        return None
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def fetch_and_cache() -> dict:
    print("Fetching UAE ports from PortWatch ...")
    matched = match_ports(fetch_ports_db())
    if not matched:
        raise RuntimeError("no UAE ports matched in the PortWatch database")

    ports = []
    for disp, emirate, flat, flon, note, row in matched:
        print(f"  downloading daily data: {disp}  ({row.get('portname')}, {row.get('portid')})")
        daily = fetch_daily(row["portid"])
        ports.append(
            {
                "disp": disp,
                "emirate": emirate,
                "flat": flat,
                "flon": flon,
                "note": note,
                "db": row,
                "daily": daily,
            }
        )

    cache = {"fetched_at": time.time(), "ports": ports}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache), encoding="utf-8")
    print(f"Saved {len(ports)} ports to {CACHE_FILE}")
    return cache


def main(refresh: bool = False) -> dict:
    cache = load_cache()
    if cache and not refresh:
        age_h = (time.time() - cache.get("fetched_at", 0)) / 3600
        if age_h < CACHE_MAX_AGE_H:
            print(f"Using cached PortWatch data ({age_h:.1f} h old). Use --refresh to re-download.")
            return cache

    try:
        return fetch_and_cache()
    except Exception as exc:
        if cache:
            print(f"WARNING: download failed ({exc}); using older cache.")
            return cache
        sys.exit(
            f"\nCould not fetch data from PortWatch: {exc}\n"
            "The PortWatch ArcGIS service may have moved, or the network "
            "cannot reach services9.arcgis.com."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch IMF PortWatch UAE port data")
    parser.add_argument("--refresh", action="store_true", help="Force re-download even if cache is fresh")
    args = parser.parse_args()
    result = main(refresh=args.refresh)
    n_days = sum(len(p.get("daily") or {}) for p in result.get("ports") or [])
    print(f"Ready: {len(result.get('ports') or [])} ports, {n_days} daily rows total")
