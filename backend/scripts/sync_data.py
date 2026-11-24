
import os

import cpi
import foreign_trade
import gdp
import job_postings
import employment
import licenses
import oil_prod
import pmi
import portwatch
import portwatch_hormuz
import tourism
import psycopg
import supabase_sync
from dotenv import load_dotenv

load_dotenv()


# table -> SQL expression for the period column
PERIOD_COLUMNS = {
    "gdp_quarterly": "time_period || '-' || quarter",
    "trade_sect_mth": "time_period",
    "cpi_monthly": "time_period",
    "economic_licenses": "year",
    "employment_growth": "year",
    "uae_pmi": "month",
    "job_postings_monthly": "month",
    "oil_production_monthly": "period",
}


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")

    # Latest period already in Supabase per table; None means "use the default start".
    latest: dict[str, str | None] = dict.fromkeys(PERIOD_COLUMNS)
    if database_url:
        with psycopg.connect(database_url) as conn:
            for table, expression in PERIOD_COLUMNS.items():
                latest[table] = supabase_sync.latest_period(conn, table, expression)
    else:
        print("DATABASE_URL not set: fetching from default start dates, no Supabase sync.\n")

    gdp_from = latest["gdp_quarterly"] or gdp.DEFAULT_START
    trade_from = latest["trade_sect_mth"] or foreign_trade.DEFAULT_START
    cpi_from = latest["cpi_monthly"] or cpi.DEFAULT_START
    licenses_from = latest["economic_licenses"]
    licenses_year = int(float(licenses_from)) if licenses_from else licenses.DEFAULT_FROM_YEAR
    employment_from = latest["employment_growth"]
    employment_year = (
        int(float(employment_from)) if employment_from else employment.DEFAULT_FROM_YEAR
    )
    pmi_from = latest["uae_pmi"] or pmi.DEFAULT_START
    jobs_from = latest["job_postings_monthly"] or job_postings.DEFAULT_START
    oil_from = latest["oil_production_monthly"] or oil_prod.DEFAULT_START

    print("--- Fetching GDP data ---")
    gdp.main(start_period=gdp_from)

    print("\n--- Fetching foreign trade data ---")
    foreign_trade.main(start_period=trade_from)

    print("\n--- Fetching CPI data ---")
    cpi.main(start_period=cpi_from)

    print("\n--- Fetching Abu Dhabi economic licenses ---")
    licenses.main(from_year=licenses_year)

    print("\n--- Fetching Abu Dhabi employment growth ---")
    employment.main(from_year=employment_year)

    print("\n--- Fetching UAE Manufacturing PMI ---")
    pmi.main(start_month=pmi_from)

    print("\n--- Fetching UAE job postings ---")
    job_postings.main(start_month=jobs_from)

    print("\n--- Fetching UAE crude oil production ---")
    oil_prod.main(start_month=oil_from)

    print("\n--- Fetching UAE PortWatch port activity ---")
    portwatch.main(refresh=True)

    print("\n--- Fetching Strait of Hormuz PortWatch data ---")
    portwatch_hormuz.main(refresh=True)

    print("\n--- Fetching UAE travel concerns (Google Trends) ---")
    tourism.main(refresh=True)

    if database_url:
        print("\n--- Syncing to Supabase ---")
        supabase_sync.main()


if __name__ == "__main__":
    main()
