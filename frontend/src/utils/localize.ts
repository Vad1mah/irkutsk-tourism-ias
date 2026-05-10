/**
 * Map various API enum values and chart series keys (English) to Russian display labels.
 *
 * Pattern: each domain exposes a `*_LABELS` Record + a `localize*` function with safe fallback.
 */

export const CONFIDENCE_LABELS: Record<'high' | 'medium' | 'low', string> = {
  high: 'высокая',
  medium: 'средняя',
  low: 'низкая',
}

export function localizeConfidence(c: string): string {
  return CONFIDENCE_LABELS[c as 'high' | 'medium' | 'low'] ?? c
}

export const ACCOMMODATION_TYPE_LABELS: Record<string, string> = {
  hotel: 'Гостиница',
  apartment: 'Апартаменты',
  hostel: 'Хостел',
  guesthouse: 'Гостевой дом',
  sanatorium: 'Санаторий',
  resort: 'Курорт',
  motel: 'Мотель',
  cottage: 'Коттедж',
  recreation_center: 'База отдыха',
  unknown: 'Тип не указан',
  '': 'Тип не указан',
}

export function localizeAccommodationType(t: string | null | undefined): string {
  if (t == null) return 'Тип не указан'
  return ACCOMMODATION_TYPE_LABELS[t] ?? t
}

export const SERIES_LABELS: Record<string, string> = {
  factual: 'Факт',
  forecast: 'Прогноз',
  upper: 'Верхняя граница',
  lower: 'Нижняя граница',
  pickup: 'Изменение бронирований',
  booked: 'Бронирований всего',
  occupancy: 'Загрузка',
  revpar: 'RevPAR',
  adr: 'ADR',
}

export function localizeSeries(name: string): string {
  return SERIES_LABELS[name] ?? name
}

export const SIZE_BUCKET_LABELS: Record<string, string> = {
  mini: 'Мини',
  mid: 'Средние',
  large: 'Крупные',
}

export function localizeSizeBucket(b: string): string {
  return SIZE_BUCKET_LABELS[b] ?? b
}

export const MODEL_INFO: Record<string, { label: string; about: string }> = {
  ensemble: {
    label: 'Ансамбль',
    about: 'Среднее по трём моделям прогноза с весами по точности на исторических данных. Сглаживает ошибки отдельных моделей.',
  },
  prophet: {
    label: 'Prophet',
    about: 'Раскладывает ряд на тренд + сезонность (неделя/год) + праздники. Хорошо ловит регулярные паттерны, плохо — резкие события.',
  },
  neuralprophet: {
    label: 'NeuralProphet',
    about: 'Prophet + нейросеть на лаговых значениях загрузки. Чувствительнее к недавним сдвигам спроса.',
  },
  xgboost: {
    label: 'XGBoost',
    about: 'Градиентный бустинг на 38 признаках (лаги, погода, события, праздники). Реагирует на нелинейные взаимодействия факторов.',
  },
}

export function localizeModel(name: string): string {
  return MODEL_INFO[name.toLowerCase()]?.label ?? name
}

export const FORECAST_HEADER_TEXT = 'Среднее по трём моделям прогноза. Слева — факт за 14 дней, справа — прогноз на 14 вперёд.'
export const FORECAST_METHODOLOGY_TEXT =
  'Используются три модели: Prophet (тренды и сезонность), NeuralProphet (нейросеть на лагах), XGBoost (бустинг на 38 признаках). Итоговый прогноз — среднее с весами по точности на истории. Подробности — в разделе «О проекте».'
