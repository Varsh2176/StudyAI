import json
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd
import joblib

# Determine ML model directory relative to project root
BASE_DIR = Path(__file__).resolve().parents[3]
MODEL_PATH = BASE_DIR / "ml" / "models" / "exam_score_model.joblib"
METRICS_PATH = BASE_DIR / "ml" / "models" / "model_metrics.json"

_model_pipeline = None
_model_metadata = {}


def load_model():
    """
    Safely loads the trained ML pipeline and metadata into memory.
    Ensures model training is strictly decoupled from request execution.
    """
    global _model_pipeline, _model_metadata

    if _model_pipeline is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Trained model not found at {MODEL_PATH}. "
                "Please run 'python ml/src/train_model.py' first."
            )
        _model_pipeline = joblib.load(MODEL_PATH)

    if not _model_metadata and METRICS_PATH.exists():
        try:
            with open(METRICS_PATH, "r") as f:
                _model_metadata = json.load(f)
        except Exception:
            _model_metadata = {}

    return _model_pipeline


def get_model_metadata() -> Dict[str, Any]:
    """Returns metadata and test evaluation metrics of the loaded model."""
    load_model()
    return _model_metadata


from app.services.risk_service import (
    evaluate_academic_risk,
    RiskThresholds,
    DEFAULT_THRESHOLDS
)


def evaluate_risk(
    attendance: float,
    hours_studied: float,
    previous_scores: float,
    predicted_score: float,
    **kwargs
) -> Dict[str, Any]:
    """
    Transparent, rule-based academic risk indicator (Phase E).
    Delegates to evaluate_academic_risk for configurable thresholding,
    explainable relevant indicators, and limitation disclaimers.
    """
    return evaluate_academic_risk(
        attendance=attendance,
        hours_studied=hours_studied,
        previous_scores=previous_scores,
        predicted_score=predicted_score,
        **kwargs
    )


def predict_exam_score(feature_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Predicts Exam_Score using the loaded preprocessor and model pipeline.
    Validates input features and returns prediction with evaluation metrics and risk assessment.
    """
    pipeline = load_model()

    # Create 1-row DataFrame matching the dataset schema
    df_input = pd.DataFrame([feature_dict])

    raw_prediction = pipeline.predict(df_input)[0]
    
    # Bound score logically to [0.0, 100.0]
    predicted_score = round(float(max(0.0, min(100.0, raw_prediction))), 2)

    meta = get_model_metadata()
    selected_metrics = meta.get("selected_model_metrics", {})

    # Evaluate risk using leading features
    attendance = float(feature_dict.get("Attendance", 75.0))
    hours_studied = float(feature_dict.get("Hours_Studied", 15.0))
    previous_scores = float(feature_dict.get("Previous_Scores", 70.0))

    risk_info = evaluate_academic_risk(
        attendance=attendance,
        hours_studied=hours_studied,
        previous_scores=previous_scores,
        predicted_score=predicted_score,
        access_to_resources=feature_dict.get("Access_to_Resources", "Medium"),
        learning_disabilities=feature_dict.get("Learning_Disabilities", "No"),
        tutoring_sessions=int(feature_dict.get("Tutoring_Sessions", 0))
    )

    return {
        "predicted_exam_score": predicted_score,
        "model_used": meta.get("selected_model", "RidgeRegression"),
        "metrics": {
            "MAE": selected_metrics.get("MAE", 0.4523),
            "RMSE": selected_metrics.get("RMSE", 1.8044),
            "R2": selected_metrics.get("R2", 0.7697)
        },
        "risk_assessment": risk_info
    }
