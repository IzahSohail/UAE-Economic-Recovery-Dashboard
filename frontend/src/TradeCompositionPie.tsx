import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { formatValue } from './format'

export type TradeSlice = {
  name: string
  value: number
}

type Props = {
  data: TradeSlice[]
  period: string
}

/** Distinct, readable palette: enough for top sectors + Other. */
const COLORS = [
  '#1f7a6c',
  '#4a7c9b',
  '#6a7f9c',
  '#b08968',
  '#8b6b4f',
  '#5c6b7a',
  '#9a6700',
  '#64748b',
]

function shortName(name: string, max = 28) {
  if (name.length <= max) return name
  return `${name.slice(0, max - 1)}…`
}

export function TradeCompositionPie({ data, period }: Props) {
  const total = data.reduce((sum, row) => sum + row.value, 0)
  if (!data.length || total <= 0) {
    return <p className="note">No sector breakdown for this month.</p>
  }

  const chartData = data.map((row) => ({
    ...row,
    label: shortName(row.name),
    share: (row.value / total) * 100,
  }))

  return (
    <div className="trade-pie trade-pie-compact">
      <p className="trade-pie-caption">Latest mix · {period}</p>
      <div className="trade-pie-body">
        <ResponsiveContainer width="100%" height={168}>
          <PieChart margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
            <Pie
              data={chartData}
              dataKey="value"
              nameKey="label"
              cx="50%"
              cy="50%"
              innerRadius={38}
              outerRadius={68}
              paddingAngle={1.5}
              stroke="#fff"
              strokeWidth={1}
              isAnimationActive={false}
              label={false}
            >
              {chartData.map((row, index) => (
                <Cell key={row.label} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value, _name, item) => {
                const share = Number(item?.payload?.share ?? 0)
                return [
                  `AED ${formatValue(Number(value))} bn (${share.toFixed(1)}%)`,
                  String(item?.payload?.name ?? ''),
                ]
              }}
            />
          </PieChart>
        </ResponsiveContainer>
        <ul className="trade-pie-legend" aria-label="Sector shares">
          {chartData.map((row, index) => (
            <li key={row.label}>
              <span
                className="trade-pie-swatch"
                style={{ background: COLORS[index % COLORS.length] }}
              />
              <span className="trade-pie-legend-name">{shortName(row.name)}</span>
              <span className="trade-pie-legend-share">{row.share.toFixed(1)}%</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

/** Keep the chart readable: top N sectors, rest rolled into Other. */
export function buildTradeSlices(
  rows: { sector: string; sector_name: string; value: number }[],
  topN = 6,
): TradeSlice[] {
  const ranked = [...rows]
    .filter((row) => row.sector !== '_T' && row.value > 0)
    .sort((a, b) => b.value - a.value)

  if (!ranked.length) return []

  const head = ranked.slice(0, topN)
  const rest = ranked.slice(topN)
  const slices: TradeSlice[] = head.map((row) => ({
    name: row.sector_name,
    value: row.value / 1_000_000_000,
  }))

  if (rest.length) {
    slices.push({
      name: `Other (${rest.length} sectors)`,
      value: rest.reduce((sum, row) => sum + row.value, 0) / 1_000_000_000,
    })
  }

  return slices
}
