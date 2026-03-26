import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { usePageTitle } from '../hooks/usePageTitle'
import {
  Compass, MapPin, CloudSun, Calendar, Building2,
  TrendingUp, ArrowRight, Sparkles, Star, ChevronDown,
} from 'lucide-react'
import { api } from '../api/client'
import { getWeatherEmoji } from '../utils/weather'
import { Card, Button, Badge } from '../components/ui'
import { OccupancyIndicator } from '../components/OccupancyIndicator'
import { ALL_DISTRICT_NAMES, DEFAULT_DISTRICT } from '../constants/districts'

const PERIODS = [
  { label: 'Ближайшие 7 дней', value: 7 },
  { label: 'Ближайшие 14 дней', value: 14 },
  { label: 'Ближайший месяц', value: 30 },
]

const AI_QUESTIONS = [
  { icon: Calendar, text: 'Когда лучше всего ехать на Байкал?', short: 'Лучшие даты' },
  { icon: Building2, text: 'Где лучше остановиться на Ольхоне?', short: 'Где остановиться' },
  { icon: TrendingUp, text: 'Какой прогноз загрузки на ближайшую неделю?', short: 'Прогноз загрузки' },
  { icon: MapPin, text: 'Какие районы Прибайкалья самые популярные?', short: 'Популярные районы' },
]

function Home() {
  usePageTitle('Планирование поездки')
  const navigate = useNavigate()
  const [district, setDistrict] = useState(DEFAULT_DISTRICT)
  const [days, setDays] = useState(14)

  const { data: summary, isLoading: summaryLoading, isError: summaryError } = useQuery({
    queryKey: ['trip-summary', district, days],
    queryFn: () => api.getTripSummary(district, days),
    staleTime: 60_000,
  })

  const { data: bestDates, isLoading: datesLoading, isError: datesError } = useQuery({
    queryKey: ['best-dates', district, days],
    queryFn: () => api.getBestDates(district, days),
    staleTime: 120_000,
  })

  return (
    <div className="animate-fade-in space-y-8 max-w-5xl mx-auto">
      {/* Hero */}
      <div className="text-center pt-4 lg:pt-8">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[hsl(var(--primary)/0.1)] border border-[hsl(var(--primary)/0.2)] mb-4">
          <Compass size={14} className="text-[hsl(var(--primary))]" />
          <span className="text-xs font-medium text-[hsl(var(--primary))]">
            Туристическая аналитика
          </span>
        </div>
        <h1 className="text-3xl lg:text-4xl font-bold mb-3">
          Спланируйте поездку на{' '}
          <span className="gradient-text">Байкал</span>
        </h1>
        <p className="text-[hsl(var(--muted-foreground))] max-w-lg mx-auto">
          Подберите лучшие даты и районы для поездки на Байкал
        </p>
      </div>

      {/* Trip Planner */}
      <Card variant="glass" padding="lg">
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <div className="flex-1">
            <label className="text-xs font-medium text-[hsl(var(--muted-foreground))] mb-1.5 block">
              Район
            </label>
            <div className="relative">
              <MapPin size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[hsl(var(--muted-foreground))]" />
              <select
                value={district}
                onChange={(e) => setDistrict(e.target.value)}
                className="w-full pl-10 pr-10 py-3 rounded-xl bg-[hsl(var(--input))] border border-[hsl(var(--border))] text-[hsl(var(--foreground))] focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))] appearance-none cursor-pointer"
              >
                {ALL_DISTRICT_NAMES.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
              <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-[hsl(var(--muted-foreground))] pointer-events-none" />
            </div>
          </div>
          <div className="sm:w-56">
            <label className="text-xs font-medium text-[hsl(var(--muted-foreground))] mb-1.5 block">
              Период
            </label>
            <div className="relative">
              <Calendar size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[hsl(var(--muted-foreground))]" />
              <select
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="w-full pl-10 pr-10 py-3 rounded-xl bg-[hsl(var(--input))] border border-[hsl(var(--border))] text-[hsl(var(--foreground))] focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))] appearance-none cursor-pointer"
              >
                {PERIODS.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
              <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-[hsl(var(--muted-foreground))] pointer-events-none" />
            </div>
          </div>
        </div>

        {/* Summary Cards */}
        {summaryLoading ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 rounded-xl bg-[hsl(var(--secondary)/0.5)] animate-pulse" />
            ))}
          </div>
        ) : summaryError ? (
          <div className="text-center py-8 text-[hsl(var(--destructive))]">
            <p className="text-sm">Ошибка загрузки данных. Проверьте подключение к серверу.</p>
          </div>
        ) : summary ? (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
              <SummaryCard
                icon={TrendingUp}
                label="Загрузка"
                value={`${summary.forecast_occupancy}%`}
                extra={<OccupancyIndicator value={summary.forecast_occupancy} size="sm" />}
              />
              <SummaryCard
                icon={CloudSun}
                label="Погода"
                value={summary.weather.length > 0
                  ? `${Math.round(summary.weather[0].temp_max)}°C`
                  : '—'
                }
                extra={summary.weather.length > 0 && (
                  <span className="text-lg">{getWeatherEmoji(summary.weather[0].weather_code)}</span>
                )}
              />
              <SummaryCard
                icon={Calendar}
                label="Событий"
                value={String(summary.events_count)}
                extra={summary.top_events.length > 0 && (
                  <span className="text-xs text-[hsl(var(--muted-foreground))] truncate block">
                    Ближайшее: {summary.top_events[0].event_type || 'событие'}, {summary.top_events[0].date}
                  </span>
                )}
              />
              <SummaryCard
                icon={Building2}
                label="Отелей с номерами"
                value={String(summary.available_hotels)}
                extra={
                  <>
                    <span className="text-xs text-[hsl(var(--muted-foreground))] block mb-1">
                      (со свободными номерами)
                    </span>
                    {summary.avg_price ? (
                      <span className="text-xs text-[hsl(var(--muted-foreground))]">
                        от {summary.avg_price.toLocaleString()}₽
                      </span>
                    ) : null}
                  </>
                }
              />
            </div>

            {/* Recommendation */}
            <div className={`p-4 rounded-xl border ${
              summary.occupancy_level === 'low'
                ? 'bg-emerald-500/5 border-emerald-500/20'
                : summary.occupancy_level === 'high'
                  ? 'bg-red-500/5 border-red-500/20'
                  : 'bg-amber-500/5 border-amber-500/20'
            }`}>
              <p className="text-sm">{summary.recommendation}</p>
            </div>

            {/* Actions */}
            <div className="flex flex-wrap gap-3 mt-4">
              <Button variant="primary" onClick={() => navigate(`/analytics?district=${encodeURIComponent(district)}`)}>
                <MapPin size={16} />
                Подробнее о районе
              </Button>
              <Button variant="secondary" onClick={() => navigate('/events')}>
                <Calendar size={16} />
                События
              </Button>
              <Button variant="secondary" onClick={() => navigate('/map')}>
                <Compass size={16} />
                Карта
              </Button>
              <Button variant="secondary" onClick={() => navigate(`/chat?context=${encodeURIComponent(`Расскажи о ситуации в ${district} районе: загрузка, погода, события`)}`)}>
                <Sparkles size={16} />
                Спросить AI
              </Button>
            </div>
          </>
        ) : (
          <div className="text-center py-8 text-[hsl(var(--muted-foreground))]">
            <p>Не удалось загрузить данные. Проверьте подключение к серверу.</p>
          </div>
        )}
      </Card>

      {/* Best Dates */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold">Лучшие даты для поездки</h2>
            <p className="text-sm text-[hsl(var(--muted-foreground))]">
              На основе прогноза загрузки отелей на ближайшие {days} дней
            </p>
          </div>
          <Badge variant="accent" size="sm">
            <TrendingUp size={10} />
            Подобрано автоматически
          </Badge>
        </div>

        {datesLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-32 rounded-xl bg-[hsl(var(--secondary)/0.5)] animate-pulse" />
            ))}
          </div>
        ) : datesError ? (
          <Card variant="default" padding="lg" className="text-center">
            <p className="text-sm text-[hsl(var(--destructive))]">
              Ошибка загрузки лучших дат. Попробуйте обновить страницу.
            </p>
          </Card>
        ) : bestDates && bestDates.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
            {bestDates.map((bd, i) => (
              <DateCard key={bd.date} bestDate={bd} rank={i + 1} allScores={bestDates.map(d => d.score)} />
            ))}
          </div>
        ) : (
          <Card variant="default" padding="lg" className="text-center">
            <p className="text-sm text-[hsl(var(--muted-foreground))]">
              Прогноз загружается... Попробуйте обновить через минуту.
            </p>
          </Card>
        )}
      </div>

      {/* AI Quick Questions */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <Sparkles size={18} className="text-[hsl(var(--primary))]" />
          <h2 className="text-lg font-semibold">Спросите AI-помощника</h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {AI_QUESTIONS.map(({ icon: Icon, text, short }) => (
            <button
              key={text}
              onClick={() => navigate(`/chat?context=${encodeURIComponent(text)}`)}
              className="flex items-center gap-3 p-4 rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] hover:bg-[hsl(var(--secondary))] hover:border-[hsl(var(--primary)/0.3)] transition-all text-left group"
            >
              <div className="w-9 h-9 rounded-lg bg-[hsl(var(--primary)/0.1)] flex items-center justify-center text-[hsl(var(--primary))] group-hover:bg-[hsl(var(--primary)/0.2)] transition-colors flex-shrink-0">
                <Icon size={16} />
              </div>
              <span className="text-sm text-[hsl(var(--muted-foreground))] group-hover:text-[hsl(var(--foreground))] transition-colors flex-1">
                {short}
              </span>
              <ArrowRight size={14} className="text-[hsl(var(--muted-foreground))] opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function SummaryCard({ icon: Icon, label, value, extra }: {
  icon: React.ElementType
  label: string
  value: string
  extra?: React.ReactNode
}) {
  return (
    <div className="p-4 rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))]">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={14} className="text-[hsl(var(--primary))]" />
        <span className="text-xs text-[hsl(var(--muted-foreground))]">{label}</span>
      </div>
      <p className="text-xl font-bold mb-1">{value}</p>
      {extra}
    </div>
  )
}

function DateCard({ bestDate, rank, allScores }: { bestDate: { date: string; predicted_occupancy: number; weather_temp: number | null; events: string[]; score: number }; rank: number; allScores: number[] }) {
  const d = new Date(bestDate.date)
  const dayName = d.toLocaleDateString('ru-RU', { weekday: 'short' })
  const dayNum = d.getDate()
  const month = d.toLocaleDateString('ru-RU', { month: 'short' })

  const minScore = Math.min(...allScores)
  const maxScore = Math.max(...allScores)
  const range = maxScore - minScore || 1
  const stars = Math.round(((bestDate.score - minScore) / range) * 4) + 1

  return (
    <Card variant={rank === 1 ? 'glow' : 'default'} padding="md" hover className="relative">
      {rank === 1 && (
        <Badge variant="accent" size="sm" className="absolute -top-2 -right-2">
          Лучший
        </Badge>
      )}
      <div className="text-center">
        <p className="text-xs text-[hsl(var(--muted-foreground))] uppercase">{dayName}</p>
        <p className="text-2xl font-bold">{dayNum}</p>
        <p className="text-xs text-[hsl(var(--muted-foreground))]">{month}</p>
      </div>
      <div className="mt-3 space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-xs text-[hsl(var(--muted-foreground))]">Загрузка</span>
          <OccupancyIndicator value={bestDate.predicted_occupancy} size="sm" showLabel={false} />
        </div>
        <p className="text-sm font-medium text-center">{bestDate.predicted_occupancy}%</p>
        {bestDate.weather_temp !== null && (
          <p className="text-xs text-center text-[hsl(var(--muted-foreground))]">
            {bestDate.weather_temp > 0 ? '+' : ''}{bestDate.weather_temp}°C
          </p>
        )}
        <div className="flex justify-center gap-0.5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Star
              key={i}
              size={12}
              className={i < stars ? 'text-amber-400 fill-amber-400' : 'text-[hsl(var(--border))]'}
            />
          ))}
        </div>
      </div>
    </Card>
  )
}

export default Home
