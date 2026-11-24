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
import type { EmploymentGrowthPoint } from './api'
import { axisLabel, EVENT_CHART_MARGIN, EVENT_LINE_COLOR, EventLabel } from './EventMarker'
import { formatValue } from './format'

type Props = {
  data: EmploymentGrowthPoint[]
  eventPeriod: string
  eventLabel: string
}

const TOTAL = '#1f7a6c'
const MALE = '#4a7c9b'
const FEMALE = '#b08968'
const MUTED = '#64748b'
const TICK = { fontSize: 12, fill: MUTED }

export function EmploymentGrowthChart({ data, eventPeriod, eventLabel }: Props) {
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
          tickFormatter={(value) => `${formatValue(Number(value))}%`}
          label={axisLabel('YoY %')}
        />
        <Tooltip
          formatter={(value, name) => [`${formatValue(Number(value))}%`, String(name)]}
        />
        <Legend />
        <Line
          type="linear"
          dataKey="total"
          name="Total"
          stroke={TOTAL}
          strokeWidth={2.25}
          dot={false}
          isAnimationActive={false}
        />
        <Line
          type="linear"
          dataKey="male"
          name="Male"
          stroke={MALE}
          strokeWidth={1.75}
          dot={false}
          isAnimationActive={false}
        />
        <Line
          type="linear"
          dataKey="female"
          name="Female"
          stroke={FEMALE}
          strokeWidth={1.75}
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
