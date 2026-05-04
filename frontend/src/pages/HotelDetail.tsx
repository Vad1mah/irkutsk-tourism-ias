import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { Building2, MapPin, Star, ArrowLeft, TrendingUp, DollarSign, Sparkles, Loader2, AlertCircle } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent, Badge, Button } from '../components/ui'
import { ErrorState } from '../components/ErrorState'
import { usePageTitle } from '../hooks/usePageTitle'
import { api } from '../api/client'

function HotelDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [forecastDays, setForecastDays] = useState<7 | 14 | 30>(14)
  usePageTitle('Отель')

  const forecastMutation = useMutation({
    mutationFn: () => api.hotelForecast(id!, forecastDays),
  })

  const { data: hotel, isLoading, isError, refetch } = useQuery({
    queryKey: ['hotel', id],
    queryFn: () => api.getHotel(id!),
    enabled: !!id,
  })

  const { data: stats, isError: isStatsError } = useQuery({
    queryKey: ['hotel-stats', id],
    queryFn: () => api.getHotelStats(id!),
    enabled: !!id,
  })

  if (isLoading) {
    return (
      <div className="space-y-4 animate-fade-in">
        <div className="h-8 w-48 skeleton rounded-lg" />
        <div className="h-40 skeleton rounded-xl" />
        <div className="h-64 skeleton rounded-xl" />
      </div>
    )
  }

  if (isError || !hotel) {
    return <ErrorState title="Отель не найден" message="Проверьте ссылку или вернитесь к списку." onRetry={() => refetch()} />
  }

  const chartData = (stats || [])
    .sort((a, b) => a.date.localeCompare(b.date))
    .map(s => ({
      date: new Date(s.date).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }),
      occupancy: s.available_rooms_percent != null ? Math.round(100 - s.available_rooms_percent) : null,
      price: s.min_price,
      free: s.free_rooms_amount,
    }))

  const lastStat = stats?.length ? stats[stats.length - 1] : null
  const currentOccupancy = lastStat?.available_rooms_percent != null
    ? Math.round(100 - lastStat.available_rooms_percent)
    : null

  return (
    <div className="space-y-6 animate-fade-in max-w-4xl mx-auto">
      <button onClick={() => navigate(-1)} className="inline-flex items-center gap-2 text-sm text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition-colors">
        <ArrowLeft size={16} />
        Назад
      </button>

      <Card variant="glass">
        <CardContent>
          <div className="flex items-start gap-4">
            {hotel.image_url ? (
              <img
                src={hotel.image_url}
                alt={hotel.name}
                className="w-24 h-24 rounded-xl object-cover flex-shrink-0"
                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
              />
            ) : (
              <div className="w-24 h-24 rounded-xl bg-[hsl(var(--secondary))] flex items-center justify-center flex-shrink-0">
                <Building2 className="w-10 h-10 text-[hsl(var(--muted-foreground))]" />
              </div>
            )}
            <div className="flex-1 min-w-0">
              <h1 className="text-2xl font-bold mb-1">{hotel.name}</h1>
              <div className="flex items-center gap-2 text-sm text-[hsl(var(--muted-foreground))] mb-3">
                <MapPin size={14} />
                <span>{hotel.city}</span>
                {hotel.district && <Badge variant="outline" size="sm">{hotel.district}</Badge>}
              </div>
              <div className="flex flex-wrap gap-2">
                {hotel.rating != null && (
                  <Badge variant="primary" size="sm">
                    <Star size={12} /> {hotel.rating.toFixed(1)}
                  </Badge>
                )}
                {currentOccupancy != null && (
                  <Badge
                    variant={currentOccupancy > 70 ? 'danger' : currentOccupancy > 40 ? 'warning' : 'success'}
                    size="sm"
                  >
                    <TrendingUp size={12} /> Заполняемость {currentOccupancy}%
                  </Badge>
                )}
                {lastStat?.min_price != null && (
                  <Badge variant="outline" size="sm">
                    <DollarSign size={12} /> от {lastStat.min_price.toLocaleString()}₽
                  </Badge>
                )}
              </div>
              {hotel.district && (
                <button
                  onClick={() => navigate(`/forecast?district=${encodeURIComponent(hotel.district || '')}`)}
                  className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-[hsl(var(--primary)/0.1)] text-[hsl(var(--primary))] hover:bg-[hsl(var(--primary)/0.2)] transition-colors"
                >
                  <TrendingUp size={14} />
                  Прогноз района {hotel.district}
                </button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {chartData.length > 0 ? (
        <>
          <Card variant="glass">
            <CardHeader>
              <CardTitle>Загруженность</CardTitle>
              <p className="text-sm text-[hsl(var(--muted-foreground))]">
                Расчётная загруженность: доля занятых номеров по данным агрегатора
              </p>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `${v}%`} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px',
                      color: 'hsl(var(--foreground))',
                    }}
                    formatter={(v: number) => [`${v}%`, 'Заполняемость']}
                  />
                  <Area type="monotone" dataKey="occupancy" stroke="hsl(var(--primary))" fill="hsl(var(--primary))" fillOpacity={0.15} strokeWidth={2} connectNulls />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {chartData.some(d => d.price != null && d.price > 0) ? (
            <Card variant="glass">
              <CardHeader>
                <CardTitle>Динамика цен</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={200}>
                  <AreaChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `${(v / 1000).toFixed(0)}k₽`} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'hsl(var(--card))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '8px',
                        color: 'hsl(var(--foreground))',
                      }}
                      formatter={(v: number) => [`${v.toLocaleString()}₽`, 'Мин. цена']}
                    />
                    <Area type="monotone" dataKey="price" stroke="hsl(var(--accent))" fill="hsl(var(--accent))" fillOpacity={0.15} strokeWidth={2} connectNulls />
                  </AreaChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          ) : (
            <Card variant="glass">
              <CardHeader>
                <CardTitle>Динамика цен</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-[hsl(var(--muted-foreground))] py-6 text-center">
                  Нет публикуемых цен по этому объекту за период наблюдений. Минимальная цена либо не парсится агрегатором, либо нулевая. Используйте текущую «Мин. цену» в карточке выше.
                </p>
              </CardContent>
            </Card>
          )}

          {/* Прогноз для этого объекта (POST /api/forecast {hotel_id}) */}
          <Card variant="glass">
            <CardHeader>
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-[hsl(var(--primary))]" />
                  <CardTitle>Прогноз для этого объекта</CardTitle>
                </div>
                <div className="flex items-center gap-1.5">
                  {([7, 14, 30] as const).map(d => (
                    <button
                      key={d}
                      onClick={() => setForecastDays(d)}
                      disabled={forecastMutation.isPending}
                      className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                        forecastDays === d
                          ? 'bg-[hsl(var(--primary))] text-white'
                          : 'bg-[hsl(var(--secondary)/0.5)] text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--secondary))]'
                      } disabled:opacity-50`}
                    >
                      {d} {d === 30 ? 'дней' : 'дней'}
                    </button>
                  ))}
                </div>
              </div>
              <p className="text-sm text-[hsl(var(--muted-foreground))] mt-1">
                Prophet с регрессорами (погода, события, праздники). Обучается на истории объекта.
              </p>
            </CardHeader>
            <CardContent>
              {!forecastMutation.data && !forecastMutation.isPending && !forecastMutation.isError && (
                <div className="flex flex-col items-center gap-3 py-6">
                  <p className="text-sm text-[hsl(var(--muted-foreground))] text-center max-w-md">
                    Прогноз обучается под этот объект на лету (~20–30 секунд).
                    Нажмите кнопку, чтобы запустить.
                  </p>
                  <Button
                    onClick={() => forecastMutation.mutate()}
                    variant="primary"
                    size="md"
                  >
                    <TrendingUp size={16} />
                    Запросить прогноз на {forecastDays} дней
                  </Button>
                </div>
              )}

              {forecastMutation.isPending && (
                <div className="flex flex-col items-center gap-3 py-8">
                  <Loader2 className="w-8 h-8 text-[hsl(var(--primary))] animate-spin" />
                  <p className="text-sm text-[hsl(var(--muted-foreground))]">
                    Обучаем Prophet на истории объекта…
                  </p>
                </div>
              )}

              {forecastMutation.isError && (
                <div className="flex flex-col items-center gap-3 py-6">
                  <div className="flex items-center gap-2 text-[hsl(var(--destructive))]">
                    <AlertCircle size={18} />
                    <span className="text-sm font-medium">
                      {(forecastMutation.error as Error)?.message || 'Не удалось рассчитать прогноз'}
                    </span>
                  </div>
                  <Button
                    onClick={() => forecastMutation.mutate()}
                    variant="secondary"
                    size="sm"
                  >
                    Повторить
                  </Button>
                </div>
              )}

              {forecastMutation.data && forecastMutation.data.forecast.length > 0 && (
                <>
                  {(() => {
                    const fc = forecastMutation.data.forecast
                    const occs = fc.map(p => p.occupancy)
                    const avg = Math.round(occs.reduce((a, b) => a + b, 0) / occs.length)
                    const minOcc = Math.min(...occs)
                    const maxOcc = Math.max(...occs)
                    const ciAvg = Math.round(
                      fc.reduce((a, p) => a + (p.upper_bound - p.lower_bound), 0) / fc.length
                    )
                    return (
                      <>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                          <div className="text-center">
                            <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">Средняя</p>
                            <p className="text-xl font-bold tabular-nums">{avg}%</p>
                          </div>
                          <div className="text-center">
                            <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">Пик</p>
                            <p className="text-xl font-bold tabular-nums text-[hsl(var(--success))]">
                              {Math.round(maxOcc)}%
                            </p>
                          </div>
                          <div className="text-center">
                            <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">Спад</p>
                            <p className="text-xl font-bold tabular-nums text-[hsl(var(--warning))]">
                              {Math.round(minOcc)}%
                            </p>
                          </div>
                          <div className="text-center">
                            <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">CI ширина</p>
                            <p className="text-xl font-bold tabular-nums">±{Math.round(ciAvg / 2)}</p>
                          </div>
                        </div>
                        <ResponsiveContainer width="100%" height={240}>
                          <AreaChart
                            data={fc.map(p => ({
                              date: new Date(p.date).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }),
                              forecast: Math.round(p.occupancy),
                              upper: Math.round(p.upper_bound),
                              lower: Math.round(p.lower_bound),
                            }))}
                          >
                            <defs>
                              <linearGradient id="hotelFcGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.4} />
                                <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0.05} />
                              </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                            <XAxis dataKey="date" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                            <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={v => `${v}%`} />
                            <Tooltip
                              contentStyle={{
                                backgroundColor: 'hsl(var(--card))',
                                border: '1px solid hsl(var(--border))',
                                borderRadius: '8px',
                                color: 'hsl(var(--foreground))',
                              }}
                              labelFormatter={(d) => `Дата: ${d}`}
                              formatter={(v: number, _n: string, item: { dataKey?: string }) => {
                                const labels: Record<string, string> = {
                                  forecast: 'Прогноз',
                                  upper: 'Верхняя граница',
                                  lower: 'Нижняя граница',
                                }
                                return [`${v}%`, labels[item?.dataKey ?? ''] ?? item?.dataKey ?? '']
                              }}
                            />
                            <Area type="monotone" dataKey="upper" stroke="none" fill="hsl(var(--primary)/0.12)" />
                            <Area type="monotone" dataKey="lower" stroke="none" fill="hsl(var(--background))" />
                            <Area
                              type="monotone"
                              dataKey="forecast"
                              stroke="hsl(var(--primary))"
                              strokeWidth={2.5}
                              fill="url(#hotelFcGrad)"
                            />
                          </AreaChart>
                        </ResponsiveContainer>
                        <p className="text-xs text-[hsl(var(--muted-foreground))] mt-3">
                          Обучение на {forecastMutation.data.history_points} точках истории. Узкий CI = высокая уверенность.
                        </p>
                      </>
                    )
                  })()}
                </>
              )}
            </CardContent>
          </Card>

          <Card variant="default">
            <CardHeader>
              <CardTitle>Статистика ({chartData.length} записей)</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
                <div>
                  <p className="text-2xl font-bold text-[hsl(var(--primary))]">
                    {lastStat?.rooms_num || '—'}
                  </p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Всего номеров</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-[hsl(var(--success))]">
                    {lastStat?.free_rooms_amount || '—'}
                  </p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Свободно</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-[hsl(var(--accent))]">
                    {lastStat?.min_price ? `${lastStat.min_price.toLocaleString()}₽` : '—'}
                  </p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Мин. цена</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-[hsl(var(--warning))]">
                    {currentOccupancy != null ? `${currentOccupancy}%` : '—'}
                  </p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Заполняемость</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </>
      ) : (
        <Card variant="glass">
          <CardContent>
            <p className="text-center text-[hsl(var(--muted-foreground))] py-8">
              {isStatsError
                ? 'Не удалось загрузить статистику. Проверьте соединение и попробуйте обновить страницу.'
                : 'Нет данных о загруженности для этого отеля. Данные появятся после работы парсера.'}
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export default HotelDetail
