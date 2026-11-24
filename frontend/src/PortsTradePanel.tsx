import { useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { PortPoint, PortsPayload } from './api'
import { axisLabel } from './EventMarker'
import { formatPercent, formatValue } from './format'
import { PortsMap } from './PortsMap'

const WAR_MONTH = '2026-02'
const BASELINE_MONTHS = new Set(['2025-10', '2025-11', '2025-12', '2026-01'])
const PREWAR_BAR = '#6a7f9c' // slate blue
const WAR_BAR = '#c48b8b' // muted red
const POSTWAR_BAR = '#4a7c9b' // steel blue
const AVG_LINE = '#9a6700'
const MUTED = '#64748b'
const TICK = { fontSize: 12, fill: MUTED }

function barFill(period: string) {
  if (period === WAR_MONTH) return WAR_BAR
  if (period < WAR_MONTH) return PREWAR_BAR
  return POSTWAR_BAR
}

type MetricKey = 'calls' | 'import' | 'export'
type ZoneFilter = 'all' | 'green' | 'red'

const METRIC_LABEL: Record<MetricKey, string> = {
  calls: 'Port calls',
  import: 'Incoming shipment (t)',
  export: 'Outgoing shipment (t)',
}

function tone(value: number | null | undefined) {
  if (value == null) return ''
  if (value < 0) return 'negative'
  if (value > 0) return 'positive'
  return ''
}

function pct(value: number | null | undefined) {
  return value == null ? '—' : formatPercent(value, 1)
}

function ZoneBadge(props: { zone: 'green' | 'red' }) {
  return (
    <span className={`zone-badge zone-${props.zone}`}>
      {props.zone === 'green' ? 'Gulf of Oman' : 'Persian Gulf'}

    </span>
  )
}

function InsightCard(props: {
  eyebrow: string
  title: string
  body?: string
  tone?: 'positive' | 'negative' | 'neutral'
}) {
  return (
    <article className={`insight-card ${props.tone ?? 'neutral'}`}>
      <p className="insight-eyebrow">{props.eyebrow}</p>
      <h4>{props.title}</h4>
      {props.body ? <p>{props.body}</p> : null}
    </article>
  )
}

type Props = {
  data: PortsPayload
}

export function PortsTradePanel({ data }: Props) {
  const { meta, insights, ports } = data
  const [zone, setZone] = useState<ZoneFilter>('all')
  const [metric, setMetric] = useState<MetricKey>('calls')
  const defaultPort =
    insights.top_recovery?.name ??
    ports.find((p) => p.zone === 'green')?.name ??
    ports[0]?.name ??
    ''
  const [portName, setPortName] = useState(defaultPort)

  const filtered = useMemo(
    () => ports.filter((p) => (zone === 'all' ? true : p.zone === zone)),
    [ports, zone],
  )

  const selected: PortPoint | undefined =
    filtered.find((p) => p.name === portName) ?? filtered[0] ?? ports[0]

  const chartData = useMemo(() => {
    if (!selected) return []
    return selected.monthly.map((row) => ({
      period: row.period,
      value: row[metric],
      fill: barFill(row.period),
    }))
  }, [selected, metric])

  const preWarAvg = useMemo(() => {
    if (!selected) return null
    const vals = selected.monthly
      .filter((row) => BASELINE_MONTHS.has(row.period))
      .map((row) => row[metric])
    if (!vals.length) return null
    return vals.reduce((sum, v) => sum + v, 0) / vals.length
  }, [selected, metric])

  const top = insights.top_recovery
  const above = insights.ports_above_baseline
  const omanPorts = meta.green_ports?.length ? meta.green_ports : meta.red_ports

  const aboveTitle = insights.any_above_baseline
    ? `${above.map((p) => p.name).join(', ')} above baseline`
    : 'No port above baseline yet'
  const aboveBody = insights.any_above_baseline
    ? above
        .map((p) => `${p.name} ship volumes ${formatPercent(p.calls_vs_baseline, 1)} vs baseline`)
        .join('. ') + '. Prioritise capacity and routing through these ports.'
    : 'Every listed port is still below its ship-volume baseline. Focus on recovery leaders and Hormuz contingency routes.'

  const recoveryTitle = top
    ? `${top.name} leads recovery (${formatPercent(top.recovery_calls, 1)})`
    : 'Recovery leader unavailable'

  const exposureTitle =
    `Gulf of Oman ${pct(insights.green_avg_calls_vs_baseline)} vs baseline · ` +
    `Persian Gulf ${pct(insights.red_avg_calls_vs_baseline)}`
  const exposureBody = `Average ship volumes versus the baseline. Gulf of Oman-facing ports: ${omanPorts.join(', ')}.`

  return (
    <>
      <div className="insight-grid">
        <InsightCard
          eyebrow="Ship volumes vs baseline"
          title={aboveTitle}
          body={aboveBody}
          tone={insights.any_above_baseline ? 'positive' : 'negative'}
        />
        <InsightCard
          eyebrow="Greatest recovery since Feb"
          title={recoveryTitle}
          tone={top && top.recovery_calls > 0 ? 'positive' : 'neutral'}
        />
        <InsightCard
          eyebrow="Gulf of Oman vs Persian Gulf"
          title={exposureTitle}
          body={exposureBody}
          tone="neutral"
        />
      </div>

      <article className="panel span-2">
        <div className="panel-header">
          <div>
            <h3>UAE port activity · PortWatch</h3>
            <p>
              Daily ship calls and cargo tonnage, compared with baseline · latest data{' '}
              {meta.last}
            </p>
          </div>
          <div className="controls">
            <label>
              Metric
              <select
                value={metric}
                onChange={(event) => setMetric(event.target.value as MetricKey)}
              >
                {(Object.keys(METRIC_LABEL) as MetricKey[]).map((key) => (
                  <option key={key} value={key}>
                    {METRIC_LABEL[key]}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Port
              <select
                value={selected?.name ?? ''}
                onChange={(event) => setPortName(event.target.value)}
              >
                {filtered.map((p) => (
                  <option key={p.id} value={p.name}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        <div className="chips" role="group" aria-label="Coastline zone">
          {(
            [
              ['all', 'All ports'],
              ['green', 'Gulf of Oman (green)'],
              ['red', 'Persian Gulf (red)'],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              aria-pressed={zone === id}
              onClick={() => {
                setZone(id)
                const next = ports.filter((p) => (id === 'all' ? true : p.zone === id))
                if (next.length && !next.some((p) => p.name === portName)) {
                  setPortName(next[0].name)
                }
              }}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="ports-split">
          <PortsMap
            ports={filtered}
            selectedName={selected?.name ?? null}
            onSelect={(name) => {
              const port = ports.find((p) => p.name === name)
              if (zone !== 'all' && port && port.zone !== zone) setZone('all')
              setPortName(name)
            }}
          />

          <div className="ports-detail">
            {selected ? (
              <>
                <div className="port-summary">
                  <div>
                    <strong>{selected.name}</strong>
                    <ZoneBadge zone={selected.zone} />
                    <span className="port-summary-meta">
                      {selected.emirate}
                      {selected.note ? ` · ${selected.note}` : ''}
                    </span>
                  </div>
                  <div className="port-summary-kpis">
                    <span>
                      vs baseline{' '}
                      <b className={tone(selected.metrics[metric].pct_vs_baseline)}>
                        {pct(selected.metrics[metric].pct_vs_baseline)}
                      </b>
                    </span>
                    <span>
                      recovery{' '}
                      <b className={tone(selected.recovery_calls)}>
                        {pct(selected.recovery_calls)}
                      </b>
                    </span>
                    <span>
                      trade share{' '}
                      <b>
                        {selected.share_import == null ? '—' : `${selected.share_import}%`}{' '}
                        imp /{' '}
                        {selected.share_export == null ? '—' : `${selected.share_export}%`}{' '}
                        exp
                      </b>
                    </span>
                  </div>
                  {selected.industries.length ? (
                    <p className="note">Top industries: {selected.industries.join(' · ')}</p>
                  ) : null}
                </div>

                {chartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={chartData} margin={{ top: 8, right: 12, left: 10, bottom: 8 }}>
                      <CartesianGrid stroke="#e2e8f0" vertical={false} />
                      <XAxis
                        dataKey="period"
                        tick={TICK}
                        tickLine={false}
                        minTickGap={24}
                        stroke={MUTED}
                      />
                      <YAxis
                        tick={TICK}
                        tickLine={false}
                        axisLine={false}
                        width={78}
                        tickFormatter={formatValue}
                        label={axisLabel(METRIC_LABEL[metric])}
                      />
                      <Tooltip
                        formatter={(value) => [
                          formatValue(Number(value)),
                          METRIC_LABEL[metric],
                        ]}
                      />
                      <Legend
                        verticalAlign="top"
                        height={36}
                        payload={[
                          { value: 'Pre-war', type: 'square', color: PREWAR_BAR },
                          { value: 'War starts (Feb 2026)', type: 'square', color: WAR_BAR },
                          { value: 'After war start', type: 'square', color: POSTWAR_BAR },
                        ]}
                      />
                      <Bar dataKey="value" name={METRIC_LABEL[metric]} isAnimationActive={false}>
                        {chartData.map((row) => (
                          <Cell key={row.period} fill={row.fill} />
                        ))}
                      </Bar>
                      {preWarAvg != null ? (
                        <ReferenceLine
                          y={preWarAvg}
                          stroke={AVG_LINE}
                          strokeWidth={2}
                          strokeDasharray="4 4"
                          label={{
                            value: 'Pre-war avg',
                            position: 'insideTopRight',
                            fill: AVG_LINE,
                            fontSize: 11,
                          }}
                        />
                      ) : null}
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="note">No monthly series for this port.</p>
                )}
              </>
            ) : (
              <p className="note">No ports in this filter.</p>
            )}
          </div>
        </div>

        <details>
          <summary>Port comparison table</summary>
          <table>
            <thead>
              <tr>
                <th>Port</th>
                <th>Zone</th>
                <th>Calls vs baseline</th>
                <th>Recovery</th>
                <th>Import share</th>
                <th>Top industries</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((p) => (
                <tr
                  key={p.id}
                  className={selected?.id === p.id ? 'row-active' : undefined}
                  onClick={() => setPortName(p.name)}
                  style={{ cursor: 'pointer' }}
                >
                  <td>{p.name}</td>
                  <td>
                    <ZoneBadge zone={p.zone} />
                  </td>
                  <td className={tone(p.calls_vs_baseline)}>{pct(p.calls_vs_baseline)}</td>
                  <td className={tone(p.recovery_calls)}>{pct(p.recovery_calls)}</td>
                  <td>{p.share_import == null ? '—' : `${p.share_import}%`}</td>
                  <td>{p.industries.length ? p.industries.join(', ') : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
        <p className="note">
          Source: {meta.source}. Recovery = % change in daily port calls
          from early war ({meta.war_start} to {meta.early_war_end}) to latest window (
          {meta.recent_start} to {meta.last}).
          {meta.fetched ? ` Fetched ${meta.fetched}.` : ''}
        </p>
      </article>
    </>
  )
}
