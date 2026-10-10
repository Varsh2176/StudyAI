from pathlib import Path
import json
import pandas as pd
import numpy as np
import joblib

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# 1. Project paths
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "ml" / "data"
MODEL_DIR = ROOT / "ml" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# 2. Load original dataset
csv_path = DATA_DIR / "StudentPerformanceFactors.csv"
if not csv_path.exists():
    raise FileNotFoundError(f"Dataset not found at {csv_path}")

data = pd.read_csv(csv_path)

# 3. Clean target and split features
data = data.dropna(subset=["Exam_Score"])
X = data.drop(columns=["Exam_Score"])
y = data["Exam_Score"]

# Identify column types
numeric_cols = X.select_dtypes(include=["number"]).columns.tolist()
categorical_cols = X.select_dtypes(exclude=["number"]).columns.tolist()

# 4. Data Preprocessor
numeric_transformer = Pipeline([
    ("imputer", SimpleImputer(strategy="median"))
])

categorical_transformer = Pipeline([
    ("imputer", SimpleImputer(strategy="most_frequent")),
    ("encoder", OneHotEncoder(handle_unknown="ignore"))
])

preprocessor = ColumnTransformer(
    transformers=[
        ("numeric", numeric_transformer, numeric_cols),
        ("categorical", categorical_transformer, categorical_cols)
    ]
)

# 5. Train/Test Split (80/20, reproducible with random_state=42)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# 6. Candidate Models for Evaluation
candidate_models = {
    "LinearRegression": LinearRegression(),
    "RidgeRegression": Ridge(alpha=1.0, random_state=42),
    "RandomForest": RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
}

results = {}
trained_pipelines = {}

print("=== Evaluating Candidate Models ===")
for name, regressor in candidate_models.items():
    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", regressor)
    ])
    
    # Fit pipeline strictly on training data
    pipeline.fit(X_train, y_train)
    
    # Predict on test data
    y_pred = pipeline.predict(X_test)
    
    mae = float(mean_absolute_error(y_test, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    r2 = float(r2_score(y_test, y_pred))
    
    results[name] = {
        "MAE": round(mae, 4),
        "RMSE": round(rmse, 4),
        "R2": round(r2, 4)
    }
    trained_pipelines[name] = pipeline
    print(f"[{name}] MAE: {mae:.4f} | RMSE: {rmse:.4f} | R²: {r2:.4f}")

# 7. Model Selection based on lowest MAE and highest R2
best_model_name = min(results.keys(), key=lambda k: results[k]["MAE"])
best_pipeline = trained_pipelines[best_model_name]
print(f"\n--> Selected Best Model: {best_model_name} (Lowest MAE: {results[best_model_name]['MAE']})")

# 8. Save the best pipeline and evaluation metrics
model_path = MODEL_DIR / "exam_score_model.joblib"
joblib.dump(best_pipeline, model_path)
print(f"Saved complete pipeline to: {model_path}")

report_data = {
    "dataset": "StudentPerformanceFactors.csv",
    "total_rows": int(len(data)),
    "train_rows": int(len(X_train)),
    "test_rows": int(len(X_test)),
    "numeric_features": numeric_cols,
    "categorical_features": categorical_cols,
    "selected_model": best_model_name,
    "metrics_comparison": results,
    "selected_model_metrics": results[best_model_name]
}

metrics_path = MODEL_DIR / "model_metrics.json"
with open(metrics_path, "w") as f:
    json.dump(report_data, f, indent=2)
print(f"Saved metrics report to: {metrics_path}")
