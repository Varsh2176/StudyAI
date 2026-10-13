# StudyWise AI — Deployment Readiness (M9–M13)

This document covers production configuration for the **existing** StudyWise AI stack
(React + Vite frontend, FastAPI backend, MongoDB Atlas, optional Gemini).  
It does **not** claim a remote deployment has been performed.

**M11** adds security hardening (auth rate limits, stronger password/JWT checks,
production CORS fail-closed, honest Mongo persist failures) and a pre-deploy checklist.

**M12** Learning Hub local extractive tools work without `GEMINI_API_KEY`.  
**M13** is pre-deployment verification (local E2E + checklist).  
**Hybrid target (approved prep):** **Vercel** (frontend) + **Render** (FastAPI container) + **MongoDB Atlas**.  
The FastAPI + sklearn stack is **not** packaged for Vercel Python serverless (dependency footprint exceeds typical function limits). Remote deploy is still **operator-initiated** — this repo only adds config/docs.

| Layer | Selected / notes |
|-------|------------------|
| Frontend | Vercel (`frontend/` + `frontend/vercel.json` SPA rewrites) |
| Backend API | Render Docker Web Service (`Dockerfile` + optional `render.yaml`) |
| Database | MongoDB Atlas (unchanged) |
| PDF / RAG | Render **persistent disk** at `/var/data` (not ephemeral container FS) |

Do not apply irreversible provider changes or push secrets without explicit approval.

---

## 1. Prerequisites

- Node.js 18+
- Python 3.10+
- MongoDB Atlas cluster (or reachable MongoDB URI)
- Optional: Google AI Studio / Gemini API key for Tutor and grounded RAG answers
- Trained ML artifacts under `ml/models/` (run `python ml/src/train_model.py` if missing)

---

## 2. Environment variables

### Backend (`backend/.env` — never commit)

| Variable | Required | Purpose |
|----------|----------|---------|
| `MONGODB_URI` | **Yes** | MongoDB connection string (Atlas `mongodb+srv://…`) |
| `DATABASE_NAME` | Recommended | Database name (default `studyai`) |
| `GEMINI_API_KEY` | Optional | Enables Learning Hub study generation + LLM-grounded RAG answers |
| `GOOGLE_API_KEY` | Optional | Alternate name for `GEMINI_API_KEY` |
| `TUTOR_MODEL` | Optional | Gemini model id (default `gemini-3.5-flash-lite`) |
| `TUTOR_REQUEST_TIMEOUT_SECONDS` | Optional | Per-attempt tutor HTTP timeout (5–90, default 40) |
| `TUTOR_MAX_RETRIES` | Optional | Extra attempts after failure for timeouts/5xx only (0–2, default 1). Never retries 429/401/403/404. |
| `CORS_ORIGINS` | **Yes in production** | Comma-separated frontend origins, e.g. `https://app.example.com` |
| `PDF_STORAGE_DIR` | Optional | Local PDF bytes directory (default `storage/documents`) |
| `PDF_UPLOAD_MAX_BYTES` | Optional | Upload size limit (default 10 MiB) |
| `RAG_STORAGE_DIR` | Optional | Local TF-IDF index directory (default `storage/rag`) |
| `RAG_EMBEDDING_PROVIDER` | Optional | Default `local_tfidf` |
| `JWT_SECRET` | **Yes in production** | Signs short-lived access tokens (M10). Must be a strong random value (≥32 chars) when `APP_ENV=production` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Optional | Token lifetime (default 60, clamped 5–1440) |
| `APP_ENV` | **Yes in production** | Set `production` so weak/missing `JWT_SECRET` is rejected and unset `CORS_ORIGINS` fails closed |
| `AUTH_RATE_LIMIT_ATTEMPTS` | Optional | Max login/register attempts per client key (default 10, range 3–100) |
| `AUTH_RATE_LIMIT_WINDOW_SECONDS` | Optional | Sliding window for auth rate limit (default 60, range 10–3600) |

Templates: `backend/.env.example`, root `.env.example`.

### Frontend (Vite — baked into the client bundle at **build** time)

| Variable | Required | Purpose |
|----------|----------|---------|
| `VITE_API_BASE_URL` | **Yes for split hosting** | Public API origin with no trailing slash, e.g. `https://api.example.com` |

- **Local `npm run dev`:** leave unset → uses `http://127.0.0.1:8000`.
- **Production same-origin reverse proxy:** leave unset → requests use the page origin (`""`).
- **Production split hosts:** set `VITE_API_BASE_URL` before `npm run build`.

**Never** put MongoDB URIs, Gemini keys, passwords, or JWT secrets in `VITE_*` variables.
They are visible in the browser bundle.

Template: `frontend/.env.example`.

---

## 3. Local development

```bash
# Backend
cd backend
# Windows: .venv\Scripts\Activate.ps1
cp .env.example .env   # then edit secrets
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

- Frontend: http://localhost:5173  
- API docs: http://127.0.0.1:8000/docs  
- Health: http://127.0.0.1:8000/health  
- DB diagnostic: http://127.0.0.1:8000/health/database  

---

## 4. Production build and startup (local verification)

### Frontend

```bash
cd frontend
# For split hosting, set the public API URL for this build:
#   Windows PowerShell:  $env:VITE_API_BASE_URL="https://your-api.example.com"
#   bash:                export VITE_API_BASE_URL=https://your-api.example.com
npm run lint
npm run build
npm run check:prod-bundle
```

Serve `frontend/dist/` with any static host. Preview locally:

```bash
npm run preview
```

### Backend

```bash
cd backend
# Ensure production env is set (MONGODB_URI, CORS_ORIGINS, optional GEMINI_API_KEY)
# Windows PowerShell example:
#   $env:CORS_ORIGINS="https://your-frontend.example.com"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

On platforms that inject `PORT`:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Optional process manager pattern (no new dependency added by M9):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

Use a single worker unless PDF/RAG disk paths and process-local caches are reviewed for multi-worker safety.

### Backend tests

```bash
cd backend
python -m unittest tests.test_studyai -q
```

---

## 5. Frontend / backend hosting considerations

1. Build the frontend with the correct `VITE_API_BASE_URL` for the target API.
2. Deploy `frontend/dist/` as static assets.
3. Deploy the FastAPI app with `uvicorn` (or an approved ASGI server) and production env vars.
4. Set `CORS_ORIGINS` to the **exact** frontend origin(s) (scheme + host + port if non-default).
5. Confirm browser requests from the SPA reach the API (no mixed-content HTTP API from HTTPS pages).

---

## 6. MongoDB Atlas

1. Create a database user and connection string (`MONGODB_URI`).
2. **Network Access:** allow the outbound IP of your backend host (or a controlled CIDR). Avoid long-lived `0.0.0.0/0` for public deployments.
3. Confirm the cluster is not paused.
4. Verify with `GET /health` (`database: connected`) and `GET /health/database` (staged diagnostics; no secrets returned).

### Persistence behavior

| Feature | If MongoDB is down |
|---------|--------------------|
| Registration / login | **503** — in-memory registration is disabled (M10/M11). |
| Student profile | **503** — no silent durable success. |
| Study plan generate/save | **503** if the Mongo write cannot complete (M11). |
| Prediction compute | Still returns the ML score; Mongo history logging is best-effort (does not claim a durable save). |
| Documents metadata list/read/upload | **503** when Mongo is unavailable (M11 — no durable success from process cache alone). |
| PDF bytes / RAG indexes | Local disk under `PDF_STORAGE_DIR` / `RAG_STORAGE_DIR` — independent of Atlas but not durable on ephemeral disks. |

Unit tests do **not** prove live Atlas persistence. Operators must confirm via `/health/database` and a real register/profile write against Atlas.

---

## 7. CORS

- **Development:** defaults allow Vite/local origins (`localhost` / `127.0.0.1` on ports 5173, 5174, 3000).
- **Production (`APP_ENV=production`):** `CORS_ORIGINS` is **required**. If unset/empty, the allow-list is empty (fail-closed).
- Wildcard `*` entries are ignored (incompatible with credentialed apps).

---

## 8. Gemini / Learning Hub study generation

- Set `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) in the **backend** environment.
- Default model: `gemini-3.5-flash-lite` (override with `TUTOR_MODEL`).
- Default per-attempt timeout: 40s with one bounded retry on timeouts / HTTP 5xx.
- The dedicated `/tutor` chat page was removed; Learning Hub tools call `POST /ai/tutor`.
- Without a key:
  - `GET /ai/tutor/status` reports `configured: false`.
  - Learning Hub document-grounded tools use `POST /ai/hub/local` (extractive; labelled Local).
  - Topic-only Gemini generation is unavailable until a key is configured.
  - Documents RAG can still return **retrieval-only** answers when indexes exist (labelled as such).

---

## 9. PDF / RAG storage (ephemeral filesystems)

PDF uploads and TF-IDF indexes are stored on the **local filesystem** of the backend process:

- `PDF_STORAGE_DIR` → default `backend/storage/documents`
- `RAG_STORAGE_DIR` → default `backend/storage/rag`

Many PaaS free tiers use **ephemeral disks**: uploads and indexes disappear on redeploy/restart.  
For durable materials:

- Attach a persistent volume, or
- Move object storage later (out of M9 scope).

Do not commit `backend/storage/` (gitignored).

---

## 10. Health checks and smoke tests

### Automated / operator checks

| Check | Expect |
|-------|--------|
| `GET /` | API running message |
| `GET /health` | `status: healthy`; inspect `database` and `ml_model` |
| `GET /health/database` | `status: connected` when Atlas is reachable |
| `GET /ai/tutor/status` | `configured: true` only when Gemini key is set |
| `GET /predict/model-status` | Model metadata when pipeline loaded |

### Manual browser smoke tests (after deploy)

1. Open the frontend over HTTPS.
2. Register a user; confirm response `persistence` is `"mongo"` (not `"memory"`).
3. Save a student profile and reload it by email.
4. Run score prediction and open Dashboard.
5. Upload a PDF, Index, and Ask (RAG) if storage is durable.
6. Open Learning Hub → generate flashcards from uploaded notes (local; Gemini optional). Confirm `/tutor` redirects to `/hub`.
7. Confirm `/__ui` is not available in production (DEV-only gallery).

---

## 11. Authentication (M10/M11) and remaining risks

### What M10 provides

- Registration and login with **scrypt password hashes** (never plaintext).
- Short-lived **HMAC access tokens** (`Authorization: Bearer …`).
- Server-side ownership: student email is taken from the validated token; mismatched client emails return **403**.
- Protected app routes require sign-in; expired/invalid tokens return **401** and the SPA clears the session.
- Registration / document writes **fail with 503** when MongoDB is unavailable (no durable in-memory success path).

### What M11 adds

- **Auth rate limiting** on `POST /auth/register` and `POST /auth/login` (in-process sliding window; returns **429** + `Retry-After`).
- Passwords must be ≥8 characters and include **at least one letter and one number**.
- Production rejects placeholder / short `JWT_SECRET` values (`APP_ENV=production`).
- Production CORS fail-closed when `CORS_ORIGINS` is unset.
- Study-plan Mongo persist failures and document metadata Mongo outages return **503** (no silent durable success).

### Migration note

Accounts created **before M10** that still have plaintext `password` fields cannot sign in. Those users must **re-register** (or an operator must create a new hashed account). Do not migrate by verifying against plaintext.

### Remaining risks

- Access tokens are **stateless** (logout is client-side discard; no server denylist).
- Auth rate limits are **per process** — multi-worker hosts need a shared limiter for global accuracy.
- No refresh-token rotation, MFA, email verification, or password-reset flow yet.
- Gemini and Mongo secrets must stay server-side only.
- Ephemeral disk loss of PDFs/RAG indexes on many PaaS free tiers.
- Formal penetration testing / threat modeling is still out of scope.

### Pre-public checklist

- [x] Authenticated sessions with hashed passwords and ownership checks (M10).
- [x] Auth rate limiting + production CORS fail-closed + stronger password/JWT checks (M11).
- [ ] Set a strong production `JWT_SECRET` (≥32 random chars) and `APP_ENV=production`.
- [ ] Set production `CORS_ORIGINS` to exact frontend origins.
- [ ] Confirm Atlas IP allowlist is least-privilege.
- [ ] Confirm `/health/database` is `connected` in the target environment.
- [ ] Provision durable storage for PDFs/RAG if materials must survive restarts.
- [ ] Rotate any credentials that were ever committed or shared.
- [ ] Build frontend with the correct `VITE_API_BASE_URL`.
- [ ] Run lint, production build, `check:prod-bundle`, and backend tests.
- [ ] Complete manual smoke tests: register → login → profile → documents → deny cross-account access → sign out → burst-login 429.

---

## 12. Hybrid hosting: Vercel frontend + Render API

Repo prep files (no deploy performed by docs alone):

| File | Purpose |
|------|---------|
| [frontend/vercel.json](./frontend/vercel.json) | SPA rewrites for React Router |
| [Dockerfile](./Dockerfile) | API image; build context = **repo root** (includes `ml/models`) |
| [render.yaml](./render.yaml) | Optional Render Blueprint sketch + `/var/data` disk |
| [.dockerignore](./.dockerignore) | Keeps frontend/secrets/storage out of the API image |

### 12.1 Frontend on Vercel

1. Create a Vercel project with **Root Directory** = `frontend`.
2. Build command: `npm run build`. Output directory: `dist`.
3. Set **build-time** env: `VITE_API_BASE_URL` = public Render API origin (HTTPS, no trailing slash), e.g. `https://studywise-api.onrender.com`.
4. Never put `MONGODB_URI`, `JWT_SECRET`, or `GEMINI_API_KEY` in Vercel `VITE_*` vars (they are embedded in the client bundle).
5. After deploy, note the exact frontend origin (e.g. `https://your-app.vercel.app`) for backend CORS.

Local check before linking a real API:

```bash
cd frontend
# Optional: bake a placeholder API URL into the bundle for split-host checks
#   PowerShell:  $env:VITE_API_BASE_URL="https://api.example.com"
npm run lint
npm run build
npm run check:prod-bundle
```

### 12.2 Backend on Render

1. Create a **Docker** Web Service from this repository (Dockerfile at repo root).
2. Attach a **persistent disk** mounted at `/var/data` (see `render.yaml`).
3. Set runtime env (secrets in the dashboard — never commit):

| Variable | Example / notes |
|----------|-----------------|
| `APP_ENV` | `production` |
| `MONGODB_URI` | Atlas connection string |
| `DATABASE_NAME` | `studyai` |
| `JWT_SECRET` | ≥32 random chars |
| `CORS_ORIGINS` | Exact Vercel origin(s), e.g. `https://your-app.vercel.app` |
| `PDF_STORAGE_DIR` | `/var/data/documents` |
| `RAG_STORAGE_DIR` | `/var/data/rag` |
| `GEMINI_API_KEY` | Optional |
| `PORT` | Injected by Render |

4. Atlas **Network Access**: allow Render egress IPs (prefer least-privilege over open `0.0.0.0/0`).
5. Health: `GET /health` and `GET /health/database` on the Render URL.
6. Keep **one instance / one uvicorn worker** until shared rate-limit and multi-process disk locking are designed (`Dockerfile` already uses `--workers 1`).

Without a persistent disk, PDF uploads and TF-IDF indexes written under storage dirs are **not durable** across redeploys.

### Rollback guidance (after a future deploy)

1. Keep the previous Render release / Docker image **and** the previous Vercel deployment (or frontend `dist`).
2. Roll back Render to the previous release; keep the same `MONGODB_URI` unless a migration ran (none in M11–M13).
3. Redeploy the previous Vercel build if the API contract changed (M11–M13 keep contracts compatible).
4. Confirm `GET /health` and `GET /health/database` after rollback.
5. Auth tokens issued under an old `JWT_SECRET` will fail if the secret was rotated — users simply sign in again.
6. If the persistent disk was wiped, restore PDF/RAG backups under `/var/data` or re-upload materials.

---

## 13. M13 pre-deployment verification (local)

Run before any remote deploy (does **not** replace production smoke tests):

```bash
# Backend API smoke (live Mongo; unique m13-* emails; does not delete existing data)
cd backend
python scripts/m13_e2e_api_smoke.py

# Regression
python -m unittest tests.test_studyai -q
cd ../frontend
npm run lint && npm run build && npm run check:prod-bundle
```

Browser checks: register → logout → login → profile save/reload → `/tutor` redirects to `/hub` → sign out blocks `/dashboard`.

### Production fail-safe (verified in unit tests / local probes)

| Condition | Expected behavior |
|-----------|-------------------|
| `APP_ENV=production` + weak/missing `JWT_SECRET` | Auth routes raise config error (no weak signing) |
| `APP_ENV=production` + unset `CORS_ORIGINS` | Empty allow-list (fail-closed) |
| MongoDB unreachable | Register/profile/docs/plans return **503** (no silent durable success) |
| Missing `GEMINI_API_KEY` | Hub local tools + retrieval-only RAG still work; Gemini topic mode unavailable |

---

## 14. What M9–M13 do / do not claim

| Claim | Status |
|-------|--------|
| Production frontend build + bundle checks | Supported (run locally) |
| Configurable API base URL (`VITE_API_BASE_URL`) | Implemented |
| Configurable CORS (`CORS_ORIGINS`) + prod fail-closed | Implemented (M11) |
| Auth rate limiting (in-process) | Implemented (M11) |
| Learning Hub without Gemini (local extractive) | Implemented (M12) |
| Local E2E / ownership smoke | Scripts + manual browser (M13) |
| Hybrid Vercel + Render config files | Prepared (`frontend/vercel.json`, `Dockerfile`, `render.yaml`) |
| Secrets via env / `.env.example` templates | Documented |
| Remote deployment to a named host | **Not performed** |
| FastAPI on Vercel Python serverless | **Not pursued** (ML dependency size) |
| Public multi-user security guarantee | **Not claimed** |

Stop here until an operator creates the Vercel/Render projects and deploys with production secrets.
