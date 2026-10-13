from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.database.mongodb import predictions_collection
from app.deps.auth import get_current_user, require_owned_email
from app.models.schemas import ExamScorePredictionRequest, ExamScorePredictionResponse
from app.services.auth_service import AuthenticatedUser
from app.services.ml_service import get_model_metadata, predict_exam_score

router = APIRouter(prefix="/predict", tags=["Prediction"])


@router.post("/exam-score", response_model=ExamScorePredictionResponse)
def predict_score_endpoint(
    request: ExamScorePredictionRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Accepts student performance factors, evaluates using the trained ML pipeline,
    computes transparent academic risk, and logs prediction for the authenticated student.
    """
    try:
        feature_dict = request.model_dump()
        requested_email = feature_dict.pop("email", None)
        owner = require_owned_email(requested_email, current_user)

        result = predict_exam_score(feature_dict)

        if predictions_collection is not None:
            try:
                record = {
                    "email": owner,
                    "features": feature_dict,
                    "prediction": result["predicted_exam_score"],
                    "risk_assessment": result["risk_assessment"],
                    "model_used": result["model_used"],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                predictions_collection.insert_one(record)
            except Exception as db_err:
                print(f"Non-fatal error logging prediction to MongoDB: {type(db_err).__name__}")

        return result
    except HTTPException:
        raise
    except FileNotFoundError as fnf_err:
        raise HTTPException(status_code=503, detail=f"Model unavailable: {str(fnf_err)}") from fnf_err
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=f"Invalid prediction input: {str(val_err)}") from val_err
    except Exception as e:
        raise HTTPException(status_code=500, detail="Prediction failed.") from e


@router.get("/model-status")
def model_status_endpoint():
    """Returns the trained model status, evaluated test metrics, and feature lists."""
    try:
        metadata = get_model_metadata()
        return {
            "status": "ready",
            "model_name": metadata.get("selected_model", "RidgeRegression"),
            "test_metrics": metadata.get("selected_model_metrics", {}),
            "all_compared_models": metadata.get("metrics_comparison", {}),
            "features_required": {
                "numeric": metadata.get("numeric_features", []),
                "categorical": metadata.get("categorical_features", []),
            },
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


@router.get("/history/me")
def get_my_prediction_history(current_user: AuthenticatedUser = Depends(get_current_user)):
    return get_prediction_history(current_user.email, current_user)


@router.get("/history/{email}")
def get_prediction_history(
    email: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Retrieves previous predictions and risk assessments for the authenticated student."""
    owner = require_owned_email(email, current_user)
    if predictions_collection is None:
        return {"email": owner, "predictions": []}

    records = list(
        predictions_collection.find({"email": owner}, {"_id": 0})
        .sort("created_at", -1)
        .limit(10)
    )
    return {"email": owner, "predictions": records}
