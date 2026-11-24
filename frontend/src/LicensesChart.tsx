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
import type { LicensePoint } from './api'
import { axisLabel, EVENT_CHART_MARGIN, EVENT_LINE_COLOR, EventLabel } from './EventMarker'
import { formatValue } from './format'

type Props = {
  data: LicensePoint[]
  eventPeriod: string
  eventLabel: string
}

const BLUE = '#2563eb'
const GREEN = '#059669'
const MUTED = '#64748b'
const TICK = { fontSize: 12, fill: MUTED }

export function LicensesChart({ data, eventPeriod, eventLabel }: Props) {
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
          tickFormatter={formatValue}
          label={axisLabel('Licenses')}
        />
        <Tooltip formatter={(value) => formatValue(Number(value))} />
        <Legend />
        <Line
          type="linear"
          dataKey="new_licenses"
          name="New"
          stroke={BLUE}
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
        <Line
          type="linear"
          dataKey="renewed_licenses"
          name="Renewed"
          stroke={GREEN}
          strokeWidth={2}
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
