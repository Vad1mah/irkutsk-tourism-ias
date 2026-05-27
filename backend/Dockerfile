# Single-stage build для GitHub Actions runner (14 GB RAM, 70 GB SSD).
# Раньше был multi-stage с pip wheel → pip install --no-index, но удаление
# nvidia_*.whl ломало dependency resolution для torch (его метаданные требуют
# nvidia-cudnn-cu12 даже на CPU-варианте). Теперь pip install напрямую с
# PIP_INDEX_URL на pytorch CPU-канал — резолверу доступны все nvidia-stub
# wheel'ы которые отсутствуют в CPU-канале и просто пропускаются.
FROM python:3.11-slim

WORKDIR /app

# CPU-only torch (без CUDA/cuDNN/NCCL, экономит ~3-4 GB в финальном образе).
# pytorch.org CPU-канал содержит torch+cpu без транзитивных nvidia-* зависимостей.
ENV PIP_INDEX_URL=https://download.pytorch.org/whl/cpu
ENV PIP_EXTRA_INDEX_URL=https://pypi.org/simple
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Build deps нужны для компиляции C-расширений некоторых пакетов (numpy/pandas
# обычно binary wheels, но holidays и пара других могут требовать).
# Runtime deps: curl для healthcheck, libstdc++6 для XGBoost/LightGBM.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ libffi-dev libssl-dev \
        curl libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip==24.3.1 wheel==0.45.1 && \
    pip install -r requirements.txt && \
    # Очистка build-deps после установки python пакетов — экономит ~250 MB
    apt-get purge -y --auto-remove gcc g++ libffi-dev libssl-dev && \
    rm -rf /var/lib/apt/lists/* /root/.cache

COPY app/ /app/app/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/alembic.ini
COPY scripts/ /app/scripts/

ENV PYTHONPATH=/app

RUN useradd -r -u 1001 -s /bin/false appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
