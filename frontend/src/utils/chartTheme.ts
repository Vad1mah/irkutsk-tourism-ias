/**
 * Общий стиль для всех Recharts <Tooltip> в проекте.
 * Recharts по умолчанию рендерит labels/items серым `rgb(102,102,102)`,
 * что почти не читается на тёмной подложке `hsl(var(--card))`.
 * Поэтому явно прокидываем `itemStyle` и `labelStyle` с foreground цветом.
 */

const TOOLTIP_BG: React.CSSProperties = {
  backgroundColor: 'hsl(var(--card))',
  border: '1px solid hsl(var(--border))',
  borderRadius: '8px',
  fontSize: 12,
  color: 'hsl(var(--foreground))',
}

const TOOLTIP_ITEM: React.CSSProperties = {
  color: 'hsl(var(--foreground))',
}

const TOOLTIP_LABEL: React.CSSProperties = {
  color: 'hsl(var(--foreground))',
  fontWeight: 600,
  marginBottom: 2,
}

/**
 * Spread прямо в `<Tooltip {...RECHARTS_TOOLTIP_PROPS} />` —
 * остальные props (`formatter`, `labelFormatter`, `cursor`) ставь после.
 */
export const RECHARTS_TOOLTIP_PROPS = {
  contentStyle: TOOLTIP_BG,
  itemStyle: TOOLTIP_ITEM,
  labelStyle: TOOLTIP_LABEL,
} as const

/**
 * Для BarChart: убирает серый «cursor highlight» прямоугольник на hover,
 * который перекрывает столбец и делает его нечитаемым.
 * Использовать как `<Tooltip cursor={BAR_CURSOR_TRANSPARENT} />`.
 */
export const BAR_CURSOR_TRANSPARENT = { fill: 'transparent' } as const
