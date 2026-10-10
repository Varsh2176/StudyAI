from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from app.models.schemas import ExamScorePredictionRequest, ExamScorePredictionResponse
from app.services.ml_service import predict_exam_score, get_model_metadata
from app.database.mongodb import predictions_collection

router = APIRouter(prefix="/predict", tags=["Prediction"])


@router.post("/exam-score", response_model=ExamScorePredictionResponse)
def predict_score_endpoint(request: ExamScorePredictionRequest):
    """
    Accepts student performance factors, evaluates using the trained ML pipeline,
    computes transparent academic risk, and optionally logs prediction to the database.
    """
    try:
        feature_dict = request.model_dump()
        email = feature_dict.pop("email", None)

        result = predict_exam_score(feature_dict)

        # Store in MongoDB if email provided
        if email and predictions_collection is not None:
            try:
                record = {
                    "email": email,
                    "features": feature_dict,
                    "prediction": result["predicted_exam_score"],
                    "risk_assessment": result["risk_assessment"],
                    "model_used": result["model_used"],
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                predictions_collection.insert_one(record)
            except Exception as db_err:
                # Log DB error without breaking the prediction response
                print(f"Non-fatal error logging prediction to MongoDB: {db_err}")

        return result
    except FileNotFoundError as fnf_err:
        raise HTTPException(status_code=503, detail=f"Model unavailable: {str(fnf_err)}")
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=f"Invalid prediction input: {str(val_err)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


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
                "categorical": metadata.get("categorical_features", [])
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/history/{email}")
def get_prediction_history(email: str):
    """Retrieves previous predictions and risk assessments for a student."""
    if predictions_collection is None:
        return {"predictions": []}

    records = list(
        predictions_collection.find({"email": email}, {"_id": 0})
        .sort("created_at", -1)
        .limit(10)
    )
    return {"email": email, "predictions": records}
