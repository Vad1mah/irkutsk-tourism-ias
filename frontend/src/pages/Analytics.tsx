import { useState, useMemo, useEffect, memo, Fragment } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { api, type RevenueSummaryDistrict, type WeekdayHeatmapCell, type EventImpact } from '../api/client'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend,
} from 'recharts'
import {
  TrendingUp, DollarSign, BarChart3, Calendar, Download, Building2,
  Activity, AlertCircle, MapPin, Info,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent, Badge, Dropdown, Button } from '../components/ui'
import { ErrorState } from '../components/ErrorState'
import { usePageTitle } from '../hooks/usePageTitle'
import { DEFAULT_DISTRICT, ALL_DISTRICT_NAMES } from '../constants/districts'

function Analytics() {
  usePageTitle('B2B-аналитика рынка')
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedDistrict, setSelectedDistrict] = useState(searchParams.get('district') || DEFAULT_DISTRICT)

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
  })

  const { data: pickup, isLoading: loadPickup } = useQuery({
    queryKey: ['pickup-pace', selectedDistrict],
    queryFn: () => api.getPickupPace(selectedDistrict, 30),
  })

  const { data: eventsImpact } = useQuery({
    queryKey: ['events-impact'],
    queryFn: api.getEventsImpact,
  })

  const districtKpi = useMemo<RevenueSummaryDistrict | null>(() => {
    if (!revenueSummary) return null
    return revenueSummary.by_district.find(d => d.district === selectedDistrict) || null
  }, [revenueSummary, selectedDistrict])

  const topImpact = useMemo<EventImpact[]>(() => {
    if (!eventsImpact) return []
    return [...eventsImpact]
      .filter(e => e.impact != null)
      .sort((a, b) => Math.abs(b.impact || 0) - Math.abs(a.impact || 0))
      .slice(0, 10)
  }, [eventsImpact])

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
          {/* RMS KPI блок */}
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
              <span>{revenueSummary?.methodology}</span>
            </p>
          </div>

          {/* Pickup/Pace */}
          <Card variant="glass">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <Activity className="w-5 h-5 text-[hsl(var(--primary))]" />
                  <CardTitle className="text-base">Динамика бронирований по дням</CardTitle>
                </div>
                {pickup?.summary && (
                  <Badge variant={pickup.summary.trend === 'ускорение' ? 'success' : pickup.summary.trend === 'замедление' ? 'danger' : 'outline'} size="sm">
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
                Сезонные и недельные паттерны спроса по дням недели и месяцам.
              </p>
            </CardHeader>
            <CardContent>
              {loadHeat ? (
                <div className="h-64 skeleton rounded-xl" />
              ) : heatmap && heatmap.data.length > 0 ? (
                <WeekdayHeatmap heatmap={heatmap} />
              ) : (
                <p className="text-sm text-[hsl(var(--muted-foreground))] py-8 text-center">
                  Нет данных загрузки по выбранному району.
                </p>
              )}
            </CardContent>
          </Card>

          {/* RMS-сводка по районам — интерпретируемая таблица вместо горизонтальных столбцов */}
          <Card variant="glass">
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-[hsl(var(--success))]" />
                <CardTitle className="text-base">RMS-сводка по районам региона</CardTitle>
              </div>
              <p className="text-sm text-[hsl(var(--muted-foreground))]">
                RMS-метрики по районам. Колонка «Δ к региону» показывает отклонение RevPAR от средневзвешенного по региону.
              </p>
            </CardHeader>
            <CardContent>
              {(() => {
                const list = revenueSummary?.by_district ?? []
                const totalRev = list.reduce((s, d) => s + (d.revpar || 0) * (d.hotels_count || 0), 0)
                const totalHotels = list.reduce((s, d) => s + (d.hotels_count || 0), 0)
                const totalObj = totalHotels
                const regionAvgRevpar = totalObj > 0 ? totalRev / totalObj : 0
                const sorted = [...list].sort((a, b) => (b.revpar || 0) - (a.revpar || 0))
                return (
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
                        {sorted.map(d => {
                          const delta = (d.revpar || 0) - regionAvgRevpar
                          const deltaPct = regionAvgRevpar > 0 ? (delta / regionAvgRevpar) * 100 : 0
                          const isHi = d.confidence === 'high'
                          const isMid = d.confidence === 'medium'
                          return (
                            <tr key={d.district} className={`border-b border-[hsl(var(--border))] cursor-pointer hover:bg-[hsl(var(--secondary)/0.4)] ${d.district === selectedDistrict ? 'bg-[hsl(var(--primary)/0.06)]' : ''}`} onClick={() => setSelectedDistrict(d.district)}>
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
                      </tbody>
                      <tfoot>
                        <tr className="text-xs text-[hsl(var(--muted-foreground))]">
                          <td colSpan={7} className="pt-3">
                            Средневзвешенный RevPAR по региону: <span className="font-semibold text-[hsl(var(--foreground))]">{Math.round(regionAvgRevpar).toLocaleString('ru-RU')} ₽</span>. Клик по строке выбирает район.
                          </td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                )
              })()}
            </CardContent>
          </Card>

          {/* Top events impact */}
          <Card variant="glass">
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <Calendar className="w-5 h-5 text-[hsl(var(--warning))]" />
                <CardTitle className="text-base">Топ-10 событий по влиянию на спрос</CardTitle>
              </div>
              <p className="text-sm text-[hsl(var(--muted-foreground))]">
                Изменение средней загрузки в день события относительно среднего по периоду. Сортировка по модулю влияния.
              </p>
            </CardHeader>
            <CardContent>
              {topImpact.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs uppercase tracking-wider text-[hsl(var(--muted-foreground))] border-b border-[hsl(var(--border))]">
                        <th className="py-2 pr-3">Дата</th>
                        <th className="py-2 pr-3">Событие</th>
                        <th className="py-2 pr-3">Район</th>
                        <th className="py-2 pr-3 text-right">Загрузка в день</th>
                        <th className="py-2 pr-3 text-right">Ср. загрузка</th>
                        <th className="py-2 text-right">Δ влияние</th>
                      </tr>
                    </thead>
                    <tbody>
                      {topImpact.map((e, i) => (
                        <tr key={i} className="border-b border-[hsl(var(--border))] hover:bg-[hsl(var(--secondary))/0.4] cursor-pointer" onClick={() => navigate('/events')}>
                          <td className="py-2 pr-3 whitespace-nowrap">{e.date}</td>
                          <td className="py-2 pr-3 max-w-xs truncate">{e.event}</td>
                          <td className="py-2 pr-3 whitespace-nowrap">{e.district}</td>
                          <td className="py-2 pr-3 text-right tabular-nums">{e.occupancy_on_day != null ? `${e.occupancy_on_day}%` : '—'}</td>
                          <td className="py-2 pr-3 text-right tabular-nums">{e.avg_occupancy != null ? `${e.avg_occupancy}%` : '—'}</td>
                          <td className="py-2 text-right tabular-nums">
                            <span className={`inline-flex items-center gap-1 ${(e.impact || 0) > 0 ? 'text-[hsl(var(--success))]' : 'text-[hsl(var(--destructive))]'}`}>
                              {(e.impact || 0) > 0 ? '↑' : '↓'} {Math.abs(e.impact || 0).toFixed(1)}%
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-[hsl(var(--muted-foreground))] py-8 text-center">
                  Недостаточно данных для расчёта влияния событий.
                </p>
              )}
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
        </>
      )}
    </div>
  )
}

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

function WeekdayHeatmap({ heatmap }: { heatmap: { data: WeekdayHeatmapCell[]; weekdays: string[]; months: string[] } }) {
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
                  return (
                    <div
                      key={`${weekdayNum}-${mi}`}
                      className="aspect-square rounded relative group"
                      style={{ backgroundColor: cell ? colorFor(occ) : 'transparent', border: cell ? 'none' : '1px dashed hsl(var(--border))' }}
                      title={cell ? `${heatmap.weekdays[wi]}, ${heatmap.months[mi]}: ${occ}% (n=${samples})` : 'нет данных'}
                    >
                      {cell && occ > 0 && (
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
