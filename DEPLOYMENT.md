# StudyWise AI — Deployment Readiness (M9)

This document covers production configuration for the **existing** StudyWise AI stack
(React + Vite frontend, FastAPI backend, MongoDB Atlas, optional Gemini).  
It does **not** claim a remote deployment has been performed.

**Provider note:** No hosting provider is selected yet. Suitable options include:

| Layer | Common options |
|-------|----------------|
| Frontend static hosting | Vercel, Netlify, Cloudflare Pages, S3 + CloudFront |
| Backend API | Render, Railway, Fly.io, a VPS with systemd + uvicorn/gunicorn |
| Database | MongoDB Atlas (already used) |

Choose a provider only after reviewing pricing, region, and filesystem durability.
Do not apply irreversible provider-specific changes without explicit approval.

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
| `GEMINI_API_KEY` | Optional | Enables AI Tutor + LLM-grounded RAG answers |
| `GOOGLE_API_KEY` | Optional | Alternate name for `GEMINI_API_KEY` |
| `TUTOR_MODEL` | Optional | Gemini model id (default `gemini-3.5-flash-lite`) |
| `TUTOR_REQUEST_TIMEOUT_SECONDS` | Optional | Tutor HTTP timeout (5–60, default 20) |
| `CORS_ORIGINS` | **Yes in production** | Comma-separated frontend origins, e.g. `https://app.example.com` |
| `PDF_STORAGE_DIR` | Optional | Local PDF bytes directory (default `storage/documents`) |
| `PDF_UPLOAD_MAX_BYTES` | Optional | Upload size limit (default 10 MiB) |
| `RAG_STORAGE_DIR` | Optional | Local TF-IDF index directory (default `storage/rag`) |
| `RAG_EMBEDDING_PROVIDER` | Optional | Default `local_tfidf` |
| `JWT_SECRET` | **Yes in production** | Signs short-lived access tokens (M10). Must be a strong random value when `APP_ENV=production` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Optional | Token lifetime (default 60, clamped 5–1440) |
| `APP_ENV` | Recommended | Set `production` on hosted backends so weak/missing `JWT_SECRET` is rejected |

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
| Registration (`POST /auth/register`) | May fall back to **process-local in-memory** storage and returns a warning (`persistence: "memory"`). Data is lost on restart. |
| Student profile, plans, performance, documents metadata | Fail with clear errors (typically **503**). No silent durable success. |
| PDF bytes / RAG indexes | Local disk under `PDF_STORAGE_DIR` / `RAG_STORAGE_DIR` — independent of Atlas but not durable on ephemeral disks. |

Unit tests do **not** prove live Atlas persistence. Operators must confirm via `/health/database` and a real register/profile write against Atlas.

---

## 7. CORS

- **Development:** defaults allow Vite/local origins (`localhost` / `127.0.0.1` on ports 5173, 5174, 3000).
- **Production:** set `CORS_ORIGINS` to your deployed frontend origin(s) only.
- Wildcard `*` with credentials is not used.

---

## 8. Gemini / AI Tutor

- Set `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) in the **backend** environment.
- Default model: `gemini-3.5-flash-lite` (override with `TUTOR_MODEL`).
- Without a key:
  - `GET /ai/tutor/status` reports `configured: false`.
  - Tutor / hub tools that need Gemini fail with a clear configuration message.
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
6. Open Learning Hub → generate flashcards (requires Gemini).
7. Confirm `/__ui` is not available in production (DEV-only gallery).

---

## 11. Authentication (M10) and remaining risks

### What M10 provides

- Registration and login with **scrypt password hashes** (never plaintext).
- Short-lived **HMAC access tokens** (`Authorization: Bearer …`).
- Server-side ownership: student email is taken from the validated token; mismatched client emails return **403**.
- Protected app routes require sign-in; expired/invalid tokens return **401** and the SPA clears the session.
- Registration / document writes **fail with 503** when MongoDB is unavailable (no durable in-memory success path).

### Migration note

Accounts created **before M10** that still have plaintext `password` fields cannot sign in. Those users must **re-register** (or an operator must create a new hashed account). Do not migrate by verifying against plaintext.

### Remaining risks

- Access tokens are **stateless** (logout is client-side discard; no server denylist).
- No refresh-token rotation, MFA, email verification, or password-reset flow yet.
- CORS misconfiguration can still expose the API to unwanted browser origins.
- Gemini and Mongo secrets must stay server-side only.
- Ephemeral disk loss of PDFs/RAG indexes.
- No claim of rate limiting, abuse protection, or formal threat modeling.

### Pre-public checklist

- [x] Authenticated sessions with hashed passwords and ownership checks (M10).
- [ ] Set a strong production `JWT_SECRET` and `APP_ENV=production`.
- [ ] Set production `CORS_ORIGINS` to exact frontend origins.
- [ ] Confirm Atlas IP allowlist is least-privilege.
- [ ] Confirm `/health/database` is `connected` in the target environment.
- [ ] Provision durable storage for PDFs/RAG if materials must survive restarts.
- [ ] Rotate any credentials that were ever committed or shared.
- [ ] Build frontend with the correct `VITE_API_BASE_URL`.
- [ ] Run lint, production build, `check:prod-bundle`, and backend tests.
- [ ] Complete manual smoke tests: register → login → profile → documents → deny cross-account access → sign out.

---

## 12. What M9 does / does not claim

| Claim | Status |
|-------|--------|
| Production frontend build + bundle checks | Supported (run locally) |
| Configurable API base URL (`VITE_API_BASE_URL`) | Implemented |
| Configurable CORS (`CORS_ORIGINS`) | Implemented |
| Secrets via env / `.env.example` templates | Documented |
| Remote deployment to a named host | **Not performed** in M9 |
| Public multi-user security | **Not claimed** |

Stop here until a hosting provider and deployment are explicitly approved.
