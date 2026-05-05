/**
 * Map XGBoost feature names (English) to Russian display labels.
 */
export const FEATURE_LOCALIZATION: Record<string, string> = {
  lag_1: 'Лаг 1 день',
  lag_7: 'Лаг 7 дней',
  lag_14: 'Лаг 14 дней',
  lag_30: 'Лаг 30 дней',
  rolling_min_7: 'Скользящий мин. 7д',
  rolling_max_7: 'Скользящий макс. 7д',
  rolling_mean_7: 'Скользящее среднее 7д',
  rolling_std_7: 'Скользящее std 7д',
  is_weekend: 'Выходной',
  is_holiday: 'Праздник',
  holiday_indicator: 'Праздник',
  temperature: 'Температура',
  temperature_max: 'Темп. макс.',
  temperature_min: 'Темп. мин.',
  precipitation: 'Осадки',
  trend: 'Тренд',
  week_of_year: 'Неделя года',
  day_of_week: 'День недели',
  day_of_month: 'День месяца',
  month: 'Месяц',
  quarter: 'Квартал',
}

export function localizeFeature(name: string): string {
  return FEATURE_LOCALIZATION[name] ?? name
}
