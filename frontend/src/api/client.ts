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
  const response = await fetch(API_BASE + url, {
    ...options,
    headers,
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
    throw new Error(errorMessage)
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
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try { yield JSON.parse(line.slice(6)) as StreamEvent } catch { /* skip malformed */ }
          }
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
  getDistricts: () => request<DistrictData[]>('/api/analytics/districts'),
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

  getHotelsMap: (district?: string) => {
    const params = district ? `?district=${encodeURIComponent(district)}` : ''
    return request<HotelsMapData>(`/api/analytics/hotels-map${params}`)
  },

  getPriceHistory: (days: number = 180) =>
    request<PriceHistoryData>(`/api/analytics/price-history?days=${days}`),
}
