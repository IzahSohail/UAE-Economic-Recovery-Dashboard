# Economic Recovery Dashboard

UAE recovery monitor after the US-Iran conflict (Feb 2026). FastAPI backend + React/TypeScript frontend, with scrapers that refresh local files and upsert into Supabase.

## Codebase structure

```
backend/
  app/           FastAPI API (reads Supabase + local PortWatch/tourism caches)
  scripts/       Data fetchers + sync_data.py / supabase_sync.py
frontend/        Vite + React dashboard
data/            Local scrape outputs (CSVs / JSON) before or alongside DB sync
```

- `**backend/app**` – HTTP API the UI calls (`/api/gdp`, `/api/trade`, `/api/ports`, etc.).
- `**backend/scripts**` – One script per source; `sync_data.py` runs them in order then pushes CSVs to Supabase.
- `**frontend**` – Dashboard sections: Snapshot, Trade & energy, Business, Labour, Tourism.
- `**data/**` – Working copies of scraped series. Scripts write here first. Most metrics are also upserted to Supabase; PortWatch and travel concerns are read from JSON files by the API.

### Why `data/`?

Currently, I am working with some limited access APIs and scrapers which can be flaky. Keeping files under `data/` means you can re-sync the DB without re-scraping everything, inspect raw outputs, and keep a backup for sources that only return recent values (e.g. PMI).

## Data sources

| Metric | Source |
|---|---|
| GDP (total / non-oil) | FCSC / UAE.Stat (SDMX) |
| Foreign trade (flows, sectors, mix) | FCSC / UAE.Stat (SDMX) |
| CPI / inflation | FCSC / UAE.Stat (SDMX) |
| Abu Dhabi new & renewed economic licenses | SCAD |
| Employed-residents growth (Abu Dhabi, by gender) | SCAD labour force KSI |
| Manufacturing PMI | Trading Economics (scraped news); history filled via `data/uae_pmi.csv` |
| New job postings (UAE) | jobdatafeeds.com |
| Crude oil production | EIA Open Data API |
| UAE port activity (ship calls, tonnage) | IMF PortWatch (ArcGIS) |
| Strait of Hormuz throughput | IMF PortWatch chokepoints |
| Travel concern index | Google Trends |
| Snapshot news rail | Google News RSS (US-Iran war, UAE economy) |

Composites (Recovery index, Business momentum, Labour market recovery) are calculated in the frontend from these series.

## Recovery index

The index answers: **How close is the UAE economy to its pre-war normal?** A score of 100 means fully back to normal. Activity, trade, business, labour, and tourism inputs are normalised against the Oct 2025–Jan 2026 baseline, or the same period in the last pre-war year for seasonal data, and capped at 100 so strength in one area cannot hide weakness in another.

Activity, trade, and business receive full weight. Labour and tourism receive half weight and are labelled as proxies because their available signals are thinner/brittle: Abu Dhabi employment only until April '26 and Google Trends travel concern. CPI and job postings are shown in the dashboard but excluded from the index because inflation has no unambiguous recovery direction and job-posting source coverage changes over time.

## Supabase

- Postgres is the store for tabular series (GDP, trade, CPI, licenses, employment, PMI, jobs, oil).
- `backend/scripts/supabase_sync.py` creates tables if needed and upserts from `data/*.csv` using unique keys.
- The API connects with `DATABASE_URL` (session pooler connection string). If it is not set, the API serves the same series from `data/*.csv` instead, so the dashboard runs without Supabase.
- `sync_data.py` also runs without `DATABASE_URL`: it fetches every source from its default start date, rewrites the CSVs in `data/`, and skips the Supabase upsert.
- PortWatch and tourism stay as local JSON under `data/` (not synced to Supabase).

## `.env` (project root)

```bash
DATABASE_URL=postgresql://...   # Supabase Postgres (session pooler); optional, API falls back to data/*.csv
EIA_API_KEY=...                 # EIA Open Data key (oil production)
```

## How to run

From the project root:

```bash
# Python env (once)
python3 -m venv .venv
source .venv/bin/activate
pip install -e backend
.venv/bin/playwright install chromium   # for FCSC scrapers

# Refresh data → data/ → Supabase (Supabase step is skipped if DATABASE_URL is not set)
.venv/bin/python backend/scripts/sync_data.py

# API
fastapi dev backend/app/main.py
# → http://localhost:8000  · docs at /docs
```

Frontend (separate terminal):

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

Useful single-source refreshes:

```bash
.venv/bin/python backend/scripts/portwatch.py --refresh
.venv/bin/python backend/scripts/portwatch_hormuz.py --refresh
.venv/bin/python backend/scripts/tourism.py --refresh
.venv/bin/python backend/scripts/supabase_sync.py
```

## Key decisions and tradeoffs

**Tourism / aviation vs brittle indicators.**  
Trade (Strait of Hormuz) and tourism/aviation were the two shock channels worth covering for this shock. Aviation volumes (flights, departures/arrivals) are not available from a free API. Official tourism stats are mostly annual; high-frequency visitor or hotel occupancy series are not freely available at UAE scale (only sparse one-off sources, e.g. very limited Abu Dhabi occupancy). Those figures do appear in PDFs/reports. Rather than wire brittle one-off scrapes, the approach for reports would be an agent later, which seems out of scope at this stage due to time restriction. So tourism is represented only by a **travel-concern** index from Google Trends. Other Trends ideas (e.g. “Dubai holiday” demand) were rejected after inspection: they spiked in March right after the war started and would have added noise, not a clean recovery signal.

**Ports get more depth.**  
With aviation unavailable and tourism thin, PortWatch is the place for granular shock/recovery work: Oman-facing vs Persian Gulf ports, Hormuz capacity, baseline vs war windows, and recovery from early war to the latest period.

**Job postings as a free labour pulse.**  
UAE new postings are scraped from a public site. With a paid jobs API you could break this down by sector and get more actionable labour insights; the scrape is a demo-friendly proxy.

**Sync without Supabase rewrites the CSVs (to improve).**  
Incremental updates rely on Supabase: `sync_data.py` asks it for the latest stored period and only fetches from there. Without `DATABASE_URL` there is nothing to resume from, so each run refetches the full history and overwrites the CSVs. That is fine at this stage but not for routine updates. The fix woudl be tp have each fetcher read the latest period from its own CSV and merge new rows into it (as the PMI and oil scripts already do), so local files are updated rather than rewritten.

**PMI via Trading Economics.**  
No PMI API access, so values are scraped from Trading Economics news pages, which mainly expose recent months. `data/uae_pmi.csv` holds the longer history so the dashboard stays complete when the scrape only fills the latest gaps.
