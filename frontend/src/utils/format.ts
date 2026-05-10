/**
 * Форматирование дат/чисел в едином ru-RU стиле для UI.
 */

const RU_DATE_OPTS: Intl.DateTimeFormatOptions = {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
}

export function formatRuDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('ru-RU', RU_DATE_OPTS).replace('.', '')
}

export function formatRuDateRange(from: string | null | undefined, to: string | null | undefined): string {
  return `${formatRuDate(from)} – ${formatRuDate(to)}`
}
