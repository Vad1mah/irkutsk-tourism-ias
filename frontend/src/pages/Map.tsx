import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Map as MapIcon, Sparkles, TrendingUp } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent, Badge } from '../components/ui'
import { YandexMap } from '../components/YandexMap'
import { ErrorState } from '../components/ErrorState'
import { api } from '../api/client'
import { usePageTitle } from '../hooks/usePageTitle'

function Map() {
  usePageTitle('Региональная карта')
  const navigate = useNavigate()

  const { data: districts, isError, isLoading, refetch } = useQuery({
    queryKey: ['districts'],
    queryFn: api.getDistricts,
  })
  const { data: hotelsMap } = useQuery({
    queryKey: ['hotelsMap'],
    queryFn: () => api.getHotelsMap(),
  })

  const districtsList = districts || []

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-10 w-64 skeleton rounded-lg" />
        <div className="h-[520px] skeleton rounded-2xl" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="h-40 skeleton rounded-2xl" />
          <div className="h-40 skeleton rounded-2xl" />
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <ErrorState
        title="Ошибка загрузки аналитики"
        message="Не удалось загрузить данные о районах."
        onRetry={() => refetch()}
      />
    )
  }

  // Карточки KPI из hotelsMap
  const kpiItems = hotelsMap
    ? [
        { label: 'Объектов', value: String(hotelsMap.total_hotels) },
        { label: 'Номеров', value: String(hotelsMap.total_rooms) },
        { label: 'Ср. загрузка', value: `${hotelsMap.avg_occupancy}%` },
      ]
    : []

  // Top-5 по RevPAR из districts
  const top5RevPAR = [...districtsList]
    .filter(d => d.avgPrice && d.occupancy != null && (d.hotelsCount ?? 0) >= 2)
    .map(d => ({
      district: d.district,
      revpar: Math.round((d.avgPrice || 0) * (d.occupancy / 100)),
      occupancy: d.occupancy,
    }))
    .sort((a, b) => b.revpar - a.revpar)
    .slice(0, 5)

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[hsl(var(--primary))] to-[hsl(var(--accent))] flex items-center justify-center">
          <MapIcon className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Региональная карта</h1>
          <p className="text-sm text-[hsl(var(--muted-foreground))]">
            Размещение объектов по районам Прибайкалья
          </p>
        </div>
        <button
          onClick={() => navigate(`/chat?context=${encodeURIComponent('Сравни заполняемость отелей по районам Прибайкалья')}`)}
          className="ml-auto p-2 rounded-lg bg-[hsl(var(--primary)/0.1)] hover:bg-[hsl(var(--primary)/0.2)] transition-colors"
          title="Спросить AI"
        >
          <Sparkles size={16} className="text-[hsl(var(--primary))]" />
        </button>
      </div>

      {/* Map + Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-4">
        {/* Main map */}
        <Card variant="glass">
          <CardContent className="p-0 overflow-hidden rounded-2xl">
            <YandexMap
              hotels={(hotelsMap?.hotels ?? []).map(h => ({
                id: h.id,
                name: h.name,
                lat: h.lat,
                lon: h.lon,
                rooms_num: h.rooms_num,
                occupancy: h.occupancy,
                min_price: h.min_price,
              }))}
              onHotelClick={(id) => navigate(`/hotels/${id}`)}
            />
          </CardContent>
          {/* Legend */}
          <div className="flex items-center justify-center gap-6 py-3 text-xs text-[hsl(var(--muted-foreground))]">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-[#22c55e]" /> &lt;40%
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-[#f59e0b]" /> 40–70%
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-[#ef4444]" /> &gt;70%
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-[#94a3b8]" /> нет данных
            </span>
          </div>
        </Card>

        {/* Sidebar */}
        <div className="flex flex-col gap-4">
          {/* KPI */}
          {kpiItems.length > 0 && (
            <Card variant="glass">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Сводка</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {kpiItems.map(item => (
                    <div key={item.label} className="flex items-center justify-between text-sm">
                      <span className="text-[hsl(var(--muted-foreground))]">{item.label}</span>
                      <span className="font-semibold tabular-nums">{item.value}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Top-5 by RevPAR */}
          {top5RevPAR.length > 0 && (
            <Card variant="glass">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Топ-5 районов по RevPAR</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {top5RevPAR.map((d, i) => (
                    <div
                      key={d.district}
                      onClick={() => navigate(`/analytics?district=${encodeURIComponent(d.district)}`)}
                      className="flex items-center justify-between p-1.5 rounded-lg hover:bg-[hsl(var(--secondary))] transition-colors cursor-pointer"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-[hsl(var(--primary))] w-4 tabular-nums">{i + 1}</span>
                        <span className="text-xs truncate max-w-[120px]">{d.district.replace(' район', '')}</span>
                      </div>
                      <span className="text-xs font-semibold tabular-nums text-[hsl(var(--accent))]">
                        {d.revpar.toLocaleString('ru-RU')} ₽
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Filter hint */}
          <p className="text-xs text-[hsl(var(--muted-foreground))] text-center px-2">
            Кликните по маркеру на карте для просмотра информации об объекте
          </p>
        </div>
      </div>

      {/* Top-3 districts panels */}
      {districtsList.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card variant="glass">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Топ-3 района по загрузке</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {[...districtsList]
                  .filter(d => d.occupancy != null && (d.hotelsCount ?? 0) >= 2)
                  .sort((a, b) => (b.occupancy ?? 0) - (a.occupancy ?? 0))
                  .slice(0, 3)
                  .map((d, i) => (
                    <div
                      key={d.district}
                      onClick={() => navigate(`/analytics?district=${encodeURIComponent(d.district)}`)}
                      className="flex items-center justify-between p-2 rounded-lg bg-[hsl(var(--secondary)/0.4)] hover:bg-[hsl(var(--secondary))] transition-colors cursor-pointer"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-bold text-[hsl(var(--primary))] tabular-nums w-5">{i + 1}</span>
                        <span className="text-sm font-medium">{d.district}</span>
                      </div>
                      <div className="flex items-center gap-3 text-xs">
                        <span className="text-[hsl(var(--muted-foreground))]">{d.hotelsCount} объектов</span>
                        <Badge variant={d.occupancy > 70 ? 'danger' : d.occupancy > 40 ? 'warning' : 'success'} size="sm">
                          {Math.round(d.occupancy ?? 0)}%
                        </Badge>
                      </div>
                    </div>
                  ))}
              </div>
            </CardContent>
          </Card>

          <Card variant="glass">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Топ-3 района по числу объектов</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {[...districtsList]
                  .filter(d => (d.hotelsCount ?? 0) > 0)
                  .sort((a, b) => (b.hotelsCount ?? 0) - (a.hotelsCount ?? 0))
                  .slice(0, 3)
                  .map((d, i) => (
                    <div
                      key={d.district}
                      onClick={() => navigate(`/analytics?district=${encodeURIComponent(d.district)}`)}
                      className="flex items-center justify-between p-2 rounded-lg bg-[hsl(var(--secondary)/0.4)] hover:bg-[hsl(var(--secondary))] transition-colors cursor-pointer"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-bold text-[hsl(var(--accent))] tabular-nums w-5">{i + 1}</span>
                        <span className="text-sm font-medium">{d.district}</span>
                      </div>
                      <div className="flex items-center gap-3 text-xs">
                        <span className="text-[hsl(var(--muted-foreground))] tabular-nums">
                          {Math.round(d.occupancy ?? 0)}% загрузка
                        </span>
                        <span className="font-semibold tabular-nums text-[hsl(var(--accent))]">
                          {d.hotelsCount}
                        </span>
                      </div>
                    </div>
                  ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Quick AI action */}
      <div className="flex justify-center">
        <button
          onClick={() => navigate('/analytics')}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-[hsl(var(--secondary))] hover:bg-[hsl(var(--secondary)/0.8)] transition-colors text-[hsl(var(--foreground))]"
        >
          <TrendingUp size={14} />
          Перейти к детальной аналитике
        </button>
      </div>
    </div>
  )
}

export default Map
