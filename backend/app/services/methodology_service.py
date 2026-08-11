"""Методология измеримых утверждений системы.

Здесь живёт расчёт событийного эффекта на загрузку: панельная регрессия с
константой на каждую пару «район × календарный месяц», кластерной ошибкой и
перестановочным плацебо-тестом. Подробности и причины выбора — в докстроке
`MethodologyService.event_effect_regression`.

Также экспортируется `METHODOLOGY_PROMPT_RULES` — единый источник 8 правил
для системных промптов AI-агента (см. main_agent + llm_service RAG-fallback).
Изменять только здесь — оба промпта импортируют эту строку.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Mapping, Sequence

import numpy as np
from scipy.stats import t as student_t


METHODOLOGY_PROMPT_RULES = """1. Всегда указывай район или географический скоп ответа. Охват системы —
   Байкальский макрорегион: Иркутская область и прибайкальские районы Бурятии.
2. Всегда указывай период данных, на которые опирается ответ. Любое число
   объектов сопровождай окном выборки: «в справочнике», «со снимком за
   DD.MM.YYYY», «со снимком за 14 дней».
3. Всегда указывай метод расчёта метрики и базу сравнения.
4. Про влияние событий на загрузку говори только то, что показало измерение:
   в Иркутском районе эффект не обнаружен, по остальным районам независимых
   случаев слишком мало, чтобы отделить событие от сезона. Не приписывай
   отдельному событию прирост загрузки.
5. При нехватке данных — явно говори, чего не хватает, не выдумывай.
6. Сегмент объекта — это «район × размерная категория» (get_segment_benchmark).
   Районный агрегат сегментом не называй: в нём мини-отели смешаны с крупными
   базами. С конкретными конкурентами не сравнивай — таких данных нет.
7. RevPAR и ADR — это прокси: ADR считается как медиана min_price публичных
   тарифов, а не как средняя цена реализации; помечай это.
8. Пробел данных 24.06.2025 — 25.10.2025 (123 дня) известен; не интерполируй
   молча — явно отмечай разрыв."""


@dataclass(frozen=True)
class EventEffectResult:
    """Оценка среднего эффекта событий на загрузку по панели район×день.

    Attributes:
        tau: Коэффициент при признаке события, в процентных пунктах загрузки.
        se: Кластерно-робастная стандартная ошибка (кластеры — календарные даты).
        ci_lower: Нижняя граница 95%-интервала.
        ci_upper: Верхняя граница 95%-интервала.
        placebo_p: Доля перестановок с |tau| не меньше наблюдённого. None,
            если перестановочный тест не запускался.
        n_obs: Число наблюдений (пар район×день) в оценке.
        n_districts: Число районов после отсева по min_days_per_district.
        n_cells: Число ячеек «район × месяц», внутри которых шло сравнение.
        n_event_days: Число наблюдений с признаком события.
        n_episodes: Число неразрывных серий событийных дней. Показывает, сколько
            независимых случаев стоит за оценкой; месячный фестиваль — один случай,
            а не тридцать.
        n_clusters: Число кластеров стандартной ошибки (совпадает с n_cells).
        r_squared: Доля объяснённой дисперсии полной моделью.
        min_days_per_district: Порог отсева района, с которым получен результат.
        min_days_per_cell: Порог отсева ячейки, с которым получен результат.
    """

    tau: float
    se: float
    ci_lower: float
    ci_upper: float
    placebo_p: float | None
    n_obs: int
    n_districts: int
    n_cells: int
    n_event_days: int
    n_episodes: int
    n_clusters: int
    r_squared: float
    min_days_per_district: int
    min_days_per_cell: int


class MethodologyService:
    """Stateless: все методы pure-функции. Удобен для тестов и DI."""

    def event_effect_regression(
        self,
        *,
        panel: Iterable[tuple[str, date, float]],
        event_days: Mapping[str, set[date]],
        placebo_rounds: int = 1000,
        min_days_per_district: int = 30,
        min_days_per_cell: int = 4,
        seed: int = 20260810,
    ) -> EventEffectResult | None:
        """Средний эффект событий на загрузку — регрессией по всей панели.

        Оценивается модель::

            occupancy[d, t] = cell[d, month(t)] + dow[t] + tau * event[d, t] + eps

        Сезонность снимается непараметрически: своя константа у каждой пары
        «район × календарный месяц». Тем самым эффект события измеряется только
        сравнением с обычными днями того же месяца в том же районе, а форма
        сезонной кривой вообще не моделируется.

        Так сделано не из вкуса, а по результату замера. Прежний оконный baseline
        управлял шириной окна и размером выборки одним параметром, и расширение
        окна опускало базу вместо того, чтобы сузить интервал: на неизменном
        наборе дней база падала с 61.1 до 55.1 при переходе с ±3 на ±12 недель,
        а ширина интервала не сокращалась. Параметрическая сезонность из гармоник
        оказалась не лучше: на прод-данных оценка монотонно ползла с числом
        гармоник (+6.4 при одной паре против +1.6 при шести), потому что
        несмоделированный остаток сезонного пика доставался признаку события —
        в Ольхонском районе все событийные дни лежат в феврале-марте, ровно на
        пике ледового сезона. Помесячные константы этот канал закрывают: внутри
        месяца впитывать нечего.

        Стандартная ошибка — кластерная по ячейке сравнения. Кластеризация по
        отдельным датам занижала бы её в разы: многодневное событие даёт подряд
        идущие дни с общим уровнем спроса, и в данных Ольхонского района один
        месячный фестиваль выглядел бы как 28 независимых наблюдений.

        Отдельно возвращается `n_episodes` — число неразрывных серий событийных
        дней. Именно оно, а не число событийных дней, показывает, сколько
        независимых случаев стоит за оценкой: эффект, посчитанный по одному
        длинному фестивалю, не становится надёжнее оттого, что фестиваль длился
        месяц, и никакая поправка на ошибку этого не исправляет.

        Args:
            panel: Тройки (район, дата, загрузка в процентах).
            event_days: Район → множество дат, в которые есть хотя бы одно событие.
                Многодневные события должны быть развёрнуты по дням заранее.
            placebo_rounds: Число перестановок для плацебо-теста; 0 — не запускать.
            min_days_per_district: Районы с меньшим числом наблюдений отбрасываются.
            min_days_per_cell: Минимум наблюдений в паре «район × месяц». Более
                мелкие ячейки выбрасываются: собственная константа на двух днях
                описывает шум, а не сезон.
            seed: Инициализация генератора перестановок (воспроизводимость).

        Returns:
            EventEffectResult либо None, если данных не хватает на оценку.
        """
        rows = [
            (district, day, float(occ))
            for district, day, occ in panel
            if occ is not None
        ]
        if not rows:
            return None

        counts: dict[str, int] = {}
        for district, _day, _occ in rows:
            counts[district] = counts.get(district, 0) + 1
        rows = [r for r in rows if counts[r[0]] >= min_days_per_district]
        if not rows:
            return None
        rows.sort(key=lambda r: (r[1], r[0]))

        rows = _keep_informative_cells(rows, event_days, min_days_per_cell)
        if not rows:
            return None

        districts = sorted({r[0] for r in rows})
        event_flags = np.array(
            [1.0 if day in event_days.get(district, ()) else 0.0 for district, day, _ in rows]
        )
        n_event_days = int(event_flags.sum())
        if n_event_days == 0 or n_event_days == len(rows):
            return None

        X, y = _build_design(rows, event_flags)
        n_obs, n_cols = X.shape
        if n_obs <= n_cols + 1:
            return None

        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ beta
        event_col = n_cols - 1
        tau = float(beta[event_col])

        cells = sorted({_cell_of(r) for r in rows})
        cell_position = {c: i for i, c in enumerate(cells)}
        cluster_ids = np.array([cell_position[_cell_of(r)] for r in rows])
        se = _cluster_robust_se(X, resid, cluster_ids, event_col)
        n_clusters = int(np.unique(cluster_ids).size)
        if se is None or n_clusters < 2:
            return None

        t_crit = float(student_t.ppf(0.975, n_clusters - 1))
        ss_tot = float(((y - y.mean()) ** 2).sum())
        r_squared = 1.0 - float((resid**2).sum()) / ss_tot if ss_tot > 0 else 0.0

        placebo_p = _placebo_p_value(
            X[:, :event_col], y, event_flags, rows, tau, placebo_rounds, seed
        )

        return EventEffectResult(
            tau=round(tau, 3),
            se=round(se, 3),
            ci_lower=round(tau - t_crit * se, 3),
            ci_upper=round(tau + t_crit * se, 3),
            placebo_p=placebo_p,
            n_obs=n_obs,
            n_districts=len(districts),
            n_cells=len(cells),
            n_event_days=n_event_days,
            n_episodes=_count_episodes(rows, event_flags),
            n_clusters=n_clusters,
            r_squared=round(r_squared, 4),
            min_days_per_district=min_days_per_district,
            min_days_per_cell=min_days_per_cell,
        )


def _cell_of(row: tuple[str, date, float]) -> tuple[str, str]:
    """Ячейка сравнения: район и календарный месяц наблюдения."""
    return row[0], row[1].strftime("%Y-%m")


def _keep_informative_cells(
    rows: Sequence[tuple[str, date, float]],
    event_days: Mapping[str, set[date]],
    min_days_per_cell: int,
) -> list[tuple[str, date, float]]:
    """Оставить ячейки «район × месяц», внутри которых есть с чем сравнивать.

    Выбрасываются две категории. Мелкие ячейки: константа, оценённая по паре
    дней, описывает шум. Ячейки, где событие каждый день: их константа
    совпадает со столбцом события, матрица плана вырождается, а сравнивать
    внутри такой ячейки всё равно не с чем.
    """
    grouped: dict[tuple[str, str], list[tuple[str, date, float]]] = {}
    for row in rows:
        grouped.setdefault(_cell_of(row), []).append(row)

    kept: list[tuple[str, date, float]] = []
    for (district, _month), cell_rows in grouped.items():
        if len(cell_rows) < min_days_per_cell:
            continue
        days = event_days.get(district, set())
        if all(row[1] in days for row in cell_rows):
            continue
        kept.extend(cell_rows)
    kept.sort(key=lambda r: (r[1], r[0]))
    return kept


def _count_episodes(
    rows: Sequence[tuple[str, date, float]],
    event_flags: np.ndarray,
) -> int:
    """Число неразрывных серий событийных дней по всем районам.

    Месячный фестиваль — один случай, а не тридцать. Серию делит только
    наблюдённый день без события: если промежуток между двумя событийными днями
    целиком выпал из панели (загрузка в эти дни не собиралась), серия считается
    непрерывной — иначе пробел сбора данных удваивал бы число независимых
    случаев и завышал бы доверие к оценке.
    """
    observed: dict[str, set[date]] = {}
    per_district: dict[str, list[date]] = {}
    for row, flag in zip(rows, event_flags):
        observed.setdefault(row[0], set()).add(row[1])
        if flag:
            per_district.setdefault(row[0], []).append(row[1])

    episodes = 0
    for district, days in per_district.items():
        days.sort()
        panel_days = observed[district]
        episodes += 1
        for previous, current in zip(days, days[1:]):
            between = (
                previous + timedelta(days=offset)
                for offset in range(1, (current - previous).days)
            )
            if any(day in panel_days for day in between):
                episodes += 1
    return episodes


def _build_design(
    rows: Sequence[tuple[str, date, float]],
    event_flags: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Матрица плана: [район×месяц][дни недели][событие].

    Признак события идёт последним столбцом — на этом опирается индексация в
    `event_effect_regression` и разделение матрицы для плацебо-теста.
    """
    cells = sorted({_cell_of(r) for r in rows})
    cell_index = {c: i for i, c in enumerate(cells)}

    cell_dummies = np.zeros((len(rows), len(cells)))
    for i, row in enumerate(rows):
        cell_dummies[i, cell_index[_cell_of(row)]] = 1.0

    # Понедельник поглощён константой ячейки, иначе столбцы линейно зависимы.
    dow = np.zeros((len(rows), 6))
    for i, (_district, day, _occ) in enumerate(rows):
        wd = day.weekday()
        if wd > 0:
            dow[i, wd - 1] = 1.0

    X = np.hstack([cell_dummies, dow, event_flags[:, None]])
    y = np.array([r[2] for r in rows])
    return X, y


def _cluster_robust_se(
    X: np.ndarray,
    resid: np.ndarray,
    cluster_ids: np.ndarray,
    col: int,
) -> float | None:
    """Сэндвич-оценка SE с кластеризацией по датам и поправкой на малое G."""
    n_obs, n_cols = X.shape
    try:
        xtx_inv = np.linalg.inv(X.T @ X)
    except np.linalg.LinAlgError:
        return None

    meat = np.zeros((n_cols, n_cols))
    for cluster in np.unique(cluster_ids):
        mask = cluster_ids == cluster
        score = X[mask].T @ resid[mask]
        meat += np.outer(score, score)

    n_clusters = int(np.unique(cluster_ids).size)
    if n_clusters < 2 or n_obs <= n_cols:
        return None
    correction = (n_clusters / (n_clusters - 1)) * ((n_obs - 1) / (n_obs - n_cols))
    var = correction * (xtx_inv @ meat @ xtx_inv)[col, col]
    return float(np.sqrt(var)) if var > 0 else None


def _district_calendars(
    rows: Sequence[tuple[str, date, float]],
    event_flags: np.ndarray,
) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Разложить признак события по сплошному календарю каждого района.

    Сдвиг для плацебо-теста обязан идти по календарю, а не по номерам строк:
    в ряду есть провал сбора данных 24.06–25.10.2025, и сдвиг на «семь строк»
    там означал бы скачок на месяцы и потерю привязки к дню недели.

    Returns:
        По одному кортежу на район: (позиции строк района в общей панели,
        флаги событий по сплошному календарю, индексы наблюдаемых дней внутри
        этого календаря).
    """
    grouped: dict[str, list[tuple[int, date, float]]] = {}
    for i, row in enumerate(rows):
        grouped.setdefault(row[0], []).append((i, row[1], float(event_flags[i])))

    calendars: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    for entries in grouped.values():
        entries.sort(key=lambda e: e[1])
        origin = entries[0][1]
        span = (entries[-1][1] - origin).days + 1
        calendar_flags = np.zeros(span)
        slots = np.array([(day - origin).days for _i, day, _flag in entries])
        calendar_flags[slots] = [flag for _i, _day, flag in entries]
        calendars.append((
            np.array([i for i, _day, _flag in entries]),
            calendar_flags,
            slots,
        ))
    return calendars


def _placebo_p_value(
    controls: np.ndarray,
    y: np.ndarray,
    event_flags: np.ndarray,
    rows: Sequence[tuple[str, date, float]],
    tau_observed: float,
    rounds: int,
    seed: int,
) -> float | None:
    """Перестановочный тест: доля случайных раскладок с эффектом не слабее наблюдённого.

    Календарь событий каждого района сдвигается по кругу на случайное число
    недель. Сдвиг целыми неделями сохраняет и длины серий событийных дней, и их
    привязку к дням недели — переносится только момент, когда серия случилась.
    Это тот же уровень, на котором событие «назначается» в реальности, поэтому
    тест нельзя обмануть ни многодневным фестивалем, ни перекосом событий к
    выходным. Поденная перестановка здесь не годится: она рассыпала бы месячный
    фестиваль на тридцать независимых дней и дала бы заведомо малое p.

    Коэффициент на каждой раскладке берётся по теореме Фриша — Во — Ловелла:
    и отклик, и сдвинутый признак очищаются от контрольных столбцов, после чего
    tau — обычная проекция одного остатка на другой. Это даёт тот же коэффициент,
    что полная переоценка, но без тысячи разложений матрицы.

    Разрешение p ограничено числом различных сдвигов: при истории в N недель
    оно не бывает меньше примерно 1/N на район.
    """
    if rounds <= 0:
        return None

    controls_pinv = np.linalg.pinv(controls)

    def residualize(v: np.ndarray) -> np.ndarray:
        return v - controls @ (controls_pinv @ v)

    y_res = residualize(y)
    calendars = _district_calendars(rows, event_flags)

    rng = np.random.default_rng(seed)
    hits = 0
    valid = 0
    for _ in range(rounds):
        permuted = np.empty_like(event_flags)
        for row_positions, calendar_flags, calendar_slots in calendars:
            weeks = max(calendar_flags.size // 7, 1)
            shift = int(rng.integers(0, weeks)) * 7
            permuted[row_positions] = np.roll(calendar_flags, shift)[calendar_slots]
        e_res = residualize(permuted)
        denom = float(e_res @ e_res)
        if denom <= 1e-12:
            continue
        valid += 1
        if abs(float(e_res @ y_res) / denom) >= abs(tau_observed):
            hits += 1

    if valid == 0:
        return None
    # Плюс единица в числителе и знаменателе: наблюдённая раскладка сама по себе
    # допустима при нулевой гипотезе, поэтому p строго больше нуля.
    return round((hits + 1) / (valid + 1), 4)


methodology_service = MethodologyService()
