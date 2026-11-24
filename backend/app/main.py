from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.db import fetch_all
from app.news import fetch_news
from app.portwatch import build_ports_payload
from app.tourism import load_travel_concerns

app = FastAPI(title="Economic Recovery API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GdpPoint(BaseModel):
    period: str  # e.g. "2026-Q1"
    sector: str
    sector_name: str
    value: float  # AED million, constant prices
    growth: float | None  # official annual growth rate, %


class TradePoint(BaseModel):
    period: str  # e.g. "2026-02"
    trade_type: str
    trade_type_name: str
    sector: str
    sector_name: str
    value: float  # AED
    growth: float | None  # % change vs the same month a year earlier


class LicensePoint(BaseModel):
    period: str  # e.g. "2026-Q1"
    emirate: str
    new_licenses: float
    renewed_licenses: float


class CpiPoint(BaseModel):
    period: str  # e.g. "2026-02"
    division: str
    division_name: str
    yoy: float | None  # year-over-year inflation, %
    mom: float | None  # month-over-month inflation, %
    index: float | None


class PmiPoint(BaseModel):
    period: str  # e.g. "2026-02"
    pmi: float


class JobPostingsPoint(BaseModel):
    period: str  # e.g. "2026-02"
    new_jobs: int
    sources: int | None = None


class EmploymentGrowthPoint(BaseModel):
    period: str  # e.g. "2026-Q2"
    emirate: str
    total: float  # YoY growth %, all genders
    male: float | None = None
    female: float | None = None


class OilPoint(BaseModel):
    period: str  # e.g. "2026-02"
    production: float  # thousand barrels per day
    mom: float | None  # % change vs previous month


# Queries use only SQL that both Postgres and SQLite (the data/ CSV fallback) accept.
# GROUP BY also collapses any duplicate rows left behind by repeated syncs.
GDP_QUERY = """
    SELECT CAST(time_period AS text) || '-' || quarter AS period,
           measure AS sector,
           max(measure_label) AS sector_name,
           max(obs_value) FILTER (WHERE qgdp_unit = 'VAL') AS value,
           max(obs_value) FILTER (WHERE qgdp_unit = 'GWTH_RATE') AS growth
    FROM gdp_quarterly
    GROUP BY measure, time_period, quarter
    HAVING max(obs_value) FILTER (WHERE qgdp_unit = 'VAL') IS NOT NULL
    ORDER BY measure, period
"""

TRADE_QUERY = """
    SELECT time_period AS period,
           trade_type,
           max(trade_type_label) AS trade_type_name,
           CAST(hs_section AS text) AS sector,
           max(hs_section_label) AS sector_name,
           max(obs_value) AS value
    FROM trade_sect_mth
    WHERE obs_value IS NOT NULL
    GROUP BY trade_type, hs_section, time_period
    ORDER BY trade_type, hs_section, time_period
"""

# Use 'new%' / 'renewed%' — '%new%' also matches "Renewed".
LICENSES_QUERY = """
    SELECT period,
           emirate,
           max(value) FILTER (WHERE lower(indicator) LIKE 'new%') AS new_licenses,
           max(value) FILTER (WHERE lower(indicator) LIKE 'renewed%') AS renewed_licenses
    FROM economic_licenses
    WHERE value IS NOT NULL
    GROUP BY emirate, period
    HAVING max(value) FILTER (WHERE lower(indicator) LIKE 'new%') IS NOT NULL
       AND max(value) FILTER (WHERE lower(indicator) LIKE 'renewed%') IS NOT NULL
    ORDER BY period
"""

CPI_QUERY = """
    SELECT time_period AS period,
           cpi_div AS division,
           max(cpi_div_label) AS division_name,
           max(obs_value) FILTER (WHERE measure = 'CPI_YINFL') AS yoy,
           max(obs_value) FILTER (WHERE measure = 'CPI_MINFL') AS mom,
           max(obs_value) FILTER (WHERE measure = 'CPI_INDEX') AS "index"
    FROM cpi_monthly
    GROUP BY cpi_div, time_period
    ORDER BY cpi_div, time_period
"""

PMI_QUERY = """
    SELECT month AS period, pmi
    FROM uae_pmi
    WHERE pmi IS NOT NULL
    ORDER BY month
"""

JOB_POSTINGS_QUERY = """
    SELECT month AS period, new_jobs, sources
    FROM job_postings_monthly
    WHERE new_jobs IS NOT NULL
    ORDER BY month
"""

EMPLOYMENT_GROWTH_QUERY = """
    SELECT period,
           emirate,
           max(value) FILTER (WHERE lower(gender) = 'total') AS total,
           max(value) FILTER (WHERE lower(gender) = 'male') AS male,
           max(value) FILTER (WHERE lower(gender) = 'female') AS female
    FROM employment_growth
    WHERE value IS NOT NULL
      AND lower(gender) IN ('total', 'male', 'female')
    GROUP BY emirate, period
    HAVING max(value) FILTER (WHERE lower(gender) = 'total') IS NOT NULL
    ORDER BY period
"""

OIL_QUERY = """
    SELECT period, production
    FROM oil_production_monthly
    WHERE production IS NOT NULL
    ORDER BY period
"""


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/gdp")
def get_gdp() -> list[GdpPoint]:
    return fetch_all(GDP_QUERY)


@app.get("/api/trade")
def get_trade() -> list[TradePoint]:
    rows = fetch_all(TRADE_QUERY)

    # The source has no growth series for trade, so derive year-over-year change.
    values = {(r["trade_type"], r["sector"], r["period"]): r["value"] for r in rows}
    for row in rows:
        year, month = row["period"].split("-")
        year_ago = values.get((row["trade_type"], row["sector"], f"{int(year) - 1}-{month}"))
        row["growth"] = (row["value"] / year_ago - 1) * 100 if year_ago else None

    return rows


@app.get("/api/licenses")
def get_licenses() -> list[LicensePoint]:
    return fetch_all(LICENSES_QUERY)


@app.get("/api/cpi")
def get_cpi() -> list[CpiPoint]:
    rows = fetch_all(CPI_QUERY)

    # Official YoY is missing for some recent months; fill from the index.
    indexes = {(r["division"], r["period"]): r["index"] for r in rows if r["index"] is not None}
    for row in rows:
        if row["yoy"] is not None or row["index"] is None:
            continue
        year, month = row["period"].split("-")
        year_ago = indexes.get((row["division"], f"{int(year) - 1}-{month}"))
        if year_ago:
            row["yoy"] = (row["index"] / year_ago - 1) * 100

    return rows


@app.get("/api/pmi")
def get_pmi() -> list[PmiPoint]:
    return fetch_all(PMI_QUERY)


@app.get("/api/job-postings")
def get_job_postings() -> list[JobPostingsPoint]:
    return fetch_all(JOB_POSTINGS_QUERY)


@app.get("/api/employment-growth")
def get_employment_growth() -> list[EmploymentGrowthPoint]:
    return fetch_all(EMPLOYMENT_GROWTH_QUERY)


@app.get("/api/oil")
def get_oil() -> list[OilPoint]:
    rows = fetch_all(OIL_QUERY)
    previous: float | None = None
    for row in rows:
        if previous is None or previous == 0:
            row["mom"] = None
        else:
            row["mom"] = (row["production"] / previous - 1) * 100
        previous = row["production"]
    return rows


@app.get("/api/ports")
def get_ports() -> dict:
    """IMF PortWatch UAE ports: Hormuz exposure, baseline vs war, recovery."""
    try:
        return build_ports_payload()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/tourism")
def get_tourism() -> dict:
    """Google Trends travel-concern index for Dubai / UAE."""
    try:
        return load_travel_concerns()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/news")
def get_news() -> dict:
    """Latest Google News headlines for US-Iran war and UAE economy."""
    try:
        return fetch_news()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"News feed unavailable: {exc}") from exc
