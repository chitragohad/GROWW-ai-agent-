# Pulse Operator Dashboard

Next.js web dashboard for **Groww Weekly Review Pulse**, matching the [Stitch design](../stitch_groww_pulse_operator_dashboard/DESIGN.md).

## Run locally

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

Start the Python API in another terminal (from repo root):

```bash
pip install -e ".[web]"
pulse-api
```

The dashboard calls `PULSE_API_URL` (default `http://127.0.0.1:8001`). If the API is down, it falls back to `../data/runs/` and demo fixtures.

## Deploy to Vercel

1. Import the repo in Vercel and set **Root Directory** to `frontend`.
2. Add environment variable:
   - `PULSE_API_URL` = your Railway `pulse-api` public URL (e.g. `https://pulse-api-production.up.railway.app`)
3. Deploy — `vercel.json` is included for security headers.

On Vercel, the dashboard uses the API only (no local filesystem fallback).

## Data source

| Environment | Source |
|-------------|--------|
| **Vercel (production)** | Railway `GET /api/dashboard` via `PULSE_API_URL` |
| **Local dev** | Python API first, then `../data/runs/`, then demo fixtures |

## Stack

- Next.js 15 (App Router)
- React 19
- Tailwind CSS (design tokens from Stitch)
- Inter + JetBrains Mono

## Screens

v1 implements the **Operator Dashboard** only. Sidebar links for Reports, Backfill, etc. are disabled placeholders.

Action buttons (Run now, Dry run, Backfill) are UI-only in v1 — wire to a backend API in a follow-up.

See [docs/deployment-railway-vercel.md](../docs/deployment-railway-vercel.md) for the full Railway + Vercel guide.
