import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import {
  Info, Database, Brain, BarChart3, Globe, Shield,
  Cpu, Cloud, Layers, Zap, GitBranch, Server, Compass,
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
      { name: 'NeuralProphet', desc: 'Нейросетевой + авторегрессия' },
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
      { name: '5 инструментов', desc: 'Поиск, погода, прогноз, статистика' },
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
  { name: '101hotels.com', desc: 'Отели, цены, загрузка', count: '490+ отелей' },
  { name: 'irk.ru/afisha', desc: 'Афиша Иркутска', count: 'Автопарсинг' },
  { name: 'culture38.ru', desc: 'Культурные события', count: 'Автопарсинг' },
  { name: 'zeroevent.ru', desc: 'Агрегатор событий', count: 'Автопарсинг' },
  { name: 'Telegram', desc: 'Каналы о Байкале', count: '3 канала' },
  { name: 'Open-Meteo', desc: 'Погодные данные', count: 'API' },
]

function About() {
  usePageTitle('О системе')
  const { data: kpi, isError: kpiError, refetch: refetchKpi } = useQuery({ queryKey: ['kpi'], queryFn: api.getKPI })

  return (
    <div className="space-y-6 animate-fade-in max-w-4xl mx-auto">
      <div className="text-center mb-8">
        <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-[hsl(var(--primary))] to-[hsl(var(--accent))] flex items-center justify-center">
          <Info className="w-8 h-8 text-white" />
        </div>
        <h1 className="text-3xl font-bold mb-2">ИАС «Прибайкалье»</h1>
        <p className="text-lg text-[hsl(var(--muted-foreground))]">
          Информационно-аналитическая система мониторинга и прогнозирования туристической активности Иркутской области
        </p>
        <div className="flex items-center justify-center gap-2 mt-3">
          <Badge variant="primary" size="sm">ВКР 2026</Badge>
          <Badge variant="outline" size="sm">ИГУ, ИМЭИ</Badge>
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
              { label: 'Планирование', desc: 'Выберите район и период для обзора ситуации' },
              { label: 'Аналитика', desc: 'Текущая загрузка, цены и прогноз по районам' },
              { label: 'События', desc: 'Календарь мероприятий Прибайкалья' },
              { label: 'Карта', desc: 'Визуализация загрузки по регионам' },
              { label: 'Прогнозы', desc: 'ML-прогноз загрузки и анализ сезонности' },
              { label: 'AI-помощник', desc: 'Задайте любой вопрос о туризме на Байкале' },
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
              <p className="text-2xl font-bold text-[hsl(var(--primary))]">{kpi?.total_hotels || '490+'}</p>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">Отелей в базе</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-[hsl(var(--accent))]">15</p>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">Районов области</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-[hsl(var(--success))]">8</p>
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
              { icon: Brain, title: 'Прогнозирование (Ensemble)', desc: 'Prophet + NeuralProphet + XGBoost с доверительными интервалами' },
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

      <p className="text-xs text-center text-[hsl(var(--muted-foreground))] pb-4">
        Иркутский государственный университет · Институт математики, экономики и информатики · 2026
      </p>
    </div>
  )
}

export default About
