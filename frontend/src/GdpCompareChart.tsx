import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { axisLabel, EVENT_CHART_MARGIN, EVENT_LINE_COLOR, EventLabel } from './EventMarker'
import { formatValue } from './format'

type Point = {
  period: string
  total: number | null
  nonOil: number | null
}

type Props = {
  data: Point[]
  eventPeriod: string
  eventLabel: string
}

const TOTAL = '#1f7a6c'
const NON_OIL = '#4a7c9b'
const MUTED = '#64748b'
const TICK = { fontSize: 12, fill: MUTED }

export function GdpCompareChart({ data, eventPeriod, eventLabel }: Props) {
  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={data} margin={EVENT_CHART_MARGIN}>
        <CartesianGrid stroke="#e2e8f0" vertical={false} />
        <XAxis dataKey="period" tick={TICK} tickLine={false} minTickGap={24} stroke={MUTED} />
        <YAxis
          tick={TICK}
          tickLine={false}
          axisLine={false}
          width={68}
          domain={['auto', 'auto']}
          tickFormatter={formatValue}
          label={axisLabel('AED bn')}
        />
        <Tooltip
          formatter={(value, name) => [
            `AED ${formatValue(Number(value))} bn`,
            name === 'total' ? 'Total GDP' : 'Non-oil GDP',
          ]}
        />
        <Legend
          verticalAlign="top"
          height={32}
          formatter={(value) => (value === 'total' ? 'Total GDP' : 'Non-oil GDP')}
        />
        <Line
          type="linear"
          dataKey="total"
          stroke={TOTAL}
          strokeWidth={2.5}
          dot={false}
          isAnimationActive={false}
        />
        <Line
          type="linear"
          dataKey="nonOil"
          stroke={NON_OIL}
          strokeWidth={2}
          strokeDasharray="5 4"
          dot={false}
          isAnimationActive={false}
        />
        <ReferenceLine
          x={eventPeriod}
          stroke={EVENT_LINE_COLOR}
          strokeWidth={2}
          strokeDasharray="4 4"
          label={({ viewBox }: { viewBox: { x: number; y: number; width?: number } }) => (
            <EventLabel viewBox={viewBox} label={eventLabel} />
          )}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
