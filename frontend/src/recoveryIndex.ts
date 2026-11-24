import type {
  EmploymentGrowthPoint,
  LicensePoint,
  PmiPoint,
  PortsPayload,
  TravelConcernsPayload,
} from './api'

// Recovery index: how close the UAE economy is to its pre-war normal (100 = fully back).
// Every input is scored as a percentage of its own pre-war level, then averaged.

const BASELINE_MONTHS = ['2025-10', '2025-11', '2025-12', '2026-01']
const LAST_PREWAR_MONTH = '2026-01'
const LAST_PREWAR_QUARTER = '2025-Q4'
// Above-normal readings count as fully recovered, so a strong input cannot hide a weak one.
const SCORE_CAP = 100
// Proxy pillars rest on one thin, indirect signal, so they count half as much as the others.
const PROXY_WEIGHT = 0.5

type ValuePoint = { period: string; value: number }
type Level = { pct: number; asOf: string } | null

export type RecoveryInput = { label: string; score: number | null; asOf: string | null }
export type RecoveryPillar = RecoveryInput & { inputs: RecoveryInput[]; proxy: boolean }
export type RecoveryIndex = { score: number | null; pillars: RecoveryPillar[] }

const mean = (values: number[]) =>
  values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null

const yearBefore = (period: string) => `${Number(period.slice(0, 4)) - 1}${period.slice(4)}`

/** The same month or quarter in the latest year that falls entirely before the war. */
function preWarPeriod(period: string, lastPreWar: string) {
  let reference = yearBefore(period)
  while (reference > lastPreWar) reference = yearBefore(reference)
  return reference
}

/** Latest reading as % of its Oct 2025 to Jan 2026 average. For series without a seasonal cycle. */
function vsBaseline(points: ValuePoint[]): Level {
  const latest = points.at(-1)
  const baseline = mean(
    points.filter((point) => BASELINE_MONTHS.includes(point.period)).map((point) => point.value),
  )
  if (!latest || !baseline) return null
  return { pct: (latest.value / baseline) * 100, asOf: latest.period }
}

/**
 * Latest `window` periods as % of the same periods in the last pre-war year.
 * For seasonal series, where comparing with Oct to Jan would mistake the season for the war.
 */
function vsPreWarYear(points: ValuePoint[], lastPreWar: string, window = 1): Level {
  const recent = points.slice(-window)
  const latest = recent.at(-1)
  if (!latest) return null
  const byPeriod = new Map(points.map((point) => [point.period, point.value]))
  let current = 0
  let reference = 0
  for (const point of recent) {
    const preWar = byPeriod.get(preWarPeriod(point.period, lastPreWar))
    if (!preWar) return null
    current += point.value
    reference += preWar
  }
  return { pct: (current / reference) * 100, asOf: latest.period }
}

/** Level vs the last pre-war year for a series published only as YoY growth. */
function fromYoyGrowth(points: { period: string; growth: number }[], lastPreWar: string): Level {
  const latest = points.at(-1)
  if (!latest) return null
  const byPeriod = new Map(points.map((point) => [point.period, point.growth]))
  const reference = preWarPeriod(latest.period, lastPreWar)
  let pct = 100
  for (let period = latest.period; period > reference; period = yearBefore(period)) {
    const growth = byPeriod.get(period)
    if (growth == null) return null
    pct *= 1 + growth / 100
  }
  return { pct, asOf: latest.period }
}

/** Travel concern is bad when high, so a rise above baseline lowers the score. */
function travelConcernLevel(tourism: TravelConcernsPayload): Level {
  const latest = tourism.series.filter((point) => !point.partial).at(-1)
  const current = latest?.smooth ?? latest?.index
  const baseline = mean(
    tourism.series.flatMap((point) =>
      BASELINE_MONTHS.includes(point.period) && point.index != null ? [point.index] : [],
    ),
  )
  if (!latest || current == null || !baseline) return null
  return { pct: 200 - (current / baseline) * 100, asOf: latest.period }
}

/** Months since year 0, so quarters, months and days can be ordered together. */
function monthKey(asOf: string) {
  const quarter = asOf.match(/Q(\d)/)
  return Number(asOf.slice(0, 4)) * 12 + (quarter ? Number(quarter[1]) * 3 : Number(asOf.slice(5, 7)))
}

function pillar(label: string, levels: [string, Level][], proxy = false): RecoveryPillar {
  const inputs = levels.map(([inputLabel, level]) => ({
    label: inputLabel,
    score: level ? Math.min(SCORE_CAP, Math.max(0, level.pct)) : null,
    asOf: level?.asOf ?? null,
  }))
  const dates = inputs
    .flatMap((input) => (input.asOf ? [input.asOf] : []))
    .sort((a, b) => monthKey(a) - monthKey(b))
  const oldest = dates[0] ?? null
  const newest = dates.at(-1) ?? null
  return {
    label,
    score: mean(inputs.flatMap((input) => (input.score == null ? [] : [input.score]))),
    asOf: oldest === newest ? oldest : `${oldest} to ${newest}`,
    inputs,
    proxy,
  }
}

export function buildRecoveryIndex(data: {
  nonOilGdp: ValuePoint[]
  totalTrade: ValuePoint[]
  ports: PortsPayload
  pmi: PmiPoint[]
  licenses: LicensePoint[]
  employment: EmploymentGrowthPoint[]
  tourism: TravelConcernsPayload
}): RecoveryIndex {
  const { ports } = data
  const portLevel = (pct: number | null | undefined, last: string | undefined): Level =>
    pct == null || !last ? null : { pct, asOf: last.slice(0, 7) }
  const licenseSeries = (pick: (row: LicensePoint) => number) =>
    data.licenses.map((row) => ({ period: row.period, value: pick(row) }))

  // Job postings are left out: only one pre-war month exists and the scraper's
  // source count has since tripled, so its level cannot be compared with pre-war.
  const pillars = [
    pillar('Activity', [
      ['Non-oil GDP', vsPreWarYear(data.nonOilGdp, LAST_PREWAR_QUARTER)],
    ]),
    pillar('Trade', [
      ['Total trade', vsPreWarYear(data.totalTrade, LAST_PREWAR_MONTH, 3)],
      ['Oman ports', portLevel(ports.insights.green_calls_pct_of_baseline, ports.meta.last)],
      ['Hormuz', portLevel(ports.hormuz?.pct_of_baseline, ports.hormuz?.last)],
    ]),
    pillar('Business', [
      ['PMI', vsBaseline(data.pmi.map((row) => ({ period: row.period, value: row.pmi })))],
      [
        'New licenses',
        vsPreWarYear(licenseSeries((row) => row.new_licenses), LAST_PREWAR_QUARTER),
      ],
      [
        'Renewed licenses',
        vsPreWarYear(licenseSeries((row) => row.renewed_licenses), LAST_PREWAR_QUARTER),
      ],
    ]),
    pillar(
      'Labour',
      [
        [
          'Employment',
          fromYoyGrowth(
            data.employment.map((row) => ({ period: row.period, growth: row.total })),
            LAST_PREWAR_QUARTER,
          ),
        ],
      ],
      true,
    ),
    pillar('Tourism', [['Travel concern', travelConcernLevel(data.tourism)]], true),
  ]

  // Weighted average over the pillars that have data.
  let total = 0
  let weights = 0
  for (const item of pillars) {
    if (item.score == null) continue
    const weight = item.proxy ? PROXY_WEIGHT : 1
    total += item.score * weight
    weights += weight
  }

  return { score: weights ? total / weights : null, pillars }
}
