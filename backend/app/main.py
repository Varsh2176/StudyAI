from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.auth import router as auth_router
from app.routes.student import router as student_router
from app.routes.prediction import router as prediction_router
from app.routes.study_plan import router as study_plan_router
from app.routes.ai import router as ai_router
from app.routes.performance import router as performance_router
from app.routes.documents import router as documents_router
from app.services.ml_service import load_model, get_model_metadata
from app.database.mongodb import (
    close_mongo_client,
    db,
    diagnose_mongodb_connectivity,
    get_database_status_summary,
)


# Local-development CORS defaults. Production must set CORS_ORIGINS explicitly.
_DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:3000",
]


def _is_production_env() -> bool:
    env = (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "development").strip().lower()
    return env in {"production", "prod"}


def get_cors_origins() -> list[str]:
    """
    Comma-separated CORS_ORIGINS from the environment, or local-dev defaults.

    M11: In production/prod, CORS_ORIGINS is required. Missing or empty values
    fail closed (empty allow-list) instead of falling back to localhost.
    Example production value: https://app.example.com,https://www.example.com
    """
    raw = (os.getenv("CORS_ORIGINS") or "").strip()
    if not raw:
        if _is_production_env():
            print(
                "WARNING: APP_ENV is production but CORS_ORIGINS is unset. "
                "Browser cross-origin requests will be denied until CORS_ORIGINS is configured."
            )
            return []
        return list(_DEFAULT_CORS_ORIGINS)
    origins = [part.strip() for part in raw.split(",") if part.strip()]
    if not origins:
        if _is_production_env():
            return []
        return list(_DEFAULT_CORS_ORIGINS)
    # Reject wildcard allow-all which is incompatible with credentialed apps.
    if any(origin == "*" for origin in origins):
        print("WARNING: CORS_ORIGINS must not include '*'. Ignoring wildcard entry.")
        origins = [o for o in origins if o != "*"]
        if not origins and _is_production_env():
            return []
    return origins


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Safe startup initialization: pre-load the ML model pipeline once
    try:
        load_model()
        print("ML model pipeline successfully loaded at application startup.")
    except Exception as e:
        print(f"Warning: Failed to load ML model on startup: {e}")
    yield
    # Close MongoClient on shutdown (safe no-op if already closed via atexit).
    close_mongo_client()


app = FastAPI(
    title="StudyAI API",
    description="AI-Integrated Personalized and Adaptive Study Planning System",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration — restrict to configured frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(auth_router)
app.include_router(student_router)
app.include_router(prediction_router)
app.include_router(study_plan_router)
app.include_router(ai_router)
app.include_router(performance_router)
app.include_router(documents_router)


@app.get("/")
def root():
    return {
        "message": "StudyWise AI API is running",
        "version": "1.0.0"
    }


@app.get("/health")
def health():
    meta = get_model_metadata()
    model_name = meta.get("selected_model", "Unavailable")
    model_r2 = meta.get("selected_model_metrics", {}).get("R2", None)
    db_summary = get_database_status_summary()

    return {
        "status": "healthy",
        "database": db_summary.get("database"),
        "database_failure_stage": db_summary.get("failure_stage"),
        "database_detail": db_summary.get("detail"),
        "database_name": db.name if db is not None else None,
        "ml_model": {
            "loaded": True if model_name != "Unavailable" else False,
            "algorithm": model_name,
            "r2_score": model_r2
        }
    }


@app.get("/health/database")
def health_database():
    """
    Safe staged MongoDB connectivity diagnostic.
    Reports failure stage without exposing URI or credentials.
    """
    return diagnose_mongodb_connectivity()