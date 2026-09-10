#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
api_pid=""

cleanup() {
  if [[ -n "${api_pid}" ]]; then
    kill "${api_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

"${repo_dir}/scripts/run_api.sh" &
api_pid="$!"

for _ in {1..40}; do
  if curl -fsS "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done

if ! curl -fsS "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
  echo "API did not start on http://127.0.0.1:8000" >&2
  exit 1
fi

cd "${repo_dir}/apps/web"
npm run dev
