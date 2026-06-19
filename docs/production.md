# Production deployment — Groww Weekly Review Pulse

Operator guide for scheduled production runs (Phase 9).

**Related:** [architecture.md §16](./architecture.md#16-environments) · [implementation-plan.md §Phase 9](./implementation-plan.md#phase-9--production-readiness--scheduler)

---

## Production targets

| Asset | Value |
|-------|-------|
| Google Doc | *Weekly Review Pulse — Groww* |
| Doc ID | `1ArysoTqwaheaUsz4QLHdm5HKOvkkAe_aDwbVnz43ZfA` (also in `config/products/groww.yaml`) |
| MCP server | [Chitra MCP on Railway](https://github.com/chitragohad/Chitra-MCP-server) |
| Schedule | Monday 09:00 IST via `.github/workflows/weekly-pulse.yml` |
| Email mode | `send` in production (gated — see below) |

Google OAuth credentials live **only** on the Railway MCP server. The pulse repo never holds Gmail or Docs OAuth secrets.

---

## Go-live gate (email send)

Production `mode=send` is blocked unless explicitly confirmed:

```bash
# Option A — CLI flag
PULSE_ENV=production pulse run --product groww --confirm-production-send

# Option B — environment variable (used by GitHub Actions)
PULSE_ENV=production PULSE_PRODUCTION_CONFIRM=1 pulse run --product groww
```

Development and staging default to `draft` unless `PULSE_EMAIL_MODE=send` is set.

---

## GitHub Actions secrets

Configure these in **Settings → Secrets and variables → Actions**:

| Secret | Required | Notes |
|--------|----------|-------|
| `GROQ_API_KEY` | Yes | Groq summarization |
| `MCP_SERVER_URL` | Yes | Hosted MCP base URL |
| `MCP_APPROVAL_KEY` | Yes | `X-Approval-Key` header |
| `GOOGLE_DOC_ID` | Yes | Production Doc ID |
| `PULSE_EMAIL_RECIPIENTS` | Yes | Comma-separated stakeholder emails |
| `PULSE_ALERT_WEBHOOK_URL` | No | Slack/Discord webhook for failure alerts |

The workflow sets `PULSE_ENV=production`, `PULSE_PRODUCTION_CONFIRM=1`, and `PULSE_EMAIL_MODE=send`.

### Manual trigger

Use **Actions → Weekly Pulse → Run workflow** to test with an optional `--iso-week` override.

### Data persistence

The workflow caches `data/ledger/` and `data/cache/` between runs and uploads artifacts for 30 days. For long-term ledger backup, periodically download artifacts or copy `data/ledger/pulse.db`.

---

## Monitoring

### Structured logs

Every stage emits JSON logs with `run_id`, `product`, `iso_week`, and `stage`. Stage durations appear in `audit.json` under `metrics.stage_durations_seconds`.

### Failure alerts

On `failed` or `partial` ledger status, the orchestrator:

1. Logs an ERROR-level structured event (`stage: monitoring`)
2. POSTs to `PULSE_ALERT_WEBHOOK_URL` when configured

Check recent failures:

```bash
pulse check-failures --product groww --since-days 7
```

Exit code 1 when any failed/partial runs exist (suitable for CI).

### Operator queries

```bash
# What was sent for week X?
pulse status --product groww --iso-week 2026-W24

# SQL against ledger
sqlite3 data/ledger/pulse.db \
  "SELECT run_id, iso_week, status, error_message FROM runs ORDER BY started_at DESC LIMIT 10;"
```

---

## Stakeholder sign-off

Before enabling the scheduler with `send`, complete [sign-off-checklist.md](./sign-off-checklist.md) with product leads.

---

## Cron alternative (self-hosted)

If not using GitHub Actions, add to crontab on a machine with persistent `data/`:

```cron
# Monday 09:00 IST
30 3 * * 1 cd /path/to/pulse && .venv/bin/pulse run --product groww --confirm-production-send >> /var/log/pulse.log 2>&1
```

Ensure `.env` or systemd environment provides the secrets listed above.
