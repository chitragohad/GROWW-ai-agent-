# Deployment Plan — Railway + Vercel

Deploy **Groww Weekly Review Pulse** as a split stack:

| Platform | Role | Component |
|----------|------|-----------|
| **Vercel** | Frontend | Next.js operator dashboard (`frontend/`) |
| **Railway** | Backend + scheduler | Python FastAPI API, weekly pulse worker, persistent data |
| **Railway** (existing) | Google delivery | [Chitra MCP server](https://github.com/chitragohad/Chitra-MCP-server) — Docs + Gmail |

**Related:** [production.md](./production.md) · [architecture.md](./architecture.md)

---

## 1. Target architecture

```
┌─────────────────────┐         HTTPS          ┌──────────────────────────────┐
│  Vercel             │  ───────────────────▶  │  Railway: pulse-api          │
│  Next.js dashboard  │   /api/dashboard       │  FastAPI (pulse.api.server)  │
│  groww-pulse.vercel │                        │  + SQLite ledger on Volume   │
└─────────────────────┘                        └──────────────┬───────────────┘
                                                              │
                    ┌─────────────────────────────────────────┼─────────────────────┐
                    │                                         │                     │
                    ▼                                         ▼                     ▼
           ┌────────────────┐                        ┌─────────────────┐    ┌──────────────┐
           │ Groq API       │                        │ Play Store      │    │ Chitra MCP   │
           │ summarization  │                        │ (public scrape) │    │ (Railway)    │
           └────────────────┘                        └─────────────────┘    └──────────────┘

┌──────────────────────────────┐
│  Railway: pulse-worker       │  Cron Mon 09:00 IST → `pulse run --confirm-production-send`
│  (optional separate service) │
└──────────────────────────────┘
```

### Design decisions

1. **Vercel hosts UI only** — no Play Store scraping, no BGE embeddings, no SQLite on Vercel.
2. **Railway hosts Python** — API always-on; worker/cron for weekly runs; **Railway Volume** for `data/`.
3. **Keep Chitra MCP separate** — Google OAuth stays on the existing Railway MCP project.
4. **Replace GitHub Actions cron** (optional) — Railway cron is simpler once Volume + worker exist; GHA can remain as fallback during migration.

---

## 2. Pre-deployment checklist

### Code changes required (before first deploy)

| # | Change | Why |
|---|--------|-----|
| 1 | Add `Dockerfile` (or Railway Nixpacks start command) for Python API | Railway needs a defined start: `pulse-api` or `uvicorn pulse.api.server:app` |
| 2 | Add `frontend/vercel.json` or set Vercel **Root Directory** = `frontend` | Monorepo; Vercel must not build repo root |
| 3 | Set `PULSE_API_URL` on Vercel → Railway public URL | Dashboard fetches backend over HTTPS |
| 4 | Update FastAPI CORS to allow Vercel domain(s) | Replace localhost-only origins in `pulse/api/server.py` |
| 5 | Remove filesystem fallback in production frontend | Vercel has no access to `../data`; API-only path in prod |
| 6 | Pin Python **3.11** on Railway | Matches CI; better wheel support for ML deps |
| 7 | Configure `HF_HOME` on Volume | Cache BGE model (`BAAI/bge-small-en-v1.5`) across deploys |

### Repository layout (deploy roots)

```
repo/
├── frontend/          → Vercel project (root directory)
├── pulse/               → Railway Python service
├── config/              → Bundled in Railway image
├── pyproject.toml       → pip install -e ".[web]"
└── data/                → Railway Volume mount (not in git)
```

---

## 3. Railway — Backend API service

### Service: `pulse-api`

**Purpose:** Serve dashboard JSON, status, and check-failures endpoints.

| Setting | Value |
|---------|-------|
| **Start command** | `pulse-api` or `uvicorn pulse.api.server:app --host 0.0.0.0 --port $PORT` |
| **Health check** | `GET /health` |
| **Port** | Railway `$PORT` (map internally; public HTTPS via Railway domain) |
| **Plan** | Starter or Pro — ML deps need **≥2 GB RAM** recommended for first BGE load |

#### Build

**Option A — Nixpacks (no Dockerfile)**

Railway settings:

```bash
# Build
pip install -e ".[web]"

# Start
uvicorn pulse.api.server:app --host 0.0.0.0 --port ${PORT:-8001}
```

**Option B — Dockerfile (recommended for ML reproducibility)**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY pulse/ pulse/
COPY config/ config/
RUN pip install --no-cache-dir -e ".[web]"
ENV PULSE_DATA_DIR=/data HF_HOME=/data/hf-cache
VOLUME /data
CMD uvicorn pulse.api.server:app --host 0.0.0.0 --port ${PORT:-8001}
```

#### Volume mount

| Mount path | Contents |
|------------|----------|
| `/data` | `PULSE_DATA_DIR` — ledger, cache, runs, embeddings, HF cache |

Set env:

```bash
PULSE_DATA_DIR=/data
HF_HOME=/data/hf-cache
```

#### Environment variables (Railway `pulse-api`)

| Variable | Required | Example |
|----------|----------|---------|
| `PULSE_ENV` | Yes | `production` |
| `PULSE_DATA_DIR` | Yes | `/data` |
| `HF_HOME` | Yes | `/data/hf-cache` |
| `GROQ_API_KEY` | For live analysis | *(secret)* |
| `MCP_SERVER_URL` | Yes | `https://web-production-bf583.up.railway.app` |
| `MCP_APPROVAL_KEY` | Yes | *(secret)* |
| `GOOGLE_DOC_ID` | Yes | Production Doc ID |
| `PULSE_EMAIL_RECIPIENTS` | Yes | `a@x.com,b@y.com` |
| `PULSE_EMAIL_MODE` | Yes | `draft` (API) or `send` (worker only) |
| `PULSE_ALERT_WEBHOOK_URL` | No | Slack webhook |

#### CORS update

In `pulse/api/server.py`, add production Vercel URL:

```python
allow_origins=[
    "http://localhost:3000",
    "https://your-app.vercel.app",
    "https://*.vercel.app",  # preview deploys — tighten for prod
]
```

#### Deploy steps (Railway)

1. Create Railway project → **Deploy from GitHub repo**.
2. Add service → select this repository.
3. Set **Root Directory** = `/` (repo root, not `frontend`).
4. Add **Volume** (1–5 GB) mounted at `/data`.
5. Configure build + start commands (or Dockerfile path).
6. Add environment variables (use Railway shared variables for secrets).
7. Deploy → copy public URL, e.g. `https://pulse-api-production.up.railway.app`.
8. Verify: `curl https://<railway-api>/health` and `/api/dashboard`.

---

## 4. Railway — Weekly worker (cron)

### Service: `pulse-worker`

**Purpose:** Run `pulse run --product groww --confirm-production-send` every Monday 09:00 IST.

| Setting | Value |
|---------|-------|
| **Type** | Cron job **or** second Railway service with shared Volume |
| **Schedule** | `30 3 * * 1` (UTC) = Monday 09:00 IST |
| **Command** | See below |
| **Volume** | **Same** `/data` volume as `pulse-api` (shared via Railway volume attachment) |

#### Cron command

```bash
pulse run --product groww --confirm-production-send
```

#### Worker environment (additional to API)

| Variable | Value |
|----------|-------|
| `PULSE_ENV` | `production` |
| `PULSE_PRODUCTION_CONFIRM` | `1` |
| `PULSE_EMAIL_MODE` | `send` |

#### Resource notes

- First run downloads BGE (~130 MB) and may take **2–5 min** cold start.
- Full pipeline (884 reviews) ~ **1–3 min** after warm cache.
- Set cron **timeout ≥ 15 min**.
- **Do not** run API and worker on the same process — separate services sharing one Volume.

#### Migration from GitHub Actions

| Phase | Action |
|-------|--------|
| **Phase A** | Deploy Railway API + Vercel; keep GHA cron for weekly runs |
| **Phase B** | Attach Volume to Railway worker; run one manual `workflow_dispatch` + Railway dry-run in parallel |
| **Phase C** | Enable Railway cron; disable GHA schedule (keep workflow for manual triggers) |

---

## 5. Vercel — Frontend dashboard

### Project settings

| Setting | Value |
|---------|-------|
| **Framework** | Next.js |
| **Root Directory** | `frontend` |
| **Build Command** | `npm run build` (default) |
| **Output Directory** | `.next` (default) |
| **Node.js** | 20.x |

#### Environment variables (Vercel)

| Variable | Environment | Value |
|----------|-------------|-------|
| `PULSE_API_URL` | Production | `https://<pulse-api>.up.railway.app` |
| `PULSE_API_URL` | Preview | Railway staging API URL or production |
| `PULSE_ENV` | Production | `production` |

The dashboard calls `${PULSE_API_URL}/api/dashboard` server-side (`frontend/lib/dashboard-data.ts`).

Optional: use Vercel rewrite so browser calls same-origin `/api/backend/dashboard` → Railway (already in `next.config.ts`).

#### Deploy steps (Vercel)

1. Import GitHub repo in Vercel.
2. Set **Root Directory** = `frontend`.
3. Add `PULSE_API_URL` → Railway API HTTPS URL.
4. Deploy.
5. Open dashboard → confirm KPIs and runs table load.
6. Add custom domain (optional): `pulse.yourdomain.com`.

#### Vercel limitations (awareness)

| Limitation | Mitigation |
|------------|------------|
| No local `data/` access | Always use Railway API in production |
| Serverless cold starts | Dashboard SSR may add ~1s; acceptable for internal tool |
| No long-running jobs | Weekly `pulse run` stays on Railway worker, not Vercel |

---

## 6. Secrets matrix (all platforms)

| Secret | Vercel | Railway API | Railway Worker | GHA (legacy) | Chitra MCP |
|--------|--------|-------------|----------------|--------------|------------|
| `GROQ_API_KEY` | — | ✓ | ✓ | ✓ | — |
| `MCP_SERVER_URL` | — | ✓ | ✓ | ✓ | — |
| `MCP_APPROVAL_KEY` | — | ✓ | ✓ | ✓ | — |
| `GOOGLE_DOC_ID` | — | ✓ | ✓ | ✓ | — |
| `PULSE_EMAIL_RECIPIENTS` | — | ✓ | ✓ | ✓ | — |
| `PULSE_ALERT_WEBHOOK_URL` | — | ✓ | ✓ | ✓ | — |
| Google OAuth | — | — | — | — | ✓ (MCP only) |

---

## 7. Deployment phases (recommended order)

### Phase 1 — Railway API (staging)

1. Deploy `pulse-api` with `PULSE_ENV=staging`, `PULSE_EMAIL_MODE=draft`.
2. Mount Volume; run one manual `pulse dry-run` via Railway shell.
3. Confirm `/api/dashboard` returns real run data after dry-run.

### Phase 2 — Vercel dashboard

1. Point `PULSE_API_URL` at Railway staging API.
2. Verify dashboard loads; fix CORS if needed.
3. Share preview URL with operators.

### Phase 3 — Railway worker + production

1. Deploy worker with shared Volume.
2. Run manual: `pulse run --iso-week 2026-W24 --email-mode draft`.
3. Complete [sign-off-checklist.md](./sign-off-checklist.md).
4. Enable cron with `PULSE_EMAIL_MODE=send` + `PULSE_PRODUCTION_CONFIRM=1`.

### Phase 4 — Decommission GHA cron (optional)

1. Disable schedule in `.github/workflows/weekly-pulse.yml`.
2. Keep `workflow_dispatch` for emergency manual runs.

---

## 8. Verification checklist

After full deploy:

- [ ] `GET https://<railway-api>/health` → `{"status":"ok"}`
- [ ] `GET https://<railway-api>/api/dashboard` → JSON with `runs`, `kpis`
- [ ] Vercel dashboard shows runs table and KPI cards
- [ ] Doc link opens Google Doc section with anchor `groww-{iso_week}`
- [ ] Manual worker run completes; ledger row `status=completed` on Volume
- [ ] Re-run same ISO week → skipped (idempotent)
- [ ] `pulse check-failures` via API returns 200 with empty alerts (or expected failures)
- [ ] Alert webhook fires on forced failure (optional test)

---

## 9. Monitoring & ops

| Signal | Where |
|--------|-------|
| API uptime | Railway metrics + `/health` |
| Weekly run success | SQLite ledger on Volume; dashboard UI |
| Failures | `GET /api/check-failures`; `PULSE_ALERT_WEBHOOK_URL` |
| Logs | Railway log drain; structured JSON from pulse |
| Artifacts | `data/runs/{run_id}/` on Volume — backup Volume periodically |

### Backup

- Snapshot Railway Volume weekly (Railway backup or rsync `data/ledger/pulse.db`).
- Export Google Doc is already the stakeholder-facing archive.

---

## 10. Cost & sizing (estimate)

| Service | Suggested tier | Notes |
|---------|----------------|-------|
| Vercel | Hobby / Pro | Low traffic internal dashboard |
| Railway `pulse-api` | 2 GB RAM | BGE model + FastAPI |
| Railway `pulse-worker` | 2 GB RAM, cron-only | Same image; runs ~5 min/week |
| Railway Volume | 1–5 GB | Cache + ledger + embeddings |
| Chitra MCP | Existing | No change |
| Groq | Pay-per-token | ~12K tokens/run budget |

---

## 11. Rollback

| Failure | Rollback |
|---------|----------|
| Bad API deploy | Railway → redeploy previous deployment |
| Bad frontend | Vercel → instant rollback to prior deployment |
| Bad weekly run | Ledger marks `failed`; fix and re-run — Doc/email idempotency prevents duplicates |
| Volume corruption | Restore Volume snapshot; re-run missed weeks via `pulse backfill` |

---

## 12. Files to add (implementation follow-up)

When executing this plan, add these repo files:

| File | Purpose |
|------|---------|
| `Dockerfile` | Railway Python image with ML deps |
| `railway.toml` | Build/start config for API + worker |
| `frontend/vercel.json` | Optional redirects, headers |
| `.env.railway.example` | Document Railway env vars |
| Update `pulse/api/server.py` | CORS + `$PORT` binding |
| Update `README.md` | Link to this plan |

---

## 13. Quick reference URLs (fill after deploy)

| Environment | Frontend (Vercel) | API (Railway) |
|-------------|-------------------|---------------|
| Production | `https://____________.vercel.app` | `https://____________.up.railway.app` |
| Staging | Preview branch URL | Staging Railway service |

| External | URL |
|----------|-----|
| Chitra MCP | `https://web-production-bf583.up.railway.app` |
| Google Doc | `https://docs.google.com/document/d/1ArysoTqwaheaUsz4QLHdm5HKOvkkAe_aDwbVnz43ZfA/edit` |
