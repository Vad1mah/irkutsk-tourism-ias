import { useState, useMemo, useEffect, memo, Fragment } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams, useNavigate } from 'react-router-dom'
import {
  api,
  type RevenueSummaryDistrict,
  type WeekdayHeatmapCell,
  type CorrectedEventsImpact,
  type SegmentsResponse,
  type PriceDistributionResponse,
} from '../api/client'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend, BarChart, Cell,
} from 'recharts'
import {
  TrendingUp, DollarSign, BarChart3, Calendar, Download, Building2,
  Activity, AlertCircle, MapPin, Info,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent, Badge, Dropdown, Button } from '../components/ui'
import { ErrorState } from '../components/ErrorState'
import { usePageTitle } from '../hooks/usePageTitle'
import { DEFAULT_DISTRICT, ALL_DISTRICT_NAMES } from '../constants/districts'

type Tab = 'regions' | 'seasonality' | 'events' | 'segments'

const TAB_LABELS: Record<Tab, string> = {
  regions: 'Регионы',
  seasonality: 'Сезонность',
  events: 'События',
  segments: 'Сегменты',
}

function Analytics() {
  usePageTitle('B2B-аналитика рынка')
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedDistrict, setSelectedDistrict] = useState(searchParams.get('district') || DEFAULT_DISTRICT)
  const [activeTab, setActiveTab] = useState<Tab>('regions')

  useEffect(() => {
    setSearchParams({ district: selectedDistrict }, { replace: true })
  }, [selectedDistrict, setSearchParams])

  const { data: revenueSummary, isLoading: loadRev, isError: errRev, refetch: refetchRev } = useQuery({
    queryKey: ['revenue-summary'],
    queryFn: api.getRevenueSummary,
  })

  const { data: heatmap, isLoading: loadHeat } = useQuery({
    queryKey: ['weekday-heatmap', selectedDistrict],
    queryFn: () => api.getWeekdayHeatmap(selectedDistrict),
    enabled: activeTab === 'seasonality',
  })

  const { data: pickup, isLoading: loadPickup } = useQuery({
    queryKey: ['pickup-pace', selectedDistrict],
    queryFn: () => api.getPickupPace(selectedDistrict, 30),
    enabled: activeTab === 'seasonality',
  })

  const { data: eventsImpactCorrected, isLoading: loadEvents } = useQuery({
    queryKey: ['events-impact-corrected'],
    queryFn: () => api.getEventsImpactCorrected(3),
    enabled: activeTab === 'events',
  })

  const { data: segments, isLoading: loadSegments } = useQuery({
    queryKey: ['segments'],
    queryFn: api.getSegments,
    enabled: activeTab === 'segments',
  })

  const { data: priceDistribution, isLoading: loadPriceDist } = useQuery({
    queryKey: ['price-distribution', selectedDistrict],
    queryFn: () => api.getPriceDistribution(selectedDistrict, 30),
    enabled: activeTab === 'segments',
  })

  const districtKpi = useMemo<RevenueSummaryDistrict | null>(() => {
    if (!revenueSummary) return null
    return revenueSummary.by_district.find(d => d.district === selectedDistrict) || null
  }, [revenueSummary, selectedDistrict])

  if (loadRev) return <AnalyticsSkeleton />

  if (errRev) {
    return (
      <ErrorState
        title="Ошибка загрузки RMS-метрик"
        message="Не удалось получить агрегаты по рынку. Проверьте, что backend запущен."
        onRetry={() => refetchRev()}
      />
    )
  }

  const hasData = revenueSummary && revenueSummary.by_district.length > 0

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[hsl(var(--primary))] to-[hsl(var(--accent))] flex items-center justify-center">
              <BarChart3 className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">B2B-аналитика рынка размещения</h1>
              <p className="text-sm text-[hsl(var(--muted-foreground))]">
                RMS-метрики, динамика бронирований, влияние событий на спрос
              </p>
            </div>
          </div>
          <Dropdown
            value={selectedDistrict}
            onChange={setSelectedDistrict}
            options={ALL_DISTRICT_NAMES.map(d => ({ value: d, label: d }))}
            compact
            className="w-56"
            icon={<MapPin size={14} />}
          />
        </div>

        <ExportButtons district={selectedDistrict} />
      </div>

      {!hasData && (
        <Card variant="glass" className="border-[hsl(var(--warning))]">
          <CardContent>
            <div className="flex items-center gap-3">
              <AlertCircle className="w-6 h-6 text-[hsl(var(--warning))]" />
              <div>
                <p className="font-medium">Недостаточно данных по рынку</p>
                <p className="text-sm text-[hsl(var(--muted-foreground))]">
                  Запустите парсеры или дождитесь следующего цикла APScheduler.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {hasData && (
        <>
          {/* Tab nav */}
          <div className="flex gap-2 border-b border-[hsl(var(--border))] mb-6">
            {(['regions', 'seasonality', 'events', 'segments'] as Tab[]).map(t => (
              <button
                key={t}
                onClick={() => setActiveTab(t)}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === t
                    ? 'border-b-2 border-[hsl(var(--primary))] text-[hsl(var(--primary))]'
                    : 'text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]'
                }`}
              >
                {TAB_LABELS[t]}
              </button>
            ))}
          </div>

          {/* Tab: Регионы */}
          {activeTab === 'regions' && (
            <RegionsTab
              revenueSummary={revenueSummary}
              districtKpi={districtKpi}
              selectedDistrict={selectedDistrict}
              setSelectedDistrict={setSelectedDistrict}
              navigate={navigate}
            />
          )}

          {/* Tab: Сезонность */}
          {activeTab === 'seasonality' && (
            <SeasonalityTab
              pickup={pickup}
              loadPickup={loadPickup}
              heatmap={heatmap}
              loadHeat={loadHeat}
            />
          )}

          {/* Tab: События */}
          {activeTab === 'events' && (
            <EventsTab
              eventsImpactCorrected={eventsImpactCorrected ?? null}
              loadEvents={loadEvents}
              navigate={navigate}
            />
          )}

          {/* Tab: Сегменты */}
          {activeTab === 'segments' && (
            <SegmentsTab
              segments={segments ?? null}
              loadSegments={loadSegments}
              priceDistribution={priceDistribution ?? null}
              loadPriceDist={loadPriceDist}
              selectedDistrict={selectedDistrict}
            />
          )}

          {/* Methodology footer */}
          <MethodologyFooter />
        </>
      )}
    </div>
  )
}

// ─── Tab: Регионы ────────────────────────────────────────────────────────────

function RegionsTab({
  revenueSummary,
  districtKpi,
  selectedDistrict,
  setSelectedDistrict,
  navigate,
}: {
  revenueSummary: { by_district: RevenueSummaryDistrict[]; methodology: string }
  districtKpi: RevenueSummaryDistrict | null
  selectedDistrict: string
  setSelectedDistrict: (d: string) => void
  navigate: (path: string) => void
}) {
  const [showOnlyReliable, setShowOnlyReliable] = useState(true)

  const list = revenueSummary.by_district
  const totalRev = list.reduce((s, d) => s + (d.revpar || 0) * (d.hotels_count || 0), 0)
  const totalHotels = list.reduce((s, d) => s + (d.hotels_count || 0), 0)
  const regionAvgRevpar = totalHotels > 0 ? totalRev / totalHotels : 0

  const sorted = [...list].sort((a, b) => (b.revpar || 0) - (a.revpar || 0))
  const filteredSorted = showOnlyReliable ? sorted.filter(d => d.confidence !== 'low') : sorted

  // Top-5 districts by RevPAR for mini bar chart
  const top5 = sorted.filter(d => (d.revpar || 0) > 0).slice(0, 5)

  return (
    <div className="space-y-6">
      {/* RMS KPI */}
      <div>
        <p className="text-xs uppercase tracking-wider text-[hsl(var(--muted-foreground))] mb-2">
          RMS-метрики района «{selectedDistrict}»
        </p>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <KPICard
            title="Загрузка"
            value={districtKpi ? `${districtKpi.occupancy}%` : '—'}
            icon={Activity}
            description="Средняя по району"
            accent="primary"
          />
          <KPICard
            title="ADR"
            value={districtKpi?.adr ? `${districtKpi.adr.toLocaleString('ru-RU')}₽` : '—'}
            icon={DollarSign}
            description="Средний тариф номера"
            accent="accent"
          />
          <KPICard
            title="RevPAR"
            value={districtKpi?.revpar ? `${districtKpi.revpar.toLocaleString('ru-RU')}₽` : '—'}
            icon={TrendingUp}
            description="Выручка на доступный номер"
            accent="success"
          />
          <KPICard
            title="Объектов"
            value={districtKpi ? String(districtKpi.hotels_count) : '—'}
            icon={Building2}
            description={districtKpi ? `Достоверность: ${confidenceLabel(districtKpi.confidence)}` : ''}
          />
        </div>
        <p className="text-xs text-[hsl(var(--muted-foreground))] mt-2 flex items-start gap-1.5">
          <Info size={12} className="mt-0.5 flex-shrink-0" />
          <span>{revenueSummary.methodology}</span>
        </p>
      </div>

      {/* Top-5 RevPAR mini bar chart */}
      {top5.length > 0 && (
        <Card variant="glass">
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-[hsl(var(--success))]" />
              <CardTitle className="text-base">Топ-5 районов по RevPAR</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={top5} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
                <XAxis type="number" tick={{ fontSize: 10 }} axisLine={false} tickLine={false}
                  tickFormatter={(v: number) => `${v.toLocaleString('ru-RU')}₽`} />
                <YAxis type="category" dataKey="district" width={90} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip
                  formatter={(v: number) => [`${v.toLocaleString('ru-RU')} ₽`, 'RevPAR']}
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="revpar" radius={[0, 4, 4, 0]}>
                  {top5.map((entry, index) => (
                    <Cell
                      key={entry.district}
                      fill={index === 0 ? 'hsl(var(--primary))' : `hsl(var(--primary) / ${(0.8 - index * 0.12).toFixed(2)})`}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* RMS table */}
      <Card variant="glass">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-[hsl(var(--success))]" />
              <CardTitle className="text-base">RMS-сводка по районам региона</CardTitle>
            </div>
            <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
              <input
                type="checkbox"
                checked={showOnlyReliable}
                onChange={e => setShowOnlyReliable(e.target.checked)}
                className="w-4 h-4 rounded border-[hsl(var(--border))] accent-[hsl(var(--primary))] cursor-pointer"
              />
              <span className="text-[hsl(var(--muted-foreground))]">Показывать только достоверные</span>
            </label>
          </div>
          <p className="text-sm text-[hsl(var(--muted-foreground))]">
            RMS-метрики по районам. Колонка «Δ к региону» показывает отклонение RevPAR от средневзвешенного по региону.
          </p>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wider text-[hsl(var(--muted-foreground))] border-b border-[hsl(var(--border))]">
                  <th className="py-2 pr-3">Район</th>
                  <th className="py-2 pr-3 text-right">Объектов</th>
                  <th className="py-2 pr-3 text-right">Загрузка</th>
                  <th className="py-2 pr-3 text-right">ADR</th>
                  <th className="py-2 pr-3 text-right">RevPAR</th>
                  <th className="py-2 pr-3 text-right">Δ к региону</th>
                  <th className="py-2 text-center">Достоверность</th>
                </tr>
              </thead>
              <tbody>
                {filteredSorted.map(d => {
                  const delta = (d.revpar || 0) - regionAvgRevpar
                  const deltaPct = regionAvgRevpar > 0 ? (delta / regionAvgRevpar) * 100 : 0
                  const isHi = d.confidence === 'high'
                  const isMid = d.confidence === 'medium'
                  return (
                    <tr
                      key={d.district}
                      className={`border-b border-[hsl(var(--border))] cursor-pointer hover:bg-[hsl(var(--secondary)/0.4)] ${d.district === selectedDistrict ? 'bg-[hsl(var(--primary)/0.06)]' : ''}`}
                      onClick={() => setSelectedDistrict(d.district)}
                    >
                      <td className="py-2 pr-3 font-medium">{d.district}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{d.hotels_count ?? '—'}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{d.occupancy != null ? `${d.occupancy}%` : '—'}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{d.adr ? `${d.adr.toLocaleString('ru-RU')}₽` : '—'}</td>
                      <td className="py-2 pr-3 text-right tabular-nums font-semibold">{d.revpar ? `${d.revpar.toLocaleString('ru-RU')}₽` : '—'}</td>
                      <td className={`py-2 pr-3 text-right tabular-nums ${delta > 0 ? 'text-[hsl(var(--success))]' : delta < 0 ? 'text-[hsl(var(--destructive))]' : 'text-[hsl(var(--muted-foreground))]'}`}>
                        {regionAvgRevpar > 0 ? `${delta > 0 ? '+' : ''}${deltaPct.toFixed(1)}%` : '—'}
                      </td>
                      <td className="py-2 text-center">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${isHi ? 'bg-[hsl(var(--success)/0.15)] text-[hsl(var(--success))]' : isMid ? 'bg-[hsl(var(--primary)/0.15)] text-[hsl(var(--primary))]' : 'bg-[hsl(var(--muted-foreground)/0.15)] text-[hsl(var(--muted-foreground))]'}`}>
                          {isHi ? `${d.hotels_count}+ объектов` : isMid ? `${d.hotels_count} объектов` : `${d.hotels_count ?? 0} (мало)`}
                        </span>
                      </td>
                    </tr>
                  )
                })}
                {filteredSorted.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-sm text-[hsl(var(--muted-foreground))]">
                      Нет районов с высокой/средней достоверностью. Снимите фильтр для отображения всех.
                    </td>
                  </tr>
                )}
              </tbody>
              <tfoot>
                <tr className="text-xs text-[hsl(var(--muted-foreground))]">
                  <td colSpan={7} className="pt-3">
                    Средневзвешенный RevPAR по региону:{' '}
                    <span className="font-semibold text-[hsl(var(--foreground))]">
                      {Math.round(regionAvgRevpar).toLocaleString('ru-RU')} ₽
                    </span>
                    . Клик по строке выбирает район.
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Quick navigation */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'Прогноз спроса', desc: 'Ensemble ML', icon: TrendingUp, path: `/forecast?district=${encodeURIComponent(selectedDistrict)}` },
          { label: 'События и спрос', desc: 'Календарь + impact', icon: Calendar, path: '/events' },
          { label: 'Региональная карта', desc: 'Объекты на карте', icon: MapPin, path: '/map' },
          { label: 'О системе', desc: 'Методология', icon: Info, path: '/about' },
        ].map(item => (
          <button
            key={item.path}
            onClick={() => navigate(item.path)}
            className="flex items-center gap-3 p-3 rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] hover:border-[hsl(var(--primary))] hover:shadow-lg transition-all text-left"
          >
            <div className="w-9 h-9 rounded-lg bg-[hsl(var(--primary)/0.1)] flex items-center justify-center flex-shrink-0">
              <item.icon className="w-4 h-4 text-[hsl(var(--primary))]" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium">{item.label}</p>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">{item.desc}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

// ─── Tab: Сезонность ─────────────────────────────────────────────────────────

function SeasonalityTab({
  pickup,
  loadPickup,
  heatmap,
  loadHeat,
}: {
  pickup: import('../api/client').PickupPace | undefined
  loadPickup: boolean
  heatmap: import('../api/client').WeekdayHeatmap | undefined
  loadHeat: boolean
}) {
  return (
    <div className="space-y-6">
      {/* Pickup/Pace */}
      <Card variant="glass">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-[hsl(var(--primary))]" />
              <CardTitle className="text-base">Динамика бронирований по дням</CardTitle>
            </div>
            {pickup?.summary && (
              <Badge
                variant={pickup.summary.trend === 'ускорение' ? 'success' : pickup.summary.trend === 'замедление' ? 'danger' : 'outline'}
                size="sm"
              >
                {pickup.summary.trend}
              </Badge>
            )}
          </div>
          <p className="text-sm text-[hsl(var(--muted-foreground))]">
            Изменение числа бронирований за сутки (Pickup): положительное значение — рост бронирований, отрицательное — сдача номеров. Период — последние 30 дней.
          </p>
        </CardHeader>
        <CardContent>
          {loadPickup ? (
            <div className="h-64 skeleton rounded-xl" />
          ) : (pickup?.points?.length ?? 0) > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <ComposedChart data={pickup!.points}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10 }}
                  tickFormatter={(v: string) => v.slice(5)}
                  axisLine={false}
                />
                <YAxis yAxisId="booked" tick={{ fontSize: 10 }} axisLine={false} />
                <YAxis yAxisId="pickup" orientation="right" tick={{ fontSize: 10 }} axisLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                    fontSize: 12,
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar yAxisId="pickup" dataKey="pickup" name="Δ бронирований за день" fill="hsl(var(--accent))" />
                <Line
                  yAxisId="booked"
                  type="monotone"
                  dataKey="booked"
                  name="Накопленные бронирования"
                  stroke="hsl(var(--primary))"
                  strokeWidth={2}
                  dot={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-[hsl(var(--muted-foreground))] py-8 text-center">
              Недостаточно дневных снимков для расчёта pickup за выбранный район.
            </p>
          )}

          {pickup?.summary && (pickup.points?.length ?? 0) > 0 && (
            <div className="grid grid-cols-3 gap-3 mt-3 pt-3 border-t border-[hsl(var(--border))]">
              <PickupStat label="Ср. pickup/день" value={`${pickup.summary.avg_pickup > 0 ? '+' : ''}${pickup.summary.avg_pickup}`} />
              <PickupStat label="Макс." value={`+${pickup.summary.max_pickup}`} />
              <PickupStat label="Мин." value={`${pickup.summary.min_pickup}`} />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Heatmap */}
      <Card variant="glass">
        <CardHeader className="pb-2">
          <div className="flex items-center gap-2">
            <Calendar className="w-5 h-5 text-[hsl(var(--accent))]" />
            <CardTitle className="text-base">Тепловая карта загрузки: день недели × месяц</CardTitle>
          </div>
          <p className="text-sm text-[hsl(var(--muted-foreground))]">
            Сезонные и недельные паттерны спроса по дням недели и месяцам.{' '}
            <span className="inline-flex items-center gap-1">
              <HatchIcon /> — ячейки с менее чем 5 наблюдениями (недостаточно данных).
            </span>
          </p>
        </CardHeader>
        <CardContent>
          {loadHeat ? (
            <div className="h-64 skeleton rounded-xl" />
          ) : heatmap && heatmap.data.length > 0 ? (
            <WeekdayHeatmapComponent heatmap={heatmap} />
          ) : (
            <p className="text-sm text-[hsl(var(--muted-foreground))] py-8 text-center">
              Нет данных загрузки по выбранному району.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

// ─── Tab: События ─────────────────────────────────────────────────────────────

function EventsTab({
  eventsImpactCorrected,
  loadEvents,
  navigate,
}: {
  eventsImpactCorrected: CorrectedEventsImpact | null
  loadEvents: boolean
  navigate: (path: string) => void
}) {
  const [onlySignificant, setOnlySignificant] = useState(false)

  const topImpact = useMemo(() => {
    if (!eventsImpactCorrected) return []
    let data = [...eventsImpactCorrected].filter(e => e.delta_pct != null)
    if (onlySignificant) data = data.filter(e => Math.abs(e.delta_pct ?? 0) >= 5)
    return data.sort((a, b) => Math.abs(b.delta_pct ?? 0) - Math.abs(a.delta_pct ?? 0)).slice(0, 10)
  }, [eventsImpactCorrected, onlySignificant])

  return (
    <div className="space-y-6">
      <Card variant="glass">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <Calendar className="w-5 h-5 text-[hsl(var(--warning))]" />
              <CardTitle className="text-base">Топ-10 событий по влиянию на спрос</CardTitle>
            </div>
            <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
              <input
                type="checkbox"
                checked={onlySignificant}
                onChange={e => setOnlySignificant(e.target.checked)}
                className="w-4 h-4 rounded border-[hsl(var(--border))] accent-[hsl(var(--primary))] cursor-pointer"
              />
              <span className="text-[hsl(var(--muted-foreground))]">только impact ≥ 5%</span>
            </label>
          </div>
          <p className="text-sm text-[hsl(var(--muted-foreground))]">
            Seasonal-corrected: отклонение загрузки в день события от базовой линии (похожие дни недели в окне ±3 нед.).
            Сортировка по модулю влияния.
          </p>
        </CardHeader>
        <CardContent>
          {loadEvents ? (
            <div className="h-64 skeleton rounded-xl" />
          ) : topImpact.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wider text-[hsl(var(--muted-foreground))] border-b border-[hsl(var(--border))]">
                    <th className="py-2 pr-3">Дата</th>
                    <th className="py-2 pr-3">Событие</th>
                    <th className="py-2 pr-3">Район</th>
                    <th className="py-2 pr-3 text-right">Δ%</th>
                    <th className="py-2 pr-3 text-right">Базовая</th>
                    <th className="py-2 pr-3 text-right">N набл.</th>
                    <th className="py-2 text-center">Достоверность</th>
                  </tr>
                </thead>
                <tbody>
                  {topImpact.map((e, i) => {
                    const isHi = e.confidence === 'high'
                    const isMid = e.confidence === 'medium'
                    return (
                      <tr
                        key={i}
                        className="border-b border-[hsl(var(--border))] hover:bg-[hsl(var(--secondary))/0.4] cursor-pointer"
                        onClick={() => navigate('/events')}
                      >
                        <td className="py-2 pr-3 whitespace-nowrap">{e.date}</td>
                        <td className="py-2 pr-3 max-w-xs truncate">{e.event}</td>
                        <td className="py-2 pr-3 whitespace-nowrap">{e.district}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">
                          <span className={`inline-flex items-center gap-0.5 ${(e.delta_pct ?? 0) > 0 ? 'text-[hsl(var(--success))]' : 'text-[hsl(var(--destructive))]'}`}>
                            {(e.delta_pct ?? 0) > 0 ? '↑' : '↓'} {Math.abs(e.delta_pct ?? 0).toFixed(1)}%
                          </span>
                        </td>
                        <td className="py-2 pr-3 text-right tabular-nums">
                          {e.baseline_mean != null ? `${e.baseline_mean.toFixed(1)}%` : '—'}
                        </td>
                        <td className="py-2 pr-3 text-right tabular-nums">{e.n_samples}</td>
                        <td className="py-2 text-center">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${isHi ? 'bg-[hsl(var(--success)/0.15)] text-[hsl(var(--success))]' : isMid ? 'bg-[hsl(var(--primary)/0.15)] text-[hsl(var(--primary))]' : 'bg-[hsl(var(--muted-foreground)/0.15)] text-[hsl(var(--muted-foreground))]'}`}>
                            {e.confidence}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-[hsl(var(--muted-foreground))] py-8 text-center">
              {eventsImpactCorrected && eventsImpactCorrected.length > 0 && onlySignificant
                ? 'Нет событий с влиянием ≥ 5%. Снимите фильтр для отображения всех.'
                : 'Недостаточно данных для расчёта влияния событий.'}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

// ─── Tab: Сегменты ────────────────────────────────────────────────────────────

const SIZE_LABELS: Record<string, string> = {
  mini: 'Мини',
  mid: 'Средние',
  large: 'Крупные',
}

function SegmentsTab({
  segments,
  loadSegments,
  priceDistribution,
  loadPriceDist,
  selectedDistrict,
}: {
  segments: SegmentsResponse | null
  loadSegments: boolean
  priceDistribution: PriceDistributionResponse | null
  loadPriceDist: boolean
  selectedDistrict: string
}) {
  // Bar chart data by accommodation_type
  const accTypeData = useMemo(() => {
    if (!segments) return []
    return Object.entries(segments.by_accommodation_type)
      .map(([type, v]) => ({ type: type || 'Не указан', count: v.count, avg_price: v.avg_price ?? 0 }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10)
  }, [segments])

  // Size bucket KPI cards
  const sizeBuckets = useMemo(() => {
    if (!segments) return []
    return Object.entries(segments.by_size).map(([bucket, v]) => ({
      bucket,
      label: SIZE_LABELS[bucket] || bucket,
      count: v.count,
      avg_occupancy: v.avg_occupancy,
      avg_price: v.avg_price,
    }))
  }, [segments])

  // Price distribution percentile bar data
  const pDistData = useMemo(() => {
    if (!priceDistribution) return []
    return [
      { label: 'p10', value: priceDistribution.p10 },
      { label: 'p25', value: priceDistribution.p25 },
      { label: 'p50', value: priceDistribution.p50 },
      { label: 'p75', value: priceDistribution.p75 },
      { label: 'p90', value: priceDistribution.p90 },
    ].filter(d => d.value != null) as { label: string; value: number }[]
  }, [priceDistribution])

  return (
    <div className="space-y-6">
      {/* Accommodation type bar chart */}
      <Card variant="glass">
        <CardHeader className="pb-2">
          <div className="flex items-center gap-2">
            <Building2 className="w-5 h-5 text-[hsl(var(--primary))]" />
            <CardTitle className="text-base">Структура по типу размещения</CardTitle>
          </div>
          <p className="text-sm text-[hsl(var(--muted-foreground))]">
            Количество объектов и средняя цена по типу размещения.
          </p>
        </CardHeader>
        <CardContent>
          {loadSegments ? (
            <div className="h-56 skeleton rounded-xl" />
          ) : accTypeData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={accTypeData} margin={{ left: 0, right: 16, top: 4, bottom: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                <XAxis
                  dataKey="type"
                  tick={{ fontSize: 9 }}
                  axisLine={false}
                  angle={-30}
                  textAnchor="end"
                  interval={0}
                />
                <YAxis yAxisId="count" tick={{ fontSize: 10 }} axisLine={false} />
                <YAxis yAxisId="price" orientation="right" tick={{ fontSize: 10 }} axisLine={false}
                  tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                    fontSize: 12,
                  }}
                  formatter={(v: number, name: string) =>
                    name === 'avg_price' ? [`${v.toLocaleString('ru-RU')} ₽`, 'Ср. цена'] : [v, 'Объектов']
                  }
                />
                <Legend wrapperStyle={{ fontSize: 11 }} formatter={(v) => v === 'count' ? 'Объектов' : 'Ср. цена (₽)'} />
                <Bar yAxisId="count" dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                <Bar yAxisId="price" dataKey="avg_price" fill="hsl(var(--accent))" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-[hsl(var(--muted-foreground))] py-8 text-center">Нет данных по сегментам.</p>
          )}
        </CardContent>
      </Card>

      {/* Size bucket KPI cards */}
      {sizeBuckets.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-wider text-[hsl(var(--muted-foreground))] mb-2">
            KPI по размеру объекта
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {sizeBuckets.map(b => (
              <Card key={b.bucket} hover>
                <div className="space-y-1.5">
                  <p className="text-sm font-semibold">{b.label}</p>
                  <div className="flex justify-between text-xs text-[hsl(var(--muted-foreground))]">
                    <span>Объектов</span>
                    <span className="font-medium text-[hsl(var(--foreground))]">{b.count}</span>
                  </div>
                  <div className="flex justify-between text-xs text-[hsl(var(--muted-foreground))]">
                    <span>Ср. загрузка</span>
                    <span className="font-medium text-[hsl(var(--foreground))]">
                      {b.avg_occupancy != null ? `${b.avg_occupancy.toFixed(1)}%` : '—'}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs text-[hsl(var(--muted-foreground))]">
                    <span>Ср. цена</span>
                    <span className="font-medium text-[hsl(var(--foreground))]">
                      {b.avg_price != null ? `${b.avg_price.toLocaleString('ru-RU')}₽` : '—'}
                    </span>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Price distribution percentiles */}
      <Card variant="glass">
        <CardHeader className="pb-2">
          <div className="flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-[hsl(var(--accent))]" />
            <CardTitle className="text-base">Распределение цен — {selectedDistrict}</CardTitle>
          </div>
          <p className="text-sm text-[hsl(var(--muted-foreground))]">
            Перцентили min_price за последние 30 дней. p50 — медиана (прокси-ADR).
          </p>
        </CardHeader>
        <CardContent>
          {loadPriceDist ? (
            <div className="h-48 skeleton rounded-xl" />
          ) : pDistData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={pDistData} margin={{ left: 0, right: 16, top: 4, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} axisLine={false} />
                  <YAxis tick={{ fontSize: 10 }} axisLine={false} tickFormatter={(v: number) => `${v.toLocaleString('ru-RU')}₽`} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px',
                      fontSize: 12,
                    }}
                    formatter={(v: number) => [`${v.toLocaleString('ru-RU')} ₽`, 'Цена']}
                  />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {pDistData.map((entry, index) => {
                      const alpha = 0.4 + index * 0.12
                      return (
                        <Cell
                          key={entry.label}
                          fill={`hsl(var(--primary) / ${Math.min(alpha, 0.9).toFixed(2)})`}
                        />
                      )
                    })}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              {priceDistribution && (
                <div className="flex flex-wrap gap-3 mt-2 text-xs text-[hsl(var(--muted-foreground))]">
                  <span>Выборка: {priceDistribution.samples} наблюдений</span>
                  <span>Период: {priceDistribution.days} дней</span>
                  {priceDistribution.p50 != null && (
                    <span>Медиана: <span className="font-semibold text-[hsl(var(--foreground))]">{priceDistribution.p50.toLocaleString('ru-RU')}₽</span></span>
                  )}
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-[hsl(var(--muted-foreground))] py-8 text-center">
              Нет данных о ценах по выбранному району.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

// ─── Methodology footer ───────────────────────────────────────────────────────

function MethodologyFooter() {
  return (
    <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--muted)/0.3)] p-4 space-y-1.5">
      <div className="flex items-center gap-2 mb-2">
        <Info size={14} className="text-[hsl(var(--muted-foreground))] flex-shrink-0" />
        <p className="text-xs font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">Методология</p>
      </div>
      <p className="text-xs text-[hsl(var(--muted-foreground))]">
        <span className="font-medium text-[hsl(var(--foreground))]">RevPAR</span> = ADR × Occupancy.
        Прокси-ADR = медиана min_price по объектам района за выбранный период.
      </p>
      <p className="text-xs text-[hsl(var(--muted-foreground))]">
        <span className="font-medium text-[hsl(var(--foreground))]">Достоверность:</span>{' '}
        high = ≥5 объектов с данными; medium = 2–4 объекта; low = ≤1 объект.
      </p>
      <p className="text-xs text-[hsl(var(--muted-foreground))]">
        <span className="font-medium text-[hsl(var(--foreground))]">События (seasonal_corrected):</span>{' '}
        базовая линия — медиана загрузки по похожим дням недели в окне ±3 нед. относительно даты события, исключая другие event-дни.
      </p>
    </div>
  )
}

// ─── Shared components ────────────────────────────────────────────────────────

const KPICard = memo(function KPICard({ title, value, icon: Icon, description, accent }: {
  title: string
  value: string
  icon: React.ElementType
  description: string
  accent?: 'primary' | 'accent' | 'success'
}) {
  const accentClass =
    accent === 'success' ? 'bg-[hsl(var(--success)/0.1)] text-[hsl(var(--success))]' :
    accent === 'accent' ? 'bg-[hsl(var(--accent)/0.1)] text-[hsl(var(--accent))]' :
    'bg-[hsl(var(--primary)/0.1)] text-[hsl(var(--primary))]'
  return (
    <Card hover>
      <div className="flex items-center gap-3">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${accentClass}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div className="min-w-0">
          <p className="text-xl font-bold tabular-nums truncate">{value}</p>
          <p className="text-xs text-[hsl(var(--muted-foreground))]">{title}</p>
          <p className="text-xs text-[hsl(var(--muted-foreground))] truncate">{description}</p>
        </div>
      </div>
    </Card>
  )
})

function PickupStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-[hsl(var(--muted-foreground))]">{label}</p>
      <p className="text-base font-semibold tabular-nums">{value}</p>
    </div>
  )
}

/** Small SVG icon for hatch/diagonal-stripe pattern indicator */
function HatchIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" className="inline-block align-middle">
      <defs>
        <pattern id="hatch-icon" patternUnits="userSpaceOnUse" width="4" height="4" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="4" stroke="hsl(var(--muted-foreground))" strokeWidth="1.5" strokeOpacity="0.5" />
        </pattern>
      </defs>
      <rect width="14" height="14" rx="2" fill="url(#hatch-icon)" stroke="hsl(var(--border))" strokeWidth="1" />
    </svg>
  )
}

function WeekdayHeatmapComponent({ heatmap }: { heatmap: { data: WeekdayHeatmapCell[]; weekdays: string[]; months: string[] } }) {
  const grid: Record<string, WeekdayHeatmapCell> = {}
  let max = 0
  for (const cell of heatmap.data) {
    grid[`${cell.weekday}-${cell.month}`] = cell
    if (cell.occupancy > max) max = cell.occupancy
  }

  const colorFor = (occ: number) => {
    if (max === 0) return 'hsl(var(--muted)/0.2)'
    const t = Math.min(1, occ / Math.max(max, 60))
    return `hsl(var(--primary) / ${(0.15 + t * 0.7).toFixed(2)})`
  }

  return (
    <div className="overflow-x-auto">
      {/* SVG defs for gap pattern — rendered once, referenced by cells */}
      <svg width="0" height="0" style={{ position: 'absolute' }}>
        <defs>
          <pattern id="hatch-gap" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke="hsl(var(--muted-foreground))" strokeWidth="1.5" strokeOpacity="0.35" />
          </pattern>
        </defs>
      </svg>
      <div className="inline-block min-w-full">
        <div className="grid grid-cols-[40px_repeat(12,minmax(38px,56px))] gap-1.5">
          <div />
          {heatmap.months.map(m => (
            <div key={m} className="text-[10px] text-center text-[hsl(var(--muted-foreground))] font-medium">{m}</div>
          ))}
          {heatmap.weekdays.map((wd, wi) => {
            const weekdayNum = wi + 1
            return (
              <Fragment key={`row-${weekdayNum}`}>
                <div className="text-[10px] flex items-center justify-end pr-1 text-[hsl(var(--muted-foreground))] font-medium">
                  {wd}
                </div>
                {heatmap.months.map((_, mi) => {
                  const cell = grid[`${weekdayNum}-${mi + 1}`]
                  const occ = cell?.occupancy ?? 0
                  const samples = cell?.samples ?? 0
                  const isGap = cell != null && samples < 5

                  if (!cell) {
                    return (
                      <div
                        key={`${weekdayNum}-${mi}`}
                        className="aspect-square rounded"
                        style={{ border: '1px dashed hsl(var(--border))' }}
                        title="нет данных"
                      />
                    )
                  }

                  if (isGap) {
                    return (
                      <div
                        key={`${weekdayNum}-${mi}`}
                        className="aspect-square rounded relative group overflow-hidden"
                        style={{ backgroundColor: 'hsl(var(--muted)/0.15)', border: '1px solid hsl(var(--border))' }}
                        title={`${heatmap.weekdays[wi]}, ${heatmap.months[mi]}: ${occ}% — недостаточно данных (n=${samples})`}
                      >
                        {/* diagonal stripe overlay */}
                        <svg
                          className="absolute inset-0 w-full h-full"
                          xmlns="http://www.w3.org/2000/svg"
                          aria-hidden="true"
                        >
                          <rect width="100%" height="100%" fill="url(#hatch-gap)" />
                        </svg>
                      </div>
                    )
                  }

                  return (
                    <div
                      key={`${weekdayNum}-${mi}`}
                      className="aspect-square rounded relative group"
                      style={{ backgroundColor: colorFor(occ) }}
                      title={`${heatmap.weekdays[wi]}, ${heatmap.months[mi]}: ${occ}% (n=${samples})`}
                    >
                      {occ > 0 && (
                        <span className="absolute inset-0 flex items-center justify-center text-[9px] font-semibold text-[hsl(var(--foreground))]/80">
                          {Math.round(occ)}
                        </span>
                      )}
                    </div>
                  )
                })}
              </Fragment>
            )
          })}
        </div>
      </div>
      <p className="text-xs text-[hsl(var(--muted-foreground))] mt-2 flex items-center gap-2">
        <span>Чем темнее — тем выше загрузка.</span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: 'hsl(var(--primary)/0.15)' }} />
          <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: 'hsl(var(--primary)/0.45)' }} />
          <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: 'hsl(var(--primary)/0.85)' }} />
        </span>
        <span>0–{Math.round(max)}%</span>
      </p>
    </div>
  )
}

function ExportButtons({ district }: { district: string }) {
  return (
    <div className="flex flex-wrap gap-2">
      <a href={api.exportUrl('occupancy', district)} download>
        <Button variant="secondary" size="sm">
          <Download size={14} />
          CSV — загрузка
        </Button>
      </a>
      <a href={api.exportUrl('events')} download>
        <Button variant="secondary" size="sm">
          <Download size={14} />
          CSV — события
        </Button>
      </a>
      <a href={api.exportUrl('hotels', district)} download>
        <Button variant="secondary" size="sm">
          <Download size={14} />
          CSV — реестр
        </Button>
      </a>
    </div>
  )
}

function confidenceLabel(c: 'high' | 'medium' | 'low'): string {
  return c === 'high' ? 'высокая' : c === 'medium' ? 'средняя' : 'низкая'
}

function AnalyticsSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-12 skeleton rounded-xl" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[1, 2, 3, 4].map(i => <div key={i} className="h-24 skeleton rounded-2xl" />)}
      </div>
      <div className="h-64 skeleton rounded-2xl" />
      <div className="h-64 skeleton rounded-2xl" />
      <div className="h-72 skeleton rounded-2xl" />
    </div>
  )
}

export default Analytics
