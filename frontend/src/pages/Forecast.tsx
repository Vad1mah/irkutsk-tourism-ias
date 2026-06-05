import { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, Legend, CartesianGrid,
  BarChart, Bar, ReferenceLine, ComposedChart, LabelList,
} from 'recharts'
import {
  TrendingUp, Calendar, Layers, BarChart3, Sparkles,
  Cpu, MessageSquare, Lightbulb, Loader2, Download,
  Sun, Snowflake, Leaf, Cloud, AlertCircle, Filter, Zap, DollarSign,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent, Badge, Dropdown } from '../components/ui'
import { ErrorState } from '../components/ErrorState'
import { MethodologyTooltip } from '../components/MethodologyTooltip'
import { exportChartPng } from '../utils/export'
import { usePageTitle } from '../hooks/usePageTitle'
import { DEFAULT_DISTRICTS } from '../constants/districts'
import { localizeFeature, describeFeature, featureGroup } from '../utils/localizeFeatures'
import { RECHARTS_TOOLTIP_PROPS, BAR_CURSOR_TRANSPARENT } from '../utils/chartTheme'

type SeasonData = {
  month: string
  occupancy: number
  avgPrice: number
  events: number
  season: string
  hasData?: boolean
}

type MissingPeriod = {
  month: string
  monthIndex: number
  reason: string
}

const MODEL_COLORS: Record<string, string> = {
  prophet: 'hsl(199 89% 48%)',
  neuralprophet: 'hsl(280 67% 50%)',
  xgboost: 'hsl(142 76% 36%)',
}

const MODEL_LABELS: Record<string, string> = {
  prophet: 'Prophet',
  neuralprophet: 'NeuralProphet',
  xgboost: 'XGBoost',
}

function Forecast() {
  usePageTitle('Прогнозы')
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [district, setDistrict] = useState(searchParams.get('district') || DEFAULT_DISTRICTS[0])
  const [daysAhead, setDaysAhead] = useState(7)
  const ensembleChartRef = useRef<HTMLDivElement>(null)

  const handleExport = useCallback(() => {
    if (ensembleChartRef.current) {
      exportChartPng(ensembleChartRef.current, `forecast_${district}_${daysAhead}d.png`)
    }
  }, [district, daysAhead])

  useEffect(() => {
    setSearchParams({ district, days: String(daysAhead) }, { replace: true })
  }, [district, daysAhead, setSearchParams])

  const { data: districtsData } = useQuery({
    queryKey: ['districts'],
    queryFn: () => api.getDistricts(),
    staleTime: 10 * 60 * 1000,
  })
  const districtNames = districtsData?.map(d => d.district) || DEFAULT_DISTRICTS

  const { data: ensembleData, isLoading: loadingEnsemble, isError: ensembleError, error: ensembleErrorObj } = useQuery({
    queryKey: ['ensemble', district, daysAhead],
    queryFn: () => api.ensembleForecast(district, daysAhead),
    retry: 2,
    staleTime: 10 * 60 * 1000,
  })

  const { data: compareData, isLoading: loadingCompare } = useQuery({
    queryKey: ['compare', district],
    queryFn: () => api.compareModels(district, 7),
    retry: 2,
    staleTime: 30 * 60 * 1000,
  })

  const { data: explainData, isLoading: loadingExplain, refetch: refetchExplain } = useQuery({
    queryKey: ['explain', district, daysAhead],
    queryFn: () => api.explainForecast(district, daysAhead),
    enabled: false,
    retry: 0,
    staleTime: 10 * 60 * 1000,
  })

  const { data: validationData, isLoading: loadingValidation } = useQuery({
    queryKey: ['forecast-validation', district],
    queryFn: () => api.getForecastValidation(district, 14),
    retry: 1,
    staleTime: 30 * 60 * 1000,
  })

  const isLoading = loadingEnsemble || loadingCompare

  const [viewMode, setViewMode] = useState<'simple' | 'expert' | 'seasonality'>('simple')
  const [selectedYear, setSelectedYear] = useState<number | null>(null)
  const [compareDistricts, setCompareDistricts] = useState<string[]>([])

  const { data: compareDistrictData } = useQuery({
    queryKey: ['compareDistricts', compareDistricts, daysAhead],
    queryFn: async () => {
      const results = await Promise.all(
        compareDistricts.map(d => api.ensembleForecast(d, daysAhead).then(r => ({ district: d, data: r })).catch(() => null))
      )
      return results.filter(Boolean) as { district: string; data: typeof ensembleData }[]
    },
    enabled: compareDistricts.length > 0,
    staleTime: 5 * 60 * 1000,
  })

  const { data: eventsData } = useQuery({
    queryKey: ['events'],
    queryFn: api.getEvents,
    staleTime: 10 * 60 * 1000,
  })

  const { data: correlationData, isLoading: loadingCorrelation } = useQuery({
    queryKey: ['correlation', selectedYear],
    queryFn: () => api.getCorrelation(selectedYear),
    staleTime: 10 * 60 * 1000,
  })

  const ensemblePoints = ensembleData?.ensemble || []
  const modelForecasts = ensembleData?.models || {}
  const weights = ensembleData?.weights || {}
  const metrics = compareData?.metrics || {}
  const featureImportance = compareData?.feature_importance || {}

  const monthsData: SeasonData[] = correlationData?.months || []
  const correlationCoeff = correlationData?.correlation_coefficient
  const missingPeriods: MissingPeriod[] = correlationData?.missing_periods || []
  const dataCoverage = correlationData?.data_coverage || ''
  const availableYears = correlationData?.available_years || []
  const validMonthsCount = parseInt(dataCoverage.split('/')[0] || '0', 10)
  const seasonInsights = _calculateInsights(monthsData)

  const forecastEvents = (() => {
    if (!eventsData || !ensemblePoints.length) return []
    const forecastDates = new Set(ensemblePoints.map(p => p.date))
    return eventsData.filter(e => forecastDates.has(e.date_start))
  })()

  const avgOccupancyPeriod =
    ensemblePoints.length > 0
      ? Math.round(ensemblePoints.reduce((a, b) => a + b.occupancy, 0) / ensemblePoints.length)
      : 0

  const multiModelData = _buildMultiModelData(ensemblePoints, modelForecasts)
  const topFeatures = _getTopFeatures(featureImportance)
  const featureGroupSummary = _getFeatureGroupSummary(featureImportance)

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[hsl(var(--primary))] to-[hsl(var(--accent))] flex items-center justify-center">
              <TrendingUp className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Прогнозирование</h1>
              <p className="text-sm text-[hsl(var(--muted-foreground))]">
                Прогноз заполняемости отелей
              </p>
            </div>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-3">
          {viewMode !== 'seasonality' && (
            <>
              <Dropdown
                value={district}
                onChange={setDistrict}
                options={districtNames.map(d => ({ value: d, label: d }))}
                compact
                className="w-44"
              />
              <Dropdown
                value={String(daysAhead)}
                onChange={(v) => setDaysAhead(Number(v))}
                options={[
                  { value: '7', label: '7 дней' },
                  { value: '14', label: '14 дней' },
                  { value: '30', label: '30 дней' },
                  { value: '60', label: '60 дней', hint: 'низкая точность' },
                  { value: '90', label: '90 дней', hint: 'низкая точность' },
                ]}
                compact
                className="w-40"
              />
            </>
          )}
          {viewMode === 'seasonality' && availableYears.length > 0 && (
            <Dropdown
              value={selectedYear != null ? String(selectedYear) : ''}
              onChange={(v) => setSelectedYear(v ? Number(v) : null)}
              options={[
                { value: '', label: 'Все годы' },
                ...availableYears.map(y => ({ value: String(y), label: String(y) })),
              ]}
              icon={<Filter size={14} />}
              compact
              className="w-40"
            />
          )}
          <div className="flex rounded-xl border border-[hsl(var(--border))] overflow-hidden">
            <button
              onClick={() => setViewMode('simple')}
              className={`px-3 py-2 text-xs font-medium transition-colors ${viewMode === 'simple' ? 'bg-[hsl(var(--primary))] text-white' : 'bg-[hsl(var(--card))] hover:bg-[hsl(var(--secondary))]'}`}
              title="Ансамблевый прогноз заполняемости"
            >
              Прогноз
            </button>
            <button
              onClick={() => setViewMode('expert')}
              className={`px-3 py-2 text-xs font-medium transition-colors ${viewMode === 'expert' ? 'bg-[hsl(var(--primary))] text-white' : 'bg-[hsl(var(--card))] hover:bg-[hsl(var(--secondary))]'}`}
              title="Сравнение моделей и метрики точности"
            >
              Модели
            </button>
            <button
              onClick={() => setViewMode('seasonality')}
              className={`px-3 py-2 text-xs font-medium transition-colors ${viewMode === 'seasonality' ? 'bg-[hsl(var(--primary))] text-white' : 'bg-[hsl(var(--card))] hover:bg-[hsl(var(--secondary))]'}`}
              title="Сезонные паттерны и корреляции"
            >
              Сезонность
            </button>
          </div>
        </div>
      </div>

      {viewMode === 'seasonality' ? (
        loadingCorrelation ? (
          <SeasonalitySkeleton />
        ) : monthsData.length === 0 || validMonthsCount === 0 ? (
          <Card variant="glass" className="border-[hsl(var(--warning))]">
            <CardContent>
              <div className="flex items-center gap-3">
                <AlertCircle className="w-6 h-6 text-[hsl(var(--warning))]" />
                <div>
                  <p className="font-medium">
                    {selectedYear != null ? `Нет данных за ${selectedYear} год` : 'Нет данных о сезонности'}
                  </p>
                  <p className="text-sm text-[hsl(var(--muted-foreground))]">
                    {selectedYear != null && availableYears.length > 0
                      ? `За выбранный год ни в одном месяце не накоплено достаточно наблюдений. Доступны годы с данными: ${availableYears.join(', ')}.`
                      : 'Для анализа сезонности нужны данные за несколько месяцев.'}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        ) : (
          <>
            {missingPeriods.length > 0 && (
              <Card variant="glass" className="border-l-4 border-l-[hsl(var(--muted-foreground))]">
                <CardContent>
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-[hsl(var(--muted-foreground))] flex-shrink-0 mt-0.5" />
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="font-medium text-sm">Неполные данные</p>
                        <Badge variant="secondary" size="sm">{dataCoverage}</Badge>
                      </div>
                      <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                        Отсутствуют: {missingPeriods.map(p => p.month).join(', ')}. На графиках показаны серым.
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Insight cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Card variant="gradient" className="bg-gradient-to-br from-[hsl(var(--success)/0.1)] to-[hsl(var(--success)/0.05)] border-[hsl(var(--success)/0.3)]">
                <CardContent>
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-xl bg-[hsl(var(--success)/0.2)] flex items-center justify-center">
                      <Sun className="w-5 h-5 text-[hsl(var(--success))]" />
                    </div>
                    <Badge variant="success" size="sm">Низкий сезон</Badge>
                  </div>
                  <h3 className="font-semibold">{seasonInsights.bestMonth || '—'}</h3>
                  <p className="text-sm text-[hsl(var(--muted-foreground))]">{seasonInsights.bestReason}</p>
                </CardContent>
              </Card>
              <Card variant="default" className="border-l-4 border-l-[hsl(var(--warning))]">
                <CardContent>
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-xl bg-[hsl(var(--warning)/0.1)] flex items-center justify-center">
                      <TrendingUp className="w-5 h-5 text-[hsl(var(--warning))]" />
                    </div>
                    <Badge variant="warning" size="sm">Высокий сезон</Badge>
                  </div>
                  <h3 className="font-semibold">{seasonInsights.peakMonth || '—'}</h3>
                  <p className="text-sm text-[hsl(var(--muted-foreground))]">{seasonInsights.peakReason}</p>
                </CardContent>
              </Card>
              <Card variant="default" className="border-l-4 border-l-[hsl(var(--primary))]">
                <CardContent>
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-xl bg-[hsl(var(--primary)/0.1)] flex items-center justify-center">
                      <DollarSign className="w-5 h-5 text-[hsl(var(--primary))]" />
                    </div>
                    <Badge variant="primary" size="sm">Минимум цены</Badge>
                  </div>
                  <h3 className="font-semibold">{seasonInsights.cheapestMonth || '—'}</h3>
                  <p className="text-sm text-[hsl(var(--muted-foreground))]">{seasonInsights.cheapestReason}</p>
                </CardContent>
              </Card>
            </div>

            {/* Correlation chart */}
            <Card variant="glass">
              <CardHeader>
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div>
                    <CardTitle>События и загруженность</CardTitle>
                    <p className="text-sm text-[hsl(var(--muted-foreground))] mt-1">
                      Как события статистически связаны с заполняемостью (корреляция, не причинность)
                    </p>
                  </div>
                  {correlationCoeff !== null && correlationCoeff !== undefined && (
                    <Badge variant="accent">
                      <Zap size={12} />
                      Корреляция: {correlationCoeff}{' '}
                      {Math.abs(Number(correlationCoeff)) >= 0.7
                        ? '(сильная связь)'
                        : Math.abs(Number(correlationCoeff)) >= 0.4
                          ? '(умеренная связь)'
                          : Math.abs(Number(correlationCoeff)) >= 0.2
                            ? '(слабая связь)'
                            : '(связь не выявлена)'}
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={280}>
                  <ComposedChart data={_getSeasonChartData(monthsData)}>
                    <defs>
                      <linearGradient id="occGradSeason" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="missGradSeason" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="hsl(var(--muted))" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="hsl(var(--muted))" stopOpacity={0.1} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis dataKey="month" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis yAxisId="left" tickFormatter={(v) => `${v}%`} axisLine={false} tickLine={false} />
                    <YAxis yAxisId="right" orientation="right" axisLine={false} tickLine={false} />
                    <Tooltip
                      {...RECHARTS_TOOLTIP_PROPS}
                      cursor={BAR_CURSOR_TRANSPARENT}
                      formatter={(value, name) => {
                        const v = value as number | null
                        const n = name as string
                        if (v === null) return ['Нет данных', 'Пропуск']
                        const labels: Record<string, string> = {
                          occupancyDisplay: 'Загруженность',
                          events: 'События',
                          missingArea: 'Статус',
                        }
                        if (n === 'missingArea') return ['Парсер неактивен', 'Пропуск']
                        if (n === 'occupancyDisplay') return [`${v}%`, labels[n]]
                        return [v, labels[n] || n]
                      }}
                    />
                    <Legend />
                    <Area
                      yAxisId="left"
                      type="monotone"
                      dataKey="missingArea"
                      name="Нет данных"
                      stroke="hsl(var(--muted-foreground))"
                      strokeWidth={1}
                      strokeDasharray="4 4"
                      fill="url(#missGradSeason)"
                      connectNulls={false}
                    />
                    <Area
                      yAxisId="left"
                      type="monotone"
                      dataKey="occupancyDisplay"
                      name="Загруженность"
                      stroke="hsl(var(--primary))"
                      strokeWidth={3}
                      fill="url(#occGradSeason)"
                      connectNulls={false}
                    />
                    <Bar
                      yAxisId="right"
                      dataKey="events"
                      name="События"
                      fill="hsl(var(--accent))"
                      radius={[4, 4, 0, 0]}
                      opacity={0.8}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Price dynamics + Baikal seasons */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              <Card variant="glass">
                <CardHeader>
                  <CardTitle>Динамика цен</CardTitle>
                  <p className="text-sm text-[hsl(var(--muted-foreground))]">Средняя цена по месяцам</p>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={200}>
                    <AreaChart data={_getSeasonChartData(monthsData)}>
                      <defs>
                        <linearGradient id="priceGradSeason" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="hsl(var(--success))" stopOpacity={0.4} />
                          <stop offset="95%" stopColor="hsl(var(--success))" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                      <XAxis dataKey="month" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                      <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} axisLine={false} tickLine={false} />
                      <Tooltip
                        {...RECHARTS_TOOLTIP_PROPS}
                        formatter={(value) => {
                          const v = value as number | null
                          return v === null ? ['Нет данных'] : [`${v?.toLocaleString()}₽`, 'Ср. цена']
                        }}
                      />
                      <Area
                        type="monotone"
                        dataKey="avgPriceDisplay"
                        stroke="hsl(var(--success))"
                        strokeWidth={2}
                        fill="url(#priceGradSeason)"
                        connectNulls={false}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
              <Card variant="glass">
                <CardHeader>
                  <CardTitle>Сезоны Байкала</CardTitle>
                  <p className="text-sm text-[hsl(var(--muted-foreground))]">Характеристика по временам года</p>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <SeasonRow icon={Sun} name="Лето (Июн-Авг)" description={_seasonDesc(monthsData, ['Июн', 'Июл', 'Авг'])} color="warning" />
                    <SeasonRow icon={Leaf} name="Осень (Сен-Ноя)" description={_seasonDesc(monthsData, ['Сен', 'Окт', 'Ноя'])} color="success" />
                    <SeasonRow icon={Snowflake} name="Зима (Дек-Фев)" description={_seasonDesc(monthsData, ['Дек', 'Янв', 'Фев'])} color="primary" />
                    <SeasonRow icon={Cloud} name="Весна (Мар-Май)" description={_seasonDesc(monthsData, ['Мар', 'Апр', 'Май'])} color="accent" />
                  </div>
                </CardContent>
              </Card>
            </div>
          </>
        )
      ) : isLoading ? (
        <ForecastSkeleton />
      ) : ensembleError || (ensembleData && 'error' in ensembleData) ? (
        <ErrorState
          title="Недостаточно данных для прогноза"
          message={
            ensembleErrorObj?.message
            || String((ensembleData as Record<string, unknown>)?.error || '')
            || 'Для построения прогноза требуется минимум 30 дней данных. Попробуйте выбрать другой район.'
          }
          onRetry={() => queryClient.invalidateQueries({ queryKey: ['ensemble'] })}
        />
      ) : (
        <>
          {/* Weights summary (expert only) */}
          {viewMode === 'expert' && Object.keys(weights).length > 0 && (
            <div className="grid grid-cols-3 gap-3">
              {Object.entries(weights).map(([model, weight]) => (
                <Card key={model} hover className="text-center">
                  <div className="flex items-center justify-center gap-2 mb-1">
                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: MODEL_COLORS[model] || 'gray' }} />
                    <span className="text-sm font-medium">{MODEL_LABELS[model] || model}</span>
                  </div>
                  <p className="text-2xl font-bold">{Math.round(Number(weight) * 100)}%</p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">вклад модели</p>
                </Card>
              ))}
            </div>
          )}

          {/* Ensemble Chart with CI */}
          {ensemblePoints.length > 0 && (
            <Card variant="glass">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Layers className="w-5 h-5 text-[hsl(var(--primary))]" />
                    <CardTitle>Прогноз заполняемости с интервалом уверенности</CardTitle>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="primary" size="sm">
                      {ensembleData?.history_points} точек данных
                    </Badge>
                    <button
                      onClick={() => navigate(`/chat?context=${encodeURIComponent(`Объясни прогноз заполняемости для ${district} района на ${daysAhead} дней`)}`)}
                      className="p-1.5 rounded-lg hover:bg-[hsl(var(--primary)/0.1)] transition-colors"
                      title="Спросить AI"
                    >
                      <Sparkles size={14} className="text-[hsl(var(--primary))]" />
                    </button>
                    <button
                      onClick={handleExport}
                      className="p-1.5 rounded-lg hover:bg-[hsl(var(--secondary))] transition-colors"
                      title="Скачать PNG"
                    >
                      <Download size={14} className="text-[hsl(var(--muted-foreground))]" />
                    </button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div ref={ensembleChartRef}>
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={ensemblePoints}>
                    <defs>
                      <linearGradient id="ensGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                        <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="ciGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.1} />
                        <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 11 }}
                      tickFormatter={(d) => new Date(d).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      domain={[0, 100]}
                      tickFormatter={(v) => `${v}%`}
                      tick={{ fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                      width={50}
                    />
                    <Tooltip
                      {...RECHARTS_TOOLTIP_PROPS}
                      formatter={(v: number, name: string) => {
                        const labels: Record<string, string> = {
                          occupancy: 'Прогноз',
                          upper: 'Верхняя граница',
                          lower: 'Нижняя граница',
                        }
                        return [`${Math.round(v)}%`, labels[name] || name]
                      }}
                      labelFormatter={(d) => new Date(d).toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })}
                    />
                    <Area type="monotone" dataKey="upper" stroke="none" fill="url(#ciGrad)" />
                    <Area type="monotone" dataKey="lower" stroke="none" fill="hsl(var(--background))" />
                    <Area
                      type="monotone"
                      dataKey="occupancy"
                      stroke="hsl(var(--primary))"
                      strokeWidth={2.5}
                      fill="url(#ensGrad)"
                    />
                    {forecastEvents.slice(0, 5).map((event) => (
                      <ReferenceLine
                        key={event.event_id}
                        x={event.date_start}
                        stroke="hsl(var(--accent))"
                        strokeDasharray="4 3"
                        label={{ value: event.title.length > 18 ? event.title.slice(0, 18) + '…' : event.title, position: 'top', fontSize: 9, fill: 'hsl(var(--muted-foreground))' }}
                      />
                    ))}
                  </AreaChart>
                </ResponsiveContainer>
                {viewMode === 'simple' ? (
                  <div className="mt-4 space-y-3">
                    <p className="text-sm text-[hsl(var(--foreground))]">
                      Средняя заполняемость на период{' '}
                      {new Date(ensemblePoints[0].date).toLocaleDateString('ru-RU')}
                      {' — '}
                      {new Date(ensemblePoints[ensemblePoints.length - 1].date).toLocaleDateString('ru-RU')}:{' '}
                      <span className="font-semibold tabular-nums">{avgOccupancyPeriod}%</span>
                    </p>
                    <button
                      type="button"
                      onClick={() => setViewMode('expert')}
                      className="text-sm font-medium text-[hsl(var(--primary))] hover:underline inline-flex items-center gap-1"
                    >
                      Подробнее о моделях
                      <span aria-hidden>→</span>
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center justify-between mt-2 text-xs text-[hsl(var(--muted-foreground))]">
                    <span className="flex items-center gap-1">
                      <Calendar size={12} />
                      {new Date(ensemblePoints[0].date).toLocaleDateString('ru-RU')} — {new Date(ensemblePoints[ensemblePoints.length - 1].date).toLocaleDateString('ru-RU')}
                    </span>
                    <span>Средняя заполняемость: {avgOccupancyPeriod}%</span>
                  </div>
                )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Simple view: компактный обзор прогноза + события горизонта */}
          {viewMode === 'simple' && ensemblePoints.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {(() => {
                const occs = ensemblePoints.map(p => p.occupancy)
                const minOcc = Math.min(...occs)
                const maxOcc = Math.max(...occs)
                const minDay = ensemblePoints[occs.indexOf(minOcc)]
                const maxDay = ensemblePoints[occs.indexOf(maxOcc)]
                const ciAvg = Math.round(
                  ensemblePoints.reduce((a, p) => a + (p.upper - p.lower), 0) / ensemblePoints.length
                )
                const fmt = (d: string) =>
                  new Date(d).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
                return (
                  <>
                    <Card variant="glass" padding="md">
                      <div className="flex items-center gap-2 mb-2 text-[hsl(var(--muted-foreground))]">
                        <TrendingUp size={14} />
                        <span className="text-xs uppercase tracking-wider">Пик загрузки</span>
                      </div>
                      <p className="text-2xl font-bold tabular-nums">{Math.round(maxOcc)}%</p>
                      <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">{fmt(maxDay.date)}</p>
                    </Card>
                    <Card variant="glass" padding="md">
                      <div className="flex items-center gap-2 mb-2 text-[hsl(var(--muted-foreground))]">
                        <BarChart3 size={14} />
                        <span className="text-xs uppercase tracking-wider">Спад загрузки</span>
                      </div>
                      <p className="text-2xl font-bold tabular-nums">{Math.round(minOcc)}%</p>
                      <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">{fmt(minDay.date)}</p>
                    </Card>
                    <Card variant="glass" padding="md">
                      <div className="flex items-center gap-2 mb-2 text-[hsl(var(--muted-foreground))]">
                        <Layers size={14} />
                        <span className="text-xs uppercase tracking-wider">Доверительный интервал</span>
                      </div>
                      <p className="text-2xl font-bold tabular-nums">±{Math.round(ciAvg / 2)} п.п.</p>
                      <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                        {ciAvg < 15 ? 'высокая уверенность' : ciAvg < 30 ? 'средняя уверенность' : 'низкая уверенность'}
                      </p>
                    </Card>
                  </>
                )
              })()}
            </div>
          )}

          {/* Simple view: события в горизонте прогноза */}
          {viewMode === 'simple' && forecastEvents.length > 0 && (
            <Card variant="glass">
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <Calendar className="w-5 h-5 text-[hsl(var(--accent))]" />
                  <CardTitle className="text-base">События в горизонте прогноза</CardTitle>
                </div>
                <p className="text-sm text-[hsl(var(--muted-foreground))]">
                  Эти события могут изменить спрос в дни их проведения.
                </p>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {forecastEvents.slice(0, 6).map((event) => (
                    <div
                      key={event.event_id}
                      className="flex items-start gap-3 p-3 rounded-lg bg-[hsl(var(--secondary)/0.4)] hover:bg-[hsl(var(--secondary))] transition-colors cursor-pointer"
                      onClick={() => navigate('/events')}
                    >
                      <div className="text-xs font-mono text-[hsl(var(--primary))] whitespace-nowrap mt-0.5">
                        {new Date(event.date_start).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{event.title}</p>
                        <p className="text-xs text-[hsl(var(--muted-foreground))]">{event.location || 'Иркутск'}</p>
                      </div>
                    </div>
                  ))}
                </div>
                {forecastEvents.length > 6 && (
                  <button
                    type="button"
                    onClick={() => navigate('/events')}
                    className="mt-3 text-sm font-medium text-[hsl(var(--primary))] hover:underline inline-flex items-center gap-1"
                  >
                    Показать все ({forecastEvents.length}) →
                  </button>
                )}
              </CardContent>
            </Card>
          )}

          {/* Confidence indicator (expert: доп. контекст к интервалу) */}
          {viewMode === 'expert' && ensemblePoints.length > 0 && (
            <Card variant="glass" padding="md">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Layers size={18} className="text-[hsl(var(--primary))]" />
                  <div>
                    <p className="text-sm font-medium">Уверенность прогноза</p>
                    <p className="text-xs text-[hsl(var(--muted-foreground))]">
                      На основе ширины доверительного интервала: узкий (&lt;15 п.п.) = высокая, средний (15–30 п.п.) = средняя, широкий (&gt;30 п.п.) = низкая
                    </p>
                  </div>
                </div>
                {(() => {
                  const avgWidth = ensemblePoints.reduce((a, p) => a + (p.upper - p.lower), 0) / ensemblePoints.length
                  if (avgWidth < 15) return <Badge variant="success">Высокая</Badge>
                  if (avgWidth < 30) return <Badge variant="warning">Средняя</Badge>
                  return <Badge variant="danger">Низкая</Badge>
                })()}
              </div>
            </Card>
          )}

          {/* Multi-model comparison chart */}
          {viewMode === 'expert' && multiModelData.length > 0 && (
            <Card variant="glass">
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-[hsl(var(--accent))]" />
                  <CardTitle>Сравнение прогнозов по моделям</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={multiModelData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 10 }}
                      tickFormatter={(d) => new Date(d).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      domain={[0, 100]}
                      tickFormatter={(v) => `${v}%`}
                      tick={{ fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                      width={40}
                    />
                    <Tooltip
                      {...RECHARTS_TOOLTIP_PROPS}
                      formatter={(v: number, name: string) => [`${Math.round(v)}%`, MODEL_LABELS[name] || name]}
                      labelFormatter={(d) => new Date(d).toLocaleDateString('ru-RU', { weekday: 'short', day: 'numeric', month: 'long' })}
                    />
                    <Legend formatter={(v) => MODEL_LABELS[v] || v} />
                    {Object.keys(modelForecasts).map(model => (
                      <Line
                        key={model}
                        type="monotone"
                        dataKey={model}
                        stroke={MODEL_COLORS[model] || 'gray'}
                        strokeWidth={2}
                        dot={false}
                        strokeDasharray={model === 'xgboost' ? '5 5' : undefined}
                      />
                    ))}
                    <Line
                      type="monotone"
                      dataKey="ensemble"
                      stroke="hsl(var(--foreground))"
                      strokeWidth={3}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {/* Metrics + Feature Importance (expert only) */}
          {viewMode === 'expert' && <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {/* Metrics table */}
            {Object.keys(metrics).length > 0 && !('error' in metrics) && (
              <Card variant="glass">
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-[hsl(var(--success))]" />
                    <CardTitle>Метрики качества</CardTitle>
                  </div>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">
                    Тест на {compareData?.test_days} днях • {compareData?.history_points} точек данных
                  </p>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-[hsl(var(--border))]">
                          <th className="text-left py-2 px-2 text-[hsl(var(--muted-foreground))]">Модель</th>
                          <th className="text-right py-2 px-2 align-bottom">
                            <span className="block text-[hsl(var(--foreground))]">RMSE</span>
                            <span className="block text-xs font-normal font-sans text-[hsl(var(--muted-foreground))] leading-tight mt-0.5 max-w-[9rem] ml-auto">
                              Средняя ошибка прогноза в п.п.
                            </span>
                          </th>
                          <th className="text-right py-2 px-2 align-bottom">
                            <span className="block text-[hsl(var(--foreground))]">MAE</span>
                            <span className="block text-xs font-normal font-sans text-[hsl(var(--muted-foreground))] leading-tight mt-0.5 max-w-[9rem] ml-auto">
                              Среднее отклонение от реальных значений
                            </span>
                          </th>
                          <th className="text-right py-2 px-2 align-bottom">
                            <span className="block text-[hsl(var(--foreground))]">R²</span>
                            <span className="block text-xs font-normal font-sans text-[hsl(var(--muted-foreground))] leading-tight mt-0.5 max-w-[9rem] ml-auto">
                              Качество модели (1.0 = идеально)
                            </span>
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {['prophet', 'neuralprophet', 'xgboost']
                          .filter(m => metrics[m] && typeof metrics[m] === 'object')
                          .map(model => {
                            const m = metrics[model] as { rmse: number; mae: number; r2: number; rmse_std?: number; fold_count?: number }
                            const bestModel = compareData?.best_model ?? (metrics as Record<string, unknown>).best_model as string | undefined
                            const isBest = model === bestModel
                            return (
                              <tr key={model} className={`border-b border-[hsl(var(--border)/0.5)] ${isBest ? 'bg-[hsl(var(--success)/0.05)]' : ''}`}>
                                <td className="py-2 px-2">
                                  <div className="flex items-center gap-2">
                                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: MODEL_COLORS[model] }} />
                                    <span className="font-medium">{MODEL_LABELS[model]}</span>
                                    {isBest && <Badge variant="success" size="sm">лучшая</Badge>}
                                  </div>
                                </td>
                                <td className="text-right py-2 px-2 font-mono">
                                  {m.rmse?.toFixed(2)}
                                  {m.rmse_std !== undefined && (
                                    <span className="ml-1 text-xs text-[hsl(var(--muted-foreground))]">±{m.rmse_std.toFixed(2)}</span>
                                  )}
                                </td>
                                <td className="text-right py-2 px-2 font-mono">{m.mae?.toFixed(2)}</td>
                                <td className={`text-right py-2 px-2 font-mono ${m.r2 < 0 ? 'text-[hsl(var(--destructive))]' : ''}`}>
                                  {m.r2?.toFixed(3)}
                                </td>
                              </tr>
                            )
                          })}
                      </tbody>
                    </table>
                    {/* Phase 9: warning при R²<0 у любой модели */}
                    {Object.values(metrics).some(m => typeof m === 'object' && m !== null && 'r2' in m && (m as {r2:number}).r2 < 0) && (
                      <div className="mt-3 p-3 rounded-lg border border-[hsl(var(--warning)/0.4)] bg-[hsl(var(--warning)/0.08)] text-xs">
                        <p className="font-semibold text-[hsl(var(--warning))] mb-1">⚠ R² отрицательный у одной или нескольких моделей</p>
                        <p className="text-[hsl(var(--muted-foreground))] leading-relaxed">
                          На этом горизонте модель работает хуже простого предсказания «всегда выводить среднее».
                          Это нормально для долгосрочных прогнозов (≥30 дней) на ограниченной истории — мы располагаем
                          ~14 месяцами данных с gap-периодом летом 2025. Используйте ensemble для горизонтов ≤7-14 дней,
                          где он стабильно положителен.
                        </p>
                      </div>
                    )}
                    {Object.values(metrics).some(m => typeof m === 'object' && m !== null && 'fold_count' in m) && (
                      <p className="mt-2 text-xs text-[hsl(var(--muted-foreground))] italic">
                        Метрики получены через walk-forward CV (катящееся окно с шагом 14 дней). ± показывает разброс RMSE между fold'ами — низкое значение означает стабильное поведение модели.
                      </p>
                    )}
                  </div>

                  <div className="mt-5 grid md:grid-cols-3 gap-3 text-xs">
                    <div className="rounded-lg border border-[hsl(var(--border))] p-3">
                      <p className="font-semibold text-[hsl(var(--foreground))] mb-1 inline-flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: MODEL_COLORS.prophet }} />
                        Prophet
                      </p>
                      <p className="text-[hsl(var(--muted-foreground))] leading-relaxed">
                        Декомпозиция ряда на тренд + годовая/недельная сезонность + праздники.
                        Использует погоду как regressor. Консервативна, хороша на спокойных рядах.
                      </p>
                    </div>
                    <div className="rounded-lg border border-[hsl(var(--border))] p-3">
                      <p className="font-semibold text-[hsl(var(--foreground))] mb-1 inline-flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: MODEL_COLORS.neuralprophet }} />
                        NeuralProphet
                      </p>
                      <p className="text-[hsl(var(--muted-foreground))] leading-relaxed">
                        Нейросетевая надстройка над Prophet с lagged-регрессорами.
                        Лучше ловит автокорреляции на коротких горизонтах, но требует больше данных.
                      </p>
                    </div>
                    <div className="rounded-lg border border-[hsl(var(--border))] p-3">
                      <p className="font-semibold text-[hsl(var(--foreground))] mb-1 inline-flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: MODEL_COLORS.xgboost }} />
                        XGBoost
                      </p>
                      <p className="text-[hsl(var(--muted-foreground))] leading-relaxed">
                        Градиентный бустинг на 38 признаках (календарь, лаги, погода, события).
                        Ловит нелинейные взаимодействия. Quantile-режим даёт интервал уверенности.
                      </p>
                    </div>
                  </div>
                  <p className="mt-3 text-xs text-[hsl(var(--muted-foreground))] italic">
                    Ансамбль выбирает лучшую модель по минимальному RMSE на тестовом окне. Метка <Badge variant="success" size="sm">лучшая</Badge> — это победитель.
                  </p>
                </CardContent>
              </Card>
            )}

            {/* Feature Importance */}
            {topFeatures.length > 0 && (
              <Card variant="glass">
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <Cpu className="w-5 h-5 text-[hsl(var(--warning))]" />
                    <CardTitle>На что больше всего смотрит модель</CardTitle>
                  </div>
                  <p className="text-sm text-[hsl(var(--muted-foreground))]">
                    Чем длиннее столбик — тем сильнее признак влияет на прогноз. Бейдж справа показывает группу признака; описание — в подсказке при наведении.
                  </p>
                </CardHeader>
                <CardContent>
                  {/* Группы признаков (агрегированно) */}
                  {featureGroupSummary.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-4 pb-3 border-b border-[hsl(var(--border))]">
                      {featureGroupSummary.map(({ group, importance }) => (
                        <span
                          key={group}
                          className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-[hsl(var(--secondary))] border border-[hsl(var(--border))] text-xs"
                          title={`Суммарная важность всех ${group.toLowerCase()} признаков`}
                        >
                          <span className="text-[hsl(var(--muted-foreground))]">{group}:</span>
                          <span className="font-semibold tabular-nums">{(importance * 100).toFixed(1)}%</span>
                        </span>
                      ))}
                    </div>
                  )}
                  <ResponsiveContainer width="100%" height={Math.max(320, topFeatures.length * 38)}>
                    <BarChart data={topFeatures} layout="vertical" margin={{ left: 8, right: 80, top: 4, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.3} horizontal={false} />
                      <XAxis type="number" axisLine={false} tickLine={false} tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v*100).toFixed(0)}%`} />
                      <YAxis
                        dataKey="displayName"
                        type="category"
                        width={220}
                        tick={{ fontSize: 13 }}
                        axisLine={false}
                        tickLine={false}
                        interval={0}
                      />
                      <Tooltip
                        cursor={BAR_CURSOR_TRANSPARENT}
                        content={({ active, payload }) => {
                          if (!active || !payload?.length) return null
                          const item = payload[0].payload as { displayName: string; group: string; description: string; importance: number }
                          return (
                            <div style={RECHARTS_TOOLTIP_PROPS.contentStyle as React.CSSProperties}>
                              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                                <span style={{ ...(RECHARTS_TOOLTIP_PROPS.labelStyle as React.CSSProperties), fontWeight: 600 }}>
                                  {item.displayName}
                                </span>
                                <span style={{ fontSize: 11, padding: '1px 6px', borderRadius: 4, background: 'hsl(var(--secondary))', opacity: 0.85 }}>
                                  {item.group}
                                </span>
                              </div>
                              {item.description && (
                                <div style={{ fontSize: 12, opacity: 0.85, marginTop: 6, maxWidth: 320, lineHeight: 1.4 }}>
                                  {item.description}
                                </div>
                              )}
                              <div style={{ fontSize: 12, marginTop: 6, opacity: 0.7 }}>
                                Важность: {(item.importance * 100).toFixed(2)}%
                              </div>
                            </div>
                          )
                        }}
                      />
                      <Bar dataKey="importance" fill="hsl(var(--warning))" radius={[0, 4, 4, 0]}>
                        <LabelList
                          dataKey="group"
                          position="right"
                          style={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                        />
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            )}
          </div>}

          {/* Forecast Self-Validation */}
          {viewMode === 'expert' && (
            <Card variant="glass">
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-[hsl(var(--success))]" />
                  <CardTitle>Самовалидация модели</CardTitle>
                </div>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">
                  Сравнение прошлых прогнозов с реальными данными за 14 дней
                </p>
              </CardHeader>
              <CardContent>
                {loadingValidation ? (
                  <div className="h-32 skeleton rounded-xl" />
                ) : !validationData || validationData.samples === 0 ? (
                  <div className="flex items-start gap-3 p-4 rounded-xl bg-[hsl(var(--secondary))]">
                    <AlertCircle className="w-5 h-5 text-[hsl(var(--muted-foreground))] flex-shrink-0 mt-0.5" />
                    <p className="text-sm text-[hsl(var(--muted-foreground))]">
                      Прогнозы за прошлые периоды ещё не сохранены. Запустите ensemble-эндпоинт несколько раз — далее самовалидация заработает.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-3">
                      <div className="p-3 rounded-xl bg-[hsl(var(--secondary))] text-center">
                        <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">RMSE</p>
                        <p className="text-2xl font-bold tabular-nums">{validationData.rmse?.toFixed(2) ?? '—'}</p>
                        <p className="text-xs text-[hsl(var(--muted-foreground))]">п.п. средняя ошибка</p>
                      </div>
                      <div className="p-3 rounded-xl bg-[hsl(var(--secondary))] text-center">
                        <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">MAE</p>
                        <p className="text-2xl font-bold tabular-nums">{validationData.mae?.toFixed(2) ?? '—'}</p>
                        <p className="text-xs text-[hsl(var(--muted-foreground))]">п.п. среднее отклонение</p>
                      </div>
                    </div>
                    {validationData.mae_per_day && validationData.mae_per_day.length > 0 && (
                      <div>
                        <div className="flex items-center gap-1.5 mb-2">
                          <p className="text-xs font-medium text-[hsl(var(--muted-foreground))]">MAE по дням</p>
                          <MethodologyTooltip text="Средняя ошибка по абсолютной величине для каждого дня горизонта. Чем больше дней до прогноза — тем выше MAE. Идеальный график: ровный или слабо растущий вправо." />
                        </div>
                        <ResponsiveContainer width="100%" height={150}>
                          <BarChart data={validationData.mae_per_day.map((mae, i) => {
                            const iso = validationData.forecasted?.[i]?.date
                            const label = iso
                              ? new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' })
                              : `Д${i + 1}`
                            return { day: label, mae: Number(mae.toFixed(2)) }
                          })}>
                            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                            <XAxis dataKey="day" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} interval={validationData.mae_per_day.length > 8 ? 1 : 0} />
                            <YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false} label={{ value: 'MAE, п.п.', angle: -90, position: 'insideLeft', fontSize: 10 }} />
                            <Tooltip
                              {...RECHARTS_TOOLTIP_PROPS}
                              cursor={BAR_CURSOR_TRANSPARENT}
                              formatter={(v: number) => [`${v} п.п.`, 'MAE']}
                            />
                            <Bar dataKey="mae" fill="hsl(var(--success))" radius={[4, 4, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                    <p className="text-xs text-[hsl(var(--muted-foreground))]">
                      На основе {validationData.samples} сохранённых прогнозов
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* AI Explanation */}
          {viewMode !== 'simple' && (
          <Card variant="gradient" className="bg-gradient-to-r from-[hsl(var(--accent)/0.05)] to-[hsl(var(--primary)/0.05)] border-[hsl(var(--accent)/0.2)]">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <MessageSquare className="w-5 h-5 text-[hsl(var(--accent))]" />
                  <CardTitle>AI-объяснение прогноза</CardTitle>
                </div>
                <button
                  onClick={() => refetchExplain()}
                  disabled={loadingExplain}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-[hsl(var(--accent))] text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
                >
                  {loadingExplain ? <Loader2 size={12} className="animate-spin" /> : <Lightbulb size={12} />}
                  {loadingExplain ? 'Анализ...' : explainData ? 'Обновить' : 'Получить объяснение'}
                </button>
              </div>
            </CardHeader>
            <CardContent>
              {explainData && !explainData.error ? (
                <div className="space-y-3">
                  {explainData.explanation && (
                    <div className="p-3 rounded-xl bg-[hsl(var(--secondary))]">
                      <p className="text-sm leading-relaxed whitespace-pre-line">{explainData.explanation}</p>
                    </div>
                  )}
                  {explainData.factors && explainData.factors.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-[hsl(var(--muted-foreground))] mb-2">Факторы влияния:</p>
                      <div className="flex flex-wrap gap-1.5">
                        {explainData.factors.map((f, i) => (
                          <Badge
                            key={i}
                            variant="outline"
                            size="sm"
                            className={
                              f.direction === 'positive' ? 'border-green-500/50 text-green-600' :
                              f.direction === 'negative' ? 'border-red-500/50 text-red-600' : ''
                            }
                          >
                            {f.direction === 'positive' ? '↑' : f.direction === 'negative' ? '↓' : '•'} {f.name}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {explainData.recommendation && (
                    <div className="p-3 rounded-xl bg-[hsl(var(--success)/0.1)] border border-[hsl(var(--success)/0.2)]">
                      <div className="flex items-start gap-2">
                        <Lightbulb size={14} className="text-[hsl(var(--success))] mt-0.5 flex-shrink-0" />
                        <p className="text-sm text-[hsl(var(--success))]">{explainData.recommendation}</p>
                      </div>
                    </div>
                  )}
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">
                    Сгенерировано за {explainData.processing_time}с
                  </p>
                </div>
              ) : explainData?.error ? (
                <p className="text-sm text-[hsl(var(--destructive))]">{explainData.error}</p>
              ) : !loadingExplain ? (
                <p className="text-sm text-[hsl(var(--muted-foreground))] text-center py-4">
                  Нажмите кнопку, чтобы AI объяснил прогноз и дал рекомендации
                </p>
              ) : (
                <div className="flex items-center justify-center py-8 gap-3">
                  <Loader2 className="w-5 h-5 animate-spin text-[hsl(var(--accent))]" />
                  <span className="text-sm text-[hsl(var(--muted-foreground))]">AI анализирует прогноз...</span>
                </div>
              )}
            </CardContent>
          </Card>
          )}
          {/* District Comparison */}
          {viewMode !== 'simple' && (
          <Card variant="glass">
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <Layers className="w-5 h-5 text-[hsl(var(--accent))]" />
                <CardTitle className="text-base">Сравнение районов</CardTitle>
              </div>
              <div className="flex flex-wrap gap-1.5 mt-2">
                {districtNames
                  .filter(d => d !== district)
                  .slice(0, 6)
                  .map(d => {
                    const active = compareDistricts.includes(d)
                    return (
                      <button
                        key={d}
                        onClick={() => setCompareDistricts(prev =>
                          active ? prev.filter(x => x !== d) : prev.length < 3 ? [...prev, d] : prev
                        )}
                        className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                          active
                            ? 'bg-[hsl(var(--primary))] text-white'
                            : 'bg-[hsl(var(--secondary))] hover:bg-[hsl(var(--secondary)/0.8)]'
                        }`}
                      >
                        {d}
                      </button>
                    )
                  })}
              </div>
            </CardHeader>
            {compareDistrictData && compareDistrictData.length > 0 && (
              <CardContent>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={_mergeDistrictData(district, ensemblePoints, compareDistrictData)}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 10 }}
                      tickFormatter={(d) => new Date(d).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      domain={[0, 100]}
                      tickFormatter={(v) => `${v}%`}
                      tick={{ fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                      width={40}
                    />
                    <Tooltip
                      {...RECHARTS_TOOLTIP_PROPS}
                      formatter={(v: number, name: string) => [`${Math.round(v)}%`, name]}
                      labelFormatter={(d) => new Date(d).toLocaleDateString('ru-RU', { weekday: 'short', day: 'numeric', month: 'long' })}
                    />
                    <Legend />
                    <Line type="monotone" dataKey={district} stroke="hsl(var(--primary))" strokeWidth={2.5} dot={false} />
                    {compareDistrictData.map((cd, i) => (
                      <Line
                        key={cd.district}
                        type="monotone"
                        dataKey={cd.district}
                        stroke={COMPARE_COLORS[i]}
                        strokeWidth={2}
                        dot={false}
                        strokeDasharray={i > 0 ? '5 3' : undefined}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            )}
          </Card>
          )}
        </>
      )}
    </div>
  )
}

const COMPARE_COLORS = ['hsl(280 67% 50%)', 'hsl(142 76% 36%)', 'hsl(30 90% 50%)']

function _mergeDistrictData(
  mainDistrict: string,
  mainPoints: { date: string; occupancy: number }[],
  otherData: { district: string; data: { ensemble?: { date: string; occupancy: number }[] } | undefined }[],
) {
  const dateMap: Record<string, Record<string, number>> = {}

  mainPoints.forEach(p => {
    if (!dateMap[p.date]) dateMap[p.date] = {}
    dateMap[p.date][mainDistrict] = p.occupancy
  })

  otherData.forEach(({ district, data }) => {
    if (!data?.ensemble) return
    data.ensemble.forEach(p => {
      if (!dateMap[p.date]) dateMap[p.date] = {}
      dateMap[p.date][district] = p.occupancy
    })
  })

  return Object.entries(dateMap)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, values]) => ({ date, ...values }))
}

function ForecastSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-3">
        {[1, 2, 3].map(i => <div key={i} className="h-24 skeleton rounded-2xl" />)}
      </div>
      <div className="h-72 skeleton rounded-2xl" />
      <div className="h-64 skeleton rounded-2xl" />
    </div>
  )
}

function SeasonalitySkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[1, 2, 3].map(i => <div key={i} className="h-28 skeleton rounded-2xl" />)}
      </div>
      <div className="h-80 skeleton rounded-2xl" />
    </div>
  )
}

function SeasonRow({ icon: Icon, name, description, color }: {
  icon: React.ElementType
  name: string
  description: string
  color: 'warning' | 'success' | 'primary' | 'accent'
}) {
  const colorMap = {
    warning: 'hsl(var(--warning))',
    success: 'hsl(var(--success))',
    primary: 'hsl(var(--primary))',
    accent: 'hsl(var(--accent))',
  }

  return (
    <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-[hsl(var(--secondary)/0.5)] transition-colors">
      <div
        className="w-8 h-8 rounded-lg flex items-center justify-center"
        style={{ backgroundColor: `${colorMap[color]}20` }}
      >
        <Icon size={16} style={{ color: colorMap[color] }} />
      </div>
      <div className="flex-1">
        <p className="text-sm font-medium">{name}</p>
        <p className="text-xs text-[hsl(var(--muted-foreground))]">{description}</p>
      </div>
    </div>
  )
}

function _buildMultiModelData(
  ensemble: { date: string; occupancy: number }[],
  models: Record<string, { date: string; occupancy: number }[]>,
) {
  const dateMap: Record<string, Record<string, number>> = {}

  ensemble.forEach(p => {
    if (!dateMap[p.date]) dateMap[p.date] = {}
    dateMap[p.date].ensemble = p.occupancy
  })

  Object.entries(models).forEach(([model, points]) => {
    points.forEach(p => {
      if (!dateMap[p.date]) dateMap[p.date] = {}
      dateMap[p.date][model] = p.occupancy
    })
  })

  return Object.entries(dateMap)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, values]) => ({ date, ...values }))
}

function _getTopFeatures(fi: Record<string, Record<string, number>>) {
  const xgbFeatures = fi.xgboost || fi.XGBoost || {}
  return Object.entries(xgbFeatures)
    .map(([name, importance]) => ({
      name,
      displayName: localizeFeature(name),
      group: featureGroup(name),
      description: describeFeature(name),
      importance: Number(importance),
    }))
    .sort((a, b) => b.importance - a.importance)
    .slice(0, 10)
}

function _getFeatureGroupSummary(fi: Record<string, Record<string, number>>) {
  const xgbFeatures = fi.xgboost || fi.XGBoost || {}
  const groups: Record<string, number> = {}
  for (const [name, importance] of Object.entries(xgbFeatures)) {
    const g = featureGroup(name)
    groups[g] = (groups[g] || 0) + Number(importance)
  }
  return Object.entries(groups)
    .map(([group, importance]) => ({ group, importance }))
    .sort((a, b) => b.importance - a.importance)
}

function _getSeasonChartData(months: SeasonData[]) {
  return months.map(d => ({
    ...d,
    occupancyDisplay: d.hasData === false ? null : d.occupancy,
    avgPriceDisplay: d.hasData === false ? null : d.avgPrice,
    missingArea: d.hasData === false ? 100 : null,
  }))
}

function _calculateInsights(months: SeasonData[]) {
  const validMonths = months.filter(m => m.hasData !== false)

  if (validMonths.length === 0) {
    return {
      bestMonth: null,
      bestReason: 'Недостаточно данных',
      peakMonth: null,
      peakReason: 'Недостаточно данных',
      cheapestMonth: null,
      cheapestReason: 'Недостаточно данных',
    }
  }

  const sortedByOccupancy = [...validMonths].sort((a, b) => a.occupancy - b.occupancy)
  const bestMonth = sortedByOccupancy[0]
  const peakMonth = sortedByOccupancy[sortedByOccupancy.length - 1]
  const sortedByPrice = [...validMonths].sort((a, b) => a.avgPrice - b.avgPrice)
  const cheapestMonth = sortedByPrice[0]

  return {
    bestMonth: bestMonth?.month || null,
    bestReason: bestMonth ? `Заполняемость ${Math.round(bestMonth.occupancy)}% — окно для тех. работ, промо-тарифов, event-маркетинга` : 'Нет данных',
    peakMonth: peakMonth?.month || null,
    peakReason: peakMonth ? `Заполняемость ${Math.round(peakMonth.occupancy)}% — потенциал для динамического pricing и LOS-фильтров` : 'Нет данных',
    cheapestMonth: cheapestMonth?.month || null,
    cheapestReason: cheapestMonth ? `Ср. цена ${Math.round(cheapestMonth.avgPrice).toLocaleString()}₽` : 'Нет данных',
  }
}

function _seasonDesc(months: SeasonData[], prefixes: string[]): string {
  const filtered = months.filter(m => prefixes.some(p => m.month.startsWith(p)))
  const valid = filtered.filter(m => m.hasData !== false)
  if (valid.length === 0) return 'Нет данных за период'
  const avgOcc = Math.round(valid.reduce((a, b) => a + b.occupancy, 0) / valid.length)
  const avgPrice = Math.round(valid.reduce((a, b) => a + b.avgPrice, 0) / valid.length)
  return avgPrice > 0 ? `Заполняемость ~${avgOcc}%, ср. цена ${avgPrice.toLocaleString()}₽` : `Заполняемость ~${avgOcc}%`
}

export default Forecast
