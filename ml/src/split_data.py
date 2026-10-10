
from pathlib import Path
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

# 1. Set project paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "ml" / "data"

csv_files = list(DATA_DIR.glob("StudentPerformanceFactors.csv"))

if not csv_files:
    raise FileNotFoundError("Dataset CSV not found in ml/data")

# 2. Load dataset
data = pd.read_csv(csv_files[0])

# 3. Select target
target = "Exam_Score"

# Remove rows with missing target values
data = data.dropna(subset=[target])

X = data.drop(columns=[target])
y = data[target]

# 4. Identify numeric and categorical columns
numeric_columns = X.select_dtypes(
    include=["number"]
).columns.tolist()

categorical_columns = X.select_dtypes(
    exclude=["number"]
).columns.tolist()

# 5. Prepare preprocessing pipelines
numeric_pipeline = Pipeline([
    ("imputer", SimpleImputer(strategy="median"))
])

categorical_pipeline = Pipeline([
    ("imputer", SimpleImputer(strategy="most_frequent")),
    ("encoder", OneHotEncoder(handle_unknown="ignore"))
])

preprocessor = ColumnTransformer([
    ("numeric", numeric_pipeline, numeric_columns),
    ("categorical", categorical_pipeline, categorical_columns)
])

# 6. Split data into 80% training and 20% testing
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42
)

# 7. Fit preprocessing ONLY on training data
X_train_processed = preprocessor.fit_transform(X_train)
X_test_processed = preprocessor.transform(X_test)

# 8. Save the split data
output_dir = DATA_DIR / "processed"
output_dir.mkdir(parents=True, exist_ok=True)

pd.DataFrame(
    X_train_processed.toarray()
    if hasattr(X_train_processed, "toarray")
    else X_train_processed
).to_csv(output_dir / "X_train.csv", index=False)

pd.DataFrame(
    X_test_processed.toarray()
    if hasattr(X_test_processed, "toarray")
    else X_test_processed
).to_csv(output_dir / "X_test.csv", index=False)

y_train.to_csv(output_dir / "y_train.csv", index=False)
y_test.to_csv(output_dir / "y_test.csv", index=False)

print("Dataset preprocessing and splitting completed!")
print("Total rows:", len(data))
print("Training rows:", len(X_train))
print("Testing rows:", len(X_test))
print("Training features:", X_train_processed.shape[1])
print("Testing features:", X_test_processed.shape[1])
print("Saved files to:", output_dir)
