from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.auth import router as auth_router
from app.routes.student import router as student_router
from app.routes.prediction import router as prediction_router
from app.routes.study_plan import router as study_plan_router
from app.routes.ai import router as ai_router
from app.routes.performance import router as performance_router
from app.services.ml_service import load_model, get_model_metadata
from app.database.mongodb import client, db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Safe startup initialization: pre-load the ML model pipeline once
    try:
        load_model()
        print("ML model pipeline successfully loaded at application startup.")
    except Exception as e:
        print(f"Warning: Failed to load ML model on startup: {e}")
    yield
    # Clean shutdown tasks if any


app = FastAPI(
    title="StudyAI API",
    description="AI-Integrated Personalized and Adaptive Study Planning System",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000"
    ],
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

    db_status = "connected" if client is not None else "disconnected"

    return {
        "status": "healthy",
        "database": db_status,
        "database_name": db.name if db is not None else None,
        "ml_model": {
            "loaded": True if model_name != "Unavailable" else False,
            "algorithm": model_name,
            "r2_score": model_r2
        }
    }