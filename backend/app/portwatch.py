from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CACHE_FILE = ROOT / "data" / "portwatch_cache.json"
HORMUZ_CACHE_FILE = ROOT / "data" / "portwatch_hormuz.json"

BASELINE_START = date(2025, 10, 1)
BASELINE_END = date(2026, 1, 31)
WAR_START = date(2026, 2, 28)
DPM = 30.4375
EARLY_WAR_DAYS = 30
RECENT_DAYS = 30

# Gulf of Oman–facing ports (outside Hormuz) → green. Persian Gulf–facing → red.
OMAN_PORTS = frozenset({"Fujairah", "Khor Fakkan"})
# Back-compat alias used by tests / older callers.
RED_PORTS = OMAN_PORTS

# Ignore tiny terminals when picking a headline recovery leader.
MIN_BASELINE_CALLS = 2.0


def _avg(daily: dict[str, list[float]], d0: date, d1: date) -> tuple[float, float, float] | None:
    tot = [0.0, 0.0, 0.0]
    n = 0
    for key, vals in daily.items():
        dd = date.fromisoformat(key)
        if d0 <= dd <= d1:
            for i in range(3):
                tot[i] += float(vals[i] or 0)
            n += 1
    if not n:
        return None
    return tot[0] / n, tot[1] / n, tot[2] / n


def _pct(current: float | None, base: float | None) -> float | None:
    if current is None or base is None or base <= 0:
        return None
    return (current - base) / base * 100


def _month_add(d: date) -> date:
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def _monthly(daily: dict[str, list[float]], last: date) -> list[dict[str, Any]]:
    by: dict[str, list[float]] = {}
    for key, vals in daily.items():
        bucket = by.setdefault(key[:7], [0.0, 0.0, 0.0])
        for i in range(3):
            bucket[i] += float(vals[i] or 0)

    out: list[dict[str, Any]] = []
    cur = date(BASELINE_START.year, BASELINE_START.month, 1)
    while cur <= last:
        key = cur.strftime("%Y-%m")
        t = by.get(key, [0.0, 0.0, 0.0])
        out.append(
            {
                "period": key,
                "calls": round(t[0]),
                "import": round(t[1]),
                "export": round(t[2]),
            }
        )
        cur = _month_add(cur)
    return out


def _metric_block(base: tuple[float, float, float] | None, war: tuple[float, float, float] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for i, name in enumerate(("calls", "import", "export")):
        b = None if base is None else base[i]
        w = None if war is None else war[i]
        out[name] = {
            "baseline_daily": None if b is None else round(b, 3),
            "war_daily": None if w is None else round(w, 3),
            "baseline_month": None if b is None else round(b * DPM, 1),
            "war_month": None if w is None else round(w * DPM, 1),
            "pct_vs_baseline": None if _pct(w, b) is None else round(_pct(w, b), 1),  # type: ignore[arg-type]
        }
    return out


def _zone(name: str) -> str:
    return "green" if name in OMAN_PORTS else "red"


def load_cache() -> dict[str, Any]:
    if not CACHE_FILE.exists():
        raise FileNotFoundError(
            f"Missing {CACHE_FILE}. Run `python backend/scripts/portwatch.py` to fetch PortWatch data."
        )
    return json.loads(CACHE_FILE.read_text(encoding="utf-8"))


def _avg_capacity(daily: dict[str, dict], d0: date, d1: date) -> float | None:
    vals = [
        float(row.get("capacity") or 0)
        for key, row in daily.items()
        if d0 <= date.fromisoformat(key) <= d1
    ]
    if not vals:
        return None
    return sum(vals) / len(vals)


def build_hormuz_kpi(cache: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Current Hormuz capacity vs Oct–Jan baseline, plus MoM change."""
    if cache is None:
        if not HORMUZ_CACHE_FILE.exists():
            return None
        cache = json.loads(HORMUZ_CACHE_FILE.read_text(encoding="utf-8"))

    daily = cache.get("daily") or {}
    if not daily:
        return None

    last = date.fromisoformat(max(daily))
    recent_start = last - timedelta(days=RECENT_DAYS - 1)
    # Previous calendar-ish month window ending the day before recent_start.
    prev_end = recent_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=RECENT_DAYS - 1)

    baseline = _avg_capacity(daily, BASELINE_START, BASELINE_END)
    current = _avg_capacity(daily, recent_start, last)
    previous = _avg_capacity(daily, prev_start, prev_end)

    pct_of_baseline = None if baseline is None or baseline <= 0 or current is None else round(
        current / baseline * 100, 1
    )
    mom = None if _pct(current, previous) is None else round(_pct(current, previous), 1)  # type: ignore[arg-type]

    return {
        "name": cache.get("name") or "Strait of Hormuz",
        "pct_of_baseline": pct_of_baseline,
        "mom": mom,
        "baseline_daily_capacity": None if baseline is None else round(baseline),
        "current_daily_capacity": None if current is None else round(current),
        "baseline_start": BASELINE_START.isoformat(),
        "baseline_end": BASELINE_END.isoformat(),
        "recent_start": recent_start.isoformat(),
        "last": last.isoformat(),
    }


def build_ports_payload(cache: dict[str, Any] | None = None) -> dict[str, Any]:
    cache = cache or load_cache()
    ports_raw = cache.get("ports") or []
    all_dates = [d for p in ports_raw for d in (p.get("daily") or {})]
    if not all_dates:
        raise ValueError("PortWatch cache has no daily rows")

    last = date.fromisoformat(max(all_dates))
    early_end = WAR_START + timedelta(days=EARLY_WAR_DAYS - 1)
    recent_start = last - timedelta(days=RECENT_DAYS - 1)

    ports: list[dict[str, Any]] = []
    # Daily ship calls summed across each zone's ports: [baseline, latest window].
    zone_calls = {"green": [0.0, 0.0], "red": [0.0, 0.0]}
    for raw in ports_raw:
        daily = {k: list(v) for k, v in (raw.get("daily") or {}).items()}
        db = raw.get("db") or {}
        name = raw.get("disp") or db.get("portname") or "Unknown"

        base = _avg(daily, BASELINE_START, BASELINE_END)
        war = _avg(daily, WAR_START, last)
        early = _avg(daily, WAR_START, early_end)
        recent = _avg(daily, recent_start, last)
        metrics = _metric_block(base, war)
        if base is not None and recent is not None:
            zone_calls[_zone(name)][0] += base[0]
            zone_calls[_zone(name)][1] += recent[0]

        # Ship volumes = port calls; overall throughput = import + export tons.
        calls_vs = metrics["calls"]["pct_vs_baseline"]
        tons_base = None if base is None else base[1] + base[2]
        tons_war = None if war is None else war[1] + war[2]
        tons_early = None if early is None else early[1] + early[2]
        tons_recent = None if recent is None else recent[1] + recent[2]
        recovery_calls = _pct(None if recent is None else recent[0], None if early is None else early[0])
        recovery_tons = _pct(tons_recent, tons_early)

        industries = [
            x
            for x in (db.get("industry_top1"), db.get("industry_top2"), db.get("industry_top3"))
            if x
        ]

        ports.append(
            {
                "id": db.get("portid"),
                "name": name,
                "emirate": raw.get("emirate"),
                "note": raw.get("note"),
                "zone": _zone(name),
                "lat": db.get("lat") if db.get("lat") is not None else raw.get("flat"),
                "lon": db.get("lon") if db.get("lon") is not None else raw.get("flon"),
                "share_import": db.get("share_country_maritime_import"),
                "share_export": db.get("share_country_maritime_export"),
                "industries": industries,
                "metrics": metrics,
                "calls_vs_baseline": calls_vs,
                "tons_vs_baseline": None if _pct(tons_war, tons_base) is None else round(_pct(tons_war, tons_base), 1),  # type: ignore[arg-type]
                "recovery_calls": None if recovery_calls is None else round(recovery_calls, 1),
                "recovery_tons": None if recovery_tons is None else round(recovery_tons, 1),
                "baseline_calls_daily": None if base is None else round(base[0], 3),
                "monthly": _monthly(daily, last),
            }
        )

    ports.sort(key=lambda p: (0 if p["zone"] == "green" else 1, p["name"]))

    def zone_avg(zone: str, field: str) -> float | None:
        vals = [p[field] for p in ports if p["zone"] == zone and p[field] is not None]
        if not vals:
            return None
        return round(sum(vals) / len(vals), 1)

    def zone_calls_pct_of_baseline(zone: str) -> float | None:
        """Latest-window ship calls as % of baseline, summing ports so size counts."""
        base_calls, recent_calls = zone_calls[zone]
        if base_calls <= 0:
            return None
        return round(recent_calls / base_calls * 100, 1)

    above_baseline = [
        {"name": p["name"], "zone": p["zone"], "calls_vs_baseline": p["calls_vs_baseline"]}
        for p in ports
        if p["calls_vs_baseline"] is not None and p["calls_vs_baseline"] > 0
    ]
    above_baseline.sort(key=lambda p: p["calls_vs_baseline"], reverse=True)

    # Headline recovery: strongest early-war → recent rebound in ship volumes,
    # among ports with enough baseline activity to be decision-relevant.
    candidates = [
        p
        for p in ports
        if p["recovery_calls"] is not None
        and (p["baseline_calls_daily"] or 0) >= MIN_BASELINE_CALLS
    ]
    candidates.sort(key=lambda p: p["recovery_calls"], reverse=True)
    top = candidates[0] if candidates else None

    top_recovery = None
    if top:
        top_recovery = {
            "name": top["name"],
            "zone": top["zone"],
            "emirate": top["emirate"],
            "recovery_calls": top["recovery_calls"],
            "recovery_tons": top["recovery_tons"],
            "calls_vs_baseline": top["calls_vs_baseline"],
            "tons_vs_baseline": top["tons_vs_baseline"],
            "share_import": top["share_import"],
            "share_export": top["share_export"],
            "industries": top["industries"],
            # Best available proxy: war-period volume change at the port that
            # specializes in these industries.
            "industry_impact_calls": top["calls_vs_baseline"],
            "industry_impact_tons": top["tons_vs_baseline"],
        }

    fetched_at = cache.get("fetched_at")
    fetched = (
        datetime.fromtimestamp(fetched_at).strftime("%Y-%m-%d %H:%M")
        if isinstance(fetched_at, (int, float))
        else None
    )

    return {
        "meta": {
            "baseline_start": BASELINE_START.isoformat(),
            "baseline_end": BASELINE_END.isoformat(),
            "war_start": WAR_START.isoformat(),
            "early_war_end": early_end.isoformat(),
            "recent_start": recent_start.isoformat(),
            "last": last.isoformat(),
            "fetched": fetched,
            "source": "IMF PortWatch",
            "green_ports": sorted(OMAN_PORTS),
            "red_ports": sorted(OMAN_PORTS),  # legacy; same list historically meant Oman ports
            "green_definition": "Gulf of Oman–facing ports — Fujairah and Khor Fakkan (outside Hormuz)",
            "red_definition": "Persian Gulf–facing ports (inside Hormuz)",
            "recovery_definition": (
                f"% change in daily ship volumes from the first {EARLY_WAR_DAYS} days after "
                f"war start to the latest {RECENT_DAYS} days of PortWatch data"
            ),
        },
        "insights": {
            "ports_above_baseline": above_baseline,
            "any_above_baseline": bool(above_baseline),
            "top_recovery": top_recovery,
            "green_avg_calls_vs_baseline": zone_avg("green", "calls_vs_baseline"),
            "red_avg_calls_vs_baseline": zone_avg("red", "calls_vs_baseline"),
            "green_avg_recovery_calls": zone_avg("green", "recovery_calls"),
            "red_avg_recovery_calls": zone_avg("red", "recovery_calls"),
            "green_calls_pct_of_baseline": zone_calls_pct_of_baseline("green"),
        },
        "hormuz": build_hormuz_kpi(),
        "ports": ports,
    }
