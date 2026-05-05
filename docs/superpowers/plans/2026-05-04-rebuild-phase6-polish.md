# Phase 6: Polish & Final Defense Materials

**Goal:** Финальная подготовка к защите — синхронизация презентации с актуальными числами, генерация .drawio диаграмм, persona walkthrough тест UI, рекомендация merge-стратегии.

## Tasks

### P6-A: Презентация — синхронизация чисел

Обновить:
- `docs/presentation/PREZENTACIYA_VKR.md` — основная презентация ВКР (числа, новые tools, новые endpoint'ы, рамки).
- `docs/presentation/PREZENTACIYA_S_RECHYU.md` — речь по слайдам (синхронизировать).
- `docs/presentation/text_zashity.txt` — текст защиты (числа).

Изменения:
- Tools агента: 5/6 → **12**.
- Endpoint'ов: 59/63 → **67**.
- Тестов: 104/106 → **207**.
- Сервисов: 16 → **19** (+ MethodologyService, ParserHealthService, и др.).
- Парсеры: 8 → **17 файлов** (включая base.py, ai_extractor.py, anti_detection.py).
- Добавить упоминание B2B-rebuild фаз и MethodologyService.

### P6-B: .drawio XML генерация

Генерация `mxGraph` XML для:
- `models/UC/use_case_b2b_v2.drawio` — обновлённая диаграмма с UC1-UC12.
- `models/DOMAIN/domain_b2b_v2.drawio` — с 5 новыми сущностями.
- `models/SEQUENCE/uc11_sequence.drawio` — sequence для UC11.

Используем минимальный mxGraph XML — без сложного layout, simple boxes + arrows. Достаточно для отчёта.

### P6-C: Persona walkthrough тест

Создать `backend/tests/test_persona_walkthrough.py`:
- Mock-based тесты симулирующие 3 типичных запроса каждой персоны (отельер, администрация, исследователь).
- Каждый тест: создаёт запрос, проверяет что endpoint возвращает 200 + структура ответа имеет ключевые поля для персоны.

### P6-D: Финальный отчёт + merge guide

Создать `docs/MERGE_GUIDE.md` — пошаговая инструкция по merge всех 5 веток в master.
