export type Hotel = {
  id: string
  name: string
  city: string
  district: string | null
  lat: number | null
  lon: number | null
  rating: number | null
  min_price: number | null
  accommodation_type: string | null
  tripadvisor_rating: number | null
  tripadvisor_reviews: number | null
  tripadvisor_url: string | null
  image_url: string | null
}

export type Event = {
  event_id: string
  title: string
  description: string | null
  date_start: string
  date_end: string | null
  event_type: string | null
  location: string | null
  source_id: string
  url: string | null
  time_start: string | null
  address: string | null
  price_min: number | null
  price_max: number | null
  image_url: string | null
  age_restriction: string | null
  also_at?: string[]
}

export type QueryResponse = {
  answer: string
  sources: string[]
}

// API base URL - для локальной разработки пустая строка (прокси), для продакшена - внешний URL
const API_BASE = import.meta.env.VITE_API_URL || ''

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const method = (options?.method ?? 'GET').toUpperCase()
  const headers = new Headers(options?.headers)
  if (method !== 'GET' && method !== 'HEAD' && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const signal = options?.signal ?? AbortSignal.timeout(30_000)
  const response = await fetch(API_BASE + url, {
    ...options,
    headers,
    signal,
  })
  if (!response.ok) {
    // Пытаемся прочитать тело ошибки
    let errorMessage = `HTTP ${response.status}`
    try {
      const errorData = await response.json()
      if (errorData.detail) {
        errorMessage = errorData.detail
      }
    } catch {
      // Игнорируем ошибки парсинга
    }
    const err = new Error(errorMessage) as Error & { status: number }
    err.status = response.status
    throw err
  }
  return response.json()
}

// Analytics types
export type CorrelationData = {
  months: {
    month: string
    occupancy: number
    avgPrice: number
    events: number
    season: string
    hasData?: boolean
  }[]
  correlation_coefficient: number | null
  avg_occupancy: number | null
  peak_month: string | null
  low_month: string | null
  missing_periods?: { month: string; monthIndex: number; reason: string }[]
  data_coverage?: string
  available_years?: number[]
  selected_year?: number | null
}

export type DistrictData = {
  district: string
  occupancy: number
  freeRooms: number
  totalRooms: number
  avgPrice: number
  hotelsCount?: number
  confidence?: 'high' | 'medium' | 'low'
}

export type Recommendation = {
  type: 'tourist' | 'hotelier' | 'info'
  title: string
  description: string
  period?: string
  savings?: string
  increase?: string
}

export type KPIData = {
  total_hotels: number
  total_cities: number
  total_events: number
  total_rooms: number
  free_rooms: number
  avg_occupancy: number
  avg_price?: number | null
}

// Weather types
export type WeatherForecast = {
  location: string
  forecasts: {
    date: string
    temperature_max: number
    temperature_min: number
    temperature_mean: number
    precipitation: number
    wind_speed: number
    weather_code: number
    weather_description: string
  }[]
}

// Hotels by district type
export type HotelsByDistrict = {
  district: string
  count: number
  avg_price: number | null
  avg_rating: number | null
}

export type EnsembleResponse = {
  district: string
  history_points: number
  method: string
  weights: Record<string, number>
  ensemble: { date: string; occupancy: number; lower: number; upper: number }[]
  models: Record<string, { date: string; occupancy: number; lower: number; upper: number }[]>
}

export type CompareResponse = {
  district: string
  history_points: number
  test_days: number
  best_model?: string
  metrics: Record<string, { rmse: number; mae: number; r2: number; points: number }>
  feature_importance?: Record<string, Record<string, number>>
}

export type ForecastFactor = {
  name: string
  impact: number
  description: string
  direction: 'positive' | 'negative' | 'neutral'
}

export type ExplainResponse = {
  district: string
  target_date: string
  best_model: string
  forecasts: Record<string, { date: string; occupancy: number; lower_bound?: number; upper_bound?: number }[]>
  factors: ForecastFactor[]
  explanation: string
  recommendation: string
  processing_time: number
  error?: string | null
}

export type TripSummary = {
  district: string
  forecast_occupancy: number
  occupancy_level: 'low' | 'medium' | 'high'
  occupancy_trend: 'growing' | 'stable' | 'declining'
  forecast_source: 'ensemble' | 'fallback'
  weather: { date: string; temp_max: number; temp_min: number; weather_code: number; description: string }[]
  events_count: number
  top_events: { title: string; date: string; event_type: string | null }[]
  available_hotels: number
  avg_price: number | null
  recommendation: string
}

export type BestDate = {
  date: string
  predicted_occupancy: number
  weather_temp: number | null
  events: string[]
  score: number
}

export type EventImpact = {
  event: string
  date: string
  district: string
  source: string
  occupancy_on_day: number | null
  avg_occupancy: number | null
  impact: number | null
}

export type AnalyticsMetadata = {
  hotels_count: number
  events_count: number
  data_range: { from: string | null; to: string | null }
  last_refresh: string | null
  gap_periods: Array<{ from: string | null; to: string | null; gap_days: number; reason: string }>
}

export type ParserHealth = {
  parser_id: string
  status: 'ok' | 'warn' | 'fail'
  items_collected: number
  error: string | null
  last_run: string
}

export type BookingPacePoint = {
  date: string
  occupancy_today: number | null
  occupancy_lookback: number | null
  proxy_pickup_pct: number | null
}

export type BookingPaceResponse = {
  district: string
  days_ahead: number
  lookback_days: number
  method: string
  methodology: string
  points: BookingPacePoint[]
  summary: {
    avg_proxy_pickup_pct: number | null
    max_proxy_pickup_pct: number | null
    min_proxy_pickup_pct: number | null
    trend: string
  }
}

export type OccupancyTimeseriesResponse = {
  district: string
  days: number
  points: Array<{
    date: string
    occupancy: number
    total_rooms?: number | null
    total_capacity?: number | null
  }>
  summary: { min: number | null; max: number | null; avg: number | null; samples: number }
}

export type PriceDistributionResponse = {
  district: string
  days: number
  samples: number
  p10: number | null
  p25: number | null
  p50: number | null
  p75: number | null
  p90: number | null
}

export type CompareDistrictsResponse = {
  days: number
  districts: Array<{
    district: string
    occupancy: number | null
    adr_proxy: number | null
    revpar_proxy: number | null
    samples: number
  }>
}

export type SegmentsResponse = {
  by_size: Record<string, { count: number; avg_occupancy: number | null; avg_price: number | null }>
  by_accommodation_type: Record<string, { count: number; avg_price: number | null }>
  size_thresholds: { mini_max: number; mid_max: number }
}

export type DistrictSegmentItem = {
  count: number
  avg_occupancy: number
  avg_min_price: number | null
  revpar: number | null
}

export type DistrictSegmentsResponse = {
  district: string
  total_objects: number
  by_size: Array<DistrictSegmentItem & { size: string }>
  by_accommodation_type: Array<DistrictSegmentItem & { type: string }>
}

export type HotelSegmentBenchmarkResponse = {
  hotel: { id: string; name: string | null; district: string | null; rooms_num: number | null }
  segment: { district: string | null; size_bucket: string }
  hotel_metrics: { occupancy: number | null; min_price: number | null }
  segment_metrics: { n: number; avg_occupancy: number | null; avg_price: number | null }
  n_in_segment: number
}

export type ForecastValidationResponse = {
  district: string
  days_back: number
  samples: number
  rmse: number | null
  mae: number | null
  mae_per_day: number[]
  forecasted: Array<{ date: string; occupancy: number }>
  actual: Array<{ date: string; occupancy: number }>
}

export type CorrectedEventsImpact = Array<{
  event: string
  date: string
  district: string
  occupancy_on_day: number
  delta_pct: number | null
  baseline_mean: number | null
  ci_lower: number | null
  ci_upper: number | null
  n_samples: number
  confidence: 'high' | 'medium' | 'low'
  method: string
}>

export type MapHotel = {
  id: string; name: string; city: string; district: string
  lat: number; lon: number; rating: number | null; min_price: number | null
  rooms_num: number; free_rooms: number; occupancy: number
  max_capacity: number
}

export type HotelsMapData = {
  hotels: MapHotel[]
  total_hotels: number
  total_rooms: number
  free_rooms: number
  avg_occupancy: number
}

export type PriceHistoryData = {
  district: string
  trend: { direction: string; change_percent: number }
  period: { start: string; end: string; days: number }
  prices: { date: string; avg_price: number; samples: number }[]
}

export type WeekdayHeatmapCell = {
  weekday: number
  month: number
  occupancy: number
  samples: number
}

export type WeekdayHeatmap = {
  district: string | null
  data: WeekdayHeatmapCell[]
  weekdays: string[]
  months: string[]
  methodology: string
}

export type PickupPacePoint = {
  date: string
  booked: number
  total_rooms: number
  free_rooms: number
  hotels_count: number
  occupancy: number
  pickup: number
}

export type PickupPace = {
  district: string | null
  period: { start: string; end: string; days: number }
  points: PickupPacePoint[]
  summary: {
    avg_pickup: number
    max_pickup: number
    min_pickup: number
    trend: string
    samples: number
  }
  methodology: string
}

export type RevenueSummaryDistrict = {
  district: string
  occupancy: number
  adr: number
  revpar: number
  hotels_count: number
  confidence: 'high' | 'medium' | 'low'
}

export type RevenueSummary = {
  occupancy: number
  adr: number
  revpar: number
  by_district: RevenueSummaryDistrict[]
  methodology: string
}

export type StreamEvent = {
  type: 'token' | 'tool_start' | 'tool_end' | 'sources' | 'done' | 'error'
  content?: string
  sources?: string[]
  tools?: string[]
  tool?: string
  error?: string
}

import { DEFAULT_DISTRICT } from '../constants/districts'

export const api = {
  getHotels: async () => {
    const res = await request<{ items: Hotel[]; total: number }>('/api/hotels?limit=500')
    return res.items
  },

  getHotel: (id: string) => request<Hotel>(`/api/hotels/${encodeURIComponent(id)}`),

  getHotelStats: (id: string) => request<{
    id: string; date: string; rooms_num: number | null
    free_rooms_amount: number | null; available_rooms_percent: number | null
    min_price: number | null
  }[]>(`/api/hotels/${encodeURIComponent(id)}/statistics`),

  getEvents: () => request<Event[]>('/api/events'),

  query: (text: string, sessionId?: string) => request<QueryResponse>('/api/query', {
    method: 'POST',
    body: JSON.stringify({ text, session_id: sessionId }),
  }),

  queryStream: async function* (text: string, sessionId?: string, signal?: AbortSignal): AsyncGenerator<StreamEvent> {
    const response = await fetch(API_BASE + '/api/query/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, session_id: sessionId }),
      signal,
    })
    if (!response.ok || !response.body) {
      response.body?.cancel()
      throw new Error(`HTTP ${response.status}`)
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (value) {
          buffer += decoder.decode(value, { stream: true })
        }
        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''
        for (const block of parts) {
          const line = block.trim()
          if (line.startsWith('data: ')) {
            try {
              yield JSON.parse(line.slice(6)) as StreamEvent
            } catch {
              /* skip malformed */
            }
          }
        }
        if (done) {
          buffer += decoder.decode()
          const tail = buffer.trim()
          if (tail) {
            for (const block of tail.split(/\n\n/)) {
              const line = block.trim()
              if (line.startsWith('data: ')) {
                try {
                  yield JSON.parse(line.slice(6)) as StreamEvent
                } catch {
                  /* skip malformed */
                }
              }
            }
          }
          break
        }
      }
    } catch (err) {
      reader.cancel()
      throw err
    }
  },

  ensembleForecast: (district: string, days: number = 14, method: string = 'weighted_average') =>
    request<EnsembleResponse>(`/api/forecast/ensemble?district=${encodeURIComponent(district)}&days_ahead=${days}&method=${method}`),

  compareModels: (district: string, testDays: number = 7) =>
    request<CompareResponse>(`/api/forecast/compare-all?district=${encodeURIComponent(district)}&test_days=${testDays}`),

  getWeather: (days: number = 7) => request<WeatherForecast>(`/api/forecast/weather?days=${days}`),

  getCorrelation: (year?: number | null) => {
    const url = year ? `/api/analytics/correlation?year=${year}` : '/api/analytics/correlation'
    return request<CorrelationData>(url)
  },
  getDistricts: (dateFrom?: string, dateTo?: string) => {
    const qs = new URLSearchParams()
    if (dateFrom) qs.set('date_from', dateFrom)
    if (dateTo) qs.set('date_to', dateTo)
    const tail = qs.toString() ? `?${qs.toString()}` : ''
    return request<DistrictData[]>(`/api/analytics/districts${tail}`)
  },
  getRecommendations: () => request<Recommendation[]>('/api/analytics/recommendations'),
  getKPI: () => request<KPIData>('/api/analytics/kpi'),
  getHotelsByDistrict: () => request<HotelsByDistrict[]>('/api/analytics/hotels-by-district'),
  explainForecast: (district: string, daysAhead: number = 14) =>
    request<ExplainResponse>(`/api/forecast/explain?district=${encodeURIComponent(district)}&days_ahead=${daysAhead}`),

  getHeatmap: (days: number = 14) => request<{
    data: { district: string; date: string; occupancy: number }[]
    districts: string[]
    dates: string[]
  }>(`/api/analytics/heatmap?days=${days}`),

  getHealth: () => request<{
    status: string
    db_connected: boolean
    redis_connected: boolean
    db_backend: string
    chroma_docs: number
  }>('/health'),

  getTripSummary: (district: string = DEFAULT_DISTRICT, days: number = 14) =>
    request<TripSummary>(`/api/analytics/trip-summary?district=${encodeURIComponent(district)}&days=${days}`),

  getBestDates: (district: string = DEFAULT_DISTRICT, daysAhead: number = 30) =>
    request<BestDate[]>(`/api/analytics/best-dates?district=${encodeURIComponent(district)}&days_ahead=${daysAhead}`),

  getEventsImpact: () => request<EventImpact[]>('/api/analytics/events-impact'),

  getHotelsMap: (district?: string, snapshotDate?: string) => {
    const qs = new URLSearchParams()
    if (district) qs.set('district', district)
    if (snapshotDate) qs.set('date', snapshotDate)
    const tail = qs.toString() ? `?${qs.toString()}` : ''
    return request<HotelsMapData>(`/api/analytics/hotels-map${tail}`)
  },

  getPriceHistory: (days: number = 180, district?: string) => {
    const qs = new URLSearchParams({ days: String(days) })
    if (district) qs.set('district', district)
    return request<PriceHistoryData>(`/api/analytics/price-history?${qs.toString()}`)
  },

  getWeekdayHeatmap: (district?: string) => {
    const params = district ? `?district=${encodeURIComponent(district)}` : ''
    return request<WeekdayHeatmap>(`/api/analytics/weekday-heatmap${params}`)
  },

  getPickupPace: (district?: string, days: number = 30) => {
    const params = new URLSearchParams({ days: String(days) })
    if (district) params.set('district', district)
    return request<PickupPace>(`/api/analytics/pickup-pace?${params}`)
  },

  getRevenueSummary: () => request<RevenueSummary>('/api/analytics/revenue-summary'),

  hotelForecast: (hotelId: string, daysAhead: number = 14) =>
    request<{
      hotel_id: string | null
      district: string | null
      forecast: { date: string; occupancy: number; lower_bound: number; upper_bound: number }[]
      history_points: number
    }>('/api/forecast', {
      method: 'POST',
      body: JSON.stringify({ hotel_id: hotelId, days_ahead: daysAhead }),
      signal: AbortSignal.timeout(60_000),
    }),

  getMetadata: () => request<AnalyticsMetadata>('/api/analytics/metadata'),

  getParserHealth: () => request<ParserHealth[]>('/api/parser/health'),

  getBookingPace: (district: string, daysAhead = 14, lookbackDays = 7) => {
    const params = new URLSearchParams({ district, days_ahead: String(daysAhead), lookback_days: String(lookbackDays) })
    return request<BookingPaceResponse>(`/api/analytics/booking-pace?${params}`)
  },

  getOccupancyTimeseries: (district: string, days = 30) => {
    const params = new URLSearchParams({ district, days: String(days) })
    return request<OccupancyTimeseriesResponse>(`/api/analytics/occupancy-timeseries?${params}`)
  },

  getPriceDistribution: (district: string, days = 30) => {
    const params = new URLSearchParams({ district, days: String(days) })
    return request<PriceDistributionResponse>(`/api/analytics/price-distribution?${params}`)
  },

  compareDistricts: (districts: string[], days = 30) => {
    const params = new URLSearchParams({ districts: districts.join(','), days: String(days) })
    return request<CompareDistrictsResponse>(`/api/analytics/compare-districts?${params}`)
  },

  getSegments: () => request<SegmentsResponse>('/api/analytics/segments'),

  getDistrictSegments: (district: string) =>
    request<DistrictSegmentsResponse>(
      `/api/analytics/district-segments?district=${encodeURIComponent(district)}`,
    ),

  getHotelSegmentBenchmark: (hotelId: string) =>
    request<HotelSegmentBenchmarkResponse>(`/api/hotels/${encodeURIComponent(hotelId)}/segment-benchmark`),

  getForecastValidation: (district: string, daysBack = 14) => {
    const params = new URLSearchParams({ days_back: String(daysBack) })
    return request<ForecastValidationResponse>(`/api/forecast/${encodeURIComponent(district)}/validation?${params}`)
  },

  getEventsImpactCorrected: (windowWeeks = 3) => {
    const params = new URLSearchParams({ method: 'seasonal_corrected', window_weeks: String(windowWeeks) })
    return request<CorrectedEventsImpact>(`/api/analytics/events-impact?${params}`)
  },

  exportUrl: (
    type: 'occupancy' | 'events' | 'hotels',
    district?: string,
    dateFrom?: string,
    dateTo?: string,
  ): string => {
    const params = new URLSearchParams({ type })
    if (district) params.set('district', district)
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)
    return API_BASE + `/api/analytics/export?${params}`
  },
}
