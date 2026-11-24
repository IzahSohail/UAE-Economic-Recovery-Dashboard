export const formatValue = (value: number) =>
  value.toLocaleString(undefined, { maximumSignificantDigits: 4 })

export const formatGrowth = (value: number) =>
  `${value > 0 ? '+' : ''}${value.toFixed(1)}%`

export const formatPercent = (value: number, digits = 2) =>
  `${value > 0 ? '+' : ''}${value.toFixed(digits)}%`
