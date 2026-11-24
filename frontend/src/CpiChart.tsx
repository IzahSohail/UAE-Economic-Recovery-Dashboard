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
import type { CpiPoint } from './api'
import { axisLabel, EVENT_CHART_MARGIN, EVENT_LINE_COLOR, EventLabel } from './EventMarker'
import { formatPercent } from './format'

type Props = {
  data: CpiPoint[]
  eventPeriod: string
  eventLabel: string
}

const BLUE = '#2563eb'
const AMBER = '#d97706'
const MUTED = '#64748b'
const TICK = { fontSize: 12, fill: MUTED }

export function CpiChart({ data, eventPeriod, eventLabel }: Props) {
  return (
    <ResponsiveContainer width="100%" height={340}>
      <LineChart data={data} margin={EVENT_CHART_MARGIN}>
        <CartesianGrid stroke="#e2e8f0" vertical={false} />
        <XAxis dataKey="period" tick={TICK} tickLine={false} minTickGap={24} stroke={MUTED} />
        <YAxis
          tick={TICK}
          tickLine={false}
          axisLine={false}
          width={68}
          tickFormatter={(value: number) => `${value}%`}
          label={axisLabel('Inflation %')}
        />
        <Tooltip formatter={(value) => formatPercent(Number(value))} />
        <Legend />
        <ReferenceLine y={0} stroke={MUTED} />
        <Line
          type="linear"
          dataKey="yoy"
          name="YoY inflation"
          stroke={BLUE}
          strokeWidth={2}
          dot={false}
          connectNulls
          isAnimationActive={false}
        />
        <Line
          type="linear"
          dataKey="mom"
          name="MoM inflation"
          stroke={AMBER}
          strokeWidth={2}
          dot={false}
          connectNulls
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
