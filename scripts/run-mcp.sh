#!/bin/sh
# Portable MCP launcher — works from the repo root on any machine.
ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="$(command -v python3)"
else
  PY="$(command -v python)"
fi
exec "$PY" "$ROOT/src/perpetual/mcp_server.py"
