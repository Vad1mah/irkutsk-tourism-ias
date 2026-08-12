import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { usePageTitle } from '../hooks/usePageTitle'
import type { LucideIcon } from 'lucide-react'
import {
  TrendingUp, Banknote, Activity, Calendar, MapPin,
  BarChart3, MessageSquare, ArrowRight, Sparkles, Database, Building2,
} from 'lucide-react'
import { api } from '../api/client'
import { Card, Button, Badge, Dropdown } from '../components/ui'
import { MethodologyTooltip } from '../components/MethodologyTooltip'
import { ALL_DISTRICT_NAMES, DEFAULT_DISTRICT } from '../constants/districts'
import {
  localizeSeries,
  FORECAST_HEADER_TEXT,
  FORECAST_FACTUAL_ONLY_TEXT,
  FORECAST_METHODOLOGY_TEXT,
  PICKUP_TREND_METHODOLOGY_TEXT,
  PICKUP_PANEL_CAVEAT_TEXT,
} from '../utils/localize'
import { formatRuDate, formatRuDateRange } from '../utils/format'
import { RECHARTS_TOOLTIP_PROPS, BAR_CURSOR_TRANSPARENT } from '../utils/chartTheme'
import {
  AreaChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip, ReferenceLine, ComposedChart,
} from 'recharts'

const FORECAST_HORIZON = 14

type QuickPrompt = {
  icon: LucideIcon
  short: string
  prompt: string
}

function buildQuickPrompts(district: string): QuickPrompt[] {
  return [
    {
      icon: TrendingUp,
      short: 'Лучший район по RevPAR',
      prompt: 'Какой район показал лучший RevPAR за последние 30 дней?',
    },
    {
      icon: Calendar,
      short: 'События с пиком спроса',
      prompt: 'Топ-5 событий с наибольшим положительным влиянием на спрос',
    },
    {
      icon: Building2,
      short: 'Сравни два загруженных района',
      prompt: 'Сравни два самых загруженных района по RMS-метрикам',
    },
    {
      icon: Activity,
      short: 'Занятые номера за 30 дней',
      prompt: `Как менялось число занятых номеров в районе «${district}» за последние 30 дней?`,
    },
  ]
}

function Home() {
  usePageTitle('Командный центр')
  const navigate = useNavigate()
  const [district, setDistrict] = useState(DEFAULT_DISTRICT)
  const [forecastRequested, setForecastRequested] = useState(false)

  const { data: revenueSummary } = useQuery({
    queryKey: ['revenue-summary'],
    queryFn: api.getRevenueSummary,
    staleTime: 60_000,
  })

  const { data: forecast, isLoading: loadingForecast } = useQuery({
    queryKey: ['ensemble-forecast', district, FORECAST_HORIZON],
    queryFn: () => api.ensembleForecast(district, FORECAST_HORIZON),
    staleTime: 5 * 60_000,
    enabled: forecastRequested,
  })

  const { data: pickup } = useQuery({
    queryKey: ['pickup-pace', district, 30],
    queryFn: () => api.getPickupPace(district, 30),
    staleTime: 60_000,
  })

  const { data: occupancyTimeseries } = useQuery({
    queryKey: ['occupancy-timeseries', district, 14],
    queryFn: () => api.getOccupancyTimeseries(district, 14),
    staleTime: 5 * 60_000,
  })

  const { data: metadata } = useQuery({
    queryKey: ['analytics-metadata'],
    queryFn: api.getMetadata,
    staleTime: 10 * 60_000,
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

  // Combined factual + forecast series for chart
  const combinedSeries = useMemo(() => {
    type CombinedPoint = {
      date: string
      factual: number | undefined
      forecast: number | undefined
      lower: number | undefined
      upper: number | undefined
    }
    const today = new Date().toLocaleDateString('sv-SE')
    const allDates = new Map<string, CombinedPoint>()
    for (const p of occupancyTimeseries?.points ?? []) {
      allDates.set(p.date, { date: p.date, factual: p.occupancy, forecast: undefined, lower: undefined, upper: undefined })
    }
    for (const p of forecastSeries) {
      const existing = allDates.get(p.date)
      if (existing) {
        allDates.set(p.date, { ...existing, forecast: p.occupancy, lower: p.lower, upper: p.upper })
      } else {
        allDates.set(p.date, { date: p.date, factual: undefined, forecast: p.occupancy, lower: p.lower, upper: p.upper })
      }
    }
    // Ось всегда резервирует окно прогноза, чтобы «Сегодня» не упиралась в правый край
    for (let i = 1; i <= FORECAST_HORIZON; i++) {
      const d = new Date()
      d.setDate(d.getDate() + i)
      const iso = d.toLocaleDateString('sv-SE')
      if (!allDates.has(iso)) {
        allDates.set(iso, { date: iso, factual: undefined, forecast: undefined, lower: undefined, upper: undefined })
      }
    }
    return { series: Array.from(allDates.values()).sort((a, b) => a.date.localeCompare(b.date)), today }
  }, [occupancyTimeseries, forecastSeries])

  const quickPrompts = useMemo(() => buildQuickPrompts(district), [district])

  const asOfLabel = revenueSummary?.as_of_date
    ? new Date(revenueSummary.as_of_date).toLocaleDateString('ru-RU')
    : 'последнюю доступную дату'

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
            <span className="gradient-text">Байкальского макрорегиона</span>
          </h1>
          <p className="text-sm text-[hsl(var(--muted-foreground))] max-w-xl">
            Иркутская область и прибайкальские районы Бурятии. RMS-метрики, прогноз спроса и влияние
            событий — для отельеров, региональной администрации и исследователей.
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

      {/* Сигнал свежести данных */}
      {revenueSummary?.as_of_date && (
        <div className="-mt-2 mb-1">
          {revenueSummary.is_stale ? (
            <span className="px-2.5 py-1 rounded-full text-xs bg-[hsl(var(--warning)/0.15)] text-[hsl(var(--warning))] inline-flex items-center gap-1.5 font-medium">
              Данные устарели — последний срез {new Date(revenueSummary.as_of_date).toLocaleDateString('ru-RU')}
              {revenueSummary.data_age_days != null && revenueSummary.data_age_days > 0 ? ` (${revenueSummary.data_age_days} дн. назад)` : ''}
            </span>
          ) : (
            <span className="text-xs text-[hsl(var(--muted-foreground))]">
              Данные на {new Date(revenueSummary.as_of_date).toLocaleDateString('ru-RU')}
            </span>
          )}
        </div>
      )}

      {/* KPI блок */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KPITile
          icon={Activity}
          label="Текущая загрузка"
          value={districtKpi ? `${districtKpi.occupancy}%` : '—'}
          sub={districtKpi
            ? `${districtKpi.hotels_count} объектов со снимком за ${asOfLabel}`
            : `Нет снимка по району «${district}»`}
          accent="primary"
          tooltip="Доля занятых номеров по району: сумма занятых номеров делится на сумму номеров объектов, попавших в снимок последней доступной даты. Достоверность метрики: высокая — от 10 объектов в снимке, средняя — 3–9, низкая — 2 и меньше."
        />
        <KPITile
          icon={TrendingUp}
          label="Прогноз загрузки, 14 дней"
          value={forecastAvg != null ? `${forecastAvg}%` : '—'}
          sub={forecastRequested ? 'Среднее по горизонту, ансамбль 2 моделей' : 'Считается по кнопке «Показать прогноз»'}
          accent="success"
          tooltip="Средняя загрузка по всем 14 дням горизонта, а не значение на 14-й день. Ансамбль — взвешенное среднее двух моделей (Prophet и XGBoost). Модели обучаются в момент запроса, поэтому прогноз считается по кнопке под графиком."
        />
        <KPITile
          icon={Banknote}
          label="ADR"
          value={districtKpi?.adr ? `${districtKpi.adr.toLocaleString('ru-RU')}₽` : '—'}
          sub="Тариф номера (медиана, прокси)"
          accent="accent"
          tooltip="ADR (Average Daily Rate) — средний тариф номера за сутки. Считаем по медиане минимальных цен на сайтах бронирования. Реальный тариф обычно на 15–30% выше — мы видим только рекламируемую цену."
        />
        <KPITile
          icon={Banknote}
          label="RevPAR"
          value={districtKpi?.revpar ? `${districtKpi.revpar.toLocaleString('ru-RU')}₽` : '—'}
          sub="Выручка на доступный номер"
          tooltip="RevPAR (Revenue per Available Room) — выручка с доступного номера = ADR × Загрузка. Главный показатель в гостиничном бизнесе: учитывает и цену, и заполняемость. Используем для сравнения районов и трендов."
        />
      </div>

      {/* Forecast + Factual combined chart */}
      <Card variant="glass" padding="lg">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <div>
            <div className="flex items-center gap-1.5">
              <h2 className="text-lg font-semibold">Загрузка отелей: факт и прогноз</h2>
              <MethodologyTooltip text={FORECAST_METHODOLOGY_TEXT} />
            </div>
            <p className="text-sm text-[hsl(var(--muted-foreground))]">
              {forecastRequested ? FORECAST_HEADER_TEXT : FORECAST_FACTUAL_ONLY_TEXT} Вертикальная линия — сегодня.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 text-xs text-[hsl(var(--muted-foreground))]">
              <span className="inline-block w-3 h-0.5 bg-[hsl(var(--success))] rounded" />
              Факт
              {forecastRequested && (
                <>
                  <span className="inline-block w-3 h-0.5 bg-[hsl(var(--primary))] rounded ml-2" />
                  Прогноз
                </>
              )}
            </div>
            {!forecastRequested ? (
              <Button variant="primary" size="sm" onClick={() => setForecastRequested(true)}>
                <TrendingUp size={14} />
                Показать прогноз
              </Button>
            ) : loadingForecast ? (
              <span className="text-xs text-[hsl(var(--muted-foreground))]">Считаем прогноз…</span>
            ) : null}
            <Button variant="secondary" size="sm" onClick={() => navigate(`/forecast?district=${encodeURIComponent(district)}`)}>
              <TrendingUp size={14} />
              Подробнее
              <ArrowRight size={14} />
            </Button>
          </div>
        </div>

        {combinedSeries.series.length === 0 && loadingForecast ? (
          <div className="h-56 skeleton rounded-xl" />
        ) : combinedSeries.series.length > 0 ? (
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart data={combinedSeries.series}>
              <defs>
                <linearGradient id="forecastFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0.05} />
                </linearGradient>
                <linearGradient id="factualFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="hsl(var(--success))" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="hsl(var(--success))" stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v: string) => v.slice(5)} axisLine={false} />
              <YAxis tick={{ fontSize: 10 }} axisLine={false} domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (!active || !payload || !payload.length) return null
                  const visible = payload.filter(p => p.dataKey === 'factual' || p.dataKey === 'forecast')
                  if (!visible.length) return null
                  return (
                    <div style={{ ...RECHARTS_TOOLTIP_PROPS.contentStyle, padding: '8px 12px' }}>
                      <div style={RECHARTS_TOOLTIP_PROPS.labelStyle}>Дата: {label}</div>
                      {visible.map(p => (
                        <div key={String(p.dataKey)} style={{ color: p.stroke as string, fontWeight: 500 }}>
                          {localizeSeries(String(p.dataKey))}: {Number(p.value).toFixed(1)}%
                        </div>
                      ))}
                    </div>
                  )
                }}
              />
              <ReferenceLine x={combinedSeries.today} stroke="hsl(var(--muted-foreground))" strokeDasharray="4 2" label={{ value: 'Сегодня', fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} />
              <Area type="monotone" dataKey="upper" stroke="none" fill="hsl(var(--primary)/0.08)" connectNulls />
              <Area type="monotone" dataKey="lower" stroke="none" fill="hsl(var(--background))" connectNulls />
              <Area type="monotone" dataKey="factual" stroke="hsl(var(--success))" strokeWidth={2} fill="url(#factualFill)" connectNulls dot={false} />
              <Area type="monotone" dataKey="forecast" stroke="hsl(var(--primary))" strokeWidth={2} fill="url(#forecastFill)" strokeDasharray="5 3" connectNulls dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm text-[hsl(var(--muted-foreground))] py-8 text-center">
            По выбранному району нет дневных снимков загрузки за последние две недели.
          </p>
        )}
      </Card>

      {/* Темп бронирований */}
      <Card variant="glass" padding="lg">
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <div className="flex items-center gap-1.5">
              <Activity size={18} className="text-[hsl(var(--primary))]" />
              <h2 className="text-base font-semibold">Динамика занятых номеров</h2>
              <MethodologyTooltip text={PICKUP_PANEL_CAVEAT_TEXT} />
            </div>
            <div className="inline-flex items-center gap-2">
              {pickup?.summary && (
                <span className="inline-flex items-center gap-1">
                  <Badge
                    variant={pickup.summary.trend === 'ускорение' ? 'success' : pickup.summary.trend === 'замедление' ? 'danger' : 'outline'}
                    size="sm"
                  >
                    {pickup.summary.trend}
                  </Badge>
                  <MethodologyTooltip text={PICKUP_TREND_METHODOLOGY_TEXT} />
                </span>
              )}
              <Button variant="secondary" size="sm" onClick={() => navigate('/analytics?tab=seasonality')} title="Полная динамика с накоплением и тепловой картой">
                Подробнее
                <ArrowRight size={14} />
              </Button>
            </div>
          </div>
          {pickup && pickup.points.length > 0 ? (
            <>
              <p className="text-xs text-[hsl(var(--muted-foreground))] mb-2">
                Окно: {formatRuDateRange(pickup.period.start, pickup.period.end)} · дневных снимков: {pickup.summary.samples}
              </p>
              <ResponsiveContainer width="100%" height={140}>
                <AreaChart data={pickup.points}>
                  <XAxis dataKey="date" hide />
                  <YAxis hide />
                  <Tooltip
                    {...RECHARTS_TOOLTIP_PROPS}
                    cursor={BAR_CURSOR_TRANSPARENT}
                    formatter={(v: number) => [v > 0 ? `+${v}` : `${v}`, 'Изменение занятых номеров за сутки']}
                  />
                  <Area type="monotone" dataKey="pickup" stroke="hsl(var(--accent))" fill="hsl(var(--accent)/0.2)" />
                </AreaChart>
              </ResponsiveContainer>
              <div className="grid grid-cols-3 gap-2 mt-2 text-xs">
                <div>
                  <span className="text-[hsl(var(--muted-foreground))] inline-flex items-center gap-1">
                    Ср. за день с движением
                    <MethodologyTooltip text="Среднее изменение по дням, в которые занятость менялась. Дни без движения в среднее не входят, поэтому модуль числа выше, чем среднее по всем дням окна." />
                  </span>
                  <p className="font-semibold tabular-nums">{pickup.summary.avg_pickup > 0 ? '+' : ''}{pickup.summary.avg_pickup}</p>
                </div>
                <div>
                  <span className="text-[hsl(var(--muted-foreground))]">Макс. прирост</span>
                  <p className="font-semibold tabular-nums text-[hsl(var(--success))]">{pickup.summary.max_pickup > 0 ? '+' : ''}{pickup.summary.max_pickup}</p>
                </div>
                <div>
                  <span className="text-[hsl(var(--muted-foreground))]">Макс. спад</span>
                  <p className="font-semibold tabular-nums text-[hsl(var(--destructive))]">{pickup.summary.min_pickup > 0 ? '+' : ''}{pickup.summary.min_pickup}</p>
                </div>
              </div>
              <p className="text-xs text-[hsl(var(--muted-foreground))] mt-2 leading-snug">
                {pickup.summary.trend === 'ускорение'
                  ? 'Занятых номеров прибавляется быстрее, чем в начале окна. Имеет смысл удержать или поднять тариф на ближайшие даты.'
                  : pickup.summary.trend === 'замедление'
                    ? 'Занятых номеров прибавляется медленнее, чем в начале окна. Рассмотрите промо или скидку на нечувствительные даты.'
                    : pickup.summary.trend === 'стабильно'
                      ? 'Значимых сдвигов в темпе за окно не зафиксировано.'
                      : 'Дневных снимков с движением в окне слишком мало, чтобы судить о тренде.'}
              </p>
            </>
          ) : (
            <p className="text-sm text-[hsl(var(--muted-foreground))] py-6 text-center">Недостаточно дневных снимков, чтобы рассчитать темп бронирований по этому району.</p>
          )}
      </Card>

      {/* AI Quick prompts */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Sparkles size={18} className="text-[hsl(var(--primary))]" />
          <h2 className="text-lg font-semibold">Быстрые B2B-запросы к AI-аналитику</h2>
        </div>
        <p className="text-sm text-[hsl(var(--muted-foreground))] mb-3">
          AI-агент использует те же данные, что и дашборды: прогноз спроса, события, RMS-метрики по районам.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {quickPrompts.map(({ icon: Icon, short, prompt }) => (
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

      {/* Metadata footer */}
      {metadata && (
        <Card variant="glass" padding="md">
          <div className="flex items-center gap-2 mb-3">
            <Database size={16} className="text-[hsl(var(--muted-foreground))]" />
            <h2 className="text-sm font-semibold text-[hsl(var(--muted-foreground))] uppercase tracking-wider">
              Источники и методология
            </h2>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <p className="text-xs text-[hsl(var(--muted-foreground))] inline-flex items-center gap-1">
                Объектов в справочнике
                <MethodologyTooltip text="Все объекты размещения, когда-либо собранные парсерами. В дневной снимок попадает меньше: часть объектов в конкретный день недоступна на источниках." />
              </p>
              <p className="text-sm font-semibold tabular-nums">{metadata.hotels_count}</p>
            </div>
            <div>
              <p className="text-xs text-[hsl(var(--muted-foreground))] inline-flex items-center gap-1">
                Предстоящих событий в БД
                <MethodologyTooltip text="События с датой начала от сегодняшней, все источники, до фильтрации спама и склейки дублей. На экране «События» число меньше — там применены фильтры и дедупликация." />
              </p>
              <p className="text-sm font-semibold tabular-nums">{metadata.upcoming_events_count ?? metadata.events_count}</p>
            </div>
            <div>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">Период данных</p>
              <p className="text-sm font-semibold tabular-nums">
                {formatRuDate(metadata.data_range.from)} – {formatRuDate(metadata.data_range.to)}
              </p>
            </div>
            <div>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">Последнее обновление</p>
              <p className="text-sm font-semibold tabular-nums">
                {metadata.last_refresh ? new Date(metadata.last_refresh).toLocaleDateString('ru-RU') : '—'}
              </p>
            </div>
          </div>
          {metadata.gap_periods.length > 0 && (
            <div className="mt-2 pt-2 border-t border-[hsl(var(--border))]">
              <div className="flex items-start gap-1.5">
                <p className="text-xs text-[hsl(var(--muted-foreground))] inline-flex items-center gap-1">
                  <span>Пробелы в данных</span>
                  <MethodologyTooltip text="Периоды, когда парсеры были временно отключены и статистика по отелям не собиралась. Прогнозы и сравнения за эти даты могут быть менее точными." />
                  <span>:</span>
                </p>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">
                  {metadata.gap_periods.map(g => `${formatRuDateRange(g.from, g.to)} (${g.gap_days} дн.)`).join('; ')}
                </p>
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Quick navigation tiles */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'Аналитика рынка', desc: 'RMS-метрики, heatmap, события', icon: BarChart3, path: `/analytics?district=${encodeURIComponent(district)}` },
          { label: 'Прогноз спроса', desc: 'Взвешенное среднее 2 моделей + факторы', icon: TrendingUp, path: `/forecast?district=${encodeURIComponent(district)}` },
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
    </div>
  )
}

function KPITile({ icon: Icon, label, value, sub, accent, tooltip }: {
  icon: React.ElementType
  label: string
  value: string
  sub: string
  accent?: 'primary' | 'accent' | 'success'
  tooltip?: string
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
          <div className="flex items-center gap-1">
            <p className="text-xs text-[hsl(var(--muted-foreground))] font-medium">{label}</p>
            {tooltip && <MethodologyTooltip text={tooltip} />}
          </div>
          <p className="text-xs text-[hsl(var(--muted-foreground))] truncate">{sub}</p>
        </div>
      </div>
    </Card>
  )
}

export default Home
