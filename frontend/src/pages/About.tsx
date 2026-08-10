import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
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
      { name: 'Prophet', desc: 'Классическое прогнозирование' },
      { name: 'XGBoost', desc: 'Градиентный бустинг, 25+ фичей' },
      { name: 'Ensemble', desc: 'Взвешенное объединение моделей' },
    ],
  },
  {
    category: 'AI-агент',
    icon: Cpu,
    items: [
      { name: 'LangGraph', desc: 'Граф состояний с Command routing' },
      { name: 'Mistral Large', desc: 'LLM для tool calling' },
      { name: 'RAG (ChromaDB)', desc: 'Векторная база знаний' },
      { name: '12 B2B-инструментов', desc: 'RMS-метрики, прогноз, события, сегменты, методология' },
    ],
  },
  {
    category: 'Frontend',
    icon: Globe,
    items: [
      { name: 'React 18', desc: 'SPA + lazy loading' },
      { name: 'TypeScript', desc: 'Строгая типизация' },
      { name: 'Recharts + ECharts', desc: 'Графики и гео-карта' },
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

const DATA_SOURCES = [
  { name: '101hotels.com', desc: 'Отели, цены, заполняемость', count: '490+ отелей' },
  { name: 'irk.ru/afisha', desc: 'Афиша Иркутска', count: 'Автопарсинг' },
  { name: 'culture38.ru', desc: 'Культурные события', count: 'Автопарсинг' },
  { name: 'zeroevent.ru', desc: 'Агрегатор событий', count: 'Автопарсинг' },
  { name: 'Telegram', desc: 'Каналы о Байкале', count: '3 канала' },
  { name: 'Open-Meteo', desc: 'Погодные данные', count: 'API' },
]

function About() {
  usePageTitle('О системе')
  const { data: kpi, isError: kpiError, refetch: refetchKpi } = useQuery({ queryKey: ['kpi'], queryFn: api.getKPI })
  const { data: metadata } = useQuery({ queryKey: ['metadata'], queryFn: api.getMetadata })
  const { data: parsers } = useQuery({ queryKey: ['parser-health'], queryFn: api.getParserHealth })

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
          Иркутская область, 15 районов · мониторинг загрузки, цен и событийного спроса · ансамбль ML-моделей · AI-агент с RMS-инструментами.
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
              { label: 'Командный центр', desc: 'B2B-сводка региона: RevPAR, ADR, прогноз 14 дней, события с impact' },
              { label: 'Аналитика рынка', desc: 'KPI, RMS-метрики, тепловая карта, динамика бронирований, экспорт CSV' },
              { label: 'Прогноз спроса', desc: 'Ансамбль Prophet + XGBoost с факторами' },
              { label: 'События и спрос', desc: 'Каталог событий с расчётом impact на загрузку' },
              { label: 'Региональная карта', desc: 'GeoMap по 15 районам с цветовой шкалой загрузки' },
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
                {metadata?.hotels_count ?? kpi?.total_hotels ?? '490+'}
              </p>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">Отелей в базе</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-[hsl(var(--accent))]">15</p>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">Районов области</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-[hsl(var(--success))]">
                {parsers ? parsers.length : 8}
              </p>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">Парсеров данных</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-[hsl(var(--warning))]">3+1</p>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">ML-модели + Ensemble</p>
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
              { icon: BarChart3, title: 'Мониторинг в реальном времени', desc: 'Загруженность отелей, цены и свободные номера по 15 районам' },
              { icon: Brain, title: 'Прогнозирование (Ensemble)', desc: 'Prophet + XGBoost, горизонт до 14 дней' },
              { icon: Cpu, title: 'AI-агент с инструментами', desc: 'LangGraph + Mistral: поиск отелей, событий, погода, прогнозы' },
              { icon: Layers, title: 'Сбор данных из 8 источников', desc: 'Автоматические парсеры с расписанием (APScheduler)' },
              { icon: Shield, title: 'Безопасность', desc: 'Rate Limiting, API Key auth, SQL injection protection' },
              { icon: GitBranch, title: 'Feature Engineering', desc: '25+ признаков: лаги, праздники, погода, события, сезонность' },
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
          {parsers && parsers.length > 0 ? (
            <div className="space-y-2">
              {parsers.map((p) => {
                const statusIcon = p.status === 'ok'
                  ? <CheckCircle size={14} className="text-[hsl(var(--success))] flex-shrink-0" />
                  : p.status === 'warn'
                  ? <AlertTriangle size={14} className="text-[hsl(var(--warning))] flex-shrink-0" />
                  : <XCircle size={14} className="text-[hsl(var(--destructive))] flex-shrink-0" />
                const badgeVariant = p.status === 'ok' ? 'success' : p.status === 'warn' ? 'warning' : 'danger'
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
                      {p.items_collected > 0 && (
                        <span className="text-xs text-[hsl(var(--muted-foreground))]">{p.items_collected.toLocaleString()} зап.</span>
                      )}
                      <Badge variant={badgeVariant} size="sm">{p.status}</Badge>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {DATA_SOURCES.map(({ name, desc, count }) => (
                <div key={name} className="p-3 rounded-xl bg-[hsl(var(--secondary)/0.3)]">
                  <p className="text-sm font-medium">{name}</p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">{desc}</p>
                  <Badge variant="outline" size="sm" className="mt-1">
                    {name === '101hotels.com' && kpi?.total_hotels ? `${kpi.total_hotels} отелей` : count}
                  </Badge>
                </div>
              ))}
            </div>
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
                title: 'RevPAR и ADR',
                body: 'RevPAR = ADR × Occupancy. Прокси-ADR = медиана min_price (реальный обычно на 15–30% выше). Прокси-RevPAR используется для сравнения трендов и районов, не для абсолютного ROI.',
              },
              {
                title: 'Impact событий',
                body: 'Corrected impact событий: baseline по похожим дням недели в окне ±3 нед., исключая другие event-дни. Метод: seasonal_corrected.',
              },
              {
                title: 'Достоверность RMS-метрик',
                body: 'high (≥5 объектов), medium (2–4), low (≤1).',
              },
              {
                title: 'Период gap данных',
                body: 'Июль–сентябрь 2025 (парсеры были временно отключены) — отмечен явно во всех графиках.',
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
                expanded: 'ADR (Average Daily Rate) — средняя оплаченная цена за номер за сутки. RevPAR (Revenue Per Available Room) = ADR × Загрузка — выручка с одного доступного номера. Источник «настоящего» ADR — PMS отеля или Booking.com Insights API. У нас нет доступа, поэтому используем медиану публичных min_price (с 101hotels). Систематическое смещение: реальный ADR обычно на 15–30% выше публикуемой минимальной цены. Чтобы снять ограничение — нужен договор с PMS-провайдером (TravelLine, Bnovo) или платный API Booking.',
              },
              {
                title: 'Не делает comp set с конкретными конкурентами',
                summary: 'Используется анонимный сегментный benchmark (тип×размер).',
                expanded: 'Comp set — это набор конкретных отелей-конкурентов, выбранных вручную (обычно 3–10 объектов). RMS-системы (STR, OTA Insights) дают гостю отчёт «вы vs comp set». У нас вместо этого — статистический benchmark по сегменту: показываем «вы vs средний по сегменту вашего размера и типа». Чтобы дать конкретный comp set — нужен UI, в котором пользователь сам отметит конкурентов, и собственные ID отелей в системе (сейчас используем 101hotels.com IDs).',
              },
              {
                title: 'Не использует real-time pickup',
                summary: 'Только daily proxy-pickup из snapshot diffs.',
                expanded: 'Pickup — это новые брони, поступающие в реальном времени. RMS видят его в кабинете отельера через PMS. У нас нет доступа в PMS, поэтому считаем proxy-pickup: разница свободных номеров между двумя дневными снимками 101hotels (через каждые 2 часа). Это даёт «новые брони за сутки», но не различает источник (OTA/direct/walk-in) и не реагирует мгновенно. Чтобы получить real-time — нужен webhook от PMS.',
              },
              {
                title: 'Не учитывает channel mix, LOS, source markets, GOPPAR',
                summary: 'Эти признаки требуют данных, которые есть только у самого отеля.',
                expanded: 'Channel mix — доля бронирований по каналам (OTA Booking, прямые, агенты). LOS (Length of Stay) — средняя длина проживания. Source markets — страны/регионы гостей. GOPPAR (Gross Operating Profit per Available Room) — операционная прибыль на номер. Все эти показатели хранятся в PMS отеля и не публикуются на 101hotels. Без partnership с конкретными отелями получить их невозможно. Снимаем ограничение только переходом на B2B SaaS-модель, где отельеры сами загружают свои данные.',
              },
              {
                title: 'События из источников без detail-страниц приходят неполными',
                summary: 'afisha.irk.ru, culture38.ru — нет описания, времени, цены, адреса.',
                expanded: 'Многие региональные афиши — это HTML-листинги без отдельной страницы события. Парсер видит только: название, дату, иногда город. Описание/время/цена/возрастное ограничение не существуют в HTML — это не ограничение нашего парсера, а ограничение источника. Полные данные есть только там, где разметка schema.org/Event (kassir.ru, yandex.afisha). Снимается только с появлением API у конкретного агрегатора.',
              },
              {
                title: 'Telegram-парсинг — best-effort через web preview',
                summary: 'Без Telethon API key (api_id/hash) тянем только публичные превью каналов.',
                expanded: 'Telegram даёт два пути: (1) официальный MTProto API через Telethon — нужны api_id/hash и аккаунт-юзербот; (2) web preview t.me/s/<channel> — простой HTML, никакой авторизации, но содержит только последние ≈10 сообщений и не позволяет искать по дате. Мы используем (2), что объясняет небольшое число событий и отсутствие изображений в части сообщений. Для полноты — нужен Telethon с зарегистрированным userbot.',
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
