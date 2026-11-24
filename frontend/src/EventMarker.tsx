/** Shared dotted event line + label that stays inside the chart bounds. */

type ViewBox = { x: number; y: number; width?: number }

type Props = {
  viewBox: ViewBox
  label: string
  /** Approximate plot width; used to flip the label when near either edge. */
  plotWidth?: number
}

const INK = '#0f172a'

export function EventLabel({ viewBox, label, plotWidth = 640 }: Props) {
  const x = viewBox.x
  const y = viewBox.y - 8
  // Keep the long label readable: prefer centering, flip near edges.
  let anchor: 'start' | 'middle' | 'end' = 'middle'
  if (x < plotWidth * 0.28) anchor = 'start'
  else if (x > plotWidth * 0.72) anchor = 'end'

  // Split on the parenthesis so "(Feb 2026)" sits on a second line.
  const match = label.match(/^(.*?)\s*(\([^)]+\))\s*$/)
  const lines = match ? [match[1], match[2]] : [label]

  return (
    <text
      x={x}
      y={y}
      textAnchor={anchor}
      fontSize={11}
      fontWeight={600}
      fill={INK}
      style={{ pointerEvents: 'none' }}
    >
      {lines.map((line, index) => (
        <tspan key={line} x={x} dy={index === 0 ? 0 : 13}>
          {line}
        </tspan>
      ))}
    </text>
  )
}

export const EVENT_CHART_MARGIN = { top: 40, right: 20, bottom: 4, left: 10 }
export const EVENT_LINE_COLOR = '#0f172a'

const AXIS_LABEL_STYLE = {
  textAnchor: 'middle' as const,
  fill: '#64748b',
  fontSize: 12,
}

/** Rotated Y-axis title for Recharts. */
export function axisLabel(value: string) {
  return {
    value,
    angle: -90,
    position: 'insideLeft' as const,
    style: AXIS_LABEL_STYLE,
  }
}
