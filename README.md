# Groww Weekly Review Pulse

Automated weekly pipeline that turns public **Google Play** reviews for **Groww** into a one-page insight report and delivers it via Google Workspace (Docs + Gmail) through MCP servers.

## Documentation

| Document | Description |
|----------|-------------|
| [docs/problemStatement.md](docs/problemStatement.md) | Product intent and requirements |
| [docs/architecture.md](docs/architecture.md) | Technical architecture |
| [docs/implementation-plan.md](docs/implementation-plan.md) | Phase-wise build plan |
| [docs/edge-cases.md](docs/edge-cases.md) | Corner cases and fallbacks |
| [docs/production.md](docs/production.md) | Production scheduler, secrets, monitoring |
| [docs/deployment-railway-vercel.md](docs/deployment-railway-vercel.md) | Railway + Vercel deployment plan |
| [docs/sign-off-checklist.md](docs/sign-off-checklist.md) | Stakeholder go-live checklist |

## Prerequisites

- Python 3.9+ (3.11+ recommended)
- Node.js 20+ (optional — MCP server is hosted on Railway)

## Install

### Python (pulse agent)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Environment

```bash
cp .env.example .env
```

Fill in `.env` before live runs:

| Variable | Required for | Notes |
|----------|--------------|-------|
| `GROQ_API_KEY` | Analysis / run | Groq summarization |
| `MCP_SERVER_URL` | Live delivery | Hosted [Chitra MCP server](https://github.com/chitragohad/Chitra-MCP-server) |
| `MCP_APPROVAL_KEY` | Live delivery | `X-Approval-Key` header |
| `GOOGLE_DOC_ID` | Live delivery | Target Google Doc |
| `PULSE_EMAIL_RECIPIENTS` | Live delivery | Comma-separated recipient list |
| `PULSE_EMAIL_MODE` | Optional | `draft` (default) or `send` |
| `PULSE_PRODUCTION_CONFIRM` | Production send | Set to `1` to allow `mode=send` when `PULSE_ENV=production` |
| `PULSE_ALERT_WEBHOOK_URL` | Optional | Webhook for failed/partial run alerts |

## Operator runbook

### 1. Local dry-run (no Google credentials)

Runs ingest → analyze → render, writes `report.json` and previews under `data/runs/{run_id}/`, skips MCP. Safe for development.

```bash
source .venv/bin/activate
export GROQ_API_KEY=your_key   # needed for full summarization

pulse dry-run --product groww
# or explicit week:
pulse dry-run --product groww --iso-week 2026-W24
```

Check outputs:

```bash
ls data/runs/*/
cat data/runs/*/audit.json
pulse status --product groww --iso-week 2026-W24
```

### 2. Staging E2E (Doc append + Gmail draft)

Requires all delivery env vars above.

```bash
source .env
pulse run --product groww --iso-week 2026-W24 --email-mode draft
```

Verify:

1. `pulse status --product groww --iso-week 2026-W24` shows `completed` with `google_doc` and `gmail` delivery ids.
2. Open the Doc URL from status output — section anchor `groww-2026-W24` should be present.
3. Check Gmail drafts — subject `Groww Weekly Review Pulse — 2026-W24`, deep link to the Doc.

Re-running the same week exits 0 with `"skipped": true` — no duplicate Doc section or email.

### 3. Backfill historical weeks

Sequential runs with ledger idempotency (skips already-completed weeks):

```bash
pulse backfill --product groww --from 2026-W20 --to 2026-W22 --dry-run
pulse backfill --product groww --from 2026-W20 --to 2026-W22
```

### 4. ISO week default policy

When `--iso-week` is omitted, `pulse run` / `pulse dry-run` use the product scheduling policy (`config/products/groww.yaml`):

- **Monday before 09:00 IST** → previous complete ISO week
- **Otherwise** → current ISO week in `Asia/Kolkata`

Override anytime with `--iso-week YYYY-Www`.

### 5. Individual pipeline stages

```bash
# Ingest Play Store reviews into cache
pulse ingest --product groww --weeks-back 10
pulse ingest --product groww --force-refresh

# Analyze cached reviews only
pulse analyze --product groww --iso-week 2026-W24
pulse analyze --product groww --skip-llm   # clustering only, no Groq

# Deliver from an existing run directory
pulse deliver-doc --run-dir data/runs/... --doc-id YOUR_DOC_ID
pulse deliver-email --run-dir data/runs/... --to you@example.com
```

### 6. Production scheduler

Weekly runs are configured in [`.github/workflows/weekly-pulse.yml`](.github/workflows/weekly-pulse.yml) (Monday 09:00 IST).

See [docs/production.md](docs/production.md) for:

- GitHub Actions secrets layout
- Production send go-live gate (`PULSE_PRODUCTION_CONFIRM=1`)
- Failure alerts and `pulse check-failures`
- Cron alternative for self-hosted runners

```bash
# Production send (requires confirmation)
PULSE_ENV=production pulse run --product groww --confirm-production-send

# Check recent failures (exit 1 if any)
pulse check-failures --product groww --since-days 7
```

Complete [docs/sign-off-checklist.md](docs/sign-off-checklist.md) before enabling production `send` on the scheduler.

## Tests

```bash
pytest
```

## Operator dashboard (web)

Next.js dashboard matching the Stitch operator design:

```bash
cd frontend && npm install && npm run dev
# or from repo root:
npm run dev:web
```

See [frontend/README.md](frontend/README.md).

## Deploy (Railway + Vercel)

Production split stack: **Vercel** hosts the dashboard; **Railway** hosts the Python API, weekly worker, and persistent data volume.

| Artifact | Purpose |
|----------|---------|
| `Dockerfile` | Railway image for `pulse-api` and `pulse-worker` |
| `railway.toml` | Build + health check for `pulse-api` |
| `.env.railway.example` | Railway env template (copy vars into Railway UI) |
| `scripts/railway-weekly-pulse.sh` | Cron worker entrypoint (Mon 09:00 IST) |
| `frontend/vercel.json` | Vercel build + security headers |

**Quick start:**

1. **Railway `pulse-api`** — deploy from repo root; mount Volume at `/data`; set vars from `.env.railway.example`.
2. **Railway `pulse-worker`** (optional) — same image, start command `bash scripts/railway-weekly-pulse.sh`, same Volume, cron `30 3 * * 1`.
3. **Vercel** — root directory `frontend`; set `PULSE_API_URL` to the Railway API URL.

Full steps: [docs/deployment-railway-vercel.md](docs/deployment-railway-vercel.md).

## Project layout

```
config/           Product and pipeline YAML
frontend/         Next.js operator dashboard (Stitch design)
pulse/            Python agent (CLI, ingestion, pipeline, render, ledger, orchestrator)
data/             Cached reviews, run artifacts, SQLite ledger (gitignored)
tests/            Pytest suite
docs/             Problem statement, architecture, implementation plan
```

## Implementation status

- [x] **Phase 0** — Repository scaffold, config loaders, models, CLI stub, tests
- [x] **Phase 1** — Play Store ingestion (scrape, normalize, cache, `pulse ingest`)
- [x] **Phase 2** — Analysis pipeline (scrub, embed, cluster, Groq summarize, `pulse analyze`)
- [x] **Phase 4** — Report rendering (plain-text Doc section + email teaser)
- [x] **Phase 5** — Google Docs delivery via hosted MCP (`pulse deliver-doc`)
- [x] **Phase 6** — Gmail draft via hosted MCP (`pulse deliver-email`)
- [x] **Phase 7** — Orchestrator, SQLite ledger, idempotency (`pulse run`, `pulse status`)
- [x] **Phase 8** — Full CLI (`dry-run`, `backfill`), ISO week policy, stage metrics, runbook
- [x] **Phase 9** — GitHub Actions scheduler, production config, alerts, go-live gate, sign-off docs
