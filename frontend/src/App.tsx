import { useEffect, useState, type ReactNode } from 'react'
import './App.css'
import {
  fetchCpi,
  fetchEmploymentGrowth,
  fetchGdp,
  fetchJobPostings,
  fetchLicenses,
  fetchNews,
  fetchOil,
  fetchPmi,
  fetchPorts,
  fetchTourism,
  fetchTrade,
  type CpiPoint,
  type EmploymentGrowthPoint,
  type GdpPoint,
  type JobPostingsPoint,
  type LicensePoint,
  type NewsPayload,
  type OilPoint,
  type PmiPoint,
  type PortsPayload,
  type TradePoint,
  type TravelConcernsPayload,
} from './api'
import { formatPercent, formatValue } from './format'
import { CpiChart } from './CpiChart'
import { EmploymentGrowthChart } from './EmploymentGrowthChart'
import { GdpCompareChart } from './GdpCompareChart'
import { LicensesChart } from './LicensesChart'
import { PortsTradePanel } from './PortsTradePanel'
import { buildRecoveryIndex } from './recoveryIndex'
import { SimpleLineChart } from './SimpleLineChart'
import { buildTradeSlices, TradeCompositionPie } from './TradeCompositionPie'
import { TrendChart, type ChartType } from './TrendChart'

type OverviewChartId = 'cpi' | 'pmi'

const WAR = {
  label: 'US-Iran war starts (Feb 2026)',
  quarter: '2026-Q1',
  month: '2026-02',
}

const RECOVERY_INFO =
  'How close the UAE economy is to its pre-war normal, where 100 means fully back. ' +
  'Weighted average of five pillars: activity, trade, business, labour, and tourism. ' +
  'Labour and tourism are proxy signals and count at half weight. ' +
  'Each input is scored against the Oct 2025 to Jan 2026 baseline, or the same period ' +
  'in the last pre-war year for seasonal data, and capped at 100. ' +
  'Licenses and employment cover Abu Dhabi only.'

const TOTAL_GDP = 'TOT_GDP'
const NON_OIL_GDP = 'TOT_NO'
const TOTAL_TRADE = 'TTRADE'
const ALL_SECTORS = '_T'
const CPI_ALL = 'ALL'

type SectionId = 'overview' | 'trade-energy' | 'business' | 'labour' | 'tourism'

const NAV: { id: SectionId; title: string; focus: string }[] = [
  {
    id: 'overview',
    title: 'Snapshot',
    focus: 'Economic Health Overview',
  },
  {
    id: 'trade-energy',
    title: 'Trade & energy',
    focus: 'Are trade routes holding up?',
  },
  {
    id: 'business',
    title: 'Business',
    focus: 'Is private-sector activity recovering?',
  },
  {
    id: 'labour',
    title: 'Labour',
    focus: 'Is hiring picking up again?',
  },
  {
    id: 'tourism',
    title: 'Tourism',
    focus: 'Are travellers still worried about coming to the UAE?',
  },
]

function uniquePairs<T>(rows: T[], pick: (row: T) => [string, string]) {
  return [...new Map(rows.map(pick))]
}

function ChartTypeToggle(props: { value: ChartType; onChange: (value: ChartType) => void }) {
  return (
    <div className="toggle" role="group" aria-label="Chart type">
      <button
        type="button"
        aria-pressed={props.value === 'line'}
        onClick={() => props.onChange('line')}
      >
        Line
      </button>
      <button
        type="button"
        aria-pressed={props.value === 'bar'}
        onClick={() => props.onChange('bar')}
      >
        YoY %
      </button>
    </div>
  )
}

function MetricCard(props: {
  label: string
  display: string
  period?: string
  change?: string
  tone?: 'positive' | 'negative' | ''
  info?: string
  onClick?: () => void
  active?: boolean
  hint?: string
}) {
  const interactive = Boolean(props.onClick)
  const className = [
    'metric',
    props.tone ?? '',
    interactive ? 'metric-clickable' : '',
    props.active ? 'metric-active' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div
      className={className}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      aria-pressed={interactive ? Boolean(props.active) : undefined}
      onClick={props.onClick}
      onKeyDown={
        interactive
          ? (event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                props.onClick?.()
              }
            }
          : undefined
      }
    >
      <p className="metric-label">
        <span>{props.label}</span>
        {props.info ? (
          <span
            className="info-tip"
            tabIndex={0}
            aria-label={props.info}
            onClick={(event) => event.stopPropagation()}
            onKeyDown={(event) => event.stopPropagation()}
          >
            i
            <span className="info-tip-text" role="tooltip">
              {props.info}
            </span>
          </span>
        ) : null}
      </p>
      <p className="metric-value">{props.display}</p>
      {props.change ? <p className="metric-change">{props.change}</p> : null}
      {props.period ? <p className="metric-period">{props.period}</p> : null}
      {props.hint ? <p className="metric-hint">{props.hint}</p> : null}
    </div>
  )
}

function Panel(props: {
  title: string
  note: string
  span2?: boolean
  controls?: ReactNode
  children: ReactNode
}) {
  return (
    <article className={`panel${props.span2 ? ' span-2' : ''}`}>
      <div className="panel-header">
        <div>
          <h3>{props.title}</h3>
          <p>{props.note}</p>
        </div>
        {props.controls}
      </div>
      {props.children}
    </article>
  )
}

function toneOf(value: number | null | undefined) {
  if (value == null) return ''
  if (value < 0) return 'negative'
  if (value > 0) return 'positive'
  return ''
}

/** For metrics where a rise is bad (e.g. travel concern). */
function invertedTone(value: number | null | undefined) {
  if (value == null) return ''
  if (value > 0) return 'negative'
  if (value < 0) return 'positive'
  return ''
}

function App() {
  const [section, setSection] = useState<SectionId>('overview')
  const [gdp, setGdp] = useState<GdpPoint[] | null>(null)
  const [trade, setTrade] = useState<TradePoint[] | null>(null)
  const [licenses, setLicenses] = useState<LicensePoint[] | null>(null)
  const [cpi, setCpi] = useState<CpiPoint[] | null>(null)
  const [pmi, setPmi] = useState<PmiPoint[] | null>(null)
  const [jobs, setJobs] = useState<JobPostingsPoint[] | null>(null)
  const [employment, setEmployment] = useState<EmploymentGrowthPoint[] | null>(null)
  const [oil, setOil] = useState<OilPoint[] | null>(null)
  const [ports, setPorts] = useState<PortsPayload | null>(null)
  const [tourism, setTourism] = useState<TravelConcernsPayload | null>(null)
  const [news, setNews] = useState<NewsPayload | null>(null)
  const [newsError, setNewsError] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [tradeChart, setTradeChart] = useState<ChartType>('line')
  const [tradeFlow, setTradeFlow] = useState(TOTAL_TRADE)
  const [tradeSector, setTradeSector] = useState(ALL_SECTORS)
  const [overviewChart, setOverviewChart] = useState<OverviewChartId | null>(null)

  const toggleOverviewChart = (id: OverviewChartId) => {
    setOverviewChart((current) => (current === id ? null : id))
  }

  useEffect(() => {
    Promise.all([
      fetchGdp(),
      fetchTrade(),
      fetchLicenses(),
      fetchCpi(),
      fetchPmi(),
      fetchJobPostings(),
      fetchEmploymentGrowth(),
      fetchOil(),
      fetchPorts(),
      fetchTourism(),
    ])
      .then(
        ([
          gdpRows,
          tradeRows,
          licenseRows,
          cpiRows,
          pmiRows,
          jobRows,
          employmentRows,
          oilRows,
          portsPayload,
          tourismPayload,
        ]) => {
          setGdp(gdpRows)
          setTrade(tradeRows)
          setLicenses(licenseRows)
          setCpi(cpiRows)
          setPmi(pmiRows)
          setJobs(jobRows)
          setEmployment(employmentRows)
          setOil(oilRows)
          setPorts(portsPayload)
          setTourism(tourismPayload)
        },
      )
      .catch((err: Error) => setError(err.message))

    fetchNews()
      .then(setNews)
      .catch((err: Error) => setNewsError(err.message))
  }, [])

  if (error) {
    return (
      <div className="status">
        <h1>Economic Recovery Tracker</h1>
        <p>Could not load data: {error}</p>
      </div>
    )
  }

  if (
    !gdp ||
    !trade ||
    !licenses ||
    !cpi ||
    !pmi ||
    !jobs ||
    !employment ||
    !oil ||
    !ports ||
    !tourism
  ) {
    return (
      <div className="status">
        <h1>Economic Recovery Tracker</h1>
        <p>Loading the latest indicators…</p>
      </div>
    )
  }

  const licenseEmirate = licenses[0]?.emirate ?? 'Abu Dhabi'

  const totalGdp = gdp
    .filter((row) => row.sector === TOTAL_GDP)
    .map((row) => ({ ...row, value: row.value / 1_000 }))
  const nonOilGdp = gdp
    .filter((row) => row.sector === NON_OIL_GDP)
    .map((row) => ({ ...row, value: row.value / 1_000 }))
  const latestTotal = totalGdp.at(-1) ?? null
  const latestNonOil = nonOilGdp.at(-1) ?? null

  const gdpCompare = totalGdp
    .filter((row) => row.period >= '2024')
    .map((row) => {
      const nonOil = nonOilGdp.find((point) => point.period === row.period)
      return {
        period: row.period,
        total: row.value,
        nonOil: nonOil?.value ?? null,
      }
    })

  const tradeFlows = uniquePairs(trade, (row) => [row.trade_type, row.trade_type_name]).sort(
    ([a], [b]) => Number(b === TOTAL_TRADE) - Number(a === TOTAL_TRADE),
  )
  const tradeSectors = uniquePairs(trade, (row) => [
    row.sector,
    row.sector === ALL_SECTORS ? 'All sectors' : row.sector_name,
  ]).sort(([a], [b]) => (a === ALL_SECTORS ? -1 : b === ALL_SECTORS ? 1 : Number(a) - Number(b)))
  const tradeSeries = trade
    .filter(
      (row) =>
        row.trade_type === tradeFlow &&
        row.sector === tradeSector &&
        row.period >= '2024',
    )
    .map((row) => ({ ...row, value: row.value / 1_000_000_000 }))
  const totalTrade = trade
    .filter((row) => row.trade_type === TOTAL_TRADE && row.sector === ALL_SECTORS)
    .map((row) => ({ ...row, value: row.value / 1_000_000_000 }))
  const latestTrade = totalTrade.at(-1) ?? null

  // At-a-glance mix uses Total Trade for the latest complete month.
  const tradePiePeriod = [...trade]
    .filter((row) => row.trade_type === TOTAL_TRADE && row.sector !== ALL_SECTORS)
    .map((row) => row.period)
    .sort()
    .at(-1) ?? null
  const tradePieSlices = tradePiePeriod
    ? buildTradeSlices(
        trade.filter(
          (row) => row.trade_type === TOTAL_TRADE && row.period === tradePiePeriod,
        ),
        5,
      )
    : []
  const tradeFlowName =
    tradeFlows.find(([code]) => code === tradeFlow)?.[1] ?? tradeFlow

  const cpiAll = cpi.filter((row) => row.division === CPI_ALL)
  const cpiChartSeries = cpiAll.filter((row) => row.period >= '2024')
  const latestYoy = [...cpiAll].reverse().find((row) => row.yoy !== null) ?? null
  const latestPmi = pmi.at(-1) ?? null
  const prevPmi = pmi.length >= 2 ? pmi.at(-2) : null
  const latestOil = oil.at(-1) ?? null
  const latestJobs = jobs.at(-1) ?? null
  const prevJobs = jobs.length >= 2 ? jobs.at(-2) : null
  const latestEmployment = employment.at(-1) ?? null
  const prevEmployment = employment.length >= 2 ? employment.at(-2) : null
  const employmentQoQ =
    latestEmployment && prevEmployment
      ? latestEmployment.total - prevEmployment.total
      : null
  const latestLicenses = licenses.at(-1) ?? null
  const prevLicenses = licenses.length >= 2 ? licenses.at(-2) : null

  const pctDelta = (current: number | null | undefined, previous: number | null | undefined) => {
    if (current == null || previous == null || previous === 0) return null
    return ((current - previous) / previous) * 100
  }

  // Latest available of each: AD employment YoY (quarterly) + UAE job-postings MoM (monthly).
  const employmentYoY = latestEmployment?.total ?? null
  const hiringMom = pctDelta(latestJobs?.new_jobs, prevJobs?.new_jobs)
  const labourRecoveryScore =
    employmentYoY != null && hiringMom != null
      ? 0.6 * employmentYoY + 0.4 * hiringMom
      : null

  const pmiMovement = pctDelta(latestPmi?.pmi, prevPmi?.pmi)
  const newLicenseGrowth = pctDelta(latestLicenses?.new_licenses, prevLicenses?.new_licenses)
  const renewedLicenseGrowth = pctDelta(
    latestLicenses?.renewed_licenses,
    prevLicenses?.renewed_licenses,
  )
  const businessParts = [pmiMovement, newLicenseGrowth, renewedLicenseGrowth].filter(
    (value): value is number => value != null,
  )
  const businessComposite =
    businessParts.length > 0
      ? businessParts.reduce((sum, value) => sum + value, 0) / businessParts.length
      : null

  const recovery = buildRecoveryIndex({
    nonOilGdp,
    totalTrade,
    ports,
    pmi,
    licenses,
    employment,
    tourism,
  })
  const missingInputs = recovery.pillars.flatMap((pillar) =>
    pillar.inputs.filter((input) => input.score == null).map((input) => input.label),
  )

  const nameOf = (pairs: [string, string][], code: string) =>
    pairs.find(([pairCode]) => pairCode === code)?.[1] ?? code

  const active = NAV.find((item) => item.id === section) ?? NAV[0]

  return (
    <div className="dashboard">
      <header className="topbar">
        <div className="topbar-brand">
          <h1>Economic Recovery Tracker</h1>
          <p className="topbar-meta">
            UAE recovery after the US-Iran conflict · war start February 2026
          </p>
        </div>
        <nav className="topnav" aria-label="Recovery areas">
          {NAV.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-current={section === item.id ? 'page' : undefined}
              onClick={() => setSection(item.id)}
            >
              {item.title}
            </button>
          ))}
        </nav>
      </header>

      <main className="main">
        <div className="page-header">
          <p className="page-focus">{active.focus}</p>
          {section === 'trade-energy' ? (
            <p className="page-baseline">
              Baseline: Oct 2025 to Jan 2026 (pre-war)
            </p>
          ) : null}
        </div>

        {section === 'overview' ? (
          <div className="overview-layout">
            <div className="overview-main">
              <section className="recovery-lead">
                <div className="recovery-lead-copy">
                  <p className="recovery-lead-label">
                    <span>Recovery index</span>
                    <span className="info-tip" tabIndex={0} aria-label={RECOVERY_INFO}>
                      i
                      <span className="info-tip-text" role="tooltip">
                        {RECOVERY_INFO}
                      </span>
                    </span>
                  </p>
                  <p className="recovery-lead-value">
                    {recovery.score == null ? '—' : Math.round(recovery.score)}
                    {recovery.score == null ? null : (
                      <span className="recovery-lead-scale"> / 100</span>
                    )}
                  </p>
                  <p className="recovery-lead-note">
                    100 = pre-war normal
                    {missingInputs.length > 0 ? (
                      <span className="recovery-lead-missing">
                        {' '}
                        · Excludes {missingInputs.join(', ')} (no data)
                      </span>
                    ) : null}
                  </p>
                </div>
                <dl className="recovery-pillars">
                  {recovery.pillars.map((pillar) => (
                    <div
                      key={pillar.label}
                      title={
                        pillar.inputs
                          .map(
                            (input) =>
                              `${input.label} ${input.score == null ? 'no data' : Math.round(input.score)}`,
                          )
                          .join(' · ') + (pillar.proxy ? ' · proxy signal, half weight' : '')
                      }
                    >
                      <dt>
                        {pillar.label}
                        {pillar.proxy ? <span className="recovery-pillar-proxy">proxy</span> : null}
                      </dt>
                      <dd className="recovery-pillar-score">
                        {pillar.score == null ? '—' : Math.round(pillar.score)}
                      </dd>
                      <dd className="recovery-pillar-date">{pillar.asOf ?? 'No data'}</dd>
                    </div>
                  ))}
                </dl>
              </section>

              <section className="overview-block">
                <h2 className="overview-block-title">Key indicators</h2>
                <div className="kpi-grid kpi-grid-headline">
                  <MetricCard
                    label="GDP"
                    display={latestTotal ? `${formatValue(latestTotal.value)} bn` : '—'}
                    change={
                      latestTotal?.growth == null
                        ? undefined
                        : `${formatPercent(latestTotal.growth)} YoY`
                    }
                    period={latestTotal ? `${latestTotal.period} · AED` : undefined}
                    tone={toneOf(latestTotal?.growth)}
                  />
                  <MetricCard
                    label="Non-oil GDP"
                    display={latestNonOil ? `${formatValue(latestNonOil.value)} bn` : '—'}
                    change={
                      latestNonOil?.growth == null
                        ? undefined
                        : `${formatPercent(latestNonOil.growth)} YoY`
                    }
                    period={latestNonOil ? `${latestNonOil.period} · AED` : undefined}
                    tone={toneOf(latestNonOil?.growth)}
                  />
                  <MetricCard
                    label="Inflation (YoY)"
                    display={latestYoy?.yoy == null ? '—' : formatPercent(latestYoy.yoy)}
                    period={latestYoy?.period}
                    tone={invertedTone(latestYoy?.yoy)}
                    onClick={() => toggleOverviewChart('cpi')}
                    active={overviewChart === 'cpi'}
                    hint={overviewChart === 'cpi' ? 'Hide chart' : 'Click for chart'}
                  />
                  <MetricCard
                    label="Manufacturing PMI"
                    display={latestPmi ? formatValue(latestPmi.pmi) : '—'}
                    period={latestPmi ? `${latestPmi.period} · 50 = expansion` : undefined}
                    tone={latestPmi ? (latestPmi.pmi >= 50 ? 'positive' : 'negative') : ''}
                    onClick={() => toggleOverviewChart('pmi')}
                    active={overviewChart === 'pmi'}
                    hint={overviewChart === 'pmi' ? 'Hide chart' : 'Click for chart'}
                  />
                  <MetricCard
                    label="New licenses (Abu Dhabi)"
                    display={
                      latestLicenses ? formatValue(latestLicenses.new_licenses) : '—'
                    }
                    period={latestLicenses?.period}
                  />
                  <MetricCard
                    label="Total trade"
                    display={latestTrade ? `${formatValue(latestTrade.value)} bn` : '—'}
                    change={
                      latestTrade?.growth == null
                        ? undefined
                        : `${formatPercent(latestTrade.growth)} YoY`
                    }
                    period={latestTrade ? `${latestTrade.period} · AED` : undefined}
                    tone={toneOf(latestTrade?.growth)}
                  />
                </div>
                {overviewChart === 'cpi' ? (
                  <Panel
                    title="Inflation"
                    note="Overall CPI · YoY and MoM % · FCSC · from 2024"
                  >
                    {cpiChartSeries.some((row) => row.yoy != null || row.mom != null) ? (
                      <CpiChart
                        data={cpiChartSeries}
                        eventPeriod={WAR.month}
                        eventLabel={WAR.label}
                      />
                    ) : (
                      <p className="note">No CPI series yet.</p>
                    )}
                  </Panel>
                ) : null}
                {overviewChart === 'pmi' ? (
                  <Panel title="Manufacturing PMI" note="Monthly index · 50 = expansion">
                    {pmi.length > 0 ? (
                      <SimpleLineChart
                        data={pmi.map((row) => ({ period: row.period, value: row.pmi }))}
                        eventPeriod={WAR.month}
                        eventLabel={WAR.label}
                        guideValue={50}
                        guideLabel="50"
                        valueLabel="PMI"
                      />
                    ) : (
                      <p className="note">No PMI data yet.</p>
                    )}
                  </Panel>
                ) : null}
              </section>

              <section className="overview-block">
                <Panel
                  title="GDP trend"
                  note="Total vs non-oil · constant prices · AED billion · from 2024"
                >
                  {gdpCompare.length > 0 ? (
                    <GdpCompareChart
                      data={gdpCompare}
                      eventPeriod={WAR.quarter}
                      eventLabel={WAR.label}
                    />
                  ) : (
                    <p className="note">No GDP data yet.</p>
                  )}
                </Panel>
              </section>
            </div>

            <aside className="news-rail" aria-label="Latest news">
              <div className="news-rail-header">
                <h2>In the news</h2>
                <p></p>
              </div>
              {newsError ? (
                <p className="note">Could not load headlines.</p>
              ) : !news ? (
                <p className="note">Loading headlines…</p>
              ) : news.items.length === 0 ? (
                <p className="note">No recent headlines.</p>
              ) : (
                <ul className="news-list">
                  {news.items.map((item) => (
                    <li key={item.url}>
                      <p className="news-topic">{item.topic}</p>
                      <a href={item.url} target="_blank" rel="noreferrer">
                        {item.title}
                      </a>
                      <p className="news-meta">
                        {[
                          item.source || null,
                          item.published
                            ? new Date(item.published).toLocaleDateString(undefined, {
                                month: 'short',
                                day: 'numeric',
                              })
                            : null,
                        ]
                          .filter(Boolean)
                          .join(' · ')}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
              <p className="news-source">Google News</p>
            </aside>
          </div>
        ) : null}

        {section === 'trade-energy' ? (
          <>
            <div className="trade-glance">
              <MetricCard
                label="Crude oil production"
                display={latestOil ? `${formatValue(latestOil.production)} kbpd` : '—'}
                change={
                  latestOil?.mom == null
                    ? undefined
                    : `${formatPercent(latestOil.mom)} MoM`
                }
                period={latestOil?.period}
                tone={toneOf(latestOil?.mom)}
              />
              <MetricCard
                label="Gulf of Oman ports"
                display={
                  ports.insights.green_avg_calls_vs_baseline == null
                    ? '—'
                    : formatPercent(ports.insights.green_avg_calls_vs_baseline, 1)
                }
                change="Ship volumes vs baseline"
                period="Fujairah · Khor Fakkan"
                tone={toneOf(ports.insights.green_avg_calls_vs_baseline)}
                info={
                  'UAE ports are split by coastline relative to the Strait of Hormuz. ' +
                  'Gulf of Oman-facing ports (green: Fujairah and Khor Fakkan) sit outside the strait ' +
                  'and can still reach open ocean if Hormuz is disrupted. ' +
                  'Persian Gulf-facing ports (red: e.g. Jebel Ali, Khalifa, Abu Dhabi) sit inside the Gulf ' +
                  'and rely on Hormuz for ocean access. This KPI is the average change in ship volumes ' +
                  'at Fujairah and Khor Fakkan versus the baseline.'
                }
              />
              <MetricCard
                label="Strait of Hormuz"
                display={
                  ports.hormuz?.pct_of_baseline == null
                    ? '—'
                    : ports.hormuz.pct_of_baseline >= 100
                      ? `${(ports.hormuz.pct_of_baseline - 100).toFixed(0)}% above baseline`
                      : `${(100 - ports.hormuz.pct_of_baseline).toFixed(0)}% below baseline`
                }
                change={
                  ports.hormuz?.mom == null
                    ? undefined
                    : `${formatPercent(ports.hormuz.mom, 1)} vs last month`
                }
                period="vs baseline"
                tone={toneOf(
                  ports.hormuz?.pct_of_baseline == null
                    ? null
                    : ports.hormuz.pct_of_baseline - 100,
                )}
              />
              <aside className="trade-glance-pie" aria-label="Trade mix at a glance">
                <div className="trade-glance-pie-header">
                  <h3>
                    <span>Trade mix</span>
                    <span
                      className="info-tip"
                      tabIndex={0}
                      aria-label={
                        tradePiePeriod
                          ? `Shows sector shares for the latest complete month of FCSC total merchandise trade (${tradePiePeriod}). This is monthly data, not daily.`
                          : 'Shows sector shares for the latest complete month of FCSC total merchandise trade. This is monthly data, not daily.'
                      }
                    >
                      i
                      <span className="info-tip-text" role="tooltip">
                        {tradePiePeriod
                          ? `Shows sector shares for the latest complete month of FCSC total merchandise trade (${tradePiePeriod}). This is monthly data, not daily.`
                          : 'Shows sector shares for the latest complete month of FCSC total merchandise trade. This is monthly data, not daily.'}
                      </span>
                    </span>
                  </h3>
                  <p>Total trade · at a glance · non-oil merchandise</p>
                </div>
                {tradePiePeriod && tradePieSlices.length > 0 ? (
                  <TradeCompositionPie data={tradePieSlices} period={tradePiePeriod} />
                ) : (
                  <p className="note">No sector mix for the latest month.</p>
                )}
              </aside>
            </div>
            <div className="chart-grid">
              <PortsTradePanel data={ports} />
              <Panel
                title="Monthly foreign trade"
                note={`${tradeFlowName} · ${nameOf(tradeSectors, tradeSector)} · AED bn · from 2024`}
                span2
                controls={
                  <div className="controls">
                    <ChartTypeToggle value={tradeChart} onChange={setTradeChart} />
                    <label>
                      Flow
                      <select
                        value={tradeFlow}
                        onChange={(event) => setTradeFlow(event.target.value)}
                      >
                        {tradeFlows.map(([code, name]) => (
                          <option key={code} value={code}>
                            {name}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                }
              >
                {tradeSeries.length > 0 ? (
                  <TrendChart
                    data={tradeSeries}
                    type={tradeChart}
                    eventPeriod={WAR.month}
                    eventLabel={WAR.label}
                  />
                ) : (
                  <p className="note">No data for this flow and sector.</p>
                )}
                <details className="trade-sectors">
                  <summary>
                    Sector filter · {nameOf(tradeSectors, tradeSector)}
                  </summary>
                  <div className="chips" role="group" aria-label="Sector">
                    {tradeSectors.map(([code, name]) => (
                      <button
                        key={code}
                        type="button"
                        aria-pressed={tradeSector === code}
                        onClick={() => setTradeSector(code)}
                      >
                        {name}
                      </button>
                    ))}
                  </div>
                </details>
              </Panel>
              <Panel title="Crude oil production" note="Thousand barrels per day · EIA" span2>
                {oil.length > 0 ? (
                  <SimpleLineChart
                    data={oil.map((row) => ({ period: row.period, value: row.production }))}
                    eventPeriod={WAR.month}
                    eventLabel={WAR.label}
                    valueLabel="Production (kbpd)"
                  />
                ) : (
                  <p className="note">No oil production data yet.</p>
                )}
                <p className="note">Source: U.S. Energy Information Administration (EIA).</p>
              </Panel>
            </div>
          </>
        ) : null}

        {section === 'business' ? (
          <>
            <div className="kpi-grid">
              <MetricCard
                label="Business momentum"
                display={
                  businessComposite == null
                    ? '—'
                    : businessComposite === 0
                      ? 'Unchanged'
                      : `${businessComposite > 0 ? 'Up' : 'Down'} ${Math.abs(businessComposite).toFixed(1)}%`
                }
                change={[
                  pmiMovement == null ? null : `PMI ${formatPercent(pmiMovement, 1)}`,
                  newLicenseGrowth == null
                    ? null
                    : `New licenses ${formatPercent(newLicenseGrowth, 1)}`,
                  renewedLicenseGrowth == null
                    ? null
                    : `Renewals ${formatPercent(renewedLicenseGrowth, 1)}`,
                ]
                  .filter(Boolean)
                  .join(' · ')}
                tone={toneOf(businessComposite)}
                info={
                  'Business momentum is a simple equal-weight average of three latest growth rates: ' +
                  '(1) Manufacturing PMI month-on-month % change, ' +
                  '(2) Abu Dhabi new economic licences quarter-on-quarter % change, and ' +
                  '(3) renewed licences quarter-on-quarter % change. ' +
                  'Each available component is weighted the same; missing components are skipped. ' +
                  'A rise means business conditions are improving on average across these signals; ' +
                  'a fall means they are weakening. PMI is monthly; licences are quarterly, so the ' +
                  'composite uses the latest available reading of each.'
                }
              />
              <MetricCard
                label="Renewed licenses"
                display={
                  latestLicenses ? formatValue(latestLicenses.renewed_licenses) : '—'
                }
                period={latestLicenses?.period}
              />
            </div>
            <div className="chart-grid">
              <Panel
                title={`Economic licenses · ${licenseEmirate}`}
                note="New and renewed · quarterly"
              >
                {licenses.length > 0 ? (
                  <LicensesChart
                    data={licenses}
                    eventPeriod={WAR.quarter}
                    eventLabel={WAR.label}
                  />
                ) : (
                  <p className="note">No license data yet.</p>
                )}
                <p className="note">Source: SCAD.</p>
              </Panel>
              <Panel title="Manufacturing PMI" note="Monthly index · 50 = expansion">
                {pmi.length > 0 ? (
                  <SimpleLineChart
                    data={pmi.map((row) => ({ period: row.period, value: row.pmi }))}
                    eventPeriod={WAR.month}
                    eventLabel={WAR.label}
                    guideValue={50}
                    guideLabel="50"
                    valueLabel="PMI"
                  />
                ) : (
                  <p className="note">No PMI data yet.</p>
                )}
              </Panel>
            </div>
          </>
        ) : null}

        {section === 'labour' ? (
          <>
            <div className="kpi-grid">
              <MetricCard
                label="Labour market recovery"
                display={
                  labourRecoveryScore == null
                    ? '—'
                    : labourRecoveryScore === 0
                      ? 'Unchanged'
                      : `${labourRecoveryScore > 0 ? 'Up' : 'Down'} ${Math.abs(labourRecoveryScore).toFixed(1)}%`
                }
                change={[
                  employmentYoY == null
                    ? null
                    : `Employment ${formatPercent(employmentYoY, 1)} (${latestEmployment?.period})`,
                  hiringMom == null
                    ? null
                    : `Hiring ${formatPercent(hiringMom, 1)} (${latestJobs?.period})`,
                ]
                  .filter(Boolean)
                  .join(' · ')}
                period="60% Abu Dhabi employment · 40% UAE hiring"
                tone={toneOf(labourRecoveryScore)}
                info={
                  'Simple weighted average of two latest growth rates: ' +
                  '60% Abu Dhabi employed-residents growth vs the same quarter last year, and ' +
                  '40% month-on-month change in new UAE job postings. ' +
                  'Geography and timing differ (emirate quarterly vs national monthly), so each uses its latest available reading. ' +
                  'A rise means the blended labour signal is improving; a fall means it is softening.'
                }
              />
              <MetricCard
                label="Employed residents growth"
                display={
                  latestEmployment ? formatPercent(latestEmployment.total, 1) : '—'
                }
                change={
                  employmentQoQ == null
                    ? undefined
                    : `${employmentQoQ > 0 ? '+' : ''}${employmentQoQ.toFixed(1)} pp vs prior quarter`
                }
                period={
                  latestEmployment
                    ? `${latestEmployment.emirate} · ${latestEmployment.period}`
                    : undefined
                }
                tone={toneOf(latestEmployment?.total)}
                info={
                  'SCAD growth rate of employed residents in Abu Dhabi versus the same quarter ' +
                  'a year earlier (Total). Positive means employment is higher than a year ago. ' +
                  'Source: Statistics Centre - Abu Dhabi labour-force key statistics.'
                }
              />
              <MetricCard
                label="New job postings"
                display={latestJobs ? formatValue(latestJobs.new_jobs) : '—'}
                period={latestJobs?.period}
              />
            </div>
            <div className="chart-grid">
              <Panel
                title="Employed residents growth"
                note="Abu Dhabi · YoY % · by gender · SCAD"
                span2
              >
                {employment.length > 0 ? (
                  <EmploymentGrowthChart
                    data={employment}
                    eventPeriod={WAR.quarter}
                    eventLabel={WAR.label}
                  />
                ) : (
                  <p className="note">No employment-growth data yet.</p>
                )}
                <p className="note">
                  Growth rate of employed residents vs the same quarter last year.
                  Source: SCAD labour force (
                  <a
                    href="https://scad.gov.ae/labor-force?ThemeID=224&tab=KSI&IndicatorID=8585"
                    target="_blank"
                    rel="noreferrer"
                  >
                    indicator 8585
                  </a>
                  ).
                </p>
              </Panel>
              <Panel title="Job postings" note="New UAE job postings · monthly" span2>
                {jobs.length > 0 ? (
                  <SimpleLineChart
                    data={jobs.map((row) => ({ period: row.period, value: row.new_jobs }))}
                    eventPeriod={WAR.month}
                    eventLabel={WAR.label}
                    valueLabel="New jobs"
                  />
                ) : (
                  <p className="note">No job-postings data yet.</p>
                )}
              </Panel>
            </div>
          </>
        ) : null}

        {section === 'tourism' ? (
          <>
            <div className="kpi-grid">
              <MetricCard
                label="Travel concern"
                display={
                  tourism.mom == null
                    ? '—'
                    : tourism.mom === 0
                      ? 'Unchanged'
                      : `${tourism.mom > 0 ? 'Up' : 'Down'} ${Math.abs(tourism.mom).toFixed(1)}%`
                }
                change={
                  tourism.yoy == null
                    ? undefined
                    : `${formatPercent(tourism.yoy, 1)} vs same month last year`
                }
                period={`${tourism.latest_month} · vs prior month`}
                tone={invertedTone(tourism.mom)}
                info={
                  `Travel concern tracks Google search interest in UAE/Dubai safety, travel warnings, ` +
                  `flight disruption and trip cancellations. Each keyword is indexed to its own average, ` +
                  `capped, then averaged into one index (average complete month = 100). ` +
                  `The % shown compares the latest complete month with the previous month using a ` +
                  `${tourism.smooth_months}-month rolling average to reduce noise. ` +
                  `A rise means more concern (shown in red); a fall means less concern (green). ` +
                  `This is relative search interest, not search counts.`
                }
              />
            </div>
            <div className="chart-grid">
              <Panel
                title="Travel concern search interest"
                note={`${tourism.unit} · ${tourism.smooth_months}-month average`}
                span2
              >
                {tourism.series.some((row) => row.smooth != null) ? (
                  <SimpleLineChart
                    data={tourism.series
                      .filter((row) => row.smooth != null)
                      .map((row) => ({ period: row.period, value: row.smooth as number }))}
                    eventPeriod={WAR.month}
                    eventLabel={WAR.label}
                    guideValue={100}
                    guideLabel="100 = average"
                    valueLabel="Concern index"
                  />
                ) : (
                  <p className="note">No travel-concern series yet.</p>
                )}
                <p className="note">
                  Source: Google Trends. Terms included: {tourism.included.join(', ')}.
                  {tourism.excluded.length
                    ? ` Left out (too sparse): ${tourism.excluded.join(', ')}.`
                    : ''}
                </p>
              </Panel>
            </div>
          </>
        ) : null}
      </main>
    </div>
  )
}

export default App
