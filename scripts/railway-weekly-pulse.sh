#!/usr/bin/env bash
# Railway cron worker — weekly production pulse run (Mon 09:00 IST).
set -euo pipefail

export PULSE_ENV="${PULSE_ENV:-production}"
export PULSE_PRODUCTION_CONFIRM="${PULSE_PRODUCTION_CONFIRM:-1}"
export PULSE_EMAIL_MODE="${PULSE_EMAIL_MODE:-send}"
export PULSE_DATA_DIR="${PULSE_DATA_DIR:-/data}"
export HF_HOME="${HF_HOME:-/data/hf-cache}"

echo "[pulse-worker] starting weekly run at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
pulse run --product groww --confirm-production-send
echo "[pulse-worker] completed with exit code 0"
