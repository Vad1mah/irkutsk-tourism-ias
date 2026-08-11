/**
 * Map various API enum values and chart series keys (English) to Russian display labels.
 *
 * Pattern: each domain exposes a `*_LABELS` Record + a `localize*` function with safe fallback.
 */

export const CONFIDENCE_LABELS: Record<string, string> = {
  high: 'высокая',
  medium: 'средняя',
  low: 'низкая',
  // Значения из /correlation (сезонность) — раньше выпадали сырым английским
  limited: 'ограниченная',
  none: 'нет данных',
}

export function localizeConfidence(c: string): string {
  return CONFIDENCE_LABELS[c] ?? c
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
  pickup: 'Изменение занятых номеров',
  booked: 'Занято номеров',
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
    about: 'Взвешенное среднее двух моделей — Prophet и XGBoost — с весами по точности на исторических данных. Сглаживает ошибки отдельных моделей.',
  },
  prophet: {
    label: 'Prophet',
    about: 'Раскладывает ряд на тренд + сезонность (неделя/год) + праздники. Хорошо ловит регулярные паттерны, плохо — резкие события.',
  },
  xgboost: {
    label: 'XGBoost',
    about: 'Градиентный бустинг на 38 признаках (лаги, погода, события, праздники). Реагирует на нелинейные взаимодействия факторов.',
  },
}

export function localizeModel(name: string): string {
  return MODEL_INFO[name.toLowerCase()]?.label ?? name
}

export const FORECAST_HEADER_TEXT = 'Взвешенное среднее двух моделей. Слева — фактическая загрузка по дням, справа — прогноз на 14 дней вперёд.'
export const FORECAST_FACTUAL_ONLY_TEXT = 'Фактическая загрузка по дням. Прогноз считается по кнопке: расчёт обучает модели и занимает до минуты.'
export const FORECAST_METHODOLOGY_TEXT =
  'Используются две модели: Prophet (тренды и сезонность) и XGBoost (бустинг на 38 признаках). Итоговый прогноз — взвешенное среднее с весами по точности на истории. На горизонте дальше 3 дней ошибка сопоставима с прогнозом «завтра как вчера» — это измерено, см. раздел «О проекте».'
export const PICKUP_TREND_METHODOLOGY_TEXT =
  'Тренд считается по трём первым и трём последним дням с ненулевым изменением в окне; дни без движения в сравнении не участвуют. Само изменение — разница числа занятых номеров между соседними дневными снимками.'
export const PICKUP_PANEL_CAVEAT_TEXT =
  'Изменение числа занятых номеров между соседними дневными снимками. Состав отелей в снимке меняется день ото дня, поэтому часть изменения — смена выборки, а не брони и отмены.'
