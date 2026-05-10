# Аудит и переоформление списка источников ВКР

Документ: `docs/vkr/OTCHET_PO_PRAKTIKE.docx` (53 источника).
Эталон оформления: `Отчёт предипломной практики ПЕТЯ.docx` + правило пользователя для электронных ресурсов.

---

## 1. Обнаруженные ошибки в выходных данных (ПОДТВЕРЖДЕНО ПРОВЕРКОЙ)

| # | Запись в ВКР | Реальные данные | Источник проверки |
|---|--------------|-----------------|-------------------|
| **19** | Few S. — Burlingame, **261 p.** | **260 p.** (ISBN 978-1938377006) | Amazon, Chegg, AbeBooks |
| **20** | Norman D. A. — **347 p.** | **368 p.** (Basic Books, ISBN 978-0465050659) | Hachette, Amazon |
| **27** | Phillips R. L. — **384 p.** | **355 p.** (Stanford UP, ISBN 0-8047-4698-2) | Stanford UP, Amazon, archive.org |
| **28** | Kimes S. E. — Vol. 44, **No. 5–6** | Vol. 44, **Issue 5** (одинарный) | SAGE, Cornell scholarship.sha |
| **29** | Cross R. G. — **304 p.** | **xii + 276 = 288 p.** (ISBN 0767900332) | Amazon, archive.org, Biblio |
| **39** | Wedel M. — **Boston : Springer, 432 p.** | **Norwell : Kluwer Academic Publishers, 382 p.** | Springer, SciRP, J. of Classification |
| **49** | Zheng A., Casari A. — **218 p.** | **215 p.** | scoping data |

### Отдельный случай — [27] Phillips: цитата не соответствует источнику

В тексте ВКР:
> «Концепция управления выручкой, сформулированная **Робертом Крэндаллом и Питером Белобабой** в American Airlines, легла в основу всех последующих систем управления доходностью [27]».

Phillips R. L. (2005) — общий обзор по Pricing & Revenue Optimization, **не** первоисточник про Crandall/Belobaba.
Первоисточник: **Belobaba P. P.** *Air Travel Demand and Airline Seat Inventory Management.* — PhD thesis, MIT, 1987 (Flight Transportation Lab Report R87-7), URL: `https://dspace.mit.edu/handle/1721.1/14800`.

**Рекомендации (на выбор):**

а) Заменить [27] на Belobaba 1987 (правильный первоисточник).
б) Оставить Phillips, но изменить формулировку в тексте, чтобы она соответствовала тому, что у Phillips действительно есть (общая теория ценообразования и оптимизации выручки).
в) Добавить **оба** источника: ввести новый номер `[27a]` или переместить нумерацию — Belobaba как первоисточник + Phillips как обзорная монография.

---

## 2. Проверенные источники без замечаний

| # | Запись | Подтверждено |
|---|--------|--------------|
| 3 | Иванов В. В., Волов А. Б. — ИНФРА-М, 2007, 384 с. | ✅ ISBN 978-5-16-003073-9 |
| 17 | Tufte E. R. *VDQI*, 2nd ed., Cheshire : Graphics Press, 2001, 197 p. | ✅ ISBN 9780961392147 |
| 18 | Tufte E. R. *Envisioning Information*, 1990, 126 p. | ✅ ISBN 9780961392116 |
| 23 | Shneiderman B., IEEE VL 1996, P. 336–343 | ✅ DOI 10.1109/VL.1996.545307 |
| 30 | Box G. E. P., Jenkins G. M., …, Wiley, 5th ed., 2015, 712 p. | ✅ ISBN 978-1-118-67502-1 |
| 31 | Taylor S. J., Letham B., *American Statistician*, 72(1), 37–45, 2018 | ✅ DOI 10.1080/00031305.2017.1380080 |
| 33 | Chen T., Guestrin C., KDD 2016, P. 785–794 | ✅ DOI 10.1145/2939672.2939785 |
| 38 | Christensen et al., HarperBusiness 2016, 288 p. | ✅ ISBN 9780062435613 |
| 51 | Rosenfeld L., Morville P., O'Reilly, 3rd ed., 2006, 504 p. | ✅ ISBN 9780596527341 |

Источники 32 (Triebe NeuralProphet arXiv) и 34 (Dietterich MCS 2000) — формат стандартный, выходные данные публично известны, сохраняем как есть.

---

## 3. Типы источников у нас vs у Пети

У Пети в примере ровно три типа:
- A — англоязычная статья из proceedings конференции;
- B — переводная книга на русском;
- C — электронный ресурс (статья в онлайн-журнале).

**Типы, которые есть у нас, но НЕ показаны в примере Пети:**

| Тип | У нас номера | Эталонный шаблон |
|-----|--------------|------------------|
| 1. Учебное пособие на русском | 3 | `Фамилия И. О. Название : учебное пособие / И. О. Фамилия, И. О. Соавтор. — Город : Издательство, Год. — N с.` |
| 2. Нормативный документ / стратегия органа власти | 1 | `Название документа [Электронный ресурс] : утверждена … // Сайт ведомства. — URL: … (дата обращения: …).` |
| 3. Внутренний материал / рукопись проекта | 2 | `Название работы : материалы исследования в рамках проекта / И. О. Фамилия. — Город, Год.` |
| 4. Препринт arXiv | 32 | `Фамилия И. О. Название / И. О. Фамилия [и др.]. — arXiv preprint arXiv:NNNN.NNNNN. — Год.` |
| 5. Документация ПО (онлайн) — большинство наших ресурсов | 6, 9–15, 24–26, 36, 37, 44–48, 50, 52, 53 | `Документация Х // Х [Электронный ресурс]. — URL: … (дата обращения: …).` |
| 6. Государственный/отраслевой веб-портал | 4, 5, 40, 41, 42, 43 | то же, но "Источник" — название организации |
| 7. Англоязычная книга-монография | 17–20, 27, 29, 30, 38, 39, 49, 51 | `Surname N. Title / N. Surname. — City : Publisher, Year. — N p.` |
| 8. Статья в реферируемом журнале на английском | 28, 31 | `Surname N. Title / N. Surname // Journal. — Year. — Vol. NN, No. N. — P. NN–NN.` |

**У Пети вообще нет:** учебных пособий, нормативных документов, внутренних рукописей, препринтов arXiv, документации ПО — для них использован адаптированный ГОСТ-шаблон.

---

## 4. Шаблоны, которые я применил

Все элементы выровнены под пример Пети там, где он применим. Где у Пети шаблона не было — взят ГОСТ Р 7.0.100–2018 «Библиографическая запись. Библиографическое описание».

### 4.1. Книга / монография

**Один автор (англ.):**
```
Phillips R. L. Pricing and Revenue Optimization / R. L. Phillips. — Stanford : Stanford University Press, 2005. — 355 p.
```

**Два автора:**
```
Rosenfeld L. Information Architecture for the World Wide Web / L. Rosenfeld, P. Morville. — 3rd ed. — Sebastopol : O'Reilly Media, 2006. — 504 p.
```

**Учебное пособие на русском:**
```
Иванов В. В. Гостиничный менеджмент : учебное пособие / В. В. Иванов, А. Б. Волов. — М. : ИНФРА-М, 2007. — 384 с.
```

### 4.2. Статья в журнале / proceedings (как у Пети)

```
Kimes S. E. Revenue Management: A Retrospective / S. E. Kimes // Cornell Hotel and Restaurant Administration Quarterly. — 2003. — Vol. 44, No. 5. — P. 131–138.
```
```
Chen T. XGBoost: A Scalable Tree Boosting System / T. Chen, C. Guestrin // Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining. — 2016. — P. 785–794.
```

### 4.3. Электронный ресурс (правило пользователя)

Формула: `Название // Источник [Электронный ресурс]. — URL: … (дата обращения: DD.MM.YYYY).`

Если у материала есть автор — он перед заголовком: `Фамилия И. О. Название / И. О. Фамилия // Источник [Электронный ресурс]. — URL: …`

```
Документация FastAPI // FastAPI [Электронный ресурс]. — URL: https://fastapi.tiangolo.com/ (дата обращения: 20.03.2026).
```
```
Nielsen J. 10 Usability Heuristics for User Interface Design / J. Nielsen // Nielsen Norman Group [Электронный ресурс]. — URL: https://www.nngroup.com/articles/ten-usability-heuristics/ (дата обращения: 25.03.2026).
```

### 4.4. Препринт arXiv

```
Triebe O. NeuralProphet: Explainable Forecasting at Scale / O. Triebe [и др.]. — arXiv preprint arXiv:2111.15397. — 2021.
```

### 4.5. Нормативный документ органа власти (электронный)

```
Стратегия развития туризма Иркутской области на период до 2030 года : утверждена распоряжением Правительства Иркутской области // Министерство туризма Иркутской области [Электронный ресурс]. — URL: https://irkobl.ru/sites/tour/ (дата обращения: 15.03.2026).
```

---

## 5. ПЕРЕОФОРМЛЕННЫЙ СПИСОК ИСТОЧНИКОВ (53 шт.)

> Ошибочные значения исправлены согласно §1. Все электронные ресурсы переведены в формат пользователя.

1. Стратегия развития туризма Иркутской области на период до 2030 года : утверждена распоряжением Правительства Иркутской области // Министерство туризма Иркутской области [Электронный ресурс]. — URL: https://irkobl.ru/sites/tour/ (дата обращения: 15.03.2026).
2. Исполатов В. П. Анализ программных интерфейсов российских агрегаторов бронирования средств размещения : материалы исследования в рамках проекта / В. П. Исполатов. — Иркутск, 2025.
3. Иванов В. В. Гостиничный менеджмент : учебное пособие / В. В. Иванов, А. Б. Волов. — М. : ИНФРА-М, 2007. — 384 с.
4. Паспорт туристского кластера Иркутской области : утверждён Агентством по туризму Иркутской области // Министерство туризма Иркутской области [Электронный ресурс]. — URL: https://irkobl.ru/sites/tour/utp.php (дата обращения: 25.03.2026).
5. Аналитика индустрии гостеприимства // STR Global [Электронный ресурс]. — URL: https://str.com/ (дата обращения: 18.03.2026).
6. Документация сервиса визуализации данных // Yandex DataLens [Электронный ресурс]. — URL: https://cloud.yandex.ru/docs/datalens/ (дата обращения: 20.03.2026).
7. Hotel Price Monitor and API // Xotelo [Электронный ресурс]. — URL: https://xotelo.com/ (дата обращения: 22.03.2026).
8. Бесплатный API погодных данных // Open-Meteo [Электронный ресурс]. — URL: https://open-meteo.com/ (дата обращения: 22.03.2026).
9. Документация фреймворка FastAPI // FastAPI [Электронный ресурс]. — URL: https://fastapi.tiangolo.com/ (дата обращения: 20.03.2026).
10. PostgreSQL 16 Documentation // PostgreSQL Global Development Group [Электронный ресурс]. — URL: https://www.postgresql.org/docs/16/ (дата обращения: 20.03.2026).
11. asyncpg : асинхронный драйвер PostgreSQL для Python // Python Package Index [Электронный ресурс]. — URL: https://pypi.org/project/asyncpg/ (дата обращения: 20.03.2026).
12. Документация Redis // Redis Ltd. [Электронный ресурс]. — URL: https://redis.io/docs/ (дата обращения: 22.03.2026).
13. Документация веб-сервера nginx // nginx [Электронный ресурс]. — URL: https://nginx.org/ru/docs/ (дата обращения: 21.03.2026).
14. Документация библиотеки планирования задач APScheduler // APScheduler [Электронный ресурс]. — URL: https://apscheduler.readthedocs.io/ (дата обращения: 19.03.2026).
15. API Security Top 10 // OWASP Foundation [Электронный ресурс]. — URL: https://owasp.org/API-Security/ (дата обращения: 23.03.2026).
16. State of JavaScript 2025 : ежегодное исследование экосистемы JavaScript // Devographics [Электронный ресурс]. — URL: https://stateofjs.com/ (дата обращения: 20.03.2026).
17. Tufte E. R. The Visual Display of Quantitative Information / E. R. Tufte. — 2nd ed. — Cheshire : Graphics Press, 2001. — 197 p.
18. Tufte E. R. Envisioning Information / E. R. Tufte. — Cheshire : Graphics Press, 1990. — 126 p.
19. Few S. Information Dashboard Design: Displaying Data for At-a-Glance Monitoring / S. Few. — 2nd ed. — Burlingame : Analytics Press, 2013. — **260 p.**
20. Norman D. A. The Design of Everyday Things / D. A. Norman. — Revised and Expanded ed. — New York : Basic Books, 2013. — **368 p.**
21. Nielsen J. 10 Usability Heuristics for User Interface Design / J. Nielsen // Nielsen Norman Group [Электронный ресурс]. — URL: https://www.nngroup.com/articles/ten-usability-heuristics/ (дата обращения: 25.03.2026).
22. Frost B. Atomic Design : методология проектирования интерфейсных систем / B. Frost // Atomic Design [Электронный ресурс]. — URL: https://atomicdesign.bradfrost.com/ (дата обращения: 25.03.2026).
23. Shneiderman B. The Eyes Have It: A Task by Data Type Taxonomy for Information Visualizations / B. Shneiderman // Proceedings of the IEEE Symposium on Visual Languages. — 1996. — P. 336–343.
24. Документация сборщика Vite // Vite [Электронный ресурс]. — URL: https://vite.dev/ (дата обращения: 20.03.2026).
25. Документация CSS-фреймворка Tailwind CSS // Tailwind Labs [Электронный ресурс]. — URL: https://tailwindcss.com/docs (дата обращения: 20.03.2026).
26. Recharts : библиотека графиков для React // Recharts [Электронный ресурс]. — URL: https://recharts.org/ (дата обращения: 21.03.2026).
27. Phillips R. L. Pricing and Revenue Optimization / R. L. Phillips. — Stanford : Stanford University Press, 2005. — **355 p.** *(см. также §1: первоисточник для цитаты в тексте — Belobaba 1987)*
28. Kimes S. E. Revenue Management: A Retrospective / S. E. Kimes // Cornell Hotel and Restaurant Administration Quarterly. — 2003. — Vol. 44, **No. 5**. — P. 131–138.
29. Cross R. G. Revenue Management: Hard-Core Tactics for Market Domination / R. G. Cross. — New York : Broadway Books, 1997. — **288 p.**
30. Box G. E. P. Time Series Analysis: Forecasting and Control / G. E. P. Box, G. M. Jenkins, G. C. Reinsel, G. M. Ljung. — 5th ed. — Hoboken : Wiley, 2015. — 712 p.
31. Taylor S. J. Forecasting at Scale / S. J. Taylor, B. Letham // The American Statistician. — 2018. — Vol. 72, No. 1. — P. 37–45.
32. Triebe O. NeuralProphet: Explainable Forecasting at Scale / O. Triebe [и др.]. — arXiv preprint arXiv:2111.15397. — 2021.
33. Chen T. XGBoost: A Scalable Tree Boosting System / T. Chen, C. Guestrin // Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining. — 2016. — P. 785–794.
34. Dietterich T. G. Ensemble Methods in Machine Learning / T. G. Dietterich // Proceedings of the First International Workshop on Multiple Classifier Systems (MCS 2000). — Berlin : Springer, 2000. — P. 1–15.
35. Документация фреймворка LangGraph для построения агентов на графах состояний // LangChain [Электронный ресурс]. — URL: https://www.langchain.com/langgraph (дата обращения: 22.03.2026).
36. Платформа быстрого инференса LLM // Groq [Электронный ресурс]. — URL: https://groq.com/ (дата обращения: 22.03.2026).
37. Документация API // Mistral AI [Электронный ресурс]. — URL: https://docs.mistral.ai/ (дата обращения: 23.03.2026).
38. Christensen C. M. Competing Against Luck: The Story of Innovation and Customer Choice / C. M. Christensen, T. Hall, K. Dillon, D. S. Duncan. — New York : HarperBusiness, 2016. — 288 p.
39. Wedel M. Market Segmentation: Conceptual and Methodological Foundations / M. Wedel, W. A. Kamakura. — 2nd ed. — **Norwell : Kluwer Academic Publishers**, 2000. — **382 p.**
40. Туризм — статистика по Иркутской области // Федеральная служба государственной статистики (Росстат) [Электронный ресурс]. — URL: https://rosstat.gov.ru/ (дата обращения: 15.03.2026).
41. STR Global Hotel Benchmarking Glossary : методические материалы // CoStar Group [Электронный ресурс]. — URL: https://str.com/data-insights/glossary (дата обращения: 06.05.2026).
42. AirDNA : аналитическая платформа данных краткосрочной аренды // AirDNA [Электронный ресурс]. — URL: https://www.airdna.co/ (дата обращения: 25.03.2026).
43. Электронная путёвка : Единая информационная система электронных путёвок (ЕИСЭП) // Министерство экономического развития РФ [Электронный ресурс]. — URL: https://ev.economy.gov.ru/ (дата обращения: 25.03.2026).
44. Документация библиотеки React // Meta [Электронный ресурс]. — URL: https://react.dev/ (дата обращения: 20.03.2026).
45. Docker Documentation // Docker, Inc. [Электронный ресурс]. — URL: https://docs.docker.com/ (дата обращения: 21.03.2026).
46. Документация ORM SQLAlchemy 2.0 // SQLAlchemy [Электронный ресурс]. — URL: https://docs.sqlalchemy.org/en/20/ (дата обращения: 19.03.2026).
47. Документация библиотеки асинхронных HTTP-запросов aiohttp // aio-libs [Электронный ресурс]. — URL: https://docs.aiohttp.org/ (дата обращения: 18.03.2026).
48. 101Hotels.com : агрегатор средств размещения // 101 Hotels [Электронный ресурс]. — URL: https://www.101hotels.com/ (дата обращения: 25.03.2026).
49. Zheng A. Feature Engineering for Machine Learning: Principles and Techniques for Data Scientists / A. Zheng, A. Casari. — Sebastopol : O'Reilly Media, 2018. — **215 p.**
50. Документация векторной базы данных ChromaDB // Chroma [Электронный ресурс]. — URL: https://docs.trychroma.com/ (дата обращения: 21.03.2026).
51. Rosenfeld L. Information Architecture for the World Wide Web / L. Rosenfeld, P. Morville. — 3rd ed. — Sebastopol : O'Reilly Media, 2006. — 504 p.
52. Документация библиотеки управления серверным состоянием TanStack Query // TanStack [Электронный ресурс]. — URL: https://tanstack.com/query/ (дата обращения: 22.03.2026).
53. Apache ECharts : библиотека визуализации данных // The Apache Software Foundation [Электронный ресурс]. — URL: https://echarts.apache.org/ (дата обращения: 21.03.2026).

---

## 6. Что от вас требуется решить

1. **По [27] Phillips ↔ Belobaba** — выбрать вариант (а / б / в) из §1.
2. **Применить правки** в `OTCHET_PO_PRAKTIKE.docx` — могу автоматически прогнать заменой через python-docx, если дадите команду.
3. Подтвердить, что **формула «Название // Источник [Электронный ресурс]. — URL: …»** меня правильно интерпретирована (два варианта см. §4.3).
