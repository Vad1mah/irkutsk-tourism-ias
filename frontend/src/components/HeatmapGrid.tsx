import { useMemo } from 'react'

type HeatmapItem = { district: string; date: string; occupancy: number }

type HeatmapGridProps = {
  data: HeatmapItem[]
  districts: string[]
  dates: string[]
}

export function HeatmapGrid({ data, districts, dates }: HeatmapGridProps) {
  const matrix = useMemo(() => {
    const lookup: Record<string, Record<string, number>> = {}
    data.forEach(item => {
      if (!lookup[item.district]) lookup[item.district] = {}
      lookup[item.district][item.date] = item.occupancy
    })
    return lookup
  }, [data])

  if (dates.length === 0 || districts.length === 0) {
    return (
      <div className="text-center py-6 text-[hsl(var(--muted-foreground))]">
        Нет данных для отображения
      </div>
    )
  }

  return (
    <div className="overflow-x-auto" role="region" aria-label="Тепловая карта загруженности">
      <p className="text-xs text-[hsl(var(--muted-foreground))] mb-2 sm:hidden">← Прокрутите для просмотра →</p>
      <div className="min-w-[600px]">
        <div className="flex items-center justify-end gap-2 mb-3 text-xs flex-wrap">
          <span className="text-[hsl(var(--muted-foreground))]">Загруженность:</span>
          {[
            { color: 'hsl(142 76% 36% / 0.7)', label: '<20%' },
            { color: 'hsl(172 66% 50% / 0.7)', label: '20-40%' },
            { color: 'hsl(38 92% 50% / 0.7)', label: '40-60%' },
            { color: 'hsl(25 95% 53% / 0.7)', label: '60-80%' },
            { color: 'hsl(0 84% 60% / 0.7)', label: '>80%' },
          ].map(item => (
            <div key={item.label} className="flex items-center gap-1">
              <div className="w-3.5 h-3.5 rounded" style={{ backgroundColor: item.color }} />
              <span>{item.label}</span>
            </div>
          ))}
        </div>

        <div className="grid" style={{ gridTemplateColumns: `120px repeat(${dates.length}, 1fr)` }}>
          <div />
          {dates.map(date => (
            <div key={date} className="text-center text-xs text-[hsl(var(--muted-foreground))] py-1">
              {new Date(date).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
            </div>
          ))}
        </div>

        {districts.map(district => (
          <div
            key={district}
            className="grid items-center"
            style={{ gridTemplateColumns: `120px repeat(${dates.length}, minmax(38px, 56px))` }}
          >
            <div className="text-xs font-medium truncate pr-2 py-1" title={district}>
              {district.replace(' район', '')}
            </div>
            {dates.map(date => {
              const occupancy = matrix[district]?.[date]
              return (
                <div
                  key={date}
                  className="aspect-square m-0.5 rounded-sm flex items-center justify-center text-xs font-medium text-white cursor-default transition-transform hover:scale-110"
                  style={{ backgroundColor: _heatColor(occupancy) }}
                  title={`${district}: ${occupancy !== undefined ? `${Math.round(occupancy)}%` : 'нет данных'} (${date})`}
                >
                  {occupancy !== undefined ? Math.round(occupancy) : '—'}
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}

function _heatColor(value: number | undefined): string {
  if (value === undefined) return 'hsl(var(--muted)/0.3)'
  if (value < 20) return 'hsl(142 76% 36% / 0.7)'
  if (value < 40) return 'hsl(172 66% 50% / 0.7)'
  if (value < 60) return 'hsl(38 92% 50% / 0.7)'
  if (value < 80) return 'hsl(25 95% 53% / 0.7)'
  return 'hsl(0 84% 60% / 0.7)'
}
