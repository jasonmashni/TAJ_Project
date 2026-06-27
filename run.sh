#!/usr/bin/env bash
# Start TAJ. Creates a venv + installs core deps on first run, then launches.
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment…"
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing core dependencies…"
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "Starting TAJ on http://${TAJ_HOST:-127.0.0.1}:${TAJ_PORT:-8000}"
python -m backend.main
