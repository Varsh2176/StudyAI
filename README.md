# StudyWise AI: An AI-Integrated Personalized and Adaptive Study Planning System

A full-stack, data-driven web application designed to help students optimize their academic performance through **machine learning-based score prediction**, **transparent academic risk assessment**, **deterministic study timetable scheduling**, **modular AI tutoring with grounded RAG over uploaded notes**, and **adaptive progress tracking**.

---

## 1. System Architecture

StudyWise AI is built with strict architectural boundaries separating ML computation, deterministic constraint scheduling, and generative language tutoring:

```
┌────────────────────────────────────────────────────────┐
│                   React + Vite Frontend                │
│    (Registration, Profile, Prediction, Planner, RAG,    │
│                     Progress Dashboard)                │
└───────────────────────────┬────────────────────────────┘
                            │ REST / JSON
┌───────────────────────────▼────────────────────────────┐
│                    FastAPI Backend                     │
│ ┌────────────────────────────────────────────────────┐ │
│ │ Routes: /auth, /student, /predict, /study-plan,     │ │
│ │         /ai, /performance                          │ │
│ └────────────────────────────────────────────────────┘ │
│ ┌──────────────────┐ ┌────────────────┐ ┌────────────┐ │
│ │   ML Service     │ │   Scheduler    │ │  RAG & AI  │ │
│ │ Ridge Regression │ │ Deterministic  │ │ TF-IDF /   │ │
│ │ + Preprocessor   │ │ Priority Engine│ │ Citations  │ │
│ └──────────────────┘ └────────────────┘ └────────────┘ │
└─────────────┬───────────────────────────┬──────────────┘
              │                           │
┌─────────────▼──────────┐ ┌──────────────▼──────────────┐
│  MongoDB Atlas Cluster │ │  ml/models/ (.joblib, .json)│
│ (Users, Profiles, Plans│ │  Pretrained ML Pipeline     │
│  Quizzes, Sessions)    │ │  & Evaluated Test Metrics   │
└────────────────────────┘ └─────────────────────────────┘
```

- **ML vs. Scheduler vs. AI**:
  - **ML Model**: Evaluates tabular academic & lifestyle features to predict expected exam scores.
  - **Scheduler**: A deterministic engine that allocates study blocks (50m study / 10m break) based on subject difficulty, score deficits, and exam urgency.
  - **RAG / AI Tutor**: Ingests student-uploaded PDF/text notes, chunks passages, retrieves relevant context using vector similarity, and synthesizes answers strictly grounded in the student's material with exact page citations.

---

## 2. Dataset & Preprocessing

- **Dataset**: `ml/data/StudentPerformanceFactors.csv` (6,607 rows, 20 columns).
- **Target Variable**: `Exam_Score` (continuous numeric).
- **Missing Value Handling**:
  - `Teacher_Quality` (78 missing): Handled via categorical imputation (`most_frequent`).
  - `Parental_Education_Level` (90 missing): Handled via categorical imputation (`most_frequent`).
  - `Distance_from_Home` (67 missing): Handled via categorical imputation (`most_frequent`).
- **Feature Pipeline**:
  - Numeric columns (6): Imputed via `median` strategy (`SimpleImputer`).
  - Categorical columns (13): Imputed via `most_frequent` + encoded via `OneHotEncoder(handle_unknown='ignore')`.
  - Train/Test Split: 80% train (5,285 rows) and 20% test (1,322 rows) with reproducible random seed (`random_state=42`).

---

## 3. Model Benchmark & Evaluation

Models were trained strictly on training data and benchmarked on test data using MAE, RMSE, and R²:

| Model | Test MAE | Test RMSE | Test R² | Status |
|---|---|---|---|---|
| **Ridge Regression** | **0.4523** | **1.8044** | **0.7697** | **Selected Best Pipeline** |
| Linear Regression (Baseline) | 0.4524 | 1.8044 | 0.7696 | Candidate |
| Random Forest Regressor | 1.0841 | 2.1657 | 0.6682 | Candidate |

> **Selection Justification**: Linear and Ridge regression models significantly outperformed the Random Forest ensemble on this dataset due to strong linear correlations between leading factors (`Hours_Studied`, `Attendance`, `Previous_Scores`) and `Exam_Score`. Ridge Regression was selected as the final production model due to L2 regularization stability. The complete preprocessor and regressor are bundled in `ml/models/exam_score_model.joblib`.

---

## 4. Transparent Academic Risk Assessment (Phase E)

Because the underlying dataset contains continuous scores rather than predefined risk labels, StudyWise AI does **not** fabricate an artificial classification target. Instead, it computes a **transparent, rule-based risk indicator** using observable leading indicators available *before* final examinations:
- **Attendance**: High risk if `< 65%`, medium risk if `< 75%`.
- **Study Hours**: High risk if `< 10 hrs/week`, medium risk if `< 16 hrs/week`.
- **Prior Academic Record**: High risk if `< 55%`, medium risk if `< 70%`.
- **Predicted Exam Score**: Evaluated against the standard pass threshold (`< 60%`).

This prevents data leakage from final exam outcomes while delivering clear, actionable risk levels (**Low Risk**, **Medium Risk**, **High Risk**) with prescriptive intervention plans.

---

## 5. Grounded AI Tutor & Notes RAG (Phase F)

1. **Document Ingestion**: Accepts PDF or plain-text lecture notes with validation (format check, max 20MB).
2. **Text Extraction & Chunking**: Uses `pypdf` to extract text page-by-page and segments into overlapping windows (150 words, 30-word overlap) preserving source page numbers.
3. **Similarity Retrieval**: Uses TF-IDF cosine similarity to rank passages against student queries.
4. **Knowledge Boundary Enforcement**: When similarity fails to meet the relevance threshold, the tutor explicitly replies: *"This information is not available in your uploaded study notes."*
5. **Modular Architecture**: Works 100% offline using grounded passage extraction and citations. If a `GEMINI_API_KEY` is provided in the environment, it uses generative conversational synthesis without compromising offline fallback.

---

## 6. Installation & Setup

### Prerequisites
- Node.js (v18+)
- Python (v3.10+)
- MongoDB Atlas account or local MongoDB instance

### Backend Setup
1. Open terminal in the backend directory:
   ```bash
   cd backend
   ```
2. Activate existing virtual environment:
   ```powershell
   # Windows PowerShell
   .venv\Scripts\Activate.ps1
   ```
3. Copy environment template and configure your credentials:
   ```bash
   cp .env.example .env
   ```
   Edit `.env`:
   ```ini
   MONGODB_URI=your_mongodb_connection_string
   DATABASE_NAME=studyai
   GEMINI_API_KEY=optional_gemini_api_key
   ```
4. Train the ML model pipeline (if not already generated):
   ```bash
   python ../ml/src/train_model.py
   ```
5. Launch the FastAPI server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   Interactive Swagger documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Frontend Setup
1. In a separate terminal, open the frontend directory:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
2. Open your browser at [http://localhost:5173](http://localhost:5173).

---

## 7. Testing

Run backend test suite using Python's built-in `unittest` runner:
```bash
cd backend
python -m unittest tests/test_studyai.py
```

Test coverage includes:
- ML pipeline loading and prediction bounds
- Transparent risk assessment logic
- Deterministic study scheduler time calculations and priority shares
- RAG document chunking, passage retrieval, and grounded citations
- Out-of-scope query rejection
- API health and model status endpoints

---

## 8. Deployment Guidelines

- **Frontend**: Deployable to Vercel, Netlify, or AWS S3 + CloudFront. Build with `npm run build` (outputs to `dist/`).
- **Backend**: Deployable to Render, Railway, or AWS EC2 using `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- **Database**: MongoDB Atlas cloud cluster with IP allowlisting enabled.
- **Environment Security**: Keep `MONGODB_URI` and `GEMINI_API_KEY` in environment variables; never commit `.env` files to source control.
