# =============================================================================
# Stage 1: builder — компиляция C-расширений и сборка wheels
# =============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# CPU-only torch (без CUDA/cuDNN/NCCL, экономит ~3-4 GB).
# Основной index — pytorch CPU-канал, fallback на PyPI для остального.
# Так pip предпочитает torch+cpu, а neuralprophet/holidays/etc. берёт с PyPI.
ENV PIP_INDEX_URL=https://download.pytorch.org/whl/cpu
ENV PIP_EXTRA_INDEX_URL=https://pypi.org/simple

RUN pip install --upgrade pip==24.3.1 wheel==0.45.1 && \
    pip wheel --no-cache-dir --wheel-dir=/wheels -r requirements.txt

# =============================================================================
# Stage 2: runtime — production-образ без компилятора
# =============================================================================
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
RUN pip install --upgrade pip==24.3.1 && \
    pip install --no-cache-dir --no-index --find-links=/wheels /wheels/*.whl && \
    rm -rf /wheels

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
