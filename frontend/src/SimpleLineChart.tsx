import {
  CartesianGrid,
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
  value: number
}

type Props = {
  data: Point[]
  eventPeriod: string
  eventLabel: string
  /** Optional horizontal guide, e.g. PMI expansion threshold at 50. */
  guideValue?: number
  guideLabel?: string
  valueLabel?: string
}

const BLUE = '#2563eb'
const MUTED = '#64748b'
const TICK = { fontSize: 12, fill: MUTED }

export function SimpleLineChart({
  data,
  eventPeriod,
  eventLabel,
  guideValue,
  guideLabel,
  valueLabel = 'Value',
}: Props) {
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
          domain={['auto', 'auto']}
          tickFormatter={formatValue}
          label={axisLabel(valueLabel)}
        />
        <Tooltip
          formatter={(value) => [formatValue(Number(value)), valueLabel]}
        />
        {guideValue !== undefined ? (
          <ReferenceLine
            y={guideValue}
            stroke={MUTED}
            strokeDasharray="3 3"
            label={
              guideLabel
                ? { value: guideLabel, position: 'insideTopRight', fill: MUTED, fontSize: 12 }
                : undefined
            }
          />
        ) : null}
        <Line
          type="linear"
          dataKey="value"
          stroke={BLUE}
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
