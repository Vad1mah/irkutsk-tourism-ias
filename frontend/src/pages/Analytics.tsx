import { useState, useMemo, memo, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { api, type DistrictData, type Recommendation } from '../api/client'
import { getWeatherEmoji } from '../utils/weather'
import { generateInsights } from '../utils/insights'
import {
  ComposedChart, Line, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend,
} from 'recharts'
import {
  MapPin, Building2, TrendingUp, DollarSign, Star,
  ArrowUpRight, ArrowDownRight, Lightbulb, AlertCircle,
  Calendar, CloudSun, Map as MapIcon,
  BarChart3, MessageSquare, Info,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent, Badge } from '../components/ui'
import { ErrorState } from '../components/ErrorState'
import { InsightCard } from '../components/InsightCard'
import { usePageTitle } from '../hooks/usePageTitle'
import { DEFAULT_DISTRICT } from '../constants/districts'

function Analytics() {
  usePageTitle('Аналитика')
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedDistrict, setSelectedDistrict] = useState(searchParams.get('district') || DEFAULT_DISTRICT)
  useEffect(() => {
    setSearchParams({ district: selectedDistrict }, { replace: true })
  }, [selectedDistrict, setSearchParams])

  const { data: districtsData, isLoading: loadingDist, isError: errorDist, refetch: refetchDist } = useQuery({
    queryKey: ['districts'],
    queryFn: api.getDistricts,
  })

  const { data: recommendations, isLoading: loadingRec, isError: errorRec } = useQuery({
    queryKey: ['recommendations'],
    queryFn: api.getRecommendations,
  })

  const { data: kpiData, isLoading: loadingKpi, isError: errorKpi } = useQuery({
    queryKey: ['kpi'],
    queryFn: api.getKPI,
  })

  const { data: hotels } = useQuery({
    queryKey: ['hotels'],
    queryFn: api.getHotels,
  })

  const { data: ensembleData, isError: errorEnsemble } = useQuery({
    queryKey: ['ensemble', selectedDistrict],
    queryFn: () => api.ensembleForecast(selectedDistrict, 14),
    retry: 1,
    staleTime: 5 * 60 * 1000,
  })

  const { data: weatherData } = useQuery({
    queryKey: ['weather'],
    queryFn: () => api.getWeather(7),
  })

  const { data: eventsData } = useQuery({
    queryKey: ['events'],
    queryFn: api.getEvents,
  })

  const { data: priceHistory, isError: errorPrice } = useQuery({
    queryKey: ['price-history'],
    queryFn: () => api.getPriceHistory(180),
    staleTime: 10 * 60 * 1000,
  })

  const hasSecondaryErrors = errorRec || errorKpi || errorPrice || errorEnsemble

  const upcomingEvents = useMemo(() => {
    if (!eventsData) return []
    const now = new Date()
    return eventsData
      .filter(e => new Date(e.date_start) >= now)
      .sort((a, b) => new Date(a.date_start).getTime() - new Date(b.date_start).getTime())
      .slice(0, 5)
  }, [eventsData])

  const isLoading = loadingDist || loadingRec || loadingKpi

  const districtsList = useMemo<DistrictData[]>(() => districtsData || [], [districtsData])
  const recommendationsList = useMemo<Recommendation[]>(() => recommendations || [], [recommendations])
  const sortedDistricts = useMemo(
    () => [...districtsList].sort((a, b) => a.occupancy - b.occupancy),
    [districtsList],
  )
  const bestForTourist = sortedDistricts[0]
  const worstForTourist = sortedDistricts[sortedDistricts.length - 1]

  if (isLoading) return <AnalyticsSkeleton />

  if (errorDist) {
    return <ErrorState title="Ошибка загрузки данных" message="Не удалось загрузить данные о районах. Убедитесь, что сервер запущен." onRetry={() => refetchDist()} />
  }

  const hasNoData = districtsList.length === 0

  return (
    <div className="space-y-6 animate-fade-in">
      {hasSecondaryErrors && (
        <ErrorState
          message={`Не удалось загрузить: ${[errorKpi && 'показатели', errorRec && 'рекомендации', errorPrice && 'историю цен', errorEnsemble && 'прогноз'].filter(Boolean).join(', ')}`}
          onRetry={() => window.location.reload()}
        />
      )}

      {/* 1. Header */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[hsl(var(--primary))] to-[hsl(var(--accent))] flex items-center justify-center">
            <BarChart3 className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Аналитика района</h1>
            <p className="text-sm text-[hsl(var(--muted-foreground))]">
              Актуальные данные и мониторинг
            </p>
          </div>
        </div>
        {districtsList.length > 0 && (
          <select
            value={selectedDistrict}
            onChange={(e) => setSelectedDistrict(e.target.value)}
            className="px-4 py-2 rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] text-sm font-medium focus:outline-none focus:ring-2 focus:ring-[hsl(var(--primary))]"
          >
            {districtsList.map(d => (
              <option key={d.district} value={d.district}>{d.district}</option>
            ))}
          </select>
        )}
      </div>

      {/* 3. No-data warning */}
      {hasNoData ? (
        <Card variant="glass" className="border-[hsl(var(--warning))]">
          <CardContent>
            <div className="flex items-center gap-3">
              <AlertCircle className="w-6 h-6 text-[hsl(var(--warning))]" />
              <div>
                <p className="font-medium">Нет данных о загруженности</p>
                <p className="text-sm text-[hsl(var(--muted-foreground))]">
                  Данные появятся после запуска парсера отелей. Загрузка данных занимает 5-10 минут.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* 4. Two insight cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {bestForTourist && (
              <Card variant="gradient" className="bg-gradient-to-br from-[hsl(var(--success)/0.1)] to-[hsl(var(--success)/0.05)] border-[hsl(var(--success)/0.3)]">
                <CardContent>
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-xl bg-[hsl(var(--success)/0.2)] flex items-center justify-center">
                      <ArrowDownRight className="w-6 h-6 text-[hsl(var(--success))]" />
                    </div>
                    <div className="flex-1">
                      <Badge variant="success" size="sm" className="mb-2">Рекомендуем туристу</Badge>
                      <h3 className="text-lg font-semibold">{bestForTourist.district}</h3>
                      <p className="text-sm text-[hsl(var(--muted-foreground))]">
                        Наименьшая загрузка — <strong>{Math.round(bestForTourist.occupancy)}%</strong>
                      </p>
                      <p className="text-sm text-[hsl(var(--muted-foreground))]">
                        Свободно номеров: ~{bestForTourist.freeRooms || 'N/A'}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {worstForTourist && districtsList.length > 1 && (
              <Card variant="default" className="border-l-4 border-l-[hsl(var(--warning))]">
                <CardContent>
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-xl bg-[hsl(var(--warning)/0.1)] flex items-center justify-center">
                      <ArrowUpRight className="w-6 h-6 text-[hsl(var(--warning))]" />
                    </div>
                    <div className="flex-1">
                      <Badge variant="warning" size="sm" className="mb-2">Высокий спрос</Badge>
                      <h3 className="text-lg font-semibold">{worstForTourist.district}</h3>
                      <p className="text-sm text-[hsl(var(--muted-foreground))]">
                        Загрузка — <strong>{Math.round(worstForTourist.occupancy)}%</strong>
                      </p>
                      <p className="text-sm text-[hsl(var(--muted-foreground))]">
                        Бронируйте заранее!
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* 5. KPI cards row */}
          <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">Агрегированные показатели по всем отелям региона</p>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <KPICard
              title="Отелей"
              value={kpiData?.total_hotels?.toString() || '—'}
              icon={Building2}
              description={`${kpiData?.total_cities || 0} городов`}
            />
            <KPICard
              title="Ср. загрузка"
              value={kpiData?.avg_occupancy ? `${kpiData.avg_occupancy}%` : '—'}
              icon={TrendingUp}
              description="по всем отелям"
            />
            <KPICard
              title="Всего номеров"
              value={kpiData?.total_rooms?.toLocaleString() || '—'}
              icon={MapPin}
              description={`${kpiData?.free_rooms?.toLocaleString() || 0} свободно`}
            />
            <KPICard
              title="Ср. цена"
              value={kpiData?.avg_price ? `${Math.round(kpiData.avg_price).toLocaleString()}₽` : '—'}
              icon={DollarSign}
              description="за ночь"
            />
          </div>

          {/* 6. Ensemble preview */}
          <p className="text-xs text-[hsl(var(--muted-foreground))]">Ансамблевый прогноз загрузки на 14 дней</p>
          {(() => {
            const insights = generateInsights(kpiData, ensembleData, weatherData, upcomingEvents.length)
            return insights.length > 0 ? (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                {insights.map((insight, i) => (
                  <InsightCard key={i} {...insight} />
                ))}
              </div>
            ) : errorEnsemble ? (
              <Card variant="glass" className="border-l-4 border-l-[hsl(var(--warning))]">
                <CardContent>
                  <div className="flex items-center gap-3">
                    <AlertCircle className="w-5 h-5 text-[hsl(var(--warning))]" />
                    <p className="text-sm text-[hsl(var(--muted-foreground))]">
                      Не удалось загрузить прогноз — инсайты временно недоступны
                    </p>
                  </div>
                </CardContent>
              </Card>
            ) : null
          })()}

          {/* 7. Weather + Price by district */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {weatherData?.forecasts && weatherData.forecasts.length > 0 && (
              <Card variant="glass">
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <CloudSun className="w-5 h-5 text-[hsl(var(--warning))]" />
                    <CardTitle className="text-base">Погода в {weatherData.location || 'Иркутске'}</CardTitle>
                  </div>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Корреляция между погодными условиями и заполняемостью</p>
                </CardHeader>
                <CardContent>
                  <div className="flex gap-2 overflow-x-auto pb-2">
                    {weatherData.forecasts.slice(0, 7).map((day, i) => {
                      const date = new Date(day.date)
                      const isToday = i === 0
                      return (
                        <div
                          key={day.date}
                          className={`flex-shrink-0 text-center p-3 rounded-xl min-w-[70px] ${
                            isToday
                              ? 'bg-gradient-to-b from-[hsl(var(--primary)/0.15)] to-[hsl(var(--primary)/0.05)] border border-[hsl(var(--primary)/0.3)]'
                              : 'bg-[hsl(var(--secondary))]'
                          }`}
                        >
                          <p className="text-[10px] text-[hsl(var(--muted-foreground))]">
                            {isToday ? 'Сегодня' : date.toLocaleDateString('ru-RU', { weekday: 'short' })}
                          </p>
                          <p className="text-xs font-medium mt-0.5">
                            {date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
                          </p>
                          <div className="text-lg my-1">{getWeatherEmoji(day.weather_code)}</div>
                          <p className="text-sm font-bold">
                            {Math.round(day.temperature_max)}°
                          </p>
                          <p className="text-[10px] text-[hsl(var(--muted-foreground))]">
                            {Math.round(day.temperature_min)}°
                          </p>
                        </div>
                      )
                    })}
                  </div>
                </CardContent>
              </Card>
            )}

            {upcomingEvents.length > 0 && (
              <Card variant="glass">
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <Calendar className="w-5 h-5 text-[hsl(var(--accent))]" />
                    <CardTitle className="text-base">Ближайшие события</CardTitle>
                  </div>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Мероприятия, влияющие на загрузку</p>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {upcomingEvents.slice(0, 5).map((event) => (
                      <div
                        key={event.event_id}
                        className="flex items-center gap-3 p-2 rounded-lg hover:bg-[hsl(var(--secondary))] transition-colors cursor-pointer"
                        onClick={() => navigate('/events')}
                      >
                        <div className="w-10 h-10 rounded-lg bg-[hsl(var(--accent)/0.1)] flex flex-col items-center justify-center flex-shrink-0">
                          <span className="text-[10px] text-[hsl(var(--accent))] font-bold">
                            {new Date(event.date_start).toLocaleDateString('ru-RU', { day: 'numeric' })}
                          </span>
                          <span className="text-[8px] text-[hsl(var(--muted-foreground))]">
                            {new Date(event.date_start).toLocaleDateString('ru-RU', { month: 'short' })}
                          </span>
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{event.title}</p>
                          {event.location && (
                            <p className="text-[10px] text-[hsl(var(--muted-foreground))] truncate">{event.location}</p>
                          )}
                        </div>
                        {event.event_type && (
                          <Badge variant="outline" size="sm">{event.event_type}</Badge>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* 9. Price history chart */}
          {(priceHistory?.prices?.length ?? 0) > 0 && priceHistory && (
            <Card variant="glass">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-[hsl(var(--primary))]" />
                    <CardTitle className="text-base">Средняя цена и объём данных по районам</CardTitle>
                  </div>
                  {priceHistory.trend && (
                    <Badge variant={priceHistory.trend.direction === 'up' ? 'danger' : 'success'} size="sm">
                      {priceHistory.trend.direction === 'up' ? '↑' : '↓'} {Math.abs(priceHistory.trend.change_percent).toFixed(1)}%
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">
                  {priceHistory.period?.days
                    ? `За последние ${priceHistory.period.days} дней: ср. цена и число отелей в выборке по датам`
                    : 'Ср. цена и число отелей в выборке по датам'}
                </p>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={240}>
                  <ComposedChart data={priceHistory.prices}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v: string) => v.slice(5)} axisLine={false} />
                    <YAxis yAxisId="price" tick={{ fontSize: 10 }} tickFormatter={(v: number) => `${(v/1000).toFixed(0)}k`} axisLine={false} />
                    <YAxis yAxisId="samples" orientation="right" tick={{ fontSize: 10 }} axisLine={false} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'hsl(var(--card))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '8px',
                        color: 'hsl(var(--foreground))',
                        fontSize: 12,
                      }}
                      labelStyle={{ color: 'hsl(var(--muted-foreground))' }}
                    />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Area yAxisId="price" type="monotone" dataKey="avg_price" name="Ср. цена" stroke="hsl(var(--primary))" fill="hsl(var(--primary)/0.2)" />
                    <Line yAxisId="samples" type="monotone" dataKey="samples" name="Отелей" stroke="hsl(var(--accent))" strokeWidth={2} dot={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {/* 10. Top hotels in district */}
          {(() => {
            const districtHotels = (hotels || [])
              .filter(h => h.district === selectedDistrict)
              .sort((a, b) => (b.rating || 0) - (a.rating || 0))
              .slice(0, 6)
            return districtHotels.length > 0 ? (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Building2 className="w-5 h-5 text-[hsl(var(--primary))]" />
                  <h2 className="text-lg font-semibold">Отели — {selectedDistrict} район</h2>
                  <Badge variant="outline" size="sm">{districtHotels.length} из {(hotels || []).filter(h => h.district === selectedDistrict).length}</Badge>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {districtHotels.map(hotel => (
                    <Card
                      key={hotel.id}
                      hover
                      className="cursor-pointer"
                      onClick={() => navigate(`/hotels/${hotel.id}`)}
                    >
                      <div className="flex items-start gap-3">
                        {hotel.image_url ? (
                          <img src={hotel.image_url} alt="" className="w-14 h-14 rounded-lg object-cover flex-shrink-0" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
                        ) : (
                          <div className="w-14 h-14 rounded-lg bg-[hsl(var(--secondary))] flex items-center justify-center flex-shrink-0">
                            <Building2 className="w-6 h-6 text-[hsl(var(--muted-foreground))]" />
                          </div>
                        )}
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-sm truncate">{hotel.name}</p>
                          <p className="text-[10px] text-[hsl(var(--muted-foreground))] truncate">{hotel.city}</p>
                          <div className="flex items-center gap-2 mt-1">
                            {hotel.rating != null && (
                              <span className="inline-flex items-center gap-0.5 text-xs font-medium text-[hsl(var(--warning))]">
                                <Star size={10} /> {hotel.rating.toFixed(1)}
                              </span>
                            )}
                            {hotel.min_price != null && (
                              <span className="text-xs text-[hsl(var(--muted-foreground))]">
                                от {hotel.min_price.toLocaleString()}₽
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              </div>
            ) : null
          })()}
        </>
      )}

      {/* 11. Recommendations */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Lightbulb className="w-5 h-5 text-[hsl(var(--warning))]" />
          <h2 className="text-lg font-semibold">Рекомендации</h2>
        </div>
        {recommendationsList.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {recommendationsList.slice(0, 4).map((rec, index) => (
              <RecommendationCard key={index} recommendation={rec} />
            ))}
          </div>
        ) : (
          <Card variant="glass" className="flex items-center justify-center h-40">
            <p className="text-sm text-[hsl(var(--muted-foreground))]">
              Недостаточно данных для рекомендаций
            </p>
          </Card>
        )}
      </div>

      {/* 12. Quick navigation */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {[
          { label: 'Спросить AI', desc: `О ${selectedDistrict} районе`, icon: MessageSquare, path: `/chat?context=${encodeURIComponent(`Расскажи о ситуации в ${selectedDistrict} районе: загрузка, погода, события`)}` },
          { label: 'Карта районов', desc: 'Визуализация на карте', icon: MapIcon, path: '/map' },
          { label: 'Прогнозы', desc: 'Ensemble ML-модели', icon: TrendingUp, path: `/forecast?district=${encodeURIComponent(selectedDistrict)}` },
          { label: 'События', desc: 'Календарь мероприятий', icon: Calendar, path: '/events' },
          { label: 'О системе', desc: 'Документация', icon: Info, path: '/about' },
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
              <p className="text-[10px] text-[hsl(var(--muted-foreground))]">{item.desc}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

const KPICard = memo(function KPICard({ title, value, icon: Icon, description }: {
  title: string; value: string; icon: React.ElementType; description: string
}) {
  return (
    <Card hover>
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-[hsl(var(--primary)/0.1)] flex items-center justify-center">
          <Icon className="w-5 h-5 text-[hsl(var(--primary))]" />
        </div>
        <div>
          <p className="text-xl font-bold">{value}</p>
          <p className="text-xs text-[hsl(var(--muted-foreground))]">{title}</p>
          <p className="text-xs text-[hsl(var(--muted-foreground))]">{description}</p>
        </div>
      </div>
    </Card>
  )
})

const RecommendationCard = memo(function RecommendationCard({ recommendation }: { recommendation: Recommendation }) {
  const isTourist = recommendation.type === 'tourist'

  return (
    <Card hover className="border-l-4" style={{ borderLeftColor: isTourist ? 'hsl(var(--primary))' : 'hsl(var(--warning))' }}>
      <div className="flex items-start gap-3">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ backgroundColor: isTourist ? 'hsl(var(--primary)/0.1)' : 'hsl(var(--warning)/0.1)' }}
        >
          {isTourist ? (
            <MapPin className="w-4 h-4 text-[hsl(var(--primary))]" />
          ) : (
            <TrendingUp className="w-4 h-4 text-[hsl(var(--warning))]" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <Badge variant={isTourist ? 'primary' : 'warning'} size="sm" className="mb-1">
            {isTourist ? 'Туристу' : 'Бизнесу'}
          </Badge>
          <h4 className="font-medium text-sm truncate">{recommendation.title}</h4>
          <p className="text-xs text-[hsl(var(--muted-foreground))] line-clamp-2">{recommendation.description}</p>
        </div>
      </div>
    </Card>
  )
})

function AnalyticsSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-10 w-48 skeleton rounded-lg" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="h-32 skeleton rounded-2xl" />
        <div className="h-32 skeleton rounded-2xl" />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[1, 2, 3, 4].map(i => <div key={i} className="h-24 skeleton rounded-2xl" />)}
      </div>
      <div className="h-[450px] skeleton rounded-2xl" />
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="h-64 skeleton rounded-2xl" />
        <div className="h-64 skeleton rounded-2xl" />
      </div>
    </div>
  )
}

export default Analytics
