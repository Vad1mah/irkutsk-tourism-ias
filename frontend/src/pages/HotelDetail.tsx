import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  LineChart, Line, Legend,
} from 'recharts'
import { Building2, MapPin, Star, ArrowLeft, TrendingUp, DollarSign, Sparkles, Loader2, AlertCircle, GitCompare, CheckCircle2 } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent, Badge, Button } from '../components/ui'
import { ErrorState } from '../components/ErrorState'
import { usePageTitle } from '../hooks/usePageTitle'
import { api } from '../api/client'
import type { HotelSegmentBenchmarkResponse } from '../api/client'
import { RECHARTS_TOOLTIP_PROPS } from '../utils/chartTheme'

/** Снимок старше этого возраста подаётся как устаревший. */
const STALE_SNAPSHOT_DAYS = 2
/** Разрыв между соседними наблюдениями, который рвёт линию графика. */
const GAP_BREAK_DAYS = 2
/** Литерал района для объектов без геопривязки. */
const UNKNOWN_DISTRICT = 'Неизвестный'
/** Число объектов сегмента, ниже которого среднее неустойчиво. */
const SEGMENT_LOW_CONFIDENCE = 2
const SEGMENT_HIGH_CONFIDENCE = 10

type HotelStatRow = {
  date: string
  rooms_num: number | null
  free_rooms_amount: number | null
  min_price: number | null
}

type ForecastHorizon = 3 | 7 | 14

const FORECAST_HORIZONS: { days: ForecastHorizon; label: string; hint: string }[] = [
  { days: 3, label: '3 дня', hint: 'ошибка на уровне наивного прогноза «завтра как вчера»' },
  { days: 7, label: '7 дней', hint: 'ошибка сопоставима с наивным прогнозом' },
  { days: 14, label: '14 дней', hint: 'ошибка выше наивного прогноза' },
]

function _plural(n: number, forms: [string, string, string]): string {
  const abs = Math.abs(n) % 100
  const last = abs % 10
  if (abs > 10 && abs < 20) return forms[2]
  if (last === 1) return forms[0]
  if (last > 1 && last < 5) return forms[1]
  return forms[2]
}

function _fmtDelta(delta: number | null, unit: string): string {
  if (delta == null) return '—'
  const sign = delta >= 0 ? '+' : ''
  return `${sign}${delta.toFixed(1)}${unit}`
}

function _fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('ru-RU')
}

function _fmtAxisDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: '2-digit' })
}

function _daysSince(iso: string | null | undefined): number | null {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  return Math.floor((Date.now() - d.getTime()) / 86_400_000)
}

/** Загрузка объекта из его собственного номерного фонда; null без rooms_num. */
function _occupancy(stat: HotelStatRow): number | null {
  const rooms = stat.rooms_num ?? 0
  if (!rooms) return null
  const free = Math.min(Math.max(stat.free_rooms_amount ?? 0, 0), rooms)
  return Math.round((100 * (rooms - free)) / rooms)
}

function SegmentBenchmarkBlock({ benchmark }: { benchmark: HotelSegmentBenchmarkResponse | undefined }) {
  if (!benchmark) return null

  const { hotel, segment, hotel_metrics, segment_metrics, n_in_segment, as_of, segment_window_days } = benchmark
  const territory = segment.district ?? hotel.district ?? null

  if (!territory || territory === UNKNOWN_DISTRICT) {
    return (
      <Card variant="glass">
        <CardHeader>
          <div className="flex items-center gap-2">
            <GitCompare className="w-5 h-5 text-[hsl(var(--primary))]" />
            <CardTitle>Сравнение с сегментом</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-[hsl(var(--muted-foreground))] text-center py-4">
            Геопривязка объекта не определена — сегмент для сравнения не собирается.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (n_in_segment === 0) {
    return (
      <Card variant="glass">
        <CardHeader>
          <div className="flex items-center gap-2">
            <GitCompare className="w-5 h-5 text-[hsl(var(--primary))]" />
            <CardTitle>Сравнение с сегментом</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-[hsl(var(--muted-foreground))] text-center py-4">
            В сегменте нет других объектов со снимком за последние {segment_window_days} дней
          </p>
        </CardContent>
      </Card>
    )
  }

  const occDelta = hotel_metrics.occupancy != null && segment_metrics.avg_occupancy != null
    ? hotel_metrics.occupancy - segment_metrics.avg_occupancy
    : null
  const priceDelta = hotel_metrics.min_price != null && segment_metrics.avg_price != null
    ? hotel_metrics.min_price - segment_metrics.avg_price
    : null

  const sizeBucketLabel: Record<string, string> = { mini: 'мини', mid: 'средний', large: 'крупный' }
  const bucketLabel = sizeBucketLabel[segment.size_bucket] ?? segment.size_bucket

  const snapshotAge = _daysSince(as_of)
  const isStale = snapshotAge != null && snapshotAge > STALE_SNAPSHOT_DAYS

  const sampleNote = n_in_segment <= SEGMENT_LOW_CONFIDENCE
    ? `Выборка сегмента ниже порога достоверности: ${n_in_segment} ${_plural(n_in_segment, ['объект', 'объекта', 'объектов'])}. Среднее по такой выборке — справочная величина.`
    : n_in_segment < SEGMENT_HIGH_CONFIDENCE
      ? `Ограниченная выборка сегмента: ${n_in_segment} ${_plural(n_in_segment, ['объект', 'объекта', 'объектов'])} (достоверная — от ${SEGMENT_HIGH_CONFIDENCE}). Среднее неустойчиво.`
      : null

  const rows: {
    metric: string
    hotel: string
    segment: string
    segmentNote: string
    delta: string
    positive: boolean | null
  }[] = [
    {
      metric: 'Загрузка',
      hotel: hotel_metrics.occupancy != null ? `${hotel_metrics.occupancy.toFixed(1)}%` : '—',
      segment: segment_metrics.avg_occupancy != null ? `${segment_metrics.avg_occupancy.toFixed(1)}%` : '—',
      segmentNote: 'взвешено по номерному фонду',
      delta: _fmtDelta(occDelta, ' п.п.'),
      positive: occDelta != null ? occDelta >= 0 : null,
    },
    {
      metric: 'Мин. цена',
      hotel: hotel_metrics.min_price != null ? `${hotel_metrics.min_price.toLocaleString()} ₽` : '—',
      segment: segment_metrics.avg_price != null ? `${segment_metrics.avg_price.toLocaleString()} ₽` : '—',
      segmentNote: 'среднее по объектам',
      delta: priceDelta != null ? _fmtDelta(priceDelta, ' ₽') : '—',
      positive: priceDelta != null ? priceDelta >= 0 : null,
    },
  ]

  return (
    <Card variant="glass">
      <CardHeader>
        <div className="flex items-center gap-2">
          <GitCompare className="w-5 h-5 text-[hsl(var(--primary))]" />
          <CardTitle>Сравнение с сегментом</CardTitle>
        </div>
        <p className="text-sm text-[hsl(var(--muted-foreground))] mt-1">
          Сегмент: {territory} × {bucketLabel} — сравнение с {n_in_segment}{' '}
          {_plural(n_in_segment, ['другим объектом', 'другими объектами', 'другими объектами'])} со снимком
          за {segment_window_days} дней. Данные объекта — снимок за {_fmtDate(as_of)}.
        </p>
      </CardHeader>
      <CardContent>
        {isStale && (
          <div className="mb-3 flex items-start gap-2 p-3 rounded-lg border border-[hsl(var(--warning)/0.4)] bg-[hsl(var(--warning)/0.08)] text-xs">
            <AlertCircle size={14} className="flex-shrink-0 mt-0.5 text-[hsl(var(--warning))]" />
            <p className="text-[hsl(var(--muted-foreground))] leading-relaxed">
              <span className="font-semibold text-[hsl(var(--warning))]">Снимок объекта устарел.</span>{' '}
              Данные объекта — за {_fmtDate(as_of)}, это {snapshotAge}{' '}
              {_plural(snapshotAge ?? 0, ['день', 'дня', 'дней'])} назад, а сегмент посчитан по снимкам
              за последние {segment_window_days} дней. Строки сравниваются за разные периоды —
              разницу нельзя читать как результат объекта.
            </p>
          </div>
        )}
        {sampleNote && (
          <p className="mb-3 text-xs text-[hsl(var(--muted-foreground))]">{sampleNote}</p>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[hsl(var(--border))]">
                <th className="text-left py-2 pr-4 font-medium text-[hsl(var(--muted-foreground))]">Метрика</th>
                <th className="text-right py-2 pr-4 font-medium text-[hsl(var(--muted-foreground))]">
                  Этот объект ({_fmtDate(as_of)})
                </th>
                <th className="text-right py-2 pr-4 font-medium text-[hsl(var(--muted-foreground))]">
                  Сегмент за {segment_window_days} дней
                </th>
                <th className="text-right py-2 font-medium text-[hsl(var(--muted-foreground))]">Разница (п.п. / ₽)</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ metric, hotel: hotelVal, segment: segVal, segmentNote, delta, positive }) => (
                <tr key={metric} className="border-b border-[hsl(var(--border)/0.5)] last:border-0">
                  <td className="py-2.5 pr-4 font-medium">{metric}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">{hotelVal}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums text-[hsl(var(--muted-foreground))]">
                    {segVal}
                    <span className="block text-xs">{segmentNote}</span>
                  </td>
                  <td className={`py-2.5 text-right tabular-nums font-semibold ${
                    positive === null || isStale ? 'text-[hsl(var(--muted-foreground))]'
                    : positive ? 'text-[hsl(var(--success))]' : 'text-[hsl(var(--destructive))]'
                  }`}>{delta}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}

function HotelDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [forecastDays, setForecastDays] = useState<ForecastHorizon>(7)
  usePageTitle('Объект размещения')

  const forecastMutation = useMutation({
    mutationFn: () => api.hotelForecast(id!, forecastDays),
  })

  const validationMutation = useMutation({
    mutationFn: () => api.getHotelValidation(id!, 14),
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

  const { data: benchmark } = useQuery({
    queryKey: ['hotel-segment-benchmark', id],
    queryFn: () => api.getHotelSegmentBenchmark(id!),
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

  const sortedStats: HotelStatRow[] = (stats ?? []).slice().sort((a, b) => a.date.localeCompare(b.date))

  const chartData: { date: string; occupancy: number | null; price: number | null }[] = []
  sortedStats.forEach((s, i) => {
    const prev = i > 0 ? sortedStats[i - 1] : null
    if (prev) {
      const gapDays = Math.round(
        (new Date(s.date).getTime() - new Date(prev.date).getTime()) / 86_400_000,
      )
      if (gapDays > GAP_BREAK_DAYS) {
        chartData.push({ date: '⋯', occupancy: null, price: null })
      }
    }
    chartData.push({
      date: _fmtAxisDate(s.date),
      occupancy: _occupancy(s),
      price: s.min_price,
    })
  })

  const lastStat = sortedStats.length ? sortedStats[sortedStats.length - 1] : null
  const firstStat = sortedStats.length ? sortedStats[0] : null
  const currentOccupancy = lastStat ? _occupancy(lastStat) : null
  const snapshotAge = _daysSince(lastStat?.date)
  const isSnapshotStale = snapshotAge != null && snapshotAge > STALE_SNAPSHOT_DAYS
  const hasSeries = sortedStats.length >= 2
  const showDots = sortedStats.length < 4

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
                {currentOccupancy != null && lastStat && (
                  <Badge variant="outline" size="sm">
                    <TrendingUp size={12} /> Заполняемость {currentOccupancy}% на {_fmtDate(lastStat.date)}
                  </Badge>
                )}
                {lastStat?.min_price != null && (
                  <Badge variant="outline" size="sm">
                    <DollarSign size={12} /> от {lastStat.min_price.toLocaleString()}₽
                  </Badge>
                )}
                {isSnapshotStale && (
                  <Badge variant="warning" size="sm">
                    <AlertCircle size={12} /> Снимок устарел: {snapshotAge}{' '}
                    {_plural(snapshotAge ?? 0, ['день', 'дня', 'дней'])} назад
                  </Badge>
                )}
              </div>
              {currentOccupancy == null && lastStat && (
                <p className="mt-2 text-xs text-[hsl(var(--muted-foreground))]">
                  Номерной фонд объекта не известен — загрузка по нему не считается.
                </p>
              )}
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

      <SegmentBenchmarkBlock benchmark={benchmark} />

      {sortedStats.length > 0 ? (
        <>
          {hasSeries ? (
            <>
              <Card variant="glass">
                <CardHeader>
                  <CardTitle>Загруженность</CardTitle>
                  <p className="text-sm text-[hsl(var(--muted-foreground))]">
                    Доля занятых номеров объекта по данным агрегатора: 100 × (номера − свободные) / номера.
                    Наблюдения за {_fmtDate(firstStat?.date)} — {_fmtDate(lastStat?.date)}; разрыв в ряду
                    (в том числе пробел данных 24.06.2025 – 25.10.2025, 123 дня) линией не соединяется.
                  </p>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={250}>
                    <AreaChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis dataKey="date" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                      <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `${v}%`} />
                      <Tooltip
                        {...RECHARTS_TOOLTIP_PROPS}
                        formatter={(v: number) => [`${v}%`, 'Заполняемость']}
                      />
                      <Area
                        type="monotone" dataKey="occupancy"
                        stroke="hsl(var(--primary))" fill="hsl(var(--primary))"
                        fillOpacity={0.15} strokeWidth={2}
                        dot={showDots ? { r: 3 } : false}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              {chartData.some(d => d.price != null && d.price > 0) ? (
                <Card variant="glass">
                  <CardHeader>
                    <CardTitle>Динамика цен</CardTitle>
                    <p className="text-sm text-[hsl(var(--muted-foreground))]">
                      Минимальная опубликованная цена объекта, {_fmtDate(firstStat?.date)} — {_fmtDate(lastStat?.date)}.
                    </p>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={200}>
                      <AreaChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                        <XAxis dataKey="date" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `${(v / 1000).toFixed(0)}k₽`} />
                        <Tooltip
                          {...RECHARTS_TOOLTIP_PROPS}
                          formatter={(v: number) => [`${v.toLocaleString()}₽`, 'Мин. цена']}
                        />
                        <Area
                          type="monotone" dataKey="price"
                          stroke="hsl(var(--accent))" fill="hsl(var(--accent))"
                          fillOpacity={0.15} strokeWidth={2}
                          dot={showDots ? { r: 3 } : false}
                        />
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
            </>
          ) : (
            <Card variant="glass">
              <CardHeader>
                <CardTitle>Загруженность</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-[hsl(var(--muted-foreground))] py-6 text-center">
                  По объекту есть только одно наблюдение — снимок за {_fmtDate(lastStat?.date)}.
                  Динамика загрузки и цены недоступна.
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
                  {FORECAST_HORIZONS.map(({ days, label, hint }) => (
                    <button
                      key={days}
                      onClick={() => setForecastDays(days)}
                      disabled={forecastMutation.isPending}
                      title={hint}
                      className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                        forecastDays === days
                          ? 'bg-[hsl(var(--primary))] text-white'
                          : 'bg-[hsl(var(--secondary)/0.5)] text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--secondary))]'
                      } disabled:opacity-50`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
              <p className="text-sm text-[hsl(var(--muted-foreground))] mt-1">
                Prophet обучается на истории этого объекта. Погода берётся по центру Иркутска, события —
                общерегиональные: район объекта в запрос прогноза не передаётся. Горизонт ограничен 14 днями;
                за пределами 3–7 дней ошибка модели превышает ошибку наивного прогноза «завтра как вчера»,
                поэтому результат читается как сценарий, а не как основание для тарифного решения.
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
                    Запросить прогноз на {FORECAST_HORIZONS.find(h => h.days === forecastDays)?.label}
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
                    return (
                      <>
                        <div className="grid grid-cols-3 gap-3 mb-4">
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
                              {...RECHARTS_TOOLTIP_PROPS}
                              labelFormatter={(d) => `Дата: ${d}`}
                              formatter={(v: number, name: string) => {
                                const labels: Record<string, string> = {
                                  forecast: 'Прогноз',
                                  upper: 'Верхняя граница',
                                  lower: 'Нижняя граница',
                                }
                                return [`${v}%`, labels[name] ?? name]
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
                          Обучение на {forecastMutation.data.history_points} точках истории.
                          Полоса вокруг линии — 80% интервал Prophet; его калибровка на этих данных
                          не подтверждена, поэтому ширина полосы не является мерой точности.
                        </p>
                      </>
                    )
                  })()}
                </>
              )}
            </CardContent>
          </Card>

          {/* Точность прогноза (backtest validation для конкретного объекта) */}
          <Card variant="glass">
            <CardHeader>
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-[hsl(var(--accent))]" />
                  <CardTitle>Точность прогноза для этого объекта</CardTitle>
                </div>
                {validationMutation.data && validationMutation.data.samples > 0 && (
                  <Badge variant="outline" size="sm">
                    backtest: {validationMutation.data.samples}{' '}
                    {_plural(validationMutation.data.samples, ['наблюдение', 'наблюдения', 'наблюдений'])}
                  </Badge>
                )}
              </div>
              <p className="text-sm text-[hsl(var(--muted-foreground))] mt-1">
                Метод holdout-backtest: модель обучается на истории объекта без последних 14 наблюдений,
                прогнозирует их и сравнивается с фактом. Наблюдения идут неравномерно, поэтому 14 записей
                покрывают больше 14 календарных дней, а метрики считаются только по совпавшим датам.
                RMSE/MAE/MAPE показывают типичную ошибку именно для этого средства размещения, а не для
                усреднённого района.
              </p>
            </CardHeader>
            <CardContent>
              {!validationMutation.data && !validationMutation.isPending && !validationMutation.isError && (
                <div className="flex flex-col items-center gap-3 py-6">
                  <p className="text-sm text-[hsl(var(--muted-foreground))] text-center max-w-md">
                    Запуск занимает ~2-5 секунд: обучается Prophet и считаются метрики.
                  </p>
                  <Button onClick={() => validationMutation.mutate()} variant="secondary" size="md">
                    <CheckCircle2 size={16} />
                    Проверить точность
                  </Button>
                </div>
              )}

              {validationMutation.isPending && (
                <div className="flex flex-col items-center gap-3 py-6">
                  <Loader2 className="w-7 h-7 text-[hsl(var(--accent))] animate-spin" />
                  <p className="text-sm text-[hsl(var(--muted-foreground))]">Запускаем backtest…</p>
                </div>
              )}

              {validationMutation.isError && (
                <div className="flex items-center gap-2 text-[hsl(var(--destructive))] py-4">
                  <AlertCircle size={16} />
                  <span className="text-sm">
                    {(validationMutation.error as Error)?.message || 'Не удалось рассчитать точность'}
                  </span>
                </div>
              )}

              {validationMutation.data && validationMutation.data.error && (
                <div className="flex items-start gap-2 text-[hsl(var(--warning))] py-4 text-sm">
                  <AlertCircle size={16} className="flex-shrink-0 mt-0.5" />
                  <span>{validationMutation.data.error}</span>
                </div>
              )}

              {validationMutation.data && validationMutation.data.samples > 0 && (
                <>
                  <div className="grid grid-cols-3 gap-3 mb-4">
                    <div className="text-center">
                      <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">RMSE</p>
                      <p className="text-xl font-bold tabular-nums">{validationMutation.data.rmse?.toFixed(1)}</p>
                      <p className="text-xs text-[hsl(var(--muted-foreground))]">п.п.</p>
                    </div>
                    <div className="text-center">
                      <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">MAE</p>
                      <p className="text-xl font-bold tabular-nums">{validationMutation.data.mae?.toFixed(1)}</p>
                      <p className="text-xs text-[hsl(var(--muted-foreground))]">п.п.</p>
                    </div>
                    <div className="text-center">
                      <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">MAPE</p>
                      <p className="text-xl font-bold tabular-nums">{validationMutation.data.mape?.toFixed(1)}%</p>
                    </div>
                  </div>

                  <p className="mb-3 text-xs text-[hsl(var(--muted-foreground))] leading-relaxed">
                    Ошибку сравнивайте с наивным прогнозом «завтра как вчера»: на почти плоском ряде
                    загрузки низкий RMSE сам по себе не означает, что модель полезна.
                  </p>

                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart
                      data={validationMutation.data.forecasted.map((f, i) => ({
                        date: new Date(f.date).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }),
                        forecast: f.occupancy,
                        actual: validationMutation.data!.actual[i]?.occupancy ?? null,
                      }))}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis dataKey="date" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                      <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={v => `${v}%`} />
                      <Tooltip
                        {...RECHARTS_TOOLTIP_PROPS}
                        formatter={(v: number, name: string) => [
                          `${v.toFixed(1)}%`,
                          name === 'forecast' ? 'Прогноз' : 'Факт',
                        ]}
                      />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Line
                        type="monotone" dataKey="forecast" name="Прогноз"
                        stroke="hsl(var(--primary))" strokeWidth={2} dot={{ r: 3 }}
                      />
                      <Line
                        type="monotone" dataKey="actual" name="Факт"
                        stroke="hsl(var(--success))" strokeWidth={2} strokeDasharray="4 4" dot={{ r: 3 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-3">
                    Обучение на {validationMutation.data.history_points - validationMutation.data.test_days} наблюдениях,
                    проверка на {validationMutation.data.samples} совпавших датах
                    ({_fmtDate(validationMutation.data.actual[0]?.date)} —{' '}
                    {_fmtDate(validationMutation.data.actual[validationMutation.data.actual.length - 1]?.date)}).
                    Пунктирная линия — фактическая занятость по данным парсера.
                  </p>
                </>
              )}
            </CardContent>
          </Card>

          <Card variant="default">
            <CardHeader>
              <CardTitle>
                Статистика: {sortedStats.length}{' '}
                {_plural(sortedStats.length, ['запись', 'записи', 'записей'])} за{' '}
                {_fmtDate(firstStat?.date)} — {_fmtDate(lastStat?.date)}
              </CardTitle>
              <p className="text-sm text-[hsl(var(--muted-foreground))]">
                Значения ниже — снимок за {_fmtDate(lastStat?.date)}.
              </p>
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
                    {lastStat?.free_rooms_amount ?? '—'}
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
