# StudyWise AI: An AI-Integrated Personalized and Adaptive Study Planning System

A full-stack, data-driven web application designed to help students optimize their academic performance through **machine learning-based score prediction**, **transparent academic risk assessment**, **deterministic study timetable scheduling**, **Learning Hub study tools with grounded RAG over uploaded notes**, and **adaptive progress tracking**.

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
  - **RAG / Learning Hub generation**: Ingests student-uploaded PDF/text notes, chunks passages, retrieves relevant context using vector similarity, and synthesizes answers strictly grounded in the student's material with exact page citations. Hub tools (flashcards, summaries, etc.) share the same Gemini study-generation API.

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

## 5. Notes RAG & Learning Hub generation (M14–M16)

1. **Document Ingestion (M15)**: `POST /documents/upload` accepts PDF notes (size limit via `PDF_UPLOAD_MAX_BYTES`). Text is extracted with `pypdf` and owned by student email.
2. **Indexing (M16)**: `POST /documents/{id}/index?email=...` chunks pages (default 150 words, 30-word overlap), builds a local TF-IDF index, and persists it under `RAG_STORAGE_DIR` (`storage/rag/`). Re-index is skipped when the content hash is unchanged.
3. **Ask (M16)**: `POST /documents/rag/ask` retrieves top-k owned chunks by cosine similarity, then answers with Gemini when `GEMINI_API_KEY` is set, or a labelled **retrieval-only** mode otherwise. Responses include filename/page citations.
4. **Ownership**: Retrieval and index paths are scoped to the requesting email; cross-user access is rejected.
5. **UI**: Materials / Dashboard `PdfDocumentsPanel` supports Index, status badges, and Ask Your Notes (RAG).

### Progress Tracking (M17)

- `POST /performance/session` — log completed / partial / missed sessions with planned vs actual minutes (MongoDB only; 503 if DB down).
- `GET /performance/{email}` — progress summary (completion rates, planned vs actual hours, subject-wise metrics).
- `GET /performance/{email}/sessions` — list owned sessions.
- Frontend: `/progress` page with load/empty/error states and session logging forms.
- All queries are scoped to the student email; no in-memory permanent progress store.

### Adaptive Planning (M18)

- `POST /performance/adapt-plan` adapts the saved study plan from logged sessions (missed / partial / completed), planned-vs-actual time, quizzes, exam dates, and available hours.
- Uses the existing M11 scheduler; unfinished work raises subject priority within a capped share of future capacity (does not create unrealistic catch-up load).
- Repeat-safe via progress fingerprint: identical progress does not increase workload again.
- Historical session records are never modified. Email scoping matches the rest of the app (email is not cryptographic identity).

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
   Edit `.env` (see `backend/.env.example` for full names):
   ```ini
   MONGODB_URI=your_mongodb_connection_string
   DATABASE_NAME=studyai
   GEMINI_API_KEY=optional_gemini_api_key
   RAG_STORAGE_DIR=storage/rag
   RAG_EMBEDDING_PROVIDER=local_tfidf
   ```
   No Atlas Vector Search index is required for M16; embeddings use scikit-learn TF-IDF on disk.
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
3. Local API calls default to `http://127.0.0.1:8000`. For production builds, set `VITE_API_BASE_URL` (see `frontend/.env.example` and [DEPLOYMENT.md](./DEPLOYMENT.md)).

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

### Optional secret scanning (developer workflow)

Local [pre-commit](https://pre-commit.com/) + [gitleaks](https://github.com/gitleaks/gitleaks) is configured in `.pre-commit-config.yaml` for contributors who want push-time scanning. It is **not** an application dependency. After pinning the gitleaks `rev` tag in that file:

```bash
pip install pre-commit
pre-commit install
```

---

## 8. Deployment Guidelines (M9)

Full production configuration, security limitations, and smoke-test steps: **[DEPLOYMENT.md](./DEPLOYMENT.md)**.

Summary:

- **Frontend**: Build with `npm run build`. Set `VITE_API_BASE_URL` to the public API origin for split hosting (see `frontend/.env.example`). Verify with `npm run check:prod-bundle`.
- **Backend**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT` with `MONGODB_URI` and production `CORS_ORIGINS`.
- **Database**: MongoDB Atlas with Network Access allowlisting for the backend host.
- **Auth (M10)**: Register/login with hashed passwords and bearer access tokens. Student APIs enforce token ownership. See [DEPLOYMENT.md](./DEPLOYMENT.md) §11 for remaining risks (no refresh tokens / MFA yet).

### Secrets handling

Never commit `.env` files or live credentials. Copy `.env.example` / `backend/.env.example` / `frontend/.env.example` and fill in local values. Keep secrets in environment variables or a private secret store only. If a real credential was ever exposed in git or chat, rotate it in the provider (e.g. Atlas DB user password, Gemini API key) and treat the old value as compromised.

**No remote deployment is performed by default.** Choose a hosting provider and approve deployment explicitly before shipping.
