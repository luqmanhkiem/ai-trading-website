#!/bin/sh
# Double-click on macOS: enter Telegram credentials privately in Terminal.
AURUM_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
AURUM_PY="$AURUM_ROOT/backend/.venv/bin/python"
if [ ! -x "$AURUM_PY" ]; then
    AURUM_PY="$AURUM_ROOT/../../work/venv/bin/python"
fi
if [ ! -x "$AURUM_PY" ]; then
    echo 'Run make setup from the Aurum folder first, then reopen this helper.'
    exit 1
fi
PYTHONDONTWRITEBYTECODE=1 "$AURUM_PY" "$AURUM_ROOT/scripts/setup_telegram.py"
