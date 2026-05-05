import { useState, useMemo, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api, type Event as EventData } from '../api/client'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip as ReTooltip, ResponsiveContainer,
} from 'recharts'
import { 
  Calendar, Music, Theater, Palette, Trophy, Briefcase, 
  Film, Baby, PartyPopper, MapPin, ExternalLink, ChevronLeft, ChevronRight,
  X, Clock, Info, Ticket, Search, Database, TrendingUp, Sparkles,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent, Badge, Button, Dropdown } from '../components/ui'
import { ErrorState } from '../components/ErrorState'
import { usePageTitle } from '../hooks/usePageTitle'

// ============================================================================
// TYPES & CONSTANTS
// ============================================================================

const EVENT_TYPES = {
  concert: { icon: Music, label: 'Концерты', color: '#9333ea', bgColor: '#9333ea20' },
  theater: { icon: Theater, label: 'Театр', color: '#0ea5e9', bgColor: '#0ea5e920' },
  exhibition: { icon: Palette, label: 'Выставки', color: '#f59e0b', bgColor: '#f59e0b20' },
  festival: { icon: PartyPopper, label: 'Фестивали', color: '#22c55e', bgColor: '#22c55e20' },
  sport: { icon: Trophy, label: 'Спорт', color: '#ef4444', bgColor: '#ef444420' },
  business: { icon: Briefcase, label: 'Бизнес', color: '#3b82f6', bgColor: '#3b82f620' },
  cinema: { icon: Film, label: 'Кино', color: '#14b8a6', bgColor: '#14b8a620' },
  kids: { icon: Baby, label: 'Детям', color: '#ec4899', bgColor: '#ec489920' },
  holiday: { icon: PartyPopper, label: 'Праздники', color: '#eab308', bgColor: '#eab30820' },
  other: { icon: Calendar, label: 'Другое', color: '#6b7280', bgColor: '#6b728020' },
} as const

type EventType = keyof typeof EVENT_TYPES

const SOURCE_LABELS: Record<string, string> = {
  irk: 'Афиша Иркутска',
  culture38: 'Культура38',
  zeroevent: 'ZeroEvent',
  yandex: 'Яндекс Афиша',
  kassir: 'Кассир.ру',
  culture_rf: 'Культура РФ',
  telegram: 'Telegram',
  major: 'Крупные события',
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

function Events() {
  usePageTitle('События')
  const navigate = useNavigate()
  const [selectedType, setSelectedType] = useState<EventType | null>(null)
  const [selectedSource, setSelectedSource] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [currentMonth, setCurrentMonth] = useState(() => new Date())
  const [selectedDay, setSelectedDay] = useState<Date | null>(null)
  const [selectedEvent, setSelectedEvent] = useState<EventData | null>(null)
  
  const { data: events = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['events'],
    queryFn: api.getEvents,
  })

  const { data: impactData } = useQuery({
    queryKey: ['events-impact'],
    queryFn: api.getEventsImpact,
    staleTime: 10 * 60 * 1000,
  })

  const { data: correctedImpactData } = useQuery({
    queryKey: ['events-impact-corrected'],
    queryFn: () => api.getEventsImpactCorrected(),
    staleTime: 10 * 60 * 1000,
  })

  const impactMap = useMemo(() => {
    const map = new Map<string, number>()
    if (impactData) {
      for (const item of impactData) {
        if (item.impact !== null) {
          map.set(item.event, item.impact)
        }
      }
    }
    return map
  }, [impactData])

  const correctedImpactMap = useMemo(() => {
    const map = new Map<string, number>()
    if (correctedImpactData) {
      for (const item of correctedImpactData) {
        if (item.delta_pct !== null) {
          map.set(`${item.event.slice(0, 50)}|${item.date}`, item.delta_pct)
        }
      }
    }
    return map
  }, [correctedImpactData])

  const sourceStats = useMemo(() => {
    const counts: Record<string, number> = {}
    events.forEach(e => {
      const src = SOURCE_LABELS[e.source_id] || e.source_id.replace('telegram_', 'tg/')
      counts[src] = (counts[src] || 0) + 1
    })
    return Object.entries(counts)
      .map(([source, count]) => ({ source, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8)
  }, [events])

  const availableSources = useMemo(() => {
    const sources = new Set(events.map(e => e.source_id))
    return Array.from(sources).sort()
  }, [events])

  const filteredEvents = useMemo(() => {
    const monthStart = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), 1)
    const monthEnd = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 0)
    const query = searchQuery.toLowerCase().trim()
    
    return events.filter(event => {
      const eventDate = new Date(event.date_start)
      const inMonth = eventDate >= monthStart && eventDate <= monthEnd
      const matchesType = !selectedType || _getEventType(event) === selectedType
      const matchesSource = !selectedSource || event.source_id === selectedSource
      const matchesSearch = !query || event.title.toLowerCase().includes(query)
        || event.location?.toLowerCase().includes(query)
        || event.description?.toLowerCase().includes(query)
      return inMonth && matchesType && matchesSource && matchesSearch
    }).sort((a, b) => new Date(a.date_start).getTime() - new Date(b.date_start).getTime())
  }, [events, currentMonth, selectedType, selectedSource, searchQuery])

  // Группируем события по дате
  const eventsByDate = useMemo(() => {
    const grouped: Record<string, EventData[]> = {}
    filteredEvents.forEach(event => {
      const dateKey = event.date_start.split('T')[0]
      if (!grouped[dateKey]) grouped[dateKey] = []
      grouped[dateKey].push(event)
    })
    return grouped
  }, [filteredEvents])

  // Подсчёт по типам
  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    
    // Считаем для текущего месяца (с учётом фильтра типа)
    const monthStart = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), 1)
    const monthEnd = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 0)
    
    events.filter(event => {
      const eventDate = new Date(event.date_start)
      return eventDate >= monthStart && eventDate <= monthEnd
    }).forEach(event => {
      const type = _getEventType(event)
      counts[type] = (counts[type] || 0) + 1
    })
    
    return counts
  }, [events, currentMonth])

  // Получаем дни месяца для календаря
  const calendarDays = useMemo(() => {
    const year = currentMonth.getFullYear()
    const month = currentMonth.getMonth()
    const firstDay = new Date(year, month, 1)
    const lastDay = new Date(year, month + 1, 0)
    const startPadding = (firstDay.getDay() + 6) % 7
    
    const days: { date: Date; isCurrentMonth: boolean; events: EventData[] }[] = []
    
    for (let i = startPadding - 1; i >= 0; i--) {
      const date = new Date(year, month, -i)
      days.push({ date, isCurrentMonth: false, events: [] })
    }
    
    for (let d = 1; d <= lastDay.getDate(); d++) {
      const date = new Date(year, month, d)
      const dateKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
      days.push({ 
        date, 
        isCurrentMonth: true, 
        events: eventsByDate[dateKey] || [] 
      })
    }
    
    while (days.length < 42) {
      const date = new Date(year, month + 1, days.length - lastDay.getDate() - startPadding + 1)
      days.push({ date, isCurrentMonth: false, events: [] })
    }
    
    return days
  }, [currentMonth, eventsByDate])

  // События выбранного дня
  const selectedDayEvents = useMemo(() => {
    if (!selectedDay) return []
    const dateKey = `${selectedDay.getFullYear()}-${String(selectedDay.getMonth() + 1).padStart(2, '0')}-${String(selectedDay.getDate()).padStart(2, '0')}`
    return eventsByDate[dateKey] || []
  }, [selectedDay, eventsByDate])

  const monthName = currentMonth.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })
  const totalMonthEvents = Object.values(typeCounts).reduce((a, b) => a + b, 0)

  if (isLoading) return <EventsSkeleton />
  if (isError) return <ErrorState title="Ошибка загрузки событий" message="Не удалось загрузить события. Попробуйте повторить." onRetry={() => refetch()} />

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[hsl(var(--primary))] to-[hsl(var(--accent))] flex items-center justify-center">
            <Calendar className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">События региона</h1>
            <p className="text-sm text-[hsl(var(--muted-foreground))]">
              {totalMonthEvents} событий в {monthName}
            </p>
          </div>
          <button
            onClick={() => navigate(`/chat?context=${encodeURIComponent(`Какие события повлияют на заполняемость отелей в ${monthName}?`)}`)}
            className="ml-2 p-2 rounded-lg bg-[hsl(var(--primary)/0.1)] hover:bg-[hsl(var(--primary)/0.2)] transition-colors"
            title="Спросить AI"
          >
            <Sparkles size={16} className="text-[hsl(var(--primary))]" />
          </button>
        </div>
        
        {/* Month navigation */}
        <div className="flex items-center gap-2 bg-[hsl(var(--secondary))] rounded-xl p-1">
          <Button 
            variant="ghost" 
            size="sm"
            onClick={() => setCurrentMonth(m => new Date(m.getFullYear(), m.getMonth() - 1))}
          >
            <ChevronLeft size={16} />
          </Button>
          <span className="font-medium min-w-[160px] text-center capitalize">{monthName}</span>
          <Button 
            variant="ghost" 
            size="sm"
            onClick={() => setCurrentMonth(m => new Date(m.getFullYear(), m.getMonth() + 1))}
          >
            <ChevronRight size={16} />
          </Button>
        </div>
      </div>

      {/* Search & Source Filter */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[hsl(var(--muted-foreground))]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Поиск по событиям..."
            className="w-full pl-9 pr-3 py-2 rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] text-sm focus:outline-none focus:ring-2 focus:ring-[hsl(var(--primary))] placeholder:text-[hsl(var(--muted-foreground))]"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
            >
              <X size={14} />
            </button>
          )}
        </div>
        {availableSources.length > 1 && (
          <Dropdown
            value={selectedSource ?? ''}
            onChange={(v) => setSelectedSource(v || null)}
            options={[
              { value: '', label: 'Все источники' },
              ...availableSources.map(src => ({ value: src, label: SOURCE_LABELS[src] || src })),
            ]}
            icon={<Database size={14} />}
            compact
            className="w-52"
          />
        )}
      </div>

      {/* Legend - цветовая легенда */}
      <Card variant="glass" padding="sm">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-medium text-[hsl(var(--muted-foreground))] mr-2">
            <Info size={12} className="inline mr-1" />
            Категории:
          </span>
          {Object.entries(EVENT_TYPES).map(([type, { icon: Icon, label, color }]) => {
            const count = typeCounts[type] || 0
            if (count === 0) return null
            return (
              <button
                key={type}
                onClick={() => setSelectedType(selectedType === type ? null : type as EventType)}
                className={`
                  flex items-center gap-1.5 px-2 py-1 rounded-md text-xs transition-all
                  ${selectedType === type 
                    ? 'ring-2 ring-offset-1 ring-offset-[hsl(var(--background))]' 
                    : 'opacity-80 hover:opacity-100'
                  }
                `}
                style={{ 
                  backgroundColor: `${color}20`, 
                  color,
                  outlineColor: color
                }}
              >
                <Icon size={12} />
                <span>{label}</span>
                <span className="font-bold">({count})</span>
              </button>
            )
          })}
          {selectedType && (
            <button
              onClick={() => setSelectedType(null)}
              className="flex items-center gap-1 px-2 py-1 rounded-md text-xs bg-[hsl(var(--destructive)/0.1)] text-[hsl(var(--destructive))] hover:bg-[hsl(var(--destructive)/0.2)] transition-colors"
            >
              <X size={12} />
              Сбросить
            </button>
          )}
        </div>
      </Card>

      {/* Events by Source */}
      {sourceStats.length > 0 && (
        <Card variant="glass">
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-[hsl(var(--primary))]" />
              <CardTitle className="text-base">Источники событий</CardTitle>
            </div>
            <p className="text-sm text-[hsl(var(--muted-foreground))]">
              Распределение {events.length} событий по источникам данных
            </p>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={sourceStats} layout="vertical">
                <XAxis type="number" axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
                <YAxis dataKey="source" type="category" width={120} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                <ReTooltip
                  formatter={(v: number) => [`${v} событий`, 'Количество']}
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                    color: 'hsl(var(--foreground))',
                  }}
                />
                <Bar dataKey="count" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Calendar */}
        <div className="xl:col-span-2">
          <Card variant="glass">
            <CardContent className="p-4">
              {/* Weekday headers */}
              <div className="grid grid-cols-7 gap-1 mb-2">
                {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((day, i) => (
                  <div 
                    key={day} 
                    className={`
                      text-center text-xs font-medium py-2 rounded-lg
                      ${i >= 5 ? 'text-[hsl(var(--destructive))]' : 'text-[hsl(var(--muted-foreground))]'}
                    `}
                  >
                    {day}
                  </div>
                ))}
              </div>
              
              {/* Calendar grid */}
              <div className="grid grid-cols-7 gap-1">
                {calendarDays.map((day, index) => (
                  <CalendarDay
                    key={index}
                    day={day}
                    isSelected={selectedDay?.toDateString() === day.date.toDateString()}
                    onSelect={() => day.isCurrentMonth && day.events.length > 0 && setSelectedDay(day.date)}
                  />
                ))}
              </div>
              
              {/* Hint */}
              <p className="text-xs text-[hsl(var(--muted-foreground))] text-center mt-4">
                Нажмите на день с событиями, чтобы увидеть подробности
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Day Events Panel */}
        <div className="xl:col-span-1">
          <Card variant="glass" className="sticky top-4">
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <Calendar size={16} />
                {selectedDay 
                  ? selectedDay.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', weekday: 'long' })
                  : 'Выберите день'
                }
              </CardTitle>
            </CardHeader>
            <CardContent className="max-h-[500px] overflow-y-auto">
              {selectedDay ? (
                selectedDayEvents.length > 0 ? (
                  <div className="space-y-3">
                    {selectedDayEvents.map(event => (
                      <EventMiniCard 
                        key={event.event_id} 
                        event={event} 
                        onClick={() => setSelectedEvent(event)}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-[hsl(var(--muted-foreground))]">
                    <Calendar className="w-10 h-10 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">Нет событий в этот день</p>
                  </div>
                )
              ) : (
                <div className="text-center py-8 text-[hsl(var(--muted-foreground))]">
                  <Info className="w-10 h-10 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">Выберите день в календаре</p>
                  <p className="text-xs mt-1">чтобы увидеть события</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* All Events List */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Все события месяца</h2>
          <Badge variant="outline">{filteredEvents.length} событий</Badge>
        </div>
        
        {filteredEvents.length === 0 ? (
          <Card variant="glass">
            <CardContent className="text-center py-12">
              <Calendar className="w-16 h-16 mx-auto mb-4 text-[hsl(var(--muted-foreground))] opacity-50" />
              <p className="text-lg font-medium">Нет событий</p>
              <p className="text-sm text-[hsl(var(--muted-foreground))] mt-1">
                {selectedType ? 'Попробуйте сбросить фильтр категории' : 'В выбранном месяце событий не найдено'}
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredEvents.map(event => (
              <EventCard
                key={event.event_id}
                event={event}
                onClick={() => setSelectedEvent(event)}
                impact={impactMap.get(event.title.slice(0, 50))}
                correctedDeltaPct={correctedImpactMap.get(`${event.title.slice(0, 50)}|${event.date_start}`)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Event Detail Modal */}
      {selectedEvent && (
        <EventModal 
          event={selectedEvent} 
          onClose={() => setSelectedEvent(null)} 
        />
      )}
    </div>
  )
}

// ============================================================================
// CALENDAR DAY COMPONENT
// ============================================================================

function CalendarDay({ 
  day, 
  isSelected, 
  onSelect,
}: { 
  day: { date: Date; isCurrentMonth: boolean; events: EventData[] }
  isSelected: boolean
  onSelect: () => void
}) {
  const isToday = day.date.toDateString() === new Date().toDateString()
  const hasEvents = day.events.length > 0
  const isWeekend = day.date.getDay() === 0 || day.date.getDay() === 6
  
  // Группируем события по типу для отображения точек
  const eventTypes = useMemo(() => {
    const types = new Set<EventType>()
    day.events.forEach(e => types.add(_getEventType(e) as EventType))
    return Array.from(types).slice(0, 4) // Максимум 4 точки
  }, [day.events])

  return (
    <button
      onClick={onSelect}
      disabled={!day.isCurrentMonth || !hasEvents}
      className={`
        relative min-h-[72px] p-2 rounded-xl border transition-all text-left
        ${day.isCurrentMonth 
          ? 'bg-[hsl(var(--card))]' 
          : 'bg-[hsl(var(--muted)/0.2)] opacity-40'
        }
        ${isSelected 
          ? 'border-[hsl(var(--primary))] ring-2 ring-[hsl(var(--primary)/0.3)]' 
          : 'border-[hsl(var(--border))]'
        }
        ${isToday ? 'ring-2 ring-[hsl(var(--accent))]' : ''}
        ${hasEvents && day.isCurrentMonth 
          ? 'hover:border-[hsl(var(--primary))] hover:shadow-lg cursor-pointer' 
          : 'cursor-default'
        }
      `}
    >
      {/* Date number */}
      <div className={`
        text-sm font-semibold
        ${isToday ? 'text-[hsl(var(--primary))]' : ''}
        ${isWeekend && day.isCurrentMonth ? 'text-[hsl(var(--destructive)/0.8)]' : ''}
      `}>
        {day.date.getDate()}
        {isToday && (
          <span className="ml-1 text-xs font-normal text-[hsl(var(--primary))]">
            сегодня
          </span>
        )}
      </div>
      
      {/* Event indicators */}
      {hasEvents && day.isCurrentMonth && (
        <div className="mt-1 space-y-1">
          {/* Color dots row */}
          <div className="flex gap-1">
            {eventTypes.map((type, i) => {
              const { color } = EVENT_TYPES[type]
              return (
                <div 
                  key={i}
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: color }}
                  title={EVENT_TYPES[type].label}
                />
              )
            })}
            {day.events.length > 4 && (
              <span className="text-xs text-[hsl(var(--muted-foreground))]">
                +{day.events.length - 4}
              </span>
            )}
          </div>
          
          {/* Event count badge */}
          <div className="text-xs text-[hsl(var(--muted-foreground))]">
            {day.events.length} {_pluralize(day.events.length, 'событие', 'события', 'событий')}
          </div>
        </div>
      )}
    </button>
  )
}

// ============================================================================
// EVENT MINI CARD (for sidebar)
// ============================================================================

function EventMiniCard({ 
  event, 
  onClick 
}: { 
  event: EventData
  onClick: () => void 
}) {
  const type = _getEventType(event) as EventType
  const { icon: Icon, label, color, bgColor } = EVENT_TYPES[type]
  
  return (
    <button
      onClick={onClick}
      className="w-full text-left p-3 rounded-xl border border-[hsl(var(--border))] hover:border-[hsl(var(--primary)/0.5)] hover:shadow-md transition-all bg-[hsl(var(--card))]"
    >
      <div className="flex items-start gap-3">
        <div 
          className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ backgroundColor: bgColor }}
        >
          <Icon size={14} style={{ color }} />
        </div>
        <div className="flex-1 min-w-0">
          <span 
            className="text-xs font-medium px-1.5 py-0.5 rounded"
            style={{ backgroundColor: bgColor, color }}
          >
            {label}
          </span>
          <h4 className="font-medium text-sm mt-1 line-clamp-2">{event.title}</h4>
          {event.location && (
            <p className="text-xs text-[hsl(var(--muted-foreground))] flex items-center gap-1 mt-1">
              <MapPin size={10} />
              <span className="truncate">{event.location}</span>
            </p>
          )}
        </div>
      </div>
    </button>
  )
}

// ============================================================================
// EVENT CARD (for grid)
// ============================================================================

function EventCard({
  event,
  onClick,
  impact,
  correctedDeltaPct,
}: {
  event: EventData
  onClick: () => void
  impact?: number
  correctedDeltaPct?: number
}) {
  const type = _getEventType(event) as EventType
  const { icon: Icon, label, color, bgColor } = EVENT_TYPES[type]
  const date = new Date(event.date_start)
  
  return (
    <button
      onClick={onClick}
      className="w-full text-left rounded-2xl border border-[hsl(var(--border))] hover:border-[hsl(var(--primary))] hover:shadow-xl transition-all bg-[hsl(var(--card))] overflow-hidden group"
    >
      {/* Color bar */}
      <div className="h-1.5 group-hover:h-2 transition-all" style={{ backgroundColor: color }} />
      
      <div className="p-4">
        <div className="flex items-start gap-3">
          <div 
            className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ backgroundColor: bgColor }}
          >
            <Icon size={20} style={{ color }} />
          </div>
          
          <div className="flex-1 min-w-0">
            <span 
              className="text-xs font-medium px-2 py-0.5 rounded-full"
              style={{ backgroundColor: bgColor, color }}
            >
              {label}
            </span>
            
            <h3 className="font-semibold text-sm mt-2 line-clamp-2 group-hover:text-[hsl(var(--primary))] transition-colors">
              {event.title}
            </h3>
            
            <div className="flex items-center gap-3 mt-2 text-xs text-[hsl(var(--muted-foreground))]">
              <span className="flex items-center gap-1">
                <Clock size={12} />
                {date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
              </span>
              {event.location && (
                <span className="flex items-center gap-1 truncate">
                  <MapPin size={12} />
                  <span className="truncate max-w-[100px]">{event.location}</span>
                </span>
              )}
            </div>
          </div>
        </div>
        
        {/* Impact + Hover hint */}
        <div className="mt-3 pt-3 border-t border-[hsl(var(--border))] flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 flex-wrap">
            {impact !== undefined && (
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                impact > 5 ? 'bg-[hsl(var(--destructive)/0.1)] text-[hsl(var(--destructive))]'
                  : impact > 0 ? 'bg-[hsl(var(--warning)/0.1)] text-[hsl(var(--warning))]'
                    : 'bg-[hsl(var(--success)/0.1)] text-[hsl(var(--success))]'
              }`}>
                {impact > 0 ? '+' : ''}{impact.toFixed(0)}% к загрузке (оценка)
              </span>
            )}
            {correctedDeltaPct !== undefined && (
              <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                correctedDeltaPct >= 0
                  ? 'bg-[hsl(var(--success)/0.12)] text-[hsl(var(--success))]'
                  : 'bg-[hsl(var(--destructive)/0.1)] text-[hsl(var(--destructive))]'
              }`}>
                {correctedDeltaPct >= 0 ? '↑' : '↓'} {Math.abs(correctedDeltaPct).toFixed(1)}%
              </span>
            )}
            {impact === undefined && correctedDeltaPct === undefined && <span />}
          </div>
          <span className="text-xs text-[hsl(var(--primary))] opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
            <Info size={12} />
            Подробнее
          </span>
        </div>
      </div>
    </button>
  )
}

// ============================================================================
// EVENT DETAIL MODAL
// ============================================================================

function EventModal({ 
  event, 
  onClose,
}: { 
  event: EventData
  onClose: () => void 
}) {
  const navigate = useNavigate()
  const type = _getEventType(event) as EventType
  const { icon: Icon, label, color } = EVENT_TYPES[type]
  const date = new Date(event.date_start)

  useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handleKey)
    return () => {
      document.body.style.overflow = prev
      window.removeEventListener('keydown', handleKey)
    }
  }, [onClose])

  return createPortal(
    <div 
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={event.title}
    >
      <div
        className="bg-[hsl(var(--card))] rounded-2xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        {/* Image (if present) */}
        {event.image_url && (
          <div className="w-full h-48 overflow-hidden rounded-t-2xl">
            <img
              src={event.image_url}
              alt={event.title}
              className="w-full h-full object-cover"
              onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
            />
          </div>
        )}

        {/* Header */}
        <div
          className={`p-6 text-white relative ${!event.image_url ? 'rounded-t-2xl' : ''}`}
          style={{ backgroundColor: color }}
        >
          <button
            onClick={onClose}
            className="absolute top-4 right-4 w-8 h-8 rounded-full bg-white/20 hover:bg-white/30 flex items-center justify-center transition-colors"
          >
            <X size={18} />
          </button>

          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-xl bg-white/20 flex items-center justify-center">
              <Icon size={24} />
            </div>
            <span className="px-3 py-1 bg-white/20 rounded-full text-sm font-medium">
              {label}
            </span>
            {event.age_restriction && (
              <span className="px-2 py-0.5 bg-white/30 rounded text-xs font-bold">
                {event.age_restriction}
              </span>
            )}
          </div>

          <h2 className="text-xl font-bold">{event.title}</h2>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {/* Date & Time */}
          <div className="flex items-center gap-3 p-3 rounded-xl bg-[hsl(var(--secondary))]">
            <Calendar size={20} className="text-[hsl(var(--primary))]" />
            <div>
              <p className="font-medium">
                {date.toLocaleDateString('ru-RU', {
                  weekday: 'long',
                  day: 'numeric',
                  month: 'long',
                  year: 'numeric',
                })}
                {event.time_start && (
                  <span className="ml-2 text-sm font-normal text-[hsl(var(--muted-foreground))]">
                    в {event.time_start.slice(0, 5)}
                  </span>
                )}
              </p>
              {event.date_end && (
                <p className="text-sm text-[hsl(var(--muted-foreground))]">
                  до {new Date(event.date_end).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })}
                </p>
              )}
            </div>
          </div>

          {/* Location + Address */}
          {(event.location || event.address) && (
            <div className="flex items-start gap-3 p-3 rounded-xl bg-[hsl(var(--secondary))]">
              <MapPin size={20} className="text-[hsl(var(--primary))] flex-shrink-0 mt-0.5" />
              <div>
                {event.location && <p className="font-medium">{event.location}</p>}
                {event.address && (
                  <p className="text-sm text-[hsl(var(--muted-foreground))] mt-0.5">{event.address}</p>
                )}
                {!event.address && <p className="text-sm text-[hsl(var(--muted-foreground))]">Место проведения</p>}
              </div>
            </div>
          )}

          {/* Price */}
          {(event.price_min !== null || event.price_max !== null) && (
            <div className="flex items-center gap-3 p-3 rounded-xl bg-[hsl(var(--secondary))]">
              <Ticket size={20} className="text-[hsl(var(--primary))]" />
              <div>
                <p className="font-medium">
                  {event.price_min !== null && event.price_max !== null && event.price_min !== event.price_max
                    ? `${event.price_min.toLocaleString()} – ${event.price_max.toLocaleString()} ₽`
                    : event.price_min !== null && event.price_min === 0
                      ? 'Бесплатно'
                      : event.price_min !== null
                        ? `от ${event.price_min.toLocaleString()} ₽`
                        : event.price_max !== null
                          ? `до ${event.price_max.toLocaleString()} ₽`
                          : ''}
                </p>
                <p className="text-sm text-[hsl(var(--muted-foreground))]">Стоимость билетов</p>
              </div>
            </div>
          )}

          {/* Description */}
          {event.description && (
            <div className="p-3 rounded-xl bg-[hsl(var(--secondary))]">
              <p className="text-sm leading-relaxed">{event.description}</p>
            </div>
          )}

          {/* Source */}
          <p className="text-xs text-[hsl(var(--muted-foreground))] flex items-center gap-1">
            <Info size={12} />
            Источник: {SOURCE_LABELS[event.source_id] || event.source_id}
          </p>

          {/* Actions */}
          <div className="flex flex-wrap gap-3 pt-2">
            {event.url && (
              <a
                href={event.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl font-medium text-white transition-colors"
                style={{ backgroundColor: color }}
              >
                <Ticket size={18} />
                Перейти на сайт
                <ExternalLink size={14} />
              </a>
            )}
            <button
              onClick={() => {
                onClose()
                navigate(`/analytics?district=${encodeURIComponent(_districtFromLocation(event.location))}`)
              }}
              className="flex items-center justify-center gap-2 px-4 py-3 rounded-xl border border-[hsl(var(--primary)/0.3)] bg-[hsl(var(--primary)/0.05)] hover:bg-[hsl(var(--primary)/0.1)] text-[hsl(var(--primary))] transition-colors text-sm"
            >
              <TrendingUp size={16} />
              Влияние на заполняемость
            </button>
            <button
              onClick={onClose}
              className="px-4 py-3 rounded-xl border border-[hsl(var(--border))] hover:bg-[hsl(var(--secondary))] transition-colors"
            >
              Закрыть
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  )
}

// ============================================================================
// SKELETON
// ============================================================================

function EventsSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between">
        <div className="h-10 w-48 skeleton rounded-lg" />
        <div className="h-10 w-48 skeleton rounded-lg" />
      </div>
      <div className="h-12 skeleton rounded-xl" />
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 h-[500px] skeleton rounded-2xl" />
        <div className="h-[300px] skeleton rounded-2xl" />
      </div>
    </div>
  )
}

// ============================================================================
// HELPERS
// ============================================================================

const _API_TYPE_MAP: Record<string, EventType> = {
  concert: 'concert', theater: 'theater', exhibition: 'exhibition',
  festival: 'festival', sport: 'sport', business: 'business',
  cinema: 'cinema', kids: 'kids', holiday: 'holiday',
  culture: 'exhibition', school_holiday: 'holiday',
}

function _getEventType(event: { title: string; source_id?: string; event_type?: string | null }): EventType {
  if (event.event_type && event.event_type !== 'event') {
    const mapped = _API_TYPE_MAP[event.event_type]
    if (mapped) return mapped
  }

  const title = event.title.toLowerCase()
  if (title.includes('концерт') || title.includes('выступлен')) return 'concert'
  if (title.includes('театр') || title.includes('спектакль')) return 'theater'
  if (title.includes('выставк') || title.includes('экспозиц') || title.includes('галерея')) return 'exhibition'
  if (title.includes('фестиваль') || title.includes('fest')) return 'festival'
  if (title.includes('матч') || title.includes('соревнован') || title.includes('турнир')) return 'sport'
  if (title.includes('конференц') || title.includes('форум') || title.includes('семинар')) return 'business'
  if (title.includes('фильм') || title.includes('кино')) return 'cinema'
  if (title.includes('детск') || title.includes('дет')) return 'kids'
  if (title.includes('праздник') || title.includes('день города')) return 'holiday'

  return 'other'
}

const _CITY_TO_DISTRICT: Record<string, string> = {
  'иркутск': 'Иркутский', 'листвянк': 'Иркутский', 'хужир': 'Ольхонский',
  'ольхон': 'Ольхонский', 'байкальск': 'Слюдянский', 'слюдянк': 'Слюдянский',
  'ангарск': 'Ангарский', 'братск': 'Братский', 'шелехов': 'Шелеховский',
}

function _districtFromLocation(location?: string | null): string {
  if (!location) return 'Иркутский'
  const loc = location.toLowerCase()
  for (const [city, district] of Object.entries(_CITY_TO_DISTRICT)) {
    if (loc.includes(city)) return district
  }
  return 'Иркутский'
}

function _pluralize(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10
  const mod100 = n % 100
  
  if (mod100 >= 11 && mod100 <= 19) return many
  if (mod10 === 1) return one
  if (mod10 >= 2 && mod10 <= 4) return few
  return many
}

export default Events
