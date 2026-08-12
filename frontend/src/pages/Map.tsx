import { useState, useMemo, useEffect, useRef } from 'react'
import { useQuery, useQueries } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Map as MapIcon, Sparkles, TrendingUp, Building2, BedDouble, Activity, X, Calendar, Filter, ChevronDown, Check } from 'lucide-react'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend, BarChart, LineChart, Cell,
} from 'recharts'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui'
import { MethodologyTooltip } from '../components/MethodologyTooltip'
import { YandexMap, occupancyColor, type HotelPin } from '../components/YandexMap'
import { ErrorState } from '../components/ErrorState'
import { api } from '../api/client'
import { usePageTitle } from '../hooks/usePageTitle'
import { RECHARTS_TOOLTIP_PROPS, BAR_CURSOR_TRANSPARENT } from '../utils/chartTheme'

type Season = 'all' | 'spring' | 'summer' | 'autumn' | 'winter'

const SEASON_MONTHS: Record<Exclude<Season, 'all'>, number[]> = {
  spring: [4, 5],
  summer: [6, 7, 8, 9],
  autumn: [10, 11],
  winter: [12, 1, 2, 3],
}

const SEASON_LABELS: Record<Season, string> = {
  all: 'Весь год',
  spring: 'Весна',
  summer: 'Лето',
  autumn: 'Осень',
  winter: 'Зима',
}

const PERIOD_OPTIONS: { value: number; label: string }[] = [
  { value: 7, label: '7 дн' },
  { value: 30, label: '30 дн' },
  { value: 90, label: '90 дн' },
  { value: 180, label: '180 дн' },
  { value: 365, label: '365 дн' },
]

// Данные собираются по времени региона: календарный день считается в Asia/Irkutsk,
// иначе с 00:00 до 08:00 по Иркутску UTC-дата ещё вчерашняя и свежий снимок недоступен.
const REGION_TIME_ZONE = 'Asia/Irkutsk'

// Пробел сбора данных: парсеры были отключены, дозабор невозможен.
const DATA_GAP_FROM = '2025-06-24'
const DATA_GAP_TO = '2025-10-25'
const DATA_GAP_LABEL = '24.06.2025 – 25.10.2025 (123 дня)'

function isoToday(): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: REGION_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
}

function overlapsDataGap(from: string, to: string): boolean {
  return from <= DATA_GAP_TO && to >= DATA_GAP_FROM
}

function isValidIsoDate(s: string): boolean {
  if (!s || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return false
  const d = new Date(s + 'T00:00:00Z')
  return !isNaN(d.getTime())
}

function safeIso(s: string): string {
  return isValidIsoDate(s) ? s : isoToday()
}

function shiftDate(iso: string, deltaDays: number): string {
  const d = new Date(safeIso(iso) + 'T00:00:00Z')
  d.setUTCDate(d.getUTCDate() + deltaDays)
  return d.toISOString().slice(0, 10)
}

function seasonRangeForDate(focusDateIso: string, season: Season): { from: string; to: string } | null {
  if (season === 'all') return null
  const focus = new Date(safeIso(focusDateIso) + 'T00:00:00Z')
  const y = focus.getUTCFullYear()
  const m = focus.getUTCMonth() + 1
  if (season === 'winter') {
    const winterStartYear = m < 4 ? y - 1 : y
    return { from: `${winterStartYear}-12-01`, to: `${winterStartYear + 1}-03-31` }
  }
  const months = SEASON_MONTHS[season]
  const min = Math.min(...months)
  const max = Math.max(...months)
  const seasonYear = m < min ? y - 1 : y
  const fromMonth = String(min).padStart(2, '0')
  const toMonth = String(max).padStart(2, '0')
  const lastDay = new Date(Date.UTC(seasonYear, max, 0)).getUTCDate()
  return {
    from: `${seasonYear}-${fromMonth}-01`,
    to: `${seasonYear}-${toMonth}-${String(lastDay).padStart(2, '0')}`,
  }
}

function periodRangeFromDate(focusDateIso: string, periodDays: number): { from: string; to: string } {
  const safe = safeIso(focusDateIso)
  return { from: shiftDate(safe, -(periodDays - 1)), to: safe }
}

function fmtDateRu(iso: string): string {
  const [y, m, d] = iso.split('-')
  return `${d}.${m}.${y.slice(2)}`
}

type DistrictOption = { name: string; hotels: number }

type DistrictMultiSelectProps = {
  options: DistrictOption[]
  selected: Set<string>
  onToggle: (name: string) => void
  onClear: () => void
}

function DistrictMultiSelect({ options, selected, onToggle, onClear }: DistrictMultiSelectProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onEsc)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onEsc)
    }
  }, [])

  const summary = selected.size === 0
    ? 'Все районы'
    : selected.size === 1
      ? Array.from(selected)[0].replace(' район', '')
      : `Выбрано: ${selected.size}`

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-sm rounded-md border border-[hsl(var(--border))]
                   bg-[hsl(var(--card))] hover:border-[hsl(var(--primary)/0.5)] transition-colors text-left"
      >
        <span className="truncate">{summary}</span>
        <ChevronDown size={14} className={`flex-shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div
          className="absolute top-full mt-1 left-0 right-0 z-50 max-h-[280px] overflow-y-auto
                     rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--card))] shadow-lg"
        >
          {selected.size > 0 && (
            <button
              onClick={() => { onClear(); setOpen(false) }}
              className="w-full px-3 py-1.5 text-xs text-left text-[hsl(var(--muted-foreground))]
                         hover:bg-[hsl(var(--secondary))] border-b border-[hsl(var(--border))] inline-flex items-center gap-1.5"
            >
              <X size={11} /> Сбросить выбор
            </button>
          )}
          {options.map(opt => {
            const checked = selected.has(opt.name)
            return (
              <button
                type="button"
                key={opt.name}
                onClick={() => onToggle(opt.name)}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-sm cursor-pointer hover:bg-[hsl(var(--secondary))] select-none text-left"
              >
                <span
                  className={`flex items-center justify-center w-4 h-4 rounded border ${
                    checked
                      ? 'bg-[hsl(var(--primary))] border-[hsl(var(--primary))]'
                      : 'border-[hsl(var(--border))] bg-[hsl(var(--card))]'
                  }`}
                >
                  {checked && <Check size={10} className="text-white" strokeWidth={3} />}
                </span>
                <span className="flex-1 truncate">{opt.name.replace(' район', '')}</span>
                <span className="text-xs text-[hsl(var(--muted-foreground))] tabular-nums">{opt.hotels}</span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

function MapPage() {
  usePageTitle('Региональная карта')
  const navigate = useNavigate()

  const [selectedDistricts, setSelectedDistricts] = useState<Set<string>>(new Set())
  const [focusDate, setFocusDate] = useState<string>(isoToday())
  const [season, setSeason] = useState<Season>('all')
  const [periodDays, setPeriodDays] = useState<number>(30)
  const [chartKey, setChartKey] = useState(0)

  // Recharts ResponsiveContainer не всегда корректно пересчитывает размеры
  // после выхода Yandex Maps из fullscreen. Force-remount через key —
  // ResponsiveContainer заново измеряет parent через свой ResizeObserver,
  // без stale-расчётов. rAF + 200ms ждут окончание browser reflow и возврат
  // DOM от Yandex Maps.
  useEffect(() => {
    function onFullscreenChange() {
      requestAnimationFrame(() => {
        setTimeout(() => setChartKey(k => k + 1), 200)
      })
    }
    document.addEventListener('fullscreenchange', onFullscreenChange)
    return () => document.removeEventListener('fullscreenchange', onFullscreenChange)
  }, [])

  // periodRange и seasonRange привязаны к focusDate (anchor): дата из фильтра
  // «Карта и KPI» одновременно смещает все верхние графики и KPI.
  const seasonRange = useMemo(() => seasonRangeForDate(focusDate, season), [focusDate, season])
  const periodRange = useMemo(() => periodRangeFromDate(focusDate, periodDays), [focusDate, periodDays])

  const districtsQ = useQuery({
    queryKey: ['districts', periodRange.from, periodRange.to],
    queryFn: () => api.getDistricts(periodRange.from, periodRange.to),
  })
  const hotelsMapQ = useQuery({
    queryKey: ['hotelsMap', focusDate],
    queryFn: () => api.getHotelsMap(undefined, focusDate),
  })
  const districts = useMemo(() => districtsQ.data ?? [], [districtsQ.data])

  // Районы для графиков: все выбранные. При пустом фильтре — крупнейшие по
  // hotelsCount. Полный aggregate всех районов даёт 20+ параллельных запросов
  // (occupancy+price на каждый), что упирается в backend rate limit 60 RPM на
  // /api/analytics/* и роняет страницу с 429 Too Many Requests.
  const queryDistricts = useMemo<string[]>(() => {
    const arr = Array.from(selectedDistricts).sort()
    if (arr.length > 0) return arr
    const top = [...districts]
      .filter(d => (d.hotelsCount ?? 0) > 0)
      .sort((a, b) => (b.hotelsCount ?? 0) - (a.hotelsCount ?? 0))
      .slice(0, 3)
      .map(d => d.district)
    return top.length > 0 ? top : ['Иркутский']
  }, [selectedDistricts, districts])
  // Стабильный ключ для подзаголовков графиков
  const queryDistrictsLabel = useMemo(() => {
    const names = queryDistricts.map(d => d.replace(' район', ''))
    if (selectedDistricts.size === 0) {
      return names.length === 1 ? names[0] : `Топ-${names.length}: ${names.join(', ')}`
    }
    if (names.length <= 3) return names.join(', ')
    return `${names.length} районов`
  }, [selectedDistricts, queryDistricts])
  // Параллельные запросы occupancy и price по каждому выбранному району
  const occQueries = useQueries({
    queries: queryDistricts.map(d => ({
      queryKey: ['occ-ts', d, 365],
      queryFn: () => api.getOccupancyTimeseries(d, 365),
    })),
  })
  const priceQueries = useQueries({
    queries: queryDistricts.map(d => ({
      queryKey: ['price-history', d, 365],
      queryFn: () => api.getPriceHistory(365, d),
    })),
  })

  const hotelsMap = hotelsMapQ.data

  // Агрегация по дате: occupancy/price = AVG, rooms = SUM по выбранным районам
  const merged = useMemo(() => {
    type Bucket = {
      date: string
      occSum: number; occN: number
      priceSum: number; priceN: number
      rooms: number; roomsN: number
    }
    const bucket = new globalThis.Map<string, Bucket>()
    const init = (date: string): Bucket => {
      let b = bucket.get(date)
      if (!b) {
        b = { date, occSum: 0, occN: 0, priceSum: 0, priceN: 0, rooms: 0, roomsN: 0 }
        bucket.set(date, b)
      }
      return b
    }
    for (const q of occQueries) {
      for (const p of q.data?.points ?? []) {
        const b = init(p.date)
        if (p.occupancy != null) { b.occSum += p.occupancy; b.occN += 1 }
        if (p.total_rooms != null) { b.rooms += p.total_rooms; b.roomsN += 1 }
      }
    }
    for (const q of priceQueries) {
      for (const p of q.data?.prices ?? []) {
        const b = init(p.date)
        if (p.avg_price != null && p.avg_price > 0) { b.priceSum += p.avg_price; b.priceN += 1 }
      }
    }
    return Array.from(bucket.values())
      .map(b => ({
        date: b.date,
        occupancy: b.occN ? +(b.occSum / b.occN).toFixed(2) : undefined,
        price: b.priceN ? Math.round(b.priceSum / b.priceN) : undefined,
        total_rooms: b.roomsN ? b.rooms : null,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [occQueries, priceQueries])

  const seasonData = useMemo(() => {
    if (!seasonRange) return merged
    return merged.filter(d => d.date >= seasonRange.from && d.date <= seasonRange.to)
  }, [merged, seasonRange])

  const periodData = useMemo(() => {
    return merged.filter(d => d.date >= periodRange.from && d.date <= periodRange.to)
  }, [merged, periodRange])

  const allHotelPins = useMemo<HotelPin[]>(
    () => (hotelsMap?.hotels ?? []).map(h => ({
      id: h.id, name: h.name, lat: h.lat, lon: h.lon,
      city: h.city, district: h.district,
      rooms_num: h.rooms_num, free_rooms: h.free_rooms,
      max_capacity: h.max_capacity, occupancy: h.occupancy,
      district_occupancy: h.district_occupancy,
      min_price: h.min_price, rating: h.rating,
    })),
    [hotelsMap],
  )

  const filteredPins = useMemo(() => {
    if (selectedDistricts.size === 0) return allHotelPins
    return allHotelPins.filter(h => h.district && selectedDistricts.has(h.district))
  }, [allHotelPins, selectedDistricts])

  // Загрузка считается из номерного фонда (room-nights), а не как среднее по
  // объектам: иначе хостел на 5 номеров весит столько же, сколько отель на 150.
  const filteredKpi = useMemo(() => {
    const total_hotels = filteredPins.length
    let total_rooms = 0, free_rooms = 0
    for (const h of filteredPins) {
      if (h.rooms_num != null) total_rooms += h.rooms_num
      if (h.free_rooms != null) free_rooms += h.free_rooms
    }
    return {
      total_hotels, total_rooms, free_rooms,
      occupancy: total_rooms > 0 ? Math.round((100 * (total_rooms - free_rooms)) / total_rooms) : null,
    }
  }, [filteredPins])

  // Районы, доступные в фильтре: /api/analytics/districts не отдаёт районы
  // с выборкой меньше 4 объектов, поэтому список короче набора пинов на карте.
  const districtOptions = useMemo<DistrictOption[]>(
    () => districts
      .filter(d => (d.hotelsCount ?? 0) > 0)
      .map(d => ({ name: d.district, hotels: d.hotelsCount ?? 0 })),
    [districts],
  )

  const pinsOutsideFilter = useMemo(() => {
    const known = new Set(districtOptions.map(o => o.name))
    return allHotelPins.filter(h => !h.district || !known.has(h.district)).length
  }, [allHotelPins, districtOptions])

  // occupancy === 0 при totalRooms === 0 — это fallback-ветка backend'а «статистики
  // нет, отдаём хотя бы количество объектов», а не измеренный ноль загрузки.
  const districtsBar = useMemo(() => {
    return [...districts]
      .filter(d => (d.hotelsCount ?? 0) > 0 && d.occupancy != null && (d.totalRooms ?? 0) > 0)
      .sort((a, b) => (b.occupancy ?? 0) - (a.occupancy ?? 0))
      .map(d => ({
        district: d.district.replace(' район', ''),
        fullName: d.district,
        occupancy: Math.round(d.occupancy ?? 0),
        hotels: d.hotelsCount ?? 0,
      }))
  }, [districts])

  if (districtsQ.isLoading && !districts.length) {
    return (
      <div className="space-y-3">
        <div className="h-10 w-64 skeleton rounded-lg" />
        <div className="grid grid-cols-4 gap-3"><div className="h-20 skeleton rounded-xl" /><div className="h-20 skeleton rounded-xl" /><div className="h-20 skeleton rounded-xl" /><div className="h-20 skeleton rounded-xl" /></div>
        <div className="grid grid-cols-[1fr_360px] gap-3"><div className="h-[360px] skeleton rounded-xl" /><div className="h-[360px] skeleton rounded-xl" /></div>
      </div>
    )
  }

  if (districtsQ.isError) {
    return <ErrorState title="Ошибка загрузки аналитики" message="Не удалось загрузить данные о районах." onRetry={() => districtsQ.refetch()} />
  }

  const toggleDistrict = (name: string) => {
    setSelectedDistricts(prev => { const next = new Set(prev); if (next.has(name)) next.delete(name); else next.add(name); return next })
  }
  const clearDistricts = () => setSelectedDistricts(new Set())

  type TickPayload = { value?: number; name?: string; dataKey?: string; color?: string }
  function ChartTooltipContent(props: { active?: boolean; label?: string | number; payload?: TickPayload[] }) {
    const { active, label, payload } = props
    if (!active || !payload?.length) return null
    return (
      <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] px-3 py-2 text-xs shadow-lg">
        <p className="font-semibold mb-1">{typeof label === 'string' ? fmtDateRu(label) : label}</p>
        {payload.map((p, i) => {
          if (p.value == null) return null
          let formatted: string
          if (p.dataKey === 'price') formatted = `${Math.round(p.value).toLocaleString('ru-RU')} ₽`
          else if (p.dataKey === 'occupancy') formatted = `${p.value.toFixed(1)}%`
          else formatted = Math.round(p.value).toLocaleString('ru-RU')
          return (
            <div key={i} className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color }} />
              <span className="text-[hsl(var(--muted-foreground))]">{p.name}:</span>
              <span className="font-medium tabular-nums">{formatted}</span>
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div className="space-y-3 animate-fade-in">
      {/* Header — компактный */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[hsl(var(--primary))] to-[hsl(var(--accent))] flex items-center justify-center">
          <MapIcon className="w-4 h-4 text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-bold leading-tight">Региональная карта</h1>
          <p className="text-xs text-[hsl(var(--muted-foreground))] truncate">
            Байкальский макрорегион: Иркутская область и прибайкальские районы Бурятии. Объекты, агрегаты
            по районам и динамика цен / загрузки.
          </p>
        </div>
        <button
          onClick={() => navigate(`/chat?context=${encodeURIComponent('Сравни заполняемость отелей по районам Прибайкалья')}`)}
          className="p-2 rounded-lg bg-[hsl(var(--primary)/0.1)] hover:bg-[hsl(var(--primary)/0.2)] transition-colors"
          title="Спросить AI"
        >
          <Sparkles size={14} className="text-[hsl(var(--primary))]" />
        </button>
      </div>

      {/* Баннер «нет данных за выбранную дату» — backend strict-фильтрует
          по hotel_statistics, и пустой день виден честно (а не подменой
          на ближайший предшествующий). */}
      {hotelsMap && hotelsMap.total_hotels === 0 && (
        <div className="px-3 py-2 rounded-lg border border-[hsl(var(--warning)/0.4)] bg-[hsl(var(--warning)/0.1)] text-sm text-[hsl(var(--warning-foreground,var(--foreground)))] flex items-center gap-2">
          <Calendar size={14} />
          <span>
            За <strong>{fmtDateRu(focusDate)}</strong> нет данных от парсеров
            {focusDate === isoToday()
              ? ' — снимок за сегодня ещё не собран (отели обновляются каждые 2 ч).'
              : overlapsDataGap(focusDate, focusDate)
                ? `: дата попадает в пробел сбора данных ${DATA_GAP_LABEL}.`
                : '. Выберите другую дату.'}
          </span>
        </div>
      )}

      {/* KPI strip — горизонтальная полоска вверху, full width */}
      {hotelsMap && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card variant="glass">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 text-[hsl(var(--muted-foreground))] text-sm font-medium uppercase tracking-wider mb-1.5">
                <Building2 size={16} /> Объектов
                <MethodologyTooltip text="Объекты, у которых есть снимок парсера ровно за выбранную дату. Каталог целиком больше: часть объектов в этот день не отдала данные. Счётчик в фильтре «Районы» считает другое окно — весь выбранный период." />
              </div>
              <p className="text-3xl font-bold tabular-nums leading-tight">{filteredKpi.total_hotels.toLocaleString('ru-RU')}</p>
              <p className="text-sm text-[hsl(var(--muted-foreground))] mt-1">со снимком за {fmtDateRu(focusDate)}</p>
            </CardContent>
          </Card>
          <Card variant="glass">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 text-[hsl(var(--muted-foreground))] text-sm font-medium uppercase tracking-wider mb-1.5">
                <BedDouble size={16} /> Всего номеров
              </div>
              <p className="text-3xl font-bold tabular-nums leading-tight">{filteredKpi.total_rooms.toLocaleString('ru-RU')}</p>
              <p className="text-sm text-[hsl(var(--muted-foreground))] mt-1">
                по объектам со снимком за {fmtDateRu(focusDate)}
              </p>
            </CardContent>
          </Card>
          <Card variant="glass">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 text-[hsl(var(--muted-foreground))] text-sm font-medium uppercase tracking-wider mb-1.5">
                <BedDouble size={16} /> Свободных номеров
                <MethodologyTooltip text="Сумма свободных номеров по объектам со снимком за выбранную дату. Высокое значение означает низкую загрузку — не путать с бизнес-успехом." />
              </div>
              <p className="text-3xl font-bold tabular-nums leading-tight text-[hsl(var(--foreground))]">
                {filteredKpi.free_rooms.toLocaleString('ru-RU')}
              </p>
              <p className="text-sm text-[hsl(var(--muted-foreground))] mt-1">
                {filteredKpi.total_rooms > 0 ? `${Math.round((filteredKpi.free_rooms / filteredKpi.total_rooms) * 100)}% инвентаря` : '—'}
              </p>
            </CardContent>
          </Card>
          <Card variant="glass">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 text-[hsl(var(--muted-foreground))] text-sm font-medium uppercase tracking-wider mb-1.5">
                <Activity size={16} /> Загрузка
                <MethodologyTooltip text="Считается по номерному фонду: (все номера − свободные) / все номера. Крупные объекты весят пропорционально своему инвентарю, поэтому число не равно среднему по объектам." />
              </div>
              <p className="text-3xl font-bold tabular-nums leading-tight">
                {filteredKpi.occupancy != null ? `${filteredKpi.occupancy}%` : '—'}
              </p>
              <p className="text-sm text-[hsl(var(--muted-foreground))] mt-1">
                по номерному фонду за {fmtDateRu(focusDate)}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Row 2: Map (full block height) + Filters (h-full) */}
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px] gap-3 lg:h-[520px]">
        {/* Map — занимает весь блок целиком, легенда оверлеем */}
        <Card variant="glass" className="h-full">
          <CardContent className="p-0 overflow-hidden rounded-2xl relative h-full">
            <YandexMap hotels={filteredPins} height="100%" />
            {/* Overlay-легенда поверх карты (нижний край), полупрозрачный фон */}
            <div
              className="absolute left-2 right-2 bottom-2 px-3 py-1.5 rounded-lg
                         bg-[hsl(var(--card)/0.85)] backdrop-blur-sm border border-[hsl(var(--border))]
                         text-[11px] text-[hsl(var(--foreground))]
                         flex items-center justify-between flex-wrap gap-x-4 gap-y-1
                         pointer-events-none z-[400]"
            >
              <div className="flex items-center gap-3 flex-wrap">
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#22c55e]" /> низкая &lt;40%
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#f59e0b]" /> средняя 40–69%
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#ef4444]" /> высокая 70% и выше
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#94a3b8]" /> нет данных
                </span>
              </div>
              <span className="italic text-[hsl(var(--muted-foreground))]">
                цвет — загрузка объекта за {fmtDateRu(focusDate)} · клик по маркеру — сводка, «Подробнее» — карточка
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Filters */}
        <Card variant="glass" className="h-full flex flex-col">
          <CardHeader className="pb-2 pt-3 px-3 flex-shrink-0">
            <div className="flex items-center gap-1.5">
              <Filter size={14} className="text-[hsl(var(--primary))]" />
              <CardTitle className="text-sm">Фильтры</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-3 px-3 pb-3 flex flex-col flex-1 min-h-0 overflow-y-auto">
            {/* Карта */}
            <div className="space-y-2">
              <p className="text-[11px] uppercase tracking-wider text-[hsl(var(--muted-foreground))] font-semibold">Карта и KPI</p>
              <label className="flex items-center gap-2 text-sm">
                <Calendar size={14} className="text-[hsl(var(--muted-foreground))]" />
                <span className="text-[hsl(var(--muted-foreground))]">Дата:</span>
                <input
                  type="date"
                  value={focusDate}
                  onChange={e => {
                    const v = e.target.value
                    if (isValidIsoDate(v)) setFocusDate(v)
                  }}
                  max={isoToday()}
                  className="ml-auto px-2 py-1 text-sm rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--card))] text-[hsl(var(--foreground))] tabular-nums"
                />
              </label>
            </div>

            {/* Графики */}
            <div className="space-y-2 pt-2 border-t border-[hsl(var(--border))]">
              <p className="text-[11px] uppercase tracking-wider text-[hsl(var(--muted-foreground))] font-semibold">Графики</p>
              <div>
                <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1.5">Сезон</p>
                <div className="flex flex-wrap gap-1">
                  {(Object.keys(SEASON_LABELS) as Season[]).map(s => {
                    const active = season === s
                    return (
                      <button
                        key={s}
                        onClick={() => setSeason(s)}
                        className={`text-xs px-2.5 py-1 rounded-md border transition-colors ${
                          active
                            ? 'bg-[hsl(var(--primary))] text-white border-[hsl(var(--primary))]'
                            : 'bg-[hsl(var(--card))] text-[hsl(var(--muted-foreground))] border-[hsl(var(--border))] hover:border-[hsl(var(--primary)/0.5)]'
                        }`}
                      >{SEASON_LABELS[s]}</button>
                    )
                  })}
                </div>
              </div>
              <div>
                <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1.5">Период</p>
                <div className="flex flex-wrap gap-1">
                  {PERIOD_OPTIONS.map(p => {
                    const active = periodDays === p.value
                    return (
                      <button
                        key={p.value}
                        onClick={() => setPeriodDays(p.value)}
                        className={`text-xs px-2.5 py-1 rounded-md border transition-colors ${
                          active
                            ? 'bg-[hsl(var(--primary))] text-white border-[hsl(var(--primary))]'
                            : 'bg-[hsl(var(--card))] text-[hsl(var(--muted-foreground))] border-[hsl(var(--border))] hover:border-[hsl(var(--primary)/0.5)]'
                        }`}
                      >{p.label}</button>
                    )
                  })}
                </div>
              </div>
            </div>

            {/* Районы — multi-select dropdown */}
            {districtOptions.length > 0 && (
              <div className="space-y-1.5 pt-2 border-t border-[hsl(var(--border))] flex flex-col flex-1 min-h-0">
                <p className="text-[11px] uppercase tracking-wider text-[hsl(var(--muted-foreground))] font-semibold flex-shrink-0">
                  Районы
                </p>
                <div className="flex-shrink-0">
                  <DistrictMultiSelect
                    options={districtOptions}
                    selected={selectedDistricts}
                    onToggle={toggleDistrict}
                    onClear={clearDistricts}
                  />
                </div>
                <p className="text-[11px] text-[hsl(var(--muted-foreground))] leading-tight flex-shrink-0">
                  Число справа — объектов за {periodDays} дн.
                  {pinsOutsideFilter > 0 && (
                    <span className="block mt-0.5">
                      Ещё {pinsOutsideFilter} объектов из снимка за {fmtDateRu(focusDate)} в список не попали:
                      район не определён либо в нём меньше 4 объектов — такие районы в агрегаты не идут.
                    </span>
                  )}
                </p>
                <p className="text-[11px] text-[hsl(var(--muted-foreground))] italic leading-tight flex-shrink-0 mt-auto">
                  Графики: <strong className="text-[hsl(var(--foreground))] not-italic">{queryDistrictsLabel}</strong>
                  {queryDistricts.length > 1 && (
                    <span className="block text-xs mt-0.5 not-italic">
                      Загрузка/цена усреднены, номера суммированы по выбранным районам
                    </span>
                  )}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Charts — 2x2 grid */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
        {/* 1. Загрузка по районам */}
        <Card variant="glass" className="overflow-hidden">
          <CardHeader className="pb-2 pt-2 px-3">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-1.5">
                <CardTitle className="text-sm">Загрузка по районам</CardTitle>
                <MethodologyTooltip text="Загрузка по району за выбранный период (фильтр «Период»). Районы с выборкой меньше 4 объектов и районы без статистики за период в диаграмму не попадают. Цвет — уровень занятости. Невыбранные блёкнут." />
              </div>
              <span className="text-xs text-[hsl(var(--muted-foreground))]">
                {fmtDateRu(periodRange.from)}–{fmtDateRu(periodRange.to)}
              </span>
            </div>
          </CardHeader>
          <CardContent className="px-2 pb-2 pt-0">
            {districtsBar.length === 0 ? (
              <div className="flex items-center justify-center h-[260px] px-4 text-center text-xs text-[hsl(var(--muted-foreground))]">
                Нет данных о загрузке за {fmtDateRu(periodRange.from)}–{fmtDateRu(periodRange.to)}.
                {overlapsDataGap(periodRange.from, periodRange.to) &&
                  ` Период пересекается с пробелом сбора данных ${DATA_GAP_LABEL}.`}
              </div>
            ) : (
              <ResponsiveContainer key={chartKey} width="100%" height={260}>
                <BarChart data={districtsBar} layout="vertical" margin={{ top: 12, right: 16, left: 4, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.15} horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fontSize: 9 }} />
                  <YAxis
                    type="category"
                    dataKey="district"
                    width={120}
                    tick={{ fontSize: 10 }}
                    interval={0}
                    tickFormatter={(s: string) => (s.length > 16 ? `${s.slice(0, 15)}…` : s)}
                  />
                  <Tooltip
                    {...RECHARTS_TOOLTIP_PROPS}
                    cursor={BAR_CURSOR_TRANSPARENT}
                    formatter={(value: number) => [`${value}%`, 'Загрузка']}
                    labelFormatter={(s: string) => s}
                  />
                  <Bar dataKey="occupancy" radius={[0, 3, 3, 0]}>
                    {districtsBar.map(d => {
                      const isHighlighted = selectedDistricts.size === 0 || selectedDistricts.has(d.fullName)
                      return (
                        <Cell
                          key={d.fullName}
                          fill={occupancyColor(d.occupancy)}
                          fillOpacity={isHighlighted ? 1 : 0.25}
                        />
                      )
                    })}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* 2. Загрузка номерного фонда: occupancy + rooms + capacity */}
        <Card variant="glass" className="overflow-hidden">
          <CardHeader className="pb-2 pt-2 px-3">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-1.5">
                <CardTitle className="text-sm">Загрузка номерного фонда</CardTitle>
                <MethodologyTooltip text="Левая ось — загрузка, %. Правая ось — суммарное число номеров по выбранным районам. Вместимость в людях не показывается: у большинства объектов состав номеров не раскрыт, и парсер подставляет туда то же число номеров. Окно — выбранный период." />
              </div>
              <span className="text-xs text-[hsl(var(--muted-foreground))]">
                {queryDistrictsLabel} · {fmtDateRu(periodRange.from)}–{fmtDateRu(periodRange.to)}
              </span>
            </div>
          </CardHeader>
          <CardContent className="px-2 pb-2 pt-0">
            {periodData.filter(d => d.occupancy != null).length === 0 ? (
              <div className="flex items-center justify-center h-[260px] px-4 text-center text-xs text-[hsl(var(--muted-foreground))]">
                Нет данных за выбранный период.
                {overlapsDataGap(periodRange.from, periodRange.to) &&
                  ` Период пересекается с пробелом сбора данных ${DATA_GAP_LABEL}.`}
              </div>
            ) : (
              <ResponsiveContainer key={chartKey} width="100%" height={260}>
                <LineChart data={periodData} margin={{ top: 12, right: 12, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                  <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={fmtDateRu} minTickGap={28} />
                  <YAxis yAxisId="left" tick={{ fontSize: 10 }} unit="%" domain={[0, 100]} width={36} />
                  <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10 }} domain={['auto', 'auto']} width={42} />
                  <Tooltip content={<ChartTooltipContent />} />
                  <Legend wrapperStyle={{ fontSize: 10 }} iconSize={8} />
                  <Line yAxisId="left" type="monotone" dataKey="occupancy" name="Загрузка" stroke="#22c55e" strokeWidth={2} dot={false} connectNulls />
                  <Line yAxisId="right" type="monotone" dataKey="total_rooms" name="Всего номеров" stroke="#3b82f6" strokeWidth={1.5} strokeDasharray="6 3" dot={false} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* 3. Цена и загрузка за сезон */}
        <Card variant="glass" className="overflow-hidden">
          <CardHeader className="pb-2 pt-2 px-3">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-1.5">
                <CardTitle className="text-sm">Цена и загрузка за сезон ({SEASON_LABELS[season]})</CardTitle>
                <MethodologyTooltip text="Левая ось — прокси-ADR: медиана минимальной цены номера по объектам района, ₽. Это цена витрины, а не выручка за проданный номер. Правая ось — загрузка, %. Окно — выбранный сезон." />
              </div>
              <span className="text-xs text-[hsl(var(--muted-foreground))]">
                {queryDistrictsLabel}{seasonRange && ` · ${fmtDateRu(seasonRange.from)}–${fmtDateRu(seasonRange.to)}`}
              </span>
            </div>
          </CardHeader>
          <CardContent className="px-2 pb-2 pt-0">
            {seasonData.length === 0 ? (
              <div className="flex items-center justify-center h-[220px] px-4 text-center text-xs text-[hsl(var(--muted-foreground))]">
                Нет данных за выбранный сезон.
                {seasonRange && overlapsDataGap(seasonRange.from, seasonRange.to) &&
                  ` Сезон пересекается с пробелом сбора данных ${DATA_GAP_LABEL}.`}
              </div>
            ) : (
              <ResponsiveContainer key={chartKey} width="100%" height={220}>
                <ComposedChart data={seasonData} margin={{ top: 12, right: 12, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                  <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={fmtDateRu} minTickGap={28} />
                  <YAxis yAxisId="left" tick={{ fontSize: 10 }} unit="₽" domain={['auto', 'auto']} width={48} />
                  <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10 }} unit="%" domain={[0, 100]} width={32} />
                  <Tooltip content={<ChartTooltipContent />} />
                  <Legend wrapperStyle={{ fontSize: 10 }} iconSize={8} />
                  <Line yAxisId="left" type="monotone" dataKey="price" name="Цена" stroke="#3b82f6" strokeWidth={2} dot={false} connectNulls />
                  <Line yAxisId="right" type="monotone" dataKey="occupancy" name="Загрузка" stroke="#22c55e" strokeWidth={2} dot={false} connectNulls />
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* 4. Цена и загрузка за период */}
        <Card variant="glass" className="overflow-hidden">
          <CardHeader className="pb-2 pt-2 px-3">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-1.5">
                <CardTitle className="text-sm">Цена и загрузка за период</CardTitle>
                <MethodologyTooltip text="Окно — выбранный период до даты среза. Столбцы — прокси-ADR: медиана минимальной цены номера по объектам района, ₽. Линия — загрузка, %." />
              </div>
              <span className="text-xs text-[hsl(var(--muted-foreground))]">
                {queryDistrictsLabel} · {fmtDateRu(periodRange.from)}–{fmtDateRu(periodRange.to)}
              </span>
            </div>
          </CardHeader>
          <CardContent className="px-2 pb-2 pt-0">
            {periodData.length === 0 ? (
              <div className="flex items-center justify-center h-[220px] px-4 text-center text-xs text-[hsl(var(--muted-foreground))]">
                Нет данных за выбранный период.
                {overlapsDataGap(periodRange.from, periodRange.to) &&
                  ` Период пересекается с пробелом сбора данных ${DATA_GAP_LABEL}.`}
              </div>
            ) : (
              <ResponsiveContainer key={chartKey} width="100%" height={220}>
                <ComposedChart data={periodData} margin={{ top: 12, right: 12, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                  <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={fmtDateRu} minTickGap={28} />
                  <YAxis yAxisId="left" tick={{ fontSize: 10 }} unit="₽" domain={['auto', 'auto']} width={48} />
                  <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10 }} unit="%" domain={[0, 100]} width={32} />
                  <Tooltip content={<ChartTooltipContent />} />
                  <Legend wrapperStyle={{ fontSize: 10 }} iconSize={8} />
                  <Bar yAxisId="left" dataKey="price" name="Цена" fill="#3b82f6" fillOpacity={0.4} />
                  <Line yAxisId="right" type="monotone" dataKey="occupancy" name="Загрузка" stroke="#22c55e" strokeWidth={2} dot={false} connectNulls />
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="flex justify-center pt-1">
        <button
          onClick={() => navigate('/analytics')}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-[hsl(var(--secondary))] hover:bg-[hsl(var(--secondary)/0.8)] transition-colors text-[hsl(var(--foreground))]"
        >
          <TrendingUp size={14} />
          Перейти к детальной аналитике
        </button>
      </div>
    </div>
  )
}

export default MapPage
