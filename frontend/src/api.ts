export type SeriesPoint = {
  period: string
  value: number
  growth: number | null
}

export type GdpPoint = SeriesPoint & {
  sector: string
  sector_name: string
}

export type TradePoint = GdpPoint & {
  trade_type: string
  trade_type_name: string
}

export type LicensePoint = {
  period: string
  emirate: string
  new_licenses: number
  renewed_licenses: number
}

export type CpiPoint = {
  period: string
  division: string
  division_name: string
  yoy: number | null
  mom: number | null
  index: number | null
}

export type PmiPoint = {
  period: string
  pmi: number
}

export type JobPostingsPoint = {
  period: string
  new_jobs: number
  sources: number | null
}

export type EmploymentGrowthPoint = {
  period: string
  emirate: string
  total: number
  male: number | null
  female: number | null
}

export type OilPoint = {
  period: string
  production: number
  mom: number | null
}

export type PortMetric = {
  baseline_daily: number | null
  war_daily: number | null
  baseline_month: number | null
  war_month: number | null
  pct_vs_baseline: number | null
}

export type PortMonthly = {
  period: string
  calls: number
  import: number
  export: number
}

export type PortPoint = {
  id: string
  name: string
  emirate: string
  note: string
  zone: 'green' | 'red'
  lat: number | null
  lon: number | null
  share_import: number | null
  share_export: number | null
  industries: string[]
  metrics: {
    calls: PortMetric
    import: PortMetric
    export: PortMetric
  }
  calls_vs_baseline: number | null
  tons_vs_baseline: number | null
  recovery_calls: number | null
  recovery_tons: number | null
  baseline_calls_daily: number | null
  monthly: PortMonthly[]
}

export type PortsPayload = {
  meta: {
    baseline_start: string
    baseline_end: string
    war_start: string
    early_war_end: string
    recent_start: string
    last: string
    fetched: string | null
    source: string
    green_ports: string[]
    red_ports: string[]
  }
  insights: {
    ports_above_baseline: {
      name: string
      zone: 'green' | 'red'
      calls_vs_baseline: number
    }[]
    any_above_baseline: boolean
    top_recovery: {
      name: string
      zone: 'green' | 'red'
      emirate: string
      recovery_calls: number
      recovery_tons: number | null
      calls_vs_baseline: number | null
      tons_vs_baseline: number | null
      share_import: number | null
      share_export: number | null
      industries: string[]
    } | null
    green_avg_calls_vs_baseline: number | null
    red_avg_calls_vs_baseline: number | null
    green_avg_recovery_calls: number | null
    red_avg_recovery_calls: number | null
    /** Oman-facing ports combined: last 30 days of ship calls as % of baseline. */
    green_calls_pct_of_baseline: number | null
  }
  hormuz: {
    name: string
    pct_of_baseline: number | null
    mom: number | null
    baseline_daily_capacity: number | null
    current_daily_capacity: number | null
    baseline_start: string
    baseline_end: string
    recent_start: string
    last: string
  } | null
  ports: PortPoint[]
}

const API_BASE = 'http://localhost:8000'

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`)
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`)
  }
  return response.json()
}

export const fetchGdp = () => getJson<GdpPoint[]>('/api/gdp')
export const fetchTrade = () => getJson<TradePoint[]>('/api/trade')
export const fetchLicenses = () => getJson<LicensePoint[]>('/api/licenses')
export const fetchCpi = () => getJson<CpiPoint[]>('/api/cpi')
export const fetchPmi = () => getJson<PmiPoint[]>('/api/pmi')
export const fetchJobPostings = () => getJson<JobPostingsPoint[]>('/api/job-postings')
export const fetchEmploymentGrowth = () =>
  getJson<EmploymentGrowthPoint[]>('/api/employment-growth')
export const fetchOil = () => getJson<OilPoint[]>('/api/oil')
export const fetchPorts = () => getJson<PortsPayload>('/api/ports')

export type TravelConcernsPoint = {
  period: string
  index: number | null
  smooth: number | null
  partial: boolean
}

export type TravelConcernsPayload = {
  title: string
  latest_month: string
  latest_period: string
  smooth_months: number
  yoy: number | null
  mom: number | null
  unit: string
  included: string[]
  excluded: string[]
  series: TravelConcernsPoint[]
}

export const fetchTourism = () => getJson<TravelConcernsPayload>('/api/tourism')

export type NewsItem = {
  title: string
  url: string
  source: string
  published: string | null
  topic: string
}

export type NewsPayload = {
  queries: string[]
  items: NewsItem[]
}

export const fetchNews = () => getJson<NewsPayload>('/api/news')
