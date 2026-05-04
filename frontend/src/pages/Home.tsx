import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { usePageTitle } from '../hooks/usePageTitle'
import {
  TrendingUp, DollarSign, Activity, Calendar, MapPin,
  BarChart3, MessageSquare, ArrowRight, Building2, Sparkles,
} from 'lucide-react'
import { api } from '../api/client'
import { Card, Button, Badge, Dropdown } from '../components/ui'
import { ALL_DISTRICT_NAMES, DEFAULT_DISTRICT } from '../constants/districts'
import {
  AreaChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip,
} from 'recharts'

const FORECAST_HORIZON = 14

const B2B_QUICK_PROMPTS = [
  { icon: TrendingUp, short: 'RevPAR на майские', prompt: 'Рассчитай RevPAR на ближайшие майские праздники по Иркутскому району и сравни с прошлой неделей' },
  { icon: Calendar, short: 'События с пиком спроса', prompt: 'Какие ближайшие события дают наибольший pickup на загрузку? Список из топ-5 с расчётом influence' },
  { icon: Building2, short: 'Сравни районы по тарифу', prompt: 'Сравни средний тариф и загрузку по всем районам региона за последние 30 дней. Где RevPAR максимальный?' },
  { icon: Activity, short: 'Динамика бронирований', prompt: 'Покажи pickup/pace за последние 14 дней по Ольхонскому району. Тренд ускоряется или замедляется?' },
]

function Home() {
  usePageTitle('Командный центр')
  const navigate = useNavigate()
  const [district, setDistrict] = useState(DEFAULT_DISTRICT)

  const { data: revenueSummary } = useQuery({
    queryKey: ['revenue-summary'],
    queryFn: api.getRevenueSummary,
    staleTime: 60_000,
  })

  const { data: forecast, isLoading: loadingForecast } = useQuery({
    queryKey: ['ensemble-forecast', district, FORECAST_HORIZON],
    queryFn: () => api.ensembleForecast(district, FORECAST_HORIZON),
    staleTime: 5 * 60_000,
  })

  const { data: pickup } = useQuery({
    queryKey: ['pickup-pace', district, 30],
    queryFn: () => api.getPickupPace(district, 30),
    staleTime: 60_000,
  })

  const { data: eventsImpact } = useQuery({
    queryKey: ['events-impact'],
    queryFn: api.getEventsImpact,
    staleTime: 5 * 60_000,
  })

  const districtKpi = useMemo(() => {
    if (!revenueSummary) return null
    return revenueSummary.by_district.find(d => d.district === district) || null
  }, [revenueSummary, district])

  const forecastSeries = useMemo(() => {
    if (!forecast?.ensemble) return []
    return forecast.ensemble.map(p => ({
      date: p.date,
      occupancy: p.occupancy,
      lower: p.lower,
      upper: p.upper,
    }))
  }, [forecast])

  const forecastAvg = useMemo(() => {
    if (forecastSeries.length === 0) return null
    return Math.round(forecastSeries.reduce((s, p) => s + p.occupancy, 0) / forecastSeries.length * 10) / 10
  }, [forecastSeries])

  const upcomingImpact = useMemo(() => {
    if (!eventsImpact) return []
    return [...eventsImpact]
      .filter(e => e.impact != null)
      .sort((a, b) => Math.abs(b.impact || 0) - Math.abs(a.impact || 0))
      .slice(0, 5)
  }, [eventsImpact])

  return (
    <div className="animate-fade-in space-y-8">
      {/* Hero */}
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[hsl(var(--primary)/0.1)] border border-[hsl(var(--primary)/0.2)] mb-3">
            <BarChart3 size={14} className="text-[hsl(var(--primary))]" />
            <span className="text-xs font-medium text-[hsl(var(--primary))]">
              Командный центр · B2B-аналитика
            </span>
          </div>
          <h1 className="text-3xl lg:text-4xl font-bold mb-2">
            Рынок размещения{' '}
            <span className="gradient-text">Иркутской области</span>
          </h1>
          <p className="text-sm text-[hsl(var(--muted-foreground))] max-w-xl">
            RMS-метрики, прогноз спроса и влияние событий — для отельеров, региональной администрации и исследователей.
          </p>
        </div>

        <Dropdown
          value={district}
          onChange={setDistrict}
          options={ALL_DISTRICT_NAMES.map(d => ({ value: d, label: d }))}
          icon={<MapPin size={14} />}
          className="lg:w-56"
        />
      </div>

      {/* KPI блок */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KPITile
          icon={Activity}
          label="Текущая загрузка"
          value={districtKpi ? `${districtKpi.occupancy}%` : '—'}
          sub={`Последний срез по району «${district}»`}
          accent="primary"
        />
        <KPITile
          icon={TrendingUp}
          label="Прогноз на 14 дней"
          value={forecastAvg != null ? `${forecastAvg}%` : '—'}
          sub="Средневзвешенный ансамбль"
          accent="success"
        />
        <KPITile
          icon={DollarSign}
          label="ADR"
          value={districtKpi?.adr ? `${districtKpi.adr.toLocaleString('ru-RU')}₽` : '—'}
          sub="Средний тариф номера"
          accent="accent"
        />
        <KPITile
          icon={DollarSign}
          label="RevPAR"
          value={districtKpi?.revpar ? `${districtKpi.revpar.toLocaleString('ru-RU')}₽` : '—'}
          sub="Выручка на доступный номер"
        />
      </div>

      {/* Forecast mini-chart */}
      <Card variant="glass" padding="lg">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <div>
            <h2 className="text-lg font-semibold">Прогноз загрузки на {FORECAST_HORIZON} дней</h2>
            <p className="text-sm text-[hsl(var(--muted-foreground))]">
              Ensemble: Prophet + NeuralProphet + XGBoost. С доверительным интервалом.
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={() => navigate(`/forecast?district=${encodeURIComponent(district)}`)}>
            <TrendingUp size={14} />
            Подробный прогноз
            <ArrowRight size={14} />
          </Button>
        </div>

        {loadingForecast ? (
          <div className="h-56 skeleton rounded-xl" />
        ) : forecastSeries.length > 0 ? (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={forecastSeries}>
              <defs>
                <linearGradient id="forecastFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v: string) => v.slice(5)} axisLine={false} />
              <YAxis tick={{ fontSize: 10 }} axisLine={false} domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                  fontSize: 12,
                }}
                labelFormatter={(label: string) => `Дата: ${label}`}
                formatter={(v: number, _name: string, item: { dataKey?: string }) => {
                  const labels: Record<string, string> = {
                    occupancy: 'Прогноз',
                    upper: 'Верхняя граница',
                    lower: 'Нижняя граница',
                  }
                  return [`${v.toFixed(1)}%`, labels[item?.dataKey ?? ''] ?? item?.dataKey ?? '']
                }}
              />
              <Area type="monotone" dataKey="upper" name="Верхняя граница" stroke="none" fill="hsl(var(--primary)/0.1)" />
              <Area type="monotone" dataKey="lower" name="Нижняя граница" stroke="none" fill="hsl(var(--background))" />
              <Area type="monotone" dataKey="occupancy" name="Прогноз" stroke="hsl(var(--primary))" strokeWidth={2} fill="url(#forecastFill)" />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm text-[hsl(var(--muted-foreground))] py-8 text-center">
            Недостаточно истории для прогноза по выбранному району.
          </p>
        )}
      </Card>

      {/* Pickup + Events impact */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card variant="glass" padding="lg">
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <Activity size={18} className="text-[hsl(var(--primary))]" />
              <h2 className="text-base font-semibold">Динамика бронирований за 30 дней</h2>
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
          {pickup && pickup.points.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={140}>
                <AreaChart data={pickup.points}>
                  <XAxis dataKey="date" hide />
                  <YAxis hide />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px', fontSize: 12 }}
                    formatter={(v: number) => [`${v}`, 'Pickup']}
                  />
                  <Area type="monotone" dataKey="pickup" stroke="hsl(var(--accent))" fill="hsl(var(--accent)/0.2)" />
                </AreaChart>
              </ResponsiveContainer>
              <div className="grid grid-cols-3 gap-2 mt-2 text-xs">
                <div>
                  <span className="text-[hsl(var(--muted-foreground))]">Ср/день</span>
                  <p className="font-semibold tabular-nums">{pickup.summary.avg_pickup > 0 ? '+' : ''}{pickup.summary.avg_pickup}</p>
                </div>
                <div>
                  <span className="text-[hsl(var(--muted-foreground))]">Макс</span>
                  <p className="font-semibold tabular-nums text-[hsl(var(--success))]">+{pickup.summary.max_pickup}</p>
                </div>
                <div>
                  <span className="text-[hsl(var(--muted-foreground))]">Мин</span>
                  <p className="font-semibold tabular-nums text-[hsl(var(--destructive))]">{pickup.summary.min_pickup}</p>
                </div>
              </div>
            </>
          ) : (
            <p className="text-sm text-[hsl(var(--muted-foreground))] py-6 text-center">Нет данных pickup для района.</p>
          )}
        </Card>

        <Card variant="glass" padding="lg">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Calendar size={18} className="text-[hsl(var(--accent))]" />
              <h2 className="text-base font-semibold">Топ-5 событий по impact</h2>
            </div>
            <Button variant="secondary" size="sm" onClick={() => navigate('/events')}>
              Все события
              <ArrowRight size={14} />
            </Button>
          </div>
          {upcomingImpact.length > 0 ? (
            <div className="space-y-2">
              {upcomingImpact.map((e, i) => (
                <div key={i} className="flex items-center gap-3 p-2 rounded-lg bg-[hsl(var(--secondary))/0.4]">
                  <div className="w-9 h-9 rounded-lg bg-[hsl(var(--accent)/0.1)] flex items-center justify-center flex-shrink-0">
                    <span className="text-[10px] text-[hsl(var(--accent))] font-bold">{e.date}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{e.event}</p>
                    <p className="text-xs text-[hsl(var(--muted-foreground))]">{e.district}</p>
                  </div>
                  <Badge variant={(e.impact || 0) > 0 ? 'success' : 'danger'} size="sm">
                    {(e.impact || 0) > 0 ? '↑' : '↓'} {Math.abs(e.impact || 0).toFixed(1)}%
                  </Badge>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-[hsl(var(--muted-foreground))] py-6 text-center">Нет событий с рассчитанным impact.</p>
          )}
        </Card>
      </div>

      {/* AI Quick prompts */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Sparkles size={18} className="text-[hsl(var(--primary))]" />
          <h2 className="text-lg font-semibold">Быстрые B2B-запросы к AI-аналитику</h2>
        </div>
        <p className="text-sm text-[hsl(var(--muted-foreground))] mb-3">
          AI-агент работает с тем же ML-ядром: ensemble-прогноз, события, RMS-метрики.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {B2B_QUICK_PROMPTS.map(({ icon: Icon, short, prompt }) => (
            <button
              key={short}
              onClick={() => navigate(`/chat?context=${encodeURIComponent(prompt)}`)}
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

      {/* Quick navigation tiles */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'Аналитика рынка', desc: 'RMS-метрики, heatmap, события', icon: BarChart3, path: `/analytics?district=${encodeURIComponent(district)}` },
          { label: 'Прогноз спроса', desc: 'Ensemble ML + объяснение', icon: TrendingUp, path: `/forecast?district=${encodeURIComponent(district)}` },
          { label: 'Региональная карта', desc: 'Объекты + загрузка', icon: MapPin, path: '/map' },
          { label: 'Спросить AI', desc: 'Свой запрос в чат', icon: MessageSquare, path: '/chat' },
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

      {/* Сегменты: что доступно отельеру / администрации / исследователю */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Что доступно по сегментам</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Card variant="glass" padding="md">
            <div className="flex items-center gap-2 mb-2 text-[hsl(var(--primary))]">
              <Building2 size={16} />
              <h3 className="text-sm font-semibold uppercase tracking-wider">Отельерам</h3>
            </div>
            <p className="text-xs text-[hsl(var(--muted-foreground))] mb-3">
              Прогноз загрузки своего объекта, RMS-метрики, факторы спроса.
            </p>
            <div className="flex flex-col gap-1.5">
              <button onClick={() => navigate('/map')} className="text-xs text-left text-[hsl(var(--primary))] hover:underline">
                → Найти свой объект на карте
              </button>
              <button onClick={() => navigate(`/forecast?district=${encodeURIComponent(district)}`)} className="text-xs text-left text-[hsl(var(--primary))] hover:underline">
                → Прогноз 7–30 дней по району
              </button>
              <button onClick={() => navigate(`/analytics?district=${encodeURIComponent(district)}`)} className="text-xs text-left text-[hsl(var(--primary))] hover:underline">
                → RevPAR / ADR в моём районе
              </button>
            </div>
          </Card>

          <Card variant="glass" padding="md">
            <div className="flex items-center gap-2 mb-2 text-[hsl(var(--accent))]">
              <BarChart3 size={16} />
              <h3 className="text-sm font-semibold uppercase tracking-wider">Администрации</h3>
            </div>
            <p className="text-xs text-[hsl(var(--muted-foreground))] mb-3">
              Сводка по 15 районам, сезонность, событийная активность.
            </p>
            <div className="flex flex-col gap-1.5">
              <button onClick={() => navigate('/map')} className="text-xs text-left text-[hsl(var(--accent))] hover:underline">
                → Сравнение районов
              </button>
              <button onClick={() => navigate('/analytics')} className="text-xs text-left text-[hsl(var(--accent))] hover:underline">
                → Сезонная heatmap
              </button>
              <button onClick={() => navigate('/events')} className="text-xs text-left text-[hsl(var(--accent))] hover:underline">
                → Календарь событий
              </button>
            </div>
          </Card>

          <Card variant="glass" padding="md">
            <div className="flex items-center gap-2 mb-2 text-[hsl(var(--success))]">
              <Sparkles size={16} />
              <h3 className="text-sm font-semibold uppercase tracking-wider">Исследователям</h3>
            </div>
            <p className="text-xs text-[hsl(var(--muted-foreground))] mb-3">
              CSV-экспорт, методология, метрики моделей и feature importance.
            </p>
            <div className="flex flex-col gap-1.5">
              <a
                href="/api/analytics/export?type=occupancy"
                className="text-xs text-left text-[hsl(var(--success))] hover:underline"
              >
                → Скачать CSV: загрузка отелей
              </a>
              <a
                href="/api/analytics/export?type=events"
                className="text-xs text-left text-[hsl(var(--success))] hover:underline"
              >
                → Скачать CSV: события
              </a>
              <button onClick={() => navigate(`/forecast?district=${encodeURIComponent(district)}`)} className="text-xs text-left text-[hsl(var(--success))] hover:underline">
                → Сравнение моделей: RMSE / MAE / R²
              </button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}

function KPITile({ icon: Icon, label, value, sub, accent }: {
  icon: React.ElementType
  label: string
  value: string
  sub: string
  accent?: 'primary' | 'accent' | 'success'
}) {
  const accentClass =
    accent === 'success' ? 'bg-[hsl(var(--success)/0.1)] text-[hsl(var(--success))]' :
    accent === 'accent' ? 'bg-[hsl(var(--accent)/0.1)] text-[hsl(var(--accent))]' :
    accent === 'primary' ? 'bg-[hsl(var(--primary)/0.1)] text-[hsl(var(--primary))]' :
    'bg-[hsl(var(--secondary))] text-[hsl(var(--muted-foreground))]'
  return (
    <Card hover>
      <div className="flex items-center gap-3">
        <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${accentClass}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div className="min-w-0">
          <p className="text-2xl font-bold tabular-nums truncate">{value}</p>
          <p className="text-xs text-[hsl(var(--muted-foreground))] font-medium">{label}</p>
          <p className="text-xs text-[hsl(var(--muted-foreground))] truncate">{sub}</p>
        </div>
      </div>
    </Card>
  )
}

export default Home
