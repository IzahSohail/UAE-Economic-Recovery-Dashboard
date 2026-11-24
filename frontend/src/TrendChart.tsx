import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { SeriesPoint } from './api'
import { axisLabel, EVENT_CHART_MARGIN, EVENT_LINE_COLOR, EventLabel } from './EventMarker'
import { formatGrowth, formatValue } from './format'

export type ChartType = 'line' | 'bar'

type Props = {
  /** Values in AED billion. */
  data: SeriesPoint[]
  type: ChartType
  /** Period on the x axis where the event line is drawn. */
  eventPeriod: string
  eventLabel: string
}

const BLUE = '#2563eb'
const RED = '#dc2626'
const MUTED = '#64748b'

const TICK = { fontSize: 12, fill: MUTED }

export function TrendChart({ data, type, eventPeriod, eventLabel }: Props) {
  const grid = <CartesianGrid stroke="#e2e8f0" vertical={false} />
  const xAxis = (
    <XAxis dataKey="period" tick={TICK} tickLine={false} minTickGap={24} stroke={MUTED} />
  )
  const eventLine = (
    <ReferenceLine
      x={eventPeriod}
      stroke={EVENT_LINE_COLOR}
      strokeWidth={2}
      strokeDasharray="4 4"
      label={({ viewBox }: { viewBox: { x: number; y: number; width?: number } }) => (
        <EventLabel viewBox={viewBox} label={eventLabel} />
      )}
    />
  )

  if (type === 'bar') {
    const bars = data.filter((point) => point.growth !== null)
    return (
      <ResponsiveContainer width="100%" height={340}>
        <BarChart data={bars} margin={EVENT_CHART_MARGIN}>
          {grid}
          {xAxis}
          <YAxis
            tick={TICK}
            tickLine={false}
            axisLine={false}
            width={68}
            tickFormatter={(value: number) => `${value}%`}
            label={axisLabel('YoY %')}
          />
          <Tooltip
            cursor={{ fill: '#f1f5f9' }}
            formatter={(value) => [formatGrowth(Number(value)), 'Change vs a year earlier']}
          />
          <ReferenceLine y={0} stroke={MUTED} />
          <Bar dataKey="growth" isAnimationActive={false}>
            {bars.map((point) => (
              <Cell key={point.period} fill={(point.growth ?? 0) < 0 ? RED : BLUE} />
            ))}
          </Bar>
          {eventLine}
        </BarChart>
      </ResponsiveContainer>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={340}>
      <LineChart data={data} margin={EVENT_CHART_MARGIN}>
        {grid}
        {xAxis}
        <YAxis
          tick={TICK}
          tickLine={false}
          axisLine={false}
          width={68}
          domain={['auto', 'auto']}
          tickFormatter={formatValue}
          label={axisLabel('AED bn')}
        />
        <Tooltip formatter={(value) => [`AED ${formatValue(Number(value))} bn`, 'Value']} />
        <Line
          dataKey="value"
          type="linear"
          stroke={BLUE}
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
        {eventLine}
      </LineChart>
    </ResponsiveContainer>
  )
}
