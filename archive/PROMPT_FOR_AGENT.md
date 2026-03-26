# 🤖 ИНСТРУКЦИЯ ДЛЯ АГЕНТА (копировать в начало чата)

---

## Для SBER AI проекта

Скопировать в новый чат:

```
НОВЫЙ ПРОЕКТ: [название]

Тип: Sber AI проект
Стек: GigaChat API, FastAPI, Python

Описание: [что делает проект]

ЗАДАЧА: Подготовь окружение проекта:
1. Создай папку .cursor/rules/
2. Создай project-context.mdc с описанием проекта и стеком (GigaChat-2-Max, FastAPI)
3. Создай gigachat-prompts.mdc с правилами промптов (Markdown формат: ### Роль, ### Задача, #### Инструкция, #### Формат ответа, #### Пример, #### Примечание)
4. Создай fastapi-best-practices.mdc
5. Создай .cursorignore (venv, __pycache__, .env, node_modules)
6. Создай venv и requirements.txt с базовыми зависимостями

После этого начнём работу над проектом.
```

---

## Для НЕ Sber проекта

Скопировать в новый чат:

```
НОВЫЙ ПРОЕКТ: [название]

Тип: НЕ Sber (игнорировать дефолтный GigaChat стек)
Стек: [OpenAI / Anthropic / OpenRouter], FastAPI, Python

Описание: [что делает проект]

ЗАДАЧА: Подготовь окружение проекта:
1. Создай папку .cursor/rules/
2. Создай project-context.mdc — ВАЖНО: указать что проект НЕ использует GigaChat
3. Создай fastapi-best-practices.mdc
4. Создай .cursorignore (venv, __pycache__, .env, node_modules)
5. Создай venv и requirements.txt

После этого начнём работу над проектом.
```

---

## Для React + FastAPI проекта

Скопировать в новый чат:

```
НОВЫЙ ПРОЕКТ: [название]

Тип: Fullstack (React + FastAPI)
Стек: [GigaChat / OpenAI], FastAPI, React, TypeScript, TailwindCSS

Описание: [что делает проект]

ЗАДАЧА: Подготовь окружение:
1. Создай структуру:
   - backend/ (FastAPI)
   - frontend/ (React)
   - .cursor/rules/
2. Создай project-context.mdc
3. Создай fastapi-best-practices.mdc
4. Создай react-best-practices.mdc
5. Создай typescript-best-practices.mdc
6. Создай .cursorignore
7. Инициализируй backend (venv, requirements.txt)
8. Инициализируй frontend (npm create vite)

После этого начнём работу.
```

---

## Для продолжения работы (существующий проект)

Скопировать в новый чат:

```
ПРОДОЛЖАЕМ ПРОЕКТ: [название]

Стек: [описание стека]

Что уже сделано: [кратко]

ТЕКУЩАЯ ЗАДАЧА: [что нужно сделать]

Сначала изучи структуру проекта и существующий код, потом приступай к задаче.
```

---

# 📋 ЧТО АГЕНТ СОЗДАСТ АВТОМАТИЧЕСКИ

| Файл | Содержимое |
|------|------------|
| `.cursor/rules/project-context.mdc` | Описание проекта, стек, ограничения |
| `.cursor/rules/gigachat-prompts.mdc` | Правила промптов для GigaChat |
| `.cursor/rules/fastapi-best-practices.mdc` | Правила FastAPI |
| `.cursor/rules/react-best-practices.mdc` | Правила React (если нужно) |
| `.cursorignore` | Исключения для индексации |
| `venv/` | Виртуальное окружение |
| `requirements.txt` | Зависимости Python |

---

# 💡 ПОДСКАЗКИ

- Агент сам знает правила из User Rules
- Агент сам использует context7 для актуальной документации
- Агент сам создаст нужные файлы по инструкции
- Тебе нужно только скопировать промпт и описать проект
