#!/bin/sh
# Prefer the project venv, then python3 on PATH. Never hardcode a teammate's home.
ROOT="${CLAUDE_PROJECT_DIR:-$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)}"
if [ -x "$ROOT/.venv/bin/python" ]; then
  exec "$ROOT/.venv/bin/python" "$ROOT/hooks/perpetual_retrieve.py"
fi
if command -v python3 >/dev/null 2>&1; then
  exec python3 "$ROOT/hooks/perpetual_retrieve.py"
fi
exec python "$ROOT/hooks/perpetual_retrieve.py"
