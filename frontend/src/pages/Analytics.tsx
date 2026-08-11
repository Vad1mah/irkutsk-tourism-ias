import { useState, useMemo, useEffect, memo, Fragment } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams, useNavigate } from 'react-router-dom'
import {
  api,
  type RevenueSummary,
  type RevenueSummaryDistrict,
  type WeekdayHeatmapCell,
  type EventsEffect,
  type EventEffectEntry,
  type SegmentsResponse,
  type PriceDistributionResponse,
  type DistrictSegmentsResponse,
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
import { MethodologyTooltip } from '../components/MethodologyTooltip'
import { usePageTitle } from '../hooks/usePageTitle'
import { DEFAULT_DISTRICT, ALL_DISTRICT_NAMES } from '../constants/districts'
import { localizeConfidence, localizeAccommodationType, localizeSizeBucket } from '../utils/localize'
import { RECHARTS_TOOLTIP_PROPS, BAR_CURSOR_TRANSPARENT } from '../utils/chartTheme'

type Tab = 'regions' | 'seasonality' | 'events' | 'segments'

/** Сколько типов размещения показывает график структуры. */
const TOP_ACCOMMODATION_TYPES = 10

/** Потолок строк на файл в /api/analytics/export — выгрузка режется по самым свежим датам. */
const EXPORT_ROW_LIMIT = 10000

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
  const initialTab = (searchParams.get('tab') as Tab) ?? 'regions'
  const validTabs: Tab[] = ['regions', 'seasonality', 'events', 'segments']
  const [activeTab, setActiveTab] = useState<Tab>(
    validTabs.includes(initialTab) ? initialTab : 'regions'
  )

  useEffect(() => {
    const next: Record<string, string> = { district: selectedDistrict }
    if (activeTab !== 'regions') next.tab = activeTab
    setSearchParams(next, { replace: true })
  }, [selectedDistrict, activeTab, setSearchParams])

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

  const { data: eventsEffect, isLoading: loadEvents } = useQuery({
    queryKey: ['events-effect'],
    queryFn: api.getEventsEffect,
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
          <div role="tablist" aria-label="Разделы аналитики" className="flex gap-2 border-b border-[hsl(var(--border))] mb-6">
            {(['regions', 'seasonality', 'events', 'segments'] as Tab[]).map(t => (
              <button
                key={t}
                role="tab"
                aria-selected={activeTab === t}
                aria-controls={`tabpanel-${t}`}
                id={`tab-${t}`}
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
              eventsEffect={eventsEffect ?? null}
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
          <MethodologyFooter asOfDate={revenueSummary.as_of_date ?? null} />
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
  revenueSummary: RevenueSummary
  districtKpi: RevenueSummaryDistrict | null
  selectedDistrict: string
  setSelectedDistrict: (d: string) => void
  navigate: (path: string) => void
}) {
  const [showOnlyReliable, setShowOnlyReliable] = useState(true)
  const [expandedDistrict, setExpandedDistrict] = useState<string | null>(null)
  const { data: drillDown, isLoading: drillLoading } = useQuery({
    queryKey: ['district-segments', expandedDistrict],
    queryFn: () => api.getDistrictSegments(expandedDistrict!),
    enabled: !!expandedDistrict,
  })

  const list = revenueSummary.by_district
  const snapshotDate = _formatIsoDate(revenueSummary.as_of_date)
  // Региональный RevPAR берём из API: он взвешен по номерному фонду района,
  // как и написано в строке методологии под карточками.
  const regionAvgRevpar = revenueSummary.revpar || 0

  const sorted = [...list].sort((a, b) => (b.revpar || 0) - (a.revpar || 0))
  const filteredSorted = showOnlyReliable ? sorted.filter(d => d.confidence !== 'low') : sorted

  // Top-5 districts by RevPAR — из того же набора, что и таблица под графиком
  const top5 = filteredSorted.filter(d => (d.revpar || 0) > 0).slice(0, 5)

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
            description="Взвешена по номерному фонду"
            accent="primary"
            tooltip="Загрузка района = 100 × занятые номера / все номера объектов, приславших снимок. Это не среднее по объектам: отель на 100 номеров влияет на район сильнее, чем гостевой дом на 5."
          />
          <KPICard
            title="Прокси-ADR"
            value={districtKpi?.adr ? `${districtKpi.adr.toLocaleString('ru-RU')}₽` : '—'}
            icon={DollarSign}
            description={`Медиана мин. цены на ${snapshotDate}`}
            accent="accent"
            tooltip="Прокси-ADR — медиана минимальной цены номера по объектам района на дату среза. Это не ADR отеля из PMS: видна только рекламируемая на сайтах бронирования цена, реальный средний тариф обычно на 15–30% выше."
          />
          <KPICard
            title="RevPAR"
            value={districtKpi?.revpar ? `${districtKpi.revpar.toLocaleString('ru-RU')}₽` : '—'}
            icon={TrendingUp}
            description="Прокси-ADR × Загрузка"
            accent="success"
            tooltip="RevPAR (Revenue per Available Room) — выручка с доступного номера = прокси-ADR × Загрузка. Наследует прокси-природу цены: это оценка по рекламируемым тарифам, а не выручка по факту."
          />
          <KPICard
            title="Объектов"
            value={districtKpi ? String(districtKpi.hotels_count) : '—'}
            icon={Building2}
            description={districtKpi ? `Со снимком за ${snapshotDate} · ${localizeConfidence(districtKpi.confidence)}` : ''}
            tooltip={`Объекты района, приславшие суточный снимок за ${snapshotDate}. В справочнике объектов больше — часть не отчитывается каждый день, полный список выгружается кнопкой «CSV — реестр». Достоверность: высокая — от 10 объектов, средняя — 3–9, низкая — 2 и меньше.`}
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
              <MethodologyTooltip text="RevPAR (Revenue per Available Room) — выручка на доступный номер: прокси-ADR × Загрузка. Главный показатель в гостиничном бизнесе: учитывает и цену, и заполняемость." />
            </div>
            <p className="text-xs text-[hsl(var(--muted-foreground))]">
              Чем выше столбец, тем больше выручки приносит каждый номер района за сутки.
              Набор районов — тот же, что и в таблице ниже: при снятом фильтре достоверности
              в топ попадают и районы с двумя-тремя объектами.
            </p>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={top5} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
                <XAxis type="number" tick={{ fontSize: 10 }} axisLine={false} tickLine={false}
                  tickFormatter={(v: number) => `${v.toLocaleString('ru-RU')}₽`} />
                <YAxis type="category" dataKey="district" width={90} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip
                  {...RECHARTS_TOOLTIP_PROPS}
                  cursor={BAR_CURSOR_TRANSPARENT}
                  formatter={(v: number) => [`${v.toLocaleString('ru-RU')} ₽`, 'RevPAR']}
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
              <CardTitle className="text-base">RMS-сводка по районам макрорегиона</CardTitle>
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
            Байкальский макрорегион: Иркутская область и прибайкальские районы Бурятии —
            рынок вокруг озера не делится по границе субъектов. Колонка «Δ к региону»
            показывает отклонение RevPAR от средневзвешенного по макрорегиону.
          </p>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wider text-[hsl(var(--muted-foreground))] border-b border-[hsl(var(--border))]">
                  <th className="py-2 pr-3">Район</th>
                  <th className="py-2 pr-3 text-right">
                    <span className="inline-flex items-center gap-1 justify-end">
                      Объектов
                      <MethodologyTooltip text={`Объекты, приславшие суточный снимок за ${snapshotDate}. В справочнике района объектов больше, а в разбивке под строкой — объекты со снимком за 14 дней: это три разных окна, а не расхождение данных.`} />
                    </span>
                  </th>
                  <th className="py-2 pr-3 text-right">Загрузка</th>
                  <th className="py-2 pr-3 text-right">
                    <span className="inline-flex items-center gap-1 justify-end">
                      Прокси-ADR
                      <MethodologyTooltip text="Медиана минимальной цены номера по объектам района на дату среза. Реальный тариф выше: видна только рекламируемая цена." />
                    </span>
                  </th>
                  <th className="py-2 pr-3 text-right">
                    <span className="inline-flex items-center gap-1 justify-end">
                      RevPAR
                      <MethodologyTooltip text="RevPAR = прокси-ADR × Загрузка. Выручка с одного доступного номера за сутки." />
                    </span>
                  </th>
                  <th className="py-2 pr-3 text-right">
                    <span className="inline-flex items-center gap-1 justify-end">
                      Δ к региону
                      <MethodologyTooltip text="Отклонение RevPAR района от RevPAR макрорегиона, взвешенного по номерному фонду. Зелёный — выше макрорегиона, красный — ниже." />
                    </span>
                  </th>
                  <th className="py-2 text-center">
                    <span className="inline-flex items-center gap-1 justify-center">
                      Достоверность
                      <MethodologyTooltip text="Считается по числу объектов со снимком на дату среза: высокая — от 10 объектов, средняя — 3–9, низкая — 2 и меньше. На двух объектах «средняя по району» — это метрика одного отеля, выданная за рынок." />
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredSorted.map(d => {
                  const delta = (d.revpar || 0) - regionAvgRevpar
                  const deltaPct = regionAvgRevpar > 0 ? (delta / regionAvgRevpar) * 100 : 0
                  const isHi = d.confidence === 'high'
                  const isMid = d.confidence === 'medium'
                  const isExpanded = expandedDistrict === d.district
                  return (
                    <Fragment key={d.district}>
                      <tr
                        className={`border-b border-[hsl(var(--border))] cursor-pointer hover:bg-[hsl(var(--secondary)/0.4)] ${d.district === selectedDistrict ? 'bg-[hsl(var(--primary)/0.06)]' : ''}`}
                        onClick={() => setExpandedDistrict(isExpanded ? null : d.district)}
                      >
                        <td className="py-2 pr-3 font-medium">
                          <span className="inline-block w-3 mr-1 text-[hsl(var(--muted-foreground))]">
                            {isExpanded ? '▾' : '▸'}
                          </span>
                          {d.district}
                        </td>
                        <td className="py-2 pr-3 text-right tabular-nums">{d.hotels_count ?? '—'}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{d.occupancy != null ? `${d.occupancy}%` : '—'}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{d.adr ? `${d.adr.toLocaleString('ru-RU')}₽` : '—'}</td>
                        <td className="py-2 pr-3 text-right tabular-nums font-semibold">{d.revpar ? `${d.revpar.toLocaleString('ru-RU')}₽` : '—'}</td>
                        <td className={`py-2 pr-3 text-right tabular-nums ${delta > 0 ? 'text-[hsl(var(--success))]' : delta < 0 ? 'text-[hsl(var(--destructive))]' : 'text-[hsl(var(--muted-foreground))]'}`}>
                          {regionAvgRevpar > 0 ? `${delta > 0 ? '+' : ''}${deltaPct.toFixed(1)}%` : '—'}
                        </td>
                        <td className="py-2 text-center">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${isHi ? 'bg-[hsl(var(--success)/0.15)] text-[hsl(var(--success))]' : isMid ? 'bg-[hsl(var(--primary)/0.15)] text-[hsl(var(--primary))]' : 'bg-[hsl(var(--muted-foreground)/0.15)] text-[hsl(var(--muted-foreground))]'}`}>
                            {isHi || isMid ? `${d.hotels_count} объектов` : `${d.hotels_count ?? 0} (мало)`}
                          </span>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr className="bg-[hsl(var(--secondary)/0.25)]">
                          <td colSpan={7} className="px-3 py-4">
                            <DistrictDrillDown
                              loading={drillLoading}
                              data={drillDown}
                              onPickAsFilter={() => setSelectedDistrict(d.district)}
                              isFilterDistrict={d.district === selectedDistrict}
                            />
                          </td>
                        </tr>
                      )}
                    </Fragment>
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
                    RevPAR по макрорегиону, взвешенный по номерному фонду:{' '}
                    <span className="font-semibold text-[hsl(var(--foreground))]">
                      {Math.round(regionAvgRevpar).toLocaleString('ru-RU')} ₽
                    </span>
                    {' '}— считается по всем районам, включая скрытые фильтром достоверности,
                    поэтому сумма видимых строк с ним не сходится.
                    Клик по строке раскрывает разбивку по типам размещения.
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
          { label: 'Прогноз спроса', desc: 'Взвешенное среднее двух моделей', icon: TrendingUp, path: `/forecast?district=${encodeURIComponent(selectedDistrict)}` },
          { label: 'События и спрос', desc: 'Календарь и влияние', icon: Calendar, path: '/events' },
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
              <CardTitle className="text-base">Занятые номера и их суточное изменение</CardTitle>
            </div>
            {pickup?.summary && (
              <span className="inline-flex items-center gap-1">
                <Badge
                  variant={pickup.summary.trend === 'ускорение' ? 'success' : pickup.summary.trend === 'замедление' ? 'danger' : 'outline'}
                  size="sm"
                >
                  {pickup.summary.trend}
                </Badge>
                <MethodologyTooltip text="Сравниваются средние по первым и последним трём суткам окна, у которых изменение не равно нулю; порог — 20%. Знак базы при этом не учитывается, поэтому вывод сверяется со средним изменением за сутки в карточках ниже." />
              </span>
            )}
          </div>
          <p className="text-sm text-[hsl(var(--muted-foreground))]">
            Линия — сколько номеров района занято в этот день, столбик — изменение этой
            величины за сутки. Окно: {pickup?.period ? `${_formatIsoDate(pickup.period.start)} — ${_formatIsoDate(pickup.period.end)}` : 'последние 30 дней'}.
            Состав объектов, приславших снимок, в разные дни разный, поэтому часть суточного
            изменения — это приход и уход объектов из выборки, а не брони и отмены.
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
                  {...RECHARTS_TOOLTIP_PROPS}
                  cursor={BAR_CURSOR_TRANSPARENT}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar yAxisId="pickup" dataKey="pickup" name="Δ занятых номеров за сутки" fill="hsl(var(--accent))" />
                <Line
                  yAxisId="booked"
                  type="monotone"
                  dataKey="booked"
                  name="Занято номеров"
                  stroke="hsl(var(--primary))"
                  strokeWidth={2}
                  dot={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-[hsl(var(--muted-foreground))] py-8 text-center">
              Недостаточно дневных снимков, чтобы посчитать темп бронирований по этому району.
            </p>
          )}

          {pickup?.summary && (pickup.points?.length ?? 0) > 0 && (
            <>
              <div className="grid grid-cols-3 gap-3 mt-3 pt-3 border-t border-[hsl(var(--border))]">
                <PickupStat label="Ср. Δ (дни с изменением)" value={_signedNumber(pickup.summary.avg_pickup)} />
                <PickupStat label="Максимум за сутки" value={_signedNumber(pickup.summary.max_pickup)} />
                <PickupStat label="Минимум за сутки" value={_signedNumber(pickup.summary.min_pickup)} />
              </div>
              <p className="text-xs text-[hsl(var(--muted-foreground))] mt-2">
                {_pickupTrendNote(pickup.summary.trend, pickup.summary.avg_pickup)}
              </p>
            </>
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
              <HatchIcon /> — ячейки, где меньше 5 наблюдений (недостаточно данных).
            </span>{' '}
            Наблюдение — это объект за один день, а не календарная дата: ячейка может
            набрать сотню наблюдений с одной-единственной недели. Данные за
            24.06.2025 – 25.10.2025 (123 дня) не собирались, эти месяцы опираются
            на остаток истории.
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
  eventsEffect,
  loadEvents,
  navigate,
}: {
  eventsEffect: EventsEffect | null
  loadEvents: boolean
  navigate: (path: string) => void
}) {
  return (
    <div className="space-y-6">
      <Card variant="glass">
        <CardHeader className="pb-2">
          <div className="flex items-center gap-2">
            <Calendar className="w-5 h-5 text-[hsl(var(--warning))]" />
            <CardTitle className="text-base">Влияние событий на загрузку — что показало измерение</CardTitle>
          </div>
          <p className="text-sm text-[hsl(var(--muted-foreground))]">
            День события сравнивается с обычными днями того же календарного месяца в том же районе.{' '}
            <MethodologyTooltip text="У каждой пары «район — месяц» своя точка отсчёта, поэтому форма сезонной кривой не моделируется и подкручивать в методе нечего. Ошибка считается по этим же ячейкам: многодневный фестиваль даёт подряд идущие дни с общим уровнем спроса, и считать их независимыми наблюдениями нельзя." />
          </p>
        </CardHeader>
        <CardContent>
          {loadEvents ? (
            <div className="h-48 skeleton rounded-xl" />
          ) : eventsEffect ? (
            <div className="space-y-4">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wider text-[hsl(var(--muted-foreground))] border-b border-[hsl(var(--border))]">
                      <th className="py-2 pr-3">Район</th>
                      <th className="py-2 pr-3 text-right">Эффект, п.п.</th>
                      <th className="py-2 pr-3 text-right">95% интервал</th>
                      <th className="py-2 pr-3 text-right">
                        Эпизодов
                        <MethodologyTooltip text="Неразрывные серии событийных дней. Месячный фестиваль — это один случай, а не тридцать: оценка по нему не становится надёжнее оттого, что он длился месяц. Серия считается по дням, для которых есть снимок загрузки: день без снимка внутри фестиваля разрывает его на два эпизода." />
                      </th>
                      <th className="py-2">Вывод</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[eventsEffect.overall, ...eventsEffect.by_district].map((row, i) => (
                      <tr key={i} className="border-b border-[hsl(var(--border))]">
                        <td className="py-2 pr-3 whitespace-nowrap font-medium">
                          {row.district ?? 'Все районы (пул)'}
                        </td>
                        <td className="py-2 pr-3 text-right tabular-nums">
                          {row.identifiable && row.effect_pp != null
                            ? `${row.effect_pp > 0 ? '+' : ''}${row.effect_pp.toFixed(1)}`
                            : '—'}
                        </td>
                        <td className="py-2 pr-3 text-right tabular-nums whitespace-nowrap">
                          {row.identifiable && row.ci_lower != null && row.ci_upper != null
                            ? `[${row.ci_lower > 0 ? '+' : ''}${row.ci_lower.toFixed(1)}, ${row.ci_upper > 0 ? '+' : ''}${row.ci_upper.toFixed(1)}]`
                            : '—'}
                        </td>
                        <td className="py-2 pr-3 text-right tabular-nums">{row.episodes ?? '—'}</td>
                        <td className="py-2 text-[hsl(var(--muted-foreground))]">
                          {_eventEffectVerdict(row)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">
                Период данных: {_formatIsoDate(eventsEffect.period.from)} — {_formatIsoDate(eventsEffect.period.to)}
                {' '}(внутри него нет данных за 24.06.2025 – 25.10.2025, 123 дня).
                Район показывается с оценкой, только если в нём набралось не меньше{' '}
                {eventsEffect.min_episodes} независимых эпизодов. Ниже этого порога отделить
                событие от сезона нельзя: фестиваль, который каждый год ставят на пик спроса,
                неотличим от самого пика. Строка «Все районы» — общий пул: порог применён
                к сумме эпизодов, и в неё входят районы, которые по отдельности порог
                не проходят, поэтому переносить её вывод на конкретный район нельзя.
              </p>
              <Button variant="secondary" size="sm" onClick={() => navigate('/events')}>
                Календарь событий
              </Button>
            </div>
          ) : (
            <p className="text-sm text-[hsl(var(--muted-foreground))] py-8 text-center">
              Недостаточно данных, чтобы измерить влияние событий.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

// ─── Tab: Сегменты ────────────────────────────────────────────────────────────

type AccommodationTypeStructure = {
  rows: { type: string; count: number }[]
  /** Объектов во всём справочнике. */
  total: number
  /** Объектов, попавших в показанный топ типов. */
  shown: number
  /** Сколько всего различных типов размещения в данных. */
  kinds: number
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
  // Bar chart data by accommodation_type — топ-10 типов из справочника
  const typeStructure = useMemo<AccommodationTypeStructure>(() => {
    if (!segments) return { rows: [], total: 0, shown: 0, kinds: 0 }
    const all = Object.entries(segments.by_accommodation_type)
      .map(([type, v]) => ({ type: localizeAccommodationType(type), count: v.count }))
      .sort((a, b) => b.count - a.count)
    const rows = all.slice(0, TOP_ACCOMMODATION_TYPES)
    return {
      rows,
      total: all.reduce((s, r) => s + r.count, 0),
      shown: rows.reduce((s, r) => s + r.count, 0),
      kinds: all.length,
    }
  }, [segments])

  // Size bucket KPI cards
  const sizeBuckets = useMemo(() => {
    if (!segments) return []
    return Object.entries(segments.by_size).map(([bucket, v]) => ({
      bucket,
      label: localizeSizeBucket(bucket),
      count: v.count,
      avg_occupancy: v.avg_occupancy,
    }))
  }, [segments])

  const sizeTotal = sizeBuckets.reduce((s, b) => s + b.count, 0)
  const sizeThresholds = segments?.size_thresholds

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
            <CardTitle className="text-base">Структура по типу размещения — весь макрорегион</CardTitle>
            <MethodologyTooltip text="Распределение объектов по типу: отель, гостевой дом, хостел, апартаменты, база отдыха, шале, кемпинг и др. Тип берётся из 101hotels live-каталога и из OSM Overpass с привязкой по координатам (радиус 0.5 км)." />
          </div>
          <p className="text-sm text-[hsl(var(--muted-foreground))]">
            Топ-{TOP_ACCOMMODATION_TYPES} типов по числу объектов в справочнике всего
            макрорегиона. Выбранный в шапке район на этот блок не влияет — разрез по району
            открывается кликом по строке района на вкладке «Регионы».
          </p>
        </CardHeader>
        <CardContent>
          {loadSegments ? (
            <div className="h-56 skeleton rounded-xl" />
          ) : typeStructure.rows.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={Math.max(220, typeStructure.rows.length * 36)}>
                <BarChart data={typeStructure.rows} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis dataKey="type" type="category" width={140} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} interval={0} />
                  <Tooltip
                    {...RECHARTS_TOOLTIP_PROPS}
                    cursor={BAR_CURSOR_TRANSPARENT}
                    formatter={(v: number) => [v, 'Объектов']}
                  />
                  <Bar dataKey="count" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <p className="text-xs text-[hsl(var(--muted-foreground))] mt-2">
                На графике {typeStructure.shown} объектов из {typeStructure.total} в справочнике;
                {' '}остальные {typeStructure.total - typeStructure.shown} — редкие типы
                (всего типов {typeStructure.kinds}).
              </p>
            </>
          ) : (
            <p className="text-sm text-[hsl(var(--muted-foreground))] py-8 text-center">Нет данных по сегментам.</p>
          )}
        </CardContent>
      </Card>

      {/* Size bucket KPI cards */}
      {sizeBuckets.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-wider text-[hsl(var(--muted-foreground))] mb-2 inline-flex items-center gap-1.5">
            <span>KPI по размеру объекта — весь макрорегион</span>
            <MethodologyTooltip
              text={`Размер определяется по числу номеров: «Мини» — до ${sizeThresholds?.mini_max ?? 15} номеров, «Средние» — до ${sizeThresholds?.mid_max ?? 50}, «Крупные» — больше. Объекты без указанного числа номеров в разбивку не входят вовсе. Загрузка сегмента взвешена по номерному фонду.`}
            />
          </p>
          <p className="text-xs text-[hsl(var(--muted-foreground))] mb-2">
            {sizeTotal} объектов со снимком за 14 дней и заполненным числом номеров
            {typeStructure.total > sizeTotal
              ? ` — на ${typeStructure.total - sizeTotal} меньше, чем в структуре по типам выше: там весь справочник.`
              : '.'}
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
                    <span>Загрузка</span>
                    <span className="font-medium text-[hsl(var(--foreground))]">
                      {b.avg_occupancy != null ? `${b.avg_occupancy.toFixed(1)}%` : '—'}
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
            Распределение минимальных цен за номер по району за {priceDistribution?.days ?? 30} дней.
            Единица выборки — наблюдение «объект × день», а не объект: чем чаще объект попадал
            в парсинг, тем больше его вес. Столбец — граница: «10%» означает, что 10% наблюдений
            дешевле этой цены, а 90% — дороже.
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
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} axisLine={false} tickFormatter={_pctLabel} />
                  <YAxis tick={{ fontSize: 10 }} axisLine={false} tickFormatter={(v: number) => `${v.toLocaleString('ru-RU')}₽`} />
                  <Tooltip
                    {...RECHARTS_TOOLTIP_PROPS}
                    cursor={BAR_CURSOR_TRANSPARENT}
                    formatter={(v: number) => [`${v.toLocaleString('ru-RU')} ₽`, 'Граница цены']}
                    labelFormatter={_pctTooltipLabel}
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
                  <span>Выборка: {priceDistribution.samples} наблюдений «объект × день»</span>
                  <span>Период: {priceDistribution.days} дней</span>
                  {priceDistribution.p50 != null && (
                    <span>
                      Медиана за период:{' '}
                      <span className="font-semibold text-[hsl(var(--foreground))]">{priceDistribution.p50.toLocaleString('ru-RU')}₽</span>
                      {' '}(прокси-ADR на вкладке «Регионы» считается на дату среза, поэтому отличается)
                    </span>
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

function MethodologyFooter({ asOfDate }: { asOfDate: string | null }) {
  return (
    <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--muted)/0.3)] p-4 space-y-1.5">
      <div className="flex items-center gap-2 mb-2">
        <Info size={14} className="text-[hsl(var(--muted-foreground))] flex-shrink-0" />
        <p className="text-xs font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">Методология</p>
      </div>
      <p className="text-xs text-[hsl(var(--muted-foreground))]">
        <span className="font-medium text-[hsl(var(--foreground))]">RevPAR</span> = прокси-ADR × Загрузка.
        Прокси-ADR — медиана минимальной цены за номер по объектам района на дату среза
        ({_formatIsoDate(asOfDate)}). Перцентили цен на вкладке «Сегменты» считаются за 30 дней,
        поэтому их медиана отличается от прокси-ADR на этот день.
      </p>
      <p className="text-xs text-[hsl(var(--muted-foreground))]">
        <span className="font-medium text-[hsl(var(--foreground))]">Достоверность:</span>{' '}
        высокая — от 10 объектов со снимком на дату среза; средняя — 3–9 объектов;
        низкая — 2 и меньше.
      </p>
      <p className="text-xs text-[hsl(var(--muted-foreground))]">
        <span className="font-medium text-[hsl(var(--foreground))]">События:</span>{' '}
        панельная регрессия загрузки с собственной константой на каждую пару «район × календарный
        месяц»: день события сравнивается с обычными днями того же месяца в том же районе.
        Форма сезонной кривой не моделируется.
      </p>
      <p className="text-xs text-[hsl(var(--muted-foreground))]">
        <span className="font-medium text-[hsl(var(--foreground))]">География:</span>{' '}
        Байкальский макрорегион — Иркутская область и прибайкальские районы Республики Бурятия.
        Пробел в данных: 24.06.2025 – 25.10.2025 (123 дня), парсеры не работали.
      </p>
    </div>
  )
}

// ─── Shared components ────────────────────────────────────────────────────────

const KPICard = memo(function KPICard({ title, value, icon: Icon, description, accent, tooltip }: {
  title: string
  value: string
  icon: React.ElementType
  description: string
  accent?: 'primary' | 'accent' | 'success'
  tooltip?: string
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
          <p className="text-xs text-[hsl(var(--muted-foreground))] flex items-center gap-1">
            {title}
            {tooltip && <MethodologyTooltip text={tooltip} />}
          </p>
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
  for (const cell of heatmap.data) {
    grid[`${cell.weekday}-${cell.month}`] = cell
  }

  const observed = heatmap.data
    .filter(c => c.samples >= 5 && c.occupancy > 0)
    .map(c => c.occupancy)
  const obsMin = observed.length ? Math.min(...observed) : 0
  const obsMax = observed.length ? Math.max(...observed) : 100
  const span = Math.max(obsMax - obsMin, 1)

  const colorFor = (occ: number) => {
    if (observed.length === 0) return 'hsl(var(--muted)/0.2)'
    const t = Math.min(1, Math.max(0, (occ - obsMin) / span))
    return `hsl(var(--primary) / ${(0.15 + t * 0.75).toFixed(2)})`
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
            <div key={m} className="text-xs text-center text-[hsl(var(--muted-foreground))] font-medium">{m}</div>
          ))}
          {heatmap.weekdays.map((wd, wi) => {
            const weekdayNum = wi + 1
            return (
              <Fragment key={`row-${weekdayNum}`}>
                <div className="text-xs flex items-center justify-end pr-1 text-[hsl(var(--muted-foreground))] font-medium">
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
                        <span className="absolute inset-0 flex items-center justify-center text-[11px] font-semibold text-[hsl(var(--foreground))]/80">
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
        <span>
          {observed.length > 0
            ? `${Math.round(obsMin)}%–${Math.round(obsMax)}% (контраст по наблюдаемому диапазону)`
            : 'нет данных'}
        </span>
      </p>
    </div>
  )
}

function ExportButtons({ district }: { district: string }) {
  return (
    <div className="flex flex-col items-start sm:items-end gap-1.5">
      <div className="flex flex-wrap gap-2">
        <a href={api.exportUrl('occupancy', district)} download>
          <Button variant="secondary" size="sm">
            <Download size={14} />
            CSV — суточная загрузка
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
            CSV — реестр объектов
          </Button>
        </a>
      </div>
      <p className="text-xs text-[hsl(var(--muted-foreground))]">
        В файл попадает не больше {EXPORT_ROW_LIMIT.toLocaleString('ru-RU')} строк, самых свежих по дате:
        по суточной загрузке крупного района это лишь последние месяцы, а не вся история.
      </p>
    </div>
  )
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

const _PCT_AXIS: Record<string, string> = {
  p10: '10%', p25: '25%', p50: 'Медиана', p75: '75%', p90: '90%',
}

const _PCT_TOOLTIP: Record<string, string> = {
  p10: '10% наблюдений дешевле',
  p25: '25% наблюдений дешевле',
  p50: 'Медиана наблюдений',
  p75: '25% наблюдений дороже',
  p90: '10% наблюдений дороже',
}

function _pctLabel(v: string): string {
  return _PCT_AXIS[v] ?? v
}

function _pctTooltipLabel(v: string): string {
  return _PCT_TOOLTIP[v] ?? v
}

/** ISO-дата (YYYY-MM-DD) в привычный DD.MM.YYYY; пустое значение — прочерк. */
function _formatIsoDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-')
  return y && m && d ? `${d}.${m}.${y}` : iso
}

/** Число со знаком: у нуля знака нет. */
function _signedNumber(v: number): string {
  return v > 0 ? `+${v}` : String(v)
}

/**
 * Текст под карточками темпа бронирований.
 *
 * Бэкенд определяет тренд множительным сравнением краёв окна, поэтому при
 * отрицательной базе «ускорением» может оказаться ухудшение. Направление
 * объявляется, только когда краевое сравнение и среднее изменение сходятся.
 */
function _pickupTrendNote(trend: string, avgPickup: number): string {
  if (trend === 'недостаточно данных') {
    return 'Дневных снимков в окне слишком мало, чтобы оценить темп: направление не определяется.'
  }
  if (trend === 'ускорение' && avgPickup > 0) {
    return 'Занятых номеров прибавляется быстрее, чем в начале окна, и среднее изменение за сутки положительное.'
  }
  if (trend === 'замедление' && avgPickup < 0) {
    return 'Занятых номеров прибавляется медленнее, чем в начале окна, и среднее изменение за сутки отрицательное.'
  }
  if (trend === 'ускорение' || trend === 'замедление') {
    return 'Направление неоднозначно: сравнение краёв окна и среднее изменение за сутки расходятся в знаке.'
  }
  return 'Значимых сдвигов в темпе бронирований за окно не зафиксировано.'
}

/** Вердикт по строке событийного эффекта: интервал и перестановочный тест могут расходиться. */
function _eventEffectVerdict(row: EventEffectEntry): string {
  if (!row.identifiable) return row.reason ?? 'оценка невозможна'
  const placeboP = row.placebo_p ?? null
  if (row.detected) {
    if (placeboP == null) return 'эффект обнаружен'
    return placeboP < 0.05
      ? 'эффект обнаружен, перестановочный тест согласен'
      : 'эффект обнаружен, но перестановочный тест его не подтверждает'
  }
  if (placeboP != null && placeboP < 0.05) {
    return `неоднозначно: интервал накрывает ноль, но перестановочный тест значим (p = ${placeboP.toFixed(3)})`
  }
  return 'эффект не обнаружен'
}

function DistrictDrillDown({
  loading,
  data,
  onPickAsFilter,
  isFilterDistrict,
}: {
  loading: boolean
  data: DistrictSegmentsResponse | undefined
  onPickAsFilter: () => void
  isFilterDistrict: boolean
}) {
  if (loading) {
    return <div className="h-24 skeleton rounded-md" />
  }
  if (!data || data.total_objects === 0) {
    return (
      <p className="text-xs text-[hsl(var(--muted-foreground))] italic">
        Нет данных для сегментирования (района нет в hotel_statistics или мало объектов).
      </p>
    )
  }
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="text-xs text-[hsl(var(--muted-foreground))]">
          <span className="font-medium text-[hsl(var(--foreground))]">{data.total_objects} объектов</span>
          {' '}района <span className="font-medium text-[hsl(var(--foreground))]">{data.district}</span>
          {' '}со снимком за последние 14 дней — окно шире, чем у колонки «Объектов» в строке выше
          (там только дата среза). Метрики — по последнему снимку каждого объекта.
        </div>
        {!isFilterDistrict && (
          <button
            onClick={(e) => { e.stopPropagation(); onPickAsFilter() }}
            className="text-xs px-2 py-1 rounded-md bg-[hsl(var(--primary))] text-white hover:bg-[hsl(var(--primary)/0.9)]"
          >
            Применить фильтр
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <p className="text-xs uppercase tracking-wider text-[hsl(var(--muted-foreground))] mb-1.5">
            По типу размещения
          </p>
          <table className="w-full text-xs">
            <thead className="text-[hsl(var(--muted-foreground))]">
              <tr className="border-b border-[hsl(var(--border))]">
                <th className="text-left py-1.5">Тип</th>
                <th className="text-right py-1.5">Объектов</th>
                <th className="text-right py-1.5">Загрузка</th>
                <th className="text-right py-1.5">RevPAR</th>
              </tr>
            </thead>
            <tbody>
              {data.by_accommodation_type.map(s => (
                <tr key={s.type} className="border-b border-[hsl(var(--border)/0.4)]">
                  <td className="py-1.5">{localizeAccommodationType(s.type)}</td>
                  <td className="text-right tabular-nums">{s.count}</td>
                  <td className="text-right tabular-nums">{s.avg_occupancy.toFixed(1)}%</td>
                  <td className="text-right tabular-nums font-medium">
                    {s.revpar ? `${s.revpar.toLocaleString('ru-RU')}₽` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div>
          <p className="text-xs uppercase tracking-wider text-[hsl(var(--muted-foreground))] mb-1.5">
            По размеру
          </p>
          <table className="w-full text-xs">
            <thead className="text-[hsl(var(--muted-foreground))]">
              <tr className="border-b border-[hsl(var(--border))]">
                <th className="text-left py-1.5">Размер</th>
                <th className="text-right py-1.5">Объектов</th>
                <th className="text-right py-1.5">Загрузка</th>
                <th className="text-right py-1.5">RevPAR</th>
              </tr>
            </thead>
            <tbody>
              {data.by_size.map(s => (
                <tr key={s.size} className="border-b border-[hsl(var(--border)/0.4)]">
                  <td className="py-1.5">{localizeSizeBucket(s.size)}</td>
                  <td className="text-right tabular-nums">{s.count}</td>
                  <td className="text-right tabular-nums">{s.avg_occupancy.toFixed(1)}%</td>
                  <td className="text-right tabular-nums font-medium">
                    {s.revpar ? `${s.revpar.toLocaleString('ru-RU')}₽` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <p className="text-xs text-[hsl(var(--muted-foreground))] italic">
        RevPAR сегмента считается от среднего минимального тарифа, а не от медианы, поэтому
        с районным RevPAR в строке выше он сходиться не обязан.
      </p>
    </div>
  )
}

export default Analytics
