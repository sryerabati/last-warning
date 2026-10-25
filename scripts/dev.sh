#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python || ! -d frontend/node_modules ]]; then
  echo 'Run uv sync --group dev and npm --prefix frontend ci first.' >&2
  exit 1
fi
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload &
backend_pid=$!
npm --prefix frontend run dev &
frontend_pid=$!
cleanup() { kill "$backend_pid" "$frontend_pid" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
wait
