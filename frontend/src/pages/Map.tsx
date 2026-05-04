import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  Treemap,
} from 'recharts'
import {
  Map as MapIcon, TrendingUp,
  BarChart3, Layers, Activity,
  ExternalLink, Sparkles,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent, Badge, Button } from '../components/ui'
import { HeatmapGrid } from '../components/HeatmapGrid'
import { GeoMap } from '../components/GeoMap'
import { ErrorState } from '../components/ErrorState'
import { api } from '../api/client'
import { usePageTitle } from '../hooks/usePageTitle'

type ViewMode = 'map' | 'overview' | 'heatmap' | 'comparison'

function Map() {
  usePageTitle('Региональная карта')
  const navigate = useNavigate()
  const [viewMode, setViewMode] = useState<ViewMode>('map')
  const [selectedDistrict, setSelectedDistrict] = useState<string | null>(null)

  const { data: districts, isError, isLoading, refetch } = useQuery({ queryKey: ['districts'], queryFn: api.getDistricts })
  const { data: hotelsByDistrict, isError: errorHotelsBy } = useQuery({ queryKey: ['hotelsByDistrict'], queryFn: api.getHotelsByDistrict })
  const { data: heatmapData, isError: errorHeatmap } = useQuery({
    queryKey: ['heatmap'],
    queryFn: () => api.getHeatmap(14),
  })
  const { data: hotels, isError: errorHotels } = useQuery({ queryKey: ['hotels'], queryFn: api.getHotels })
  const { data: hotelsMap } = useQuery({ queryKey: ['hotelsMap'], queryFn: () => api.getHotelsMap() })
  const hasSecondaryErrors = errorHotelsBy || errorHeatmap || errorHotels

  const districtsList = districts || []
  const hotelsList = hotels || []

  const radarSlice = districtsList.slice(0, 6)
  const maxRadarRooms = Math.max(...radarSlice.map(d => d.totalRooms), 1)
  const maxRadarPrice = Math.max(...radarSlice.map(d => d.avgPrice || 0), 1)
  const radarData = radarSlice.map(d => ({
    district: d.district.replace(' район', '').substring(0, 10),
    occupancy: Math.min(Math.max(d.occupancy, 0), 100),
    rooms: maxRadarRooms > 0 ? Math.min((d.totalRooms / maxRadarRooms) * 100, 100) : 0,
    price: maxRadarPrice > 0 ? Math.min(((d.avgPrice || 0) / maxRadarPrice) * 100, 100) : 0,
  }))

  const treemapData = _buildTreemapData(hotelsList)

  const viewButtons: { key: ViewMode; label: string; icon: React.ElementType; desc: string }[] = [
    { key: 'map', label: 'Карта отелей', icon: MapIcon, desc: 'Размещение на карте' },
    { key: 'overview', label: 'Обзор районов', icon: Layers, desc: 'Статистика по районам' },
    { key: 'heatmap', label: 'Сезонная карта', icon: Activity, desc: 'Заполняемость по месяцам' },
    { key: 'comparison', label: 'Сравнение', icon: BarChart3, desc: 'Сравнение районов' },
  ]

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-10 w-64 skeleton rounded-lg" />
        <div className="h-96 skeleton rounded-2xl" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="h-64 skeleton rounded-2xl" />
          <div className="h-64 skeleton rounded-2xl" />
        </div>
      </div>
    )
  }

  if (isError) {
    return <ErrorState title="Ошибка загрузки аналитики" message="Не удалось загрузить данные о районах." onRetry={() => refetch()} />
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[hsl(var(--primary))] to-[hsl(var(--accent))] flex items-center justify-center">
              <MapIcon className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Региональная карта</h1>
              <p className="text-sm text-[hsl(var(--muted-foreground))]">
                Визуализация данных по районам Прибайкалья
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
        </div>
        <div className="flex gap-1 bg-[hsl(var(--secondary))] p-1 rounded-xl">
          {viewButtons.map(({ key, label, icon: Icon, desc }) => (
            <Button
              key={key}
              variant={viewMode === key ? 'primary' : 'ghost'}
              size="sm"
              onClick={() => setViewMode(key)}
              title={desc}
            >
              <Icon size={14} />
              {label}
            </Button>
          ))}
        </div>
      </div>

      {hasSecondaryErrors && (
        <ErrorState
          message={`Не удалось загрузить: ${[errorHotelsBy && 'отели по районам', errorHeatmap && 'тепловая карта', errorHotels && 'отели'].filter(Boolean).join(', ')}`}
          onRetry={() => window.location.reload()}
        />
      )}

      {viewMode === 'map' && (
        <Card variant="glass">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <MapIcon className="w-5 h-5 text-[hsl(var(--primary))]" />
                <CardTitle>Карта отелей Прибайкалья</CardTitle>
              </div>
              {hotelsMap && (
                <div className="flex items-center gap-3 text-xs text-[hsl(var(--muted-foreground))]">
                  <span>{hotelsMap.total_hotels} отелей</span>
                  <span>{hotelsMap.total_rooms} номеров</span>
                  <span>Загрузка {hotelsMap.avg_occupancy}%</span>
                </div>
              )}
            </div>
            <p className="text-sm text-[hsl(var(--muted-foreground))]">
              Размер точки пропорционален заполняемости района. Клик по отелю для перехода к карточке.
            </p>
          </CardHeader>
          <CardContent>
            <GeoMap
              districts={districtsList}
              hotels={hotelsMap?.hotels}
              onDistrictClick={(d) => navigate(`/analytics?district=${encodeURIComponent(d)}`)}
              onHotelClick={(id) => navigate(`/hotels/${id}`)}
            />
            <div className="flex items-center justify-center gap-6 mt-4 text-xs text-[hsl(var(--muted-foreground))]">
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full bg-[hsl(142,71%,45%)]" /> &lt;40%
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full bg-[hsl(38,92%,50%)]" /> 40–70%
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full bg-[hsl(0,84%,60%)]" /> &gt;70%
              </span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Map view: топ районы под картой */}
      {viewMode === 'map' && districtsList.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card variant="glass">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Топ-3 района по загрузке</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {[...districtsList]
                  .filter(d => d.occupancy != null && d.hotelsCount >= 2)
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
                        <span className="font-semibold tabular-nums text-[hsl(var(--success))]">
                          {Math.round(d.occupancy ?? 0)}%
                        </span>
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
                  .filter(d => d.hotelsCount > 0)
                  .sort((a, b) => b.hotelsCount - a.hotelsCount)
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

      {viewMode === 'overview' && (
        <>
          {/* District Cards Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {districtsList.map((d) => (
              <DistrictCard
                key={d.district}
                district={d}
                isSelected={selectedDistrict === d.district}
                onClick={() => setSelectedDistrict(
                  selectedDistrict === d.district ? null : d.district
                )}
                hotelsCount={hotelsByDistrict?.find(h => h.district === d.district)?.count || 0}
                onNavigate={(page) => navigate(`/${page}?district=${encodeURIComponent(d.district)}`)}
              />
            ))}
          </div>

          {/* Treemap — distribution by city */}
          {treemapData.length > 0 && (
            <Card variant="glass">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Layers className="w-5 h-5 text-[hsl(var(--accent))]" />
                  <CardTitle>Распределение отелей по городам</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={250}>
                  <Treemap
                    data={treemapData}
                    dataKey="size"
                    aspectRatio={4 / 3}
                    stroke="hsl(var(--border))"
                    content={<TreemapCell />}
                  />
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {viewMode === 'heatmap' && (
        <>
          {/* Occupancy Heatmap as Grid */}
          <Card variant="glass">
            <CardHeader>
              <div className="flex items-center gap-2">
                <Activity className="w-5 h-5 text-[hsl(var(--warning))]" />
                <CardTitle>Загруженность по дням (14 дней)</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              {heatmapData?.data && heatmapData.data.length > 0 ? (
                <HeatmapGrid data={heatmapData.data} districts={heatmapData.districts} dates={heatmapData.dates} />
              ) : (
                <p className="text-sm text-[hsl(var(--muted-foreground))] text-center py-8">
                  Нет данных тепловой карты для выбранных параметров
                </p>
              )}
            </CardContent>
          </Card>

        </>
      )}

      {viewMode === 'comparison' && (
        <>
          {/* Radar Comparison */}
          {radarData.length > 0 && (
            <Card variant="glass">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-[hsl(var(--primary))]" />
                  <CardTitle>Сравнение районов</CardTitle>
                </div>
                <p className="text-sm text-[hsl(var(--muted-foreground))]">
                  Шкала 0–100: заполняемость в процентах; номера и цена — доля от максимума среди районов на графике
                </p>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="hsl(var(--border))" />
                    <PolarAngleAxis
                      dataKey="district"
                      tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                    />
                    <PolarRadiusAxis
                      angle={30}
                      domain={[0, 100]}
                      tick={{ fontSize: 9 }}
                    />
                    <Radar name="Заполняемость" dataKey="occupancy" stroke="hsl(var(--primary))" fill="hsl(var(--primary))" fillOpacity={0.2} />
                    <Radar name="Номера" dataKey="rooms" stroke="hsl(var(--accent))" fill="hsl(var(--accent))" fillOpacity={0.15} />
                    <Radar name="Цена" dataKey="price" stroke="hsl(var(--warning))" fill="hsl(var(--warning))" fillOpacity={0.1} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'hsl(var(--card))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '8px',
                        color: 'hsl(var(--foreground))',
                      }}
                    />
                  </RadarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {/* Price vs Occupancy */}
          {hotelsByDistrict && hotelsByDistrict.length > 0 && (
            <Card variant="glass">
              <CardHeader>
                <CardTitle>Цена vs Количество отелей</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={hotelsByDistrict.filter(d => d.avg_price).slice(0, 8)}>
                    <XAxis
                      dataKey="district"
                      tick={{ fontSize: 9 }}
                      axisLine={false}
                      tickLine={false}
                      tickFormatter={v => v.replace(' район', '').substring(0, 8)}
                    />
                    <YAxis
                      tickFormatter={v => `${(v / 1000).toFixed(0)}k`}
                      tick={{ fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      formatter={(v: number, name: string) => [
                        name === 'avg_price' ? `${Math.round(v).toLocaleString()}₽` : v,
                        name === 'avg_price' ? 'Ср. цена' : 'Отелей',
                      ]}
                      contentStyle={{
                        backgroundColor: 'hsl(var(--card))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '8px',
                        color: 'hsl(var(--foreground))',
                      }}
                    />
                    <Bar dataKey="avg_price" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}
        </>
      )}

    </div>
  )
}

/* --- Components --- */

function DistrictCard({ district, isSelected, onClick, hotelsCount, onNavigate }: {
  district: { district: string; occupancy: number; freeRooms: number; totalRooms: number; avgPrice: number }
  isSelected: boolean; onClick: () => void; hotelsCount: number
  onNavigate: (page: string) => void
}) {
  const occ = Math.round(district.occupancy)
  const level = occ > 70 ? 'high' : occ > 40 ? 'mid' : 'low'
  const levelColorClass = level === 'high' ? 'bg-[hsl(var(--destructive))]' : level === 'mid' ? 'bg-[hsl(var(--warning))]' : 'bg-[hsl(var(--success))]'

  return (
    <Card
      hover
      className={`cursor-pointer transition-all ${isSelected ? 'ring-2 ring-[hsl(var(--primary))] scale-[1.02]' : ''}`}
      onClick={onClick}
    >
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-sm truncate">{district.district}</h3>
          <Badge variant={level === 'high' ? 'danger' : level === 'mid' ? 'warning' : 'success'} size="sm">
            {occ}%
          </Badge>
        </div>
        <div className="w-full h-2 bg-[hsl(var(--secondary))] rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${levelColorClass}`}
            style={{ width: `${occ}%` }}
          />
        </div>
        <div className="grid grid-cols-3 gap-1 text-center text-xs text-[hsl(var(--muted-foreground))]">
          <div>
            <p className="font-semibold text-xs text-[hsl(var(--foreground))]">{hotelsCount}</p>
            <p>Отелей</p>
          </div>
          <div>
            <p className="font-semibold text-xs text-[hsl(var(--foreground))]">{district.freeRooms}</p>
            <p>Свободно</p>
          </div>
          <div>
            <p className="font-semibold text-xs text-[hsl(var(--foreground))]">
              {district.avgPrice ? `${Math.round(district.avgPrice / 1000)}k` : '—'}
            </p>
            <p>Цена</p>
          </div>
        </div>
        {isSelected && (
          <div className="flex gap-1 pt-1">
            <button
              onClick={(e) => { e.stopPropagation(); onNavigate('analytics') }}
              className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg text-xs font-medium bg-[hsl(var(--primary)/0.1)] text-[hsl(var(--primary))] hover:bg-[hsl(var(--primary)/0.2)] transition-colors"
            >
              <TrendingUp size={10} /> Аналитика
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onNavigate('forecast') }}
              className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg text-xs font-medium bg-[hsl(var(--accent)/0.1)] text-[hsl(var(--accent))] hover:bg-[hsl(var(--accent)/0.2)] transition-colors"
            >
              <ExternalLink size={10} /> Прогноз
            </button>
          </div>
        )}
      </div>
    </Card>
  )
}


type TreemapCellProps = {
  x?: number
  y?: number
  width?: number
  height?: number
  name?: string
  value?: number
}

function TreemapCell({ x = 0, y = 0, width = 0, height = 0, name = '', value = 0 }: TreemapCellProps) {
  if (width < 30 || height < 20) return null
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} rx={4}
        fill="hsl(var(--primary))" fillOpacity={0.15 + (value / 200)}
        stroke="hsl(var(--border))" strokeWidth={1}
      />
      {width > 50 && height > 30 && (
        <>
          <text x={x + 6} y={y + 16} fontSize={11} fontWeight={600} fill="hsl(var(--foreground))">{name}</text>
          <text x={x + 6} y={y + 30} fontSize={10} fill="hsl(var(--muted-foreground))">{value} отелей</text>
        </>
      )}
    </g>
  )
}

/* --- Helpers --- */

function _buildTreemapData(hotels: { city: string }[]) {
  const counts: Record<string, number> = {}
  hotels.forEach(h => { counts[h.city] = (counts[h.city] || 0) + 1 })
  return Object.entries(counts)
    .map(([name, size]) => ({ name, size }))
    .sort((a, b) => b.size - a.size)
    .slice(0, 15)
}

export default Map
