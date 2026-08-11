import { useQuery } from '@tanstack/react-query'
import { api, type AnalyticsMetadata } from '../api/client'
import {
  Info, Database, Brain, BarChart3, Globe, Shield,
  Cpu, Cloud, Layers, Zap, GitBranch, Server, Compass,
  BookOpen, AlertTriangle, CheckCircle, XCircle, Clock,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent, Badge } from '../components/ui'
import { ErrorState } from '../components/ErrorState'
import { usePageTitle } from '../hooks/usePageTitle'

const TECH_STACK = [
  {
    category: 'Backend',
    icon: Server,
    items: [
      { name: 'FastAPI', desc: 'Async REST API' },
      { name: 'PostgreSQL 16', desc: 'Основная БД' },
      { name: 'Redis 7', desc: 'Кэширование + Rate Limiting' },
      { name: 'ChromaDB', desc: 'Векторный поиск (RAG)' },
    ],
  },
  {
    category: 'ML-модели',
    icon: Brain,
    items: [
      { name: 'Prophet', desc: 'Тренд и сезонность' },
      { name: 'XGBoost', desc: 'Градиентный бустинг, 38 признаков' },
      { name: 'Ансамбль', desc: 'Взвешенное среднее двух моделей' },
    ],
  },
  {
    category: 'AI-агент',
    icon: Cpu,
    items: [
      { name: 'LangGraph', desc: 'Граф состояний с Command routing' },
      { name: 'LLM с автопереключением', desc: 'Groq (Llama 3.3 70B) → DeepSeek → Mistral' },
      { name: 'RAG (ChromaDB)', desc: 'Векторная база знаний' },
      { name: '13 B2B-инструментов', desc: 'RMS-метрики, бенчмарк сегмента, события, динамика бронирований, перцентили цен' },
    ],
  },
  {
    category: 'Frontend',
    icon: Globe,
    items: [
      { name: 'React 18', desc: 'SPA + lazy loading' },
      { name: 'TypeScript', desc: 'Строгая типизация' },
      { name: 'Recharts + Yandex Maps', desc: 'Графики и карта' },
      { name: 'TailwindCSS 4', desc: 'Адаптивный дизайн' },
    ],
  },
]

const ARCH_BADGE_CLASS: Record<'primary' | 'accent' | 'success' | 'warning', string> = {
  primary: 'bg-[hsl(var(--primary)/0.1)] border-[hsl(var(--primary)/0.3)]',
  accent: 'bg-[hsl(var(--accent)/0.1)] border-[hsl(var(--accent)/0.3)]',
  success: 'bg-[hsl(var(--success)/0.1)] border-[hsl(var(--success)/0.3)]',
  warning: 'bg-[hsl(var(--warning)/0.1)] border-[hsl(var(--warning)/0.3)]',
}

const BASE_SOURCES = [
  { name: '101hotels.com', desc: 'Реестр размещения, цены, свободные номера — снимок каждые 2 часа' },
  { name: 'Open-Meteo', desc: 'Погода: факт и прогноз по центрам районов' },
]

const GAP_FALLBACK = '24.06.2025 – 25.10.2025 (123 дня)'

function formatIsoDate(iso: string | null): string | null {
  if (!iso) return null
  const parsed = new Date(iso)
  if (Number.isNaN(parsed.getTime())) return null
  return parsed.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function formatGapPeriods(periods: AnalyticsMetadata['gap_periods'] | undefined): string {
  if (!periods || periods.length === 0) return GAP_FALLBACK
  const parts = periods
    .map(({ from, to, gap_days }) => {
      const fromStr = formatIsoDate(from)
      const toStr = formatIsoDate(to)
      if (!fromStr || !toStr) return null
      return `${fromStr} – ${toStr} (${gap_days} дн.)`
    })
    .filter((part): part is string => part !== null)
  return parts.length > 0 ? parts.join('; ') : GAP_FALLBACK
}

function About() {
  usePageTitle('О системе')
  const { data: kpi, isError: kpiError, refetch: refetchKpi } = useQuery({ queryKey: ['kpi'], queryFn: api.getKPI })
  const { data: metadata } = useQuery({ queryKey: ['metadata'], queryFn: api.getMetadata })
  const { data: parsers } = useQuery({ queryKey: ['parser-health'], queryFn: api.getParserHealth })
  const { data: districts } = useQuery({
    queryKey: ['districts'],
    queryFn: () => api.getDistricts(),
    staleTime: 10 * 60 * 1000,
  })

  return (
    <div className="space-y-6 animate-fade-in max-w-4xl mx-auto">
      <div className="text-center mb-8">
        <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-[hsl(var(--primary))] to-[hsl(var(--accent))] flex items-center justify-center">
          <Info className="w-8 h-8 text-white" />
        </div>
        <h1 className="text-3xl font-bold mb-2">ИАС «Прибайкалье»</h1>
        <p className="text-lg text-[hsl(var(--muted-foreground))]">
          B2B-инструмент анализа рынка размещения и Revenue Management для трёх сегментов: владельцев средств размещения, региональной администрации и исследовательских групп.
        </p>
        <p className="text-sm text-[hsl(var(--muted-foreground))] mt-2">
          Байкальский макрорегион: Иркутская область и прибайкальские районы Бурятии · мониторинг загрузки, цен и событийного спроса · взвешенное среднее двух моделей прогноза · AI-агент с RMS-инструментами.
        </p>
        <div className="flex items-center justify-center gap-2 mt-3">
          <Badge variant="primary" size="sm">B2B</Badge>
          <Badge variant="primary" size="sm">ВКР 2026</Badge>
        </div>
      </div>

      <Card variant="glass">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Compass className="w-5 h-5 text-[hsl(var(--primary))]" />
            <CardTitle>Как пользоваться системой</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {[
              { label: 'Командный центр', desc: 'B2B-сводка региона: прокси-RevPAR, прокси-ADR, загрузка, ближайшие события' },
              { label: 'Аналитика рынка', desc: 'KPI, RMS-метрики, тепловая карта, динамика бронирований, экспорт CSV' },
              { label: 'Прогноз спроса', desc: 'Взвешенное среднее двух моделей (Prophet + XGBoost), горизонты 3/7/14 дней' },
              { label: 'События и спрос', desc: 'Каталог событий: даты, тип, источник, дедупликация. Измеренный эффект событий на загрузку — в Аналитике, вкладка «События»' },
              { label: 'Региональная карта', desc: 'Объекты на карте, загрузка и цена по районам' },
              { label: 'AI-агент', desc: 'B2B-аналитик: запросы RMS-метрик и прогнозов в режиме диалога' },
            ].map(({ label, desc }) => (
              <div key={label} className="flex items-start gap-2 p-2 rounded-lg">
                <span className="text-sm font-semibold text-[hsl(var(--primary))] whitespace-nowrap">{label}</span>
                <span className="text-sm text-[hsl(var(--muted-foreground))]">— {desc}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {kpiError && <ErrorState message="Не удалось загрузить KPI данные" onRetry={refetchKpi} />}

      <Card variant="gradient" className="bg-gradient-to-r from-[hsl(var(--primary)/0.05)] to-[hsl(var(--accent)/0.05)] border-[hsl(var(--primary)/0.2)]">
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold text-[hsl(var(--primary))]">
                {metadata?.hotels_count ?? kpi?.total_hotels ?? '—'}
              </p>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">Объектов в справочнике</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-[hsl(var(--accent))]">{districts ? districts.length : '—'}</p>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">Районов с данными (от 4 объектов)</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-[hsl(var(--success))]">
                {parsers ? parsers.length : '—'}
              </p>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">Парсеров событий</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-[hsl(var(--warning))]">2+1</p>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">Модели прогноза + ансамбль</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card variant="glass">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-[hsl(var(--warning))]" />
            <CardTitle>Ключевые возможности</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {[
              { icon: BarChart3, title: 'Регулярный мониторинг рынка', desc: 'Загрузка, цены и свободные номера по районам — снимок каждые 2 часа' },
              { icon: Brain, title: 'Прогнозирование (ансамбль)', desc: 'Взвешенное среднее Prophet и XGBoost, горизонты 3/7/14 дней' },
              { icon: Cpu, title: 'AI-агент с инструментами', desc: 'LangGraph и автопереключение LLM: RMS-метрики, отели, события, погода' },
              { icon: Layers, title: 'Автоматический сбор данных', desc: 'Парсеры событий, реестра размещения и погоды по расписанию (APScheduler); состав и состояние — в карточке «Источники данных»' },
              { icon: Shield, title: 'Безопасность', desc: 'Rate Limiting, API Key auth, SQL injection protection' },
              { icon: GitBranch, title: 'Feature Engineering', desc: '38 признаков: календарь, праздники, лаги, скользящие, погода, события, тренд, цены' },
            ].map(({ icon: Icon, title, desc }) => (
              <div key={title} className="flex items-start gap-3 p-3 rounded-xl bg-[hsl(var(--secondary)/0.3)]">
                <div className="w-9 h-9 rounded-lg bg-[hsl(var(--primary)/0.1)] flex items-center justify-center flex-shrink-0">
                  <Icon size={16} className="text-[hsl(var(--primary))]" />
                </div>
                <div>
                  <p className="text-sm font-medium">{title}</p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {TECH_STACK.map(({ category, icon: Icon, items }) => (
          <Card key={category} variant="glass">
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <Icon className="w-4 h-4 text-[hsl(var(--primary))]" />
                <CardTitle className="text-sm">{category}</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {items.map(({ name, desc }) => (
                  <div key={name} className="flex items-center justify-between">
                    <span className="text-sm font-medium">{name}</span>
                    <span className="text-xs text-[hsl(var(--muted-foreground))]">{desc}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card variant="glass">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-[hsl(var(--accent))]" />
            <CardTitle>Источники данных</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {BASE_SOURCES.map(({ name, desc }) => (
              <div key={name} className="flex items-start gap-3 p-3 rounded-xl bg-[hsl(var(--secondary)/0.3)]">
                <Database size={14} className="text-[hsl(var(--accent))] flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">{name}</p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">{desc}</p>
                </div>
              </div>
            ))}
          </div>

          <p className="text-xs text-[hsl(var(--muted-foreground))] mt-4 mb-2">
            Парсеры событий и их состояние на последний прогон:
          </p>

          {parsers && parsers.length > 0 ? (
            <div className="space-y-2">
              {parsers.map((p) => {
                const isEmpty = p.status === 'ok' && p.items_collected === 0
                const statusIcon = p.status === 'ok' && !isEmpty
                  ? <CheckCircle size={14} className="text-[hsl(var(--success))] flex-shrink-0" />
                  : p.status === 'fail'
                  ? <XCircle size={14} className="text-[hsl(var(--destructive))] flex-shrink-0" />
                  : <AlertTriangle size={14} className="text-[hsl(var(--warning))] flex-shrink-0" />
                const badgeVariant = p.status === 'fail' ? 'danger' : isEmpty || p.status === 'warn' ? 'warning' : 'success'
                const badgeLabel = isEmpty ? 'пусто' : p.status
                const lastRunStr = p.last_run
                  ? new Date(p.last_run).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
                  : '—'
                return (
                  <div key={p.parser_id} className="flex items-center gap-3 p-3 rounded-xl bg-[hsl(var(--secondary)/0.3)]">
                    {statusIcon}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{p.parser_id}</p>
                      <div className="flex items-center gap-1.5 mt-0.5 text-xs text-[hsl(var(--muted-foreground))]">
                        <Clock size={11} />
                        <span>{lastRunStr}</span>
                        {p.error && <span className="text-[hsl(var(--destructive))] truncate">· {p.error}</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className="text-xs text-[hsl(var(--muted-foreground))]">
                        {p.items_collected.toLocaleString('ru-RU')} зап.
                      </span>
                      <Badge variant={badgeVariant} size="sm">{badgeLabel}</Badge>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <p className="text-sm text-[hsl(var(--muted-foreground))]">Состояние парсеров сейчас недоступно.</p>
          )}
        </CardContent>
      </Card>

      <Card variant="glass">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Cloud className="w-5 h-5 text-[hsl(var(--success))]" />
            <CardTitle>Архитектура</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center gap-3 flex-wrap text-sm">
            {[
              { label: 'React SPA', color: 'primary' },
              { label: 'FastAPI', color: 'accent' },
              { label: 'PostgreSQL', color: 'success' },
              { label: 'Redis', color: 'warning' },
              { label: 'ChromaDB', color: 'primary' },
              { label: 'LangGraph', color: 'accent' },
            ].map(({ label, color }, i) => (
              <div key={label} className="flex items-center gap-2">
                <div className={`px-3 py-1.5 rounded-lg border font-medium text-xs ${ARCH_BADGE_CLASS[color as keyof typeof ARCH_BADGE_CLASS]}`}>
                  {label}
                </div>
                {i < 5 && <span className="text-[hsl(var(--muted-foreground))]">→</span>}
              </div>
            ))}
          </div>
          <p className="text-xs text-[hsl(var(--muted-foreground))] text-center mt-4">
            Docker Compose: PostgreSQL 16 + Redis 7 | Backend: Python 3.11+ | Frontend: Vite 7 + React 18
          </p>
        </CardContent>
      </Card>

      <Card variant="glass">
        <CardHeader>
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-[hsl(var(--success))]" />
            <CardTitle>Методология</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3 text-sm">
            {[
              {
                title: 'Покрытие данных',
                body: 'Выборка охватывает Байкальский макрорегион: районы Иркутской области и прибайкальские районы Республики Бурятия (Улан-Удэ, Прибайкальский, Кабанский, Тункинский). Поэтому «Иркутская область» границами данных не является. Районы, в которых меньше 4 объектов со свежим снимком, в разрезах по районам не показываются.',
              },
              {
                title: 'RevPAR и ADR',
                body: 'RevPAR = ADR × Occupancy. Прокси-ADR — медиана min_price по объектам района, во всех разрезах системы. Реальный тариф выше рекламируемого минимума, величину разрыва мы не измеряли. Прокси-RevPAR используется для сравнения трендов и районов, не для абсолютного ROI.',
              },
              {
                title: 'Влияние событий',
                body: 'День события сравнивается с обычными днями того же календарного месяца в том же районе; ошибка считается по этим же ячейкам, потому что многодневный фестиваль даёт подряд идущие дни с общим уровнем спроса. Надёжность определяется числом независимых эпизодов, а не числом событийных дней. На текущих данных эффект обнаружен не был.',
              },
              {
                title: 'Достоверность RMS-метрик',
                body: 'high — 10 объектов и больше, medium — от 3 до 9, low — 2 и меньше. В разрезе по районам метка low не встречается: районы с выборкой меньше 4 объектов не показываются вовсе.',
              },
              {
                title: 'Качество прогноза',
                body: 'Горизонт ограничен 14 днями. Точность измерена контролируемым rolling-origin бэктестом (backend/scripts/backtest_forecast.py: 31 origin, 29.03–02.08.2026, Иркутский район, парный бутстрэп против наивного прогноза «завтра как вчера»). MAE модели против MAE наивного: горизонт 1 день — 2,83 против 2,82; 3 дня — 3,73 против 4,69; 7 дней — 4,75 против 3,81. То есть дальше 3 дней ошибка модели сопоставима с тривиальной базой и на длинных горизонтах уступает ей. На последних 7 origins (03.07–02.08.2026) модель проигрывает наивной базе на всех горизонтах с систематическим занижением загрузки. Причина известна: пробел данных за высокий сезон 2025 года оставил модели без наблюдений июля–октября.',
              },
              {
                title: 'Пробел в данных',
                body: `Сбор был отключён: ${formatGapPeriods(metadata?.gap_periods)}. Период исключается из расчёта сезонности и не интерполируется.`,
              },
            ].map(({ title, body }) => (
              <div key={title} className="p-3 rounded-xl bg-[hsl(var(--secondary)/0.3)]">
                <p className="font-medium mb-1">{title}</p>
                <p className="text-[hsl(var(--muted-foreground))]">{body}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card variant="glass">
        <CardHeader>
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-[hsl(var(--warning))]" />
            <CardTitle>Что не делает система (известные ограничения)</CardTitle>
          </div>
          <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
            Раскройте каждый пункт, чтобы увидеть, что означает ограничение и как его снять. Это помогает корректно интерпретировать цифры.
          </p>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm">
            {[
              {
                title: 'Не показывает true ADR / RevPAR',
                summary: 'Используем прокси из min_price отелей, а не реальную выручку.',
                expanded: 'ADR (Average Daily Rate) — средняя оплаченная цена за номер за сутки. RevPAR (Revenue Per Available Room) = ADR × Загрузка — выручка с одного доступного номера. Источник «настоящего» ADR — PMS отеля или Booking.com Insights API. У нас нет доступа, поэтому используем медиану публичных min_price (с 101hotels). Смещение направленное: реальный тариф выше рекламируемого минимума, но величину разрыва мы не измеряли и не оцениваем. Чтобы снять ограничение — нужен договор с PMS-провайдером (TravelLine, Bnovo) или платный API Booking.',
              },
              {
                title: 'Не делает comp set с конкретными конкурентами',
                summary: 'Используется анонимный сегментный benchmark (тип×размер).',
                expanded: 'Comp set — это набор конкретных отелей-конкурентов, выбранных вручную (обычно 3–10 объектов). RMS-системы (STR, OTA Insights) дают гостю отчёт «вы vs comp set». У нас вместо этого — статистический benchmark по сегменту: показываем «вы vs средний по сегменту вашего размера и типа». Чтобы дать конкретный comp set — нужен UI, в котором пользователь сам отметит конкурентов, и собственные ID отелей в системе (сейчас используем 101hotels.com IDs).',
              },
              {
                title: 'Не использует real-time pickup',
                summary: 'Только daily proxy-pickup из snapshot diffs.',
                expanded: 'Pickup — это новые брони, поступающие в реальном времени. RMS видят его в кабинете отельера через PMS. У нас нет доступа в PMS, поэтому считаем proxy-pickup: разница свободных номеров между снимками соседних дней (сбор идёт каждые 2 часа). Это даёт «новые брони за сутки», но не различает источник (OTA/direct/walk-in) и не реагирует мгновенно. Чтобы получить real-time — нужен webhook от PMS.',
              },
              {
                title: 'Не учитывает channel mix, LOS, source markets, GOPPAR',
                summary: 'Эти признаки требуют данных, которые есть только у самого отеля.',
                expanded: 'Channel mix — доля бронирований по каналам (OTA Booking, прямые, агенты). LOS (Length of Stay) — средняя длина проживания. Source markets — страны/регионы гостей. GOPPAR (Gross Operating Profit per Available Room) — операционная прибыль на номер. Все эти показатели хранятся в PMS отеля и не публикуются на 101hotels. Без partnership с конкретными отелями получить их невозможно. Снимаем ограничение только переходом на B2B SaaS-модель, где отельеры сами загружают свои данные.',
              },
              {
                title: 'События из источников без detail-страниц приходят неполными',
                summary: 'afisha.irk.ru, culture38.ru — нет описания, времени, цены, адреса.',
                expanded: 'Многие региональные афиши — это HTML-листинги без отдельной страницы события. Парсер видит только: название, дату, иногда город. Описание/время/цена/возрастное ограничение не существуют в HTML — это не ограничение нашего парсера, а ограничение источника. Полные данные есть только там, где разметка schema.org/Event (kassir.ru, yandex.afisha), но оба этих источника в прод-окружении сейчас не отвечают: kassir отваливается по таймауту, yandex.afisha возвращает пустой результат. Поэтому все текущие события — из листингов без detail-страниц. Снимается только с появлением API у конкретного агрегатора либо браузерного рендеринга на прод-хосте.',
              },
              {
                title: 'Telegram-парсинг — best-effort через web preview',
                summary: 'Без Telethon API key (api_id/hash) тянем только публичные превью каналов.',
                expanded: 'Telegram даёт два пути: (1) официальный MTProto API через Telethon — нужны api_id/hash и аккаунт-юзербот; (2) web preview t.me/s/<channel> — простой HTML, никакой авторизации, но содержит только последние ≈10 сообщений и не позволяет искать по дате. Мы используем (2), что объясняет небольшое число событий и отсутствие изображений в части сообщений. В прод-окружении этот источник сейчас в отказе — обращение к t.me завершается таймаутом, свежих событий из Telegram нет. Для полноты — нужен Telethon с зарегистрированным userbot.',
              },
              {
                title: 'Alembic-миграции пока не применяются',
                summary: 'Сейчас используется create_all + ручной миграционный скрипт.',
                expanded: 'Alembic — стандартный инструмент версионирования схемы PostgreSQL. У нас каркас Alembic настроен (backend/alembic/env.py), но в production используется SQLAlchemy create_all + миграционный скрипт под каждое изменение схемы. Это упрощает работу для пилота, но затрудняет откат. До прод-деплоя — нужно перевести на ревизии Alembic (это запланировано в roadmap, но не блокирует выпускную работу).',
              },
            ].map(({ title, summary, expanded }) => (
              <details key={title} className="rounded-lg bg-[hsl(var(--secondary)/0.3)] border border-transparent open:border-[hsl(var(--border))] transition-colors group">
                <summary className="cursor-pointer list-none p-2.5 flex items-start gap-2 hover:bg-[hsl(var(--secondary)/0.5)] rounded-lg">
                  <XCircle size={14} className="text-[hsl(var(--warning))] flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <p className="font-medium text-[hsl(var(--foreground))]">{title}</p>
                    <p className="text-[hsl(var(--muted-foreground))] text-xs mt-0.5">{summary}</p>
                  </div>
                  <span className="text-[hsl(var(--muted-foreground))] text-xs flex-shrink-0 mt-0.5 group-open:rotate-180 transition-transform">▾</span>
                </summary>
                <div className="px-2.5 pb-3 pt-1 ml-6 text-xs text-[hsl(var(--muted-foreground))] leading-relaxed">
                  {expanded}
                </div>
              </details>
            ))}
          </div>
        </CardContent>
      </Card>

      <p className="text-xs text-center text-[hsl(var(--muted-foreground))] pb-4">
        Иркутский государственный университет · Институт математики, экономики и информатики · 2026
      </p>
    </div>
  )
}

export default About
