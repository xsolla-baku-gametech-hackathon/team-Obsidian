#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${repo_dir}/apps/api/src:${repo_dir}/pipelines/src:${repo_dir}/packages/core/src${PYTHONPATH:+:${PYTHONPATH}}"
exec "${repo_dir}/.venv/bin/uvicorn" ili_api.main:app --host 127.0.0.1 --port 8000 --reload
