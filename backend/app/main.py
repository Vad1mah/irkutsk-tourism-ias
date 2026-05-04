from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import hotels, events, query, forecast, documents, parser, analytics
from app.services.db_service import db_service
from app.services.chroma_service import chroma_service
from app.services.llm_service import llm_service
from app.services.cache_service import cache_service, build_ensemble_cache_key
from app.models.schemas import HealthResponse
from app.middleware.rate_limit import RateLimitMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _warmup_forecast_cache():
    """Прогрев ensemble-кэша для дефолтного района в фоне."""
    await asyncio.sleep(2)
    try:
        from app.services.data_service import data_service
        from app.services.weather_service import weather_service
        from app.services.ensemble_service import ensemble_service
        from app.constants import DEFAULT_DISTRICT
        from app.executor import run_sync
        from datetime import date, timedelta

        history = await data_service.get_occupancy_by_district(DEFAULT_DISTRICT)
        history_dicts = [
            {"date": r["date"], "occupancy": r["avg_occupancy"]}
            for r in history if r.get("avg_occupancy") is not None
        ]
        if len(history_dicts) < 14:
            logger.warning("Warmup: недостаточно данных для прогрева")
            return

        days = 14
        forecast_dates = [date.today() + timedelta(days=i) for i in range(days)]
        weather_data = await weather_service.get_weather_for_dates(forecast_dates)
        result = await run_sync(
            ensemble_service.forecast_ensemble,
            history_dicts, days, weather_data, None, None, "weighted_average",
        )
        points = result.get("ensemble", [])
        logger.info(f"Warmup: ensemble прогрев завершён, {len(points)} точек для {DEFAULT_DISTRICT}")

        key = build_ensemble_cache_key(district=DEFAULT_DISTRICT, days=days)
        if cache_service.is_connected:
            await cache_service.set(key, {
                "district": DEFAULT_DISTRICT,
                "history_points": len(history_dicts),
                "method": "weighted_average",
                "weights": result.get("weights", {}),
                "ensemble": [p.model_dump() if hasattr(p, "model_dump") else p for p in points],
                "models": {
                    name: [fp.model_dump() if hasattr(fp, "model_dump") else fp for fp in fps]
                    for name, fps in result.get("models", {}).items()
                },
            }, ttl=1800)
            logger.info("Warmup: результат сохранён в Redis")
    except Exception as e:
        logger.warning(f"Warmup failed (non-critical): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""
    # Startup
    logger.info("Starting services...")

    try:
        await db_service.connect()
        await db_service.create_tables()
        logger.info(f"PostgreSQL connected: {db_service.is_connected}")
    except Exception as e:
        logger.critical(f"PostgreSQL connection failed: {e}")
        raise

    try:
        await cache_service.connect()
        logger.info(f"Redis connected: {cache_service.is_connected}")
        if cache_service.is_connected and cache_service.client:
            app.state.redis_client = cache_service.client
            logger.info("Rate limiting middleware configured with Redis")
    except Exception as e:
        logger.warning(f"Redis connection failed (caching disabled): {e}")

    try:
        chroma_service.init()
    except Exception as e:
        logger.error(f"ChromaDB init failed (RAG will be degraded): {e}")

    llm_service.init()

    from app.scheduler import get_scheduler
    sched = get_scheduler()
    await sched.start(run_initial=False)
    logger.info("Scheduler started")

    logger.info("All services initialized")
    asyncio.create_task(_warmup_forecast_cache())
    yield

    # Shutdown
    logger.info("Shutting down services...")
    sched.stop()
    from app.executor import shutdown_executor
    shutdown_executor()
    from app.services.weather_service import weather_service
    await weather_service.close()
    await cache_service.close()
    await db_service.close()


app = FastAPI(
    title="Tourism Analytics API",
    description="API для аналитики туризма Иркутской области",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware порядок: LIFO - последний добавленный выполняется первым
# CORS должен быть последним в списке (первым в response)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

# Security headers
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    if "server" in response.headers:
        del response.headers["server"]
    return response

# Rate Limiting
app.add_middleware(RateLimitMiddleware, redis_client=None)

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    if settings.environment == "production":
        msg = "Некорректные входные данные"
    else:
        msg = str(exc)
        if any(s in msg.lower() for s in ["path", "traceback", "file", "\\", "/"]):
            msg = "Некорректные входные данные"
    return JSONResponse(status_code=400, content={"detail": msg})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"{request.method} {request.url.path} => {type(exc).__name__}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


app.include_router(hotels.router)
app.include_router(events.router)
app.include_router(query.router)
app.include_router(forecast.router)
app.include_router(documents.router)
app.include_router(parser.router)
app.include_router(analytics.router)


@app.get("/")
async def root():
    """Корневой эндпоинт API."""
    return {
        "name": "Tourism Analytics API",
        "version": "1.0.0",
        "description": "API для аналитики туризма Иркутской области",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Проверка состояния сервиса."""
    from app.services.data_service import data_service
    return HealthResponse(
        status="ok",
        db_backend="postgresql",
        db_connected=data_service.is_connected,
        redis_connected=cache_service.is_connected,
        chroma_docs=chroma_service.get_collection_count(),
    )
