#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

VENV=".venv"

if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
fi

source "$VENV/bin/activate"

pip install -q -r requirements.txt

export FLASK_APP=app.py
exec flask run --host 0.0.0.0 "$@"
