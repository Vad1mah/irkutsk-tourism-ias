# Dockerfile для парсеров ИАС Туризм
FROM python:3.11-slim

WORKDIR /app

# Системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Python зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright для браузерных парсеров
RUN playwright install chromium
RUN playwright install-deps chromium

# Копируем код
COPY app/ ./app/

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV DB_BACKEND=postgresql

# Точка входа для запуска конкретного парсера
ENTRYPOINT ["python", "-m", "app.parsers"]
