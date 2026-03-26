import type { KPIData, EnsembleResponse, WeatherForecast } from '../api/client'

export type Insight = {
  type: 'positive' | 'neutral' | 'negative' | 'info'
  title: string
  description: string
  metric?: string
}

export function generateInsights(
  kpi: KPIData | undefined,
  forecast: EnsembleResponse | undefined,
  weather: WeatherForecast | undefined,
  eventsCount: number = 0,
): Insight[] {
  const insights: Insight[] = []

  if (kpi) {
    const occ = kpi.avg_occupancy
    if (occ > 0 && occ < 40) {
      insights.push({
        type: 'positive',
        title: 'Сейчас свободно',
        description: `Загрузка всего ${occ}% — идеальное время для бронирования`,
        metric: `${occ}%`,
      })
    } else if (occ >= 40 && occ <= 70) {
      insights.push({
        type: 'neutral',
        title: 'Умеренная загрузка',
        description: `Загрузка ${occ}% — рекомендуем бронировать заранее`,
        metric: `${occ}%`,
      })
    } else if (occ > 70) {
      insights.push({
        type: 'negative',
        title: 'Высокая загрузка',
        description: `${occ}% номеров занято — бронируйте как можно раньше`,
        metric: `${occ}%`,
      })
    }
  }

  if (forecast?.ensemble?.length && forecast.ensemble.length >= 4) {
    const points = forecast.ensemble
    const half = Math.floor(points.length / 2)
    const firstHalf = points.slice(0, half).reduce((a, b) => a + b.occupancy, 0) / half
    const secondHalf = points.slice(half).reduce((a, b) => a + b.occupancy, 0) / (points.length - half)
    const diff = secondHalf - firstHalf

    if (diff > 5) {
      insights.push({
        type: 'negative',
        title: 'Загрузка растёт',
        description: `Ожидается рост на ${Math.round(diff)}% за ${points.length} дней — бронируйте заранее`,
        metric: `+${Math.round(diff)}%`,
      })
    } else if (diff < -5) {
      insights.push({
        type: 'positive',
        title: 'Загрузка снижается',
        description: `Ожидается снижение на ${Math.abs(Math.round(diff))}% — хорошее время подождать`,
        metric: `${Math.round(diff)}%`,
      })
    } else {
      insights.push({
        type: 'info',
        title: 'Стабильный прогноз',
        description: `Загрузка останется в пределах ${Math.round(Math.min(...points.map(p => p.occupancy)))}–${Math.round(Math.max(...points.map(p => p.occupancy)))}%`,
      })
    }
  }

  if (weather?.forecasts?.length) {
    const avgTemp = weather.forecasts.reduce((a, b) => a + b.temperature_max, 0) / weather.forecasts.length
    const rainyDays = weather.forecasts.filter(d => d.precipitation > 1).length

    if (avgTemp > 20) {
      insights.push({
        type: 'positive',
        title: 'Тёплая погода',
        description: `Средняя температура ${Math.round(avgTemp)}°C — отличные условия для поездки`,
        metric: `${Math.round(avgTemp)}°C`,
      })
    } else if (avgTemp < 0) {
      insights.push({
        type: 'info',
        title: 'Холодно',
        description: `Средняя температура ${Math.round(avgTemp)}°C — одевайтесь теплее`,
        metric: `${Math.round(avgTemp)}°C`,
      })
    }

    if (rainyDays > weather.forecasts.length / 2) {
      insights.push({
        type: 'negative',
        title: 'Дождливая погода',
        description: `Осадки ожидаются ${rainyDays} из ${weather.forecasts.length} дней`,
        metric: `${rainyDays} дн.`,
      })
    }
  }

  if (eventsCount > 3) {
    insights.push({
      type: 'info',
      title: `${eventsCount} событий`,
      description: 'Много мероприятий в ближайшее время — загрузка может вырасти',
      metric: String(eventsCount),
    })
  }

  return insights.slice(0, 4)
}
