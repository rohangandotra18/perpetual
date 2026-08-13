#!/bin/bash
# Perpetual pre-flight — run before every take. Takes ~90s.
cd "$(dirname "$0")" || exit 1
source .venv/bin/activate
export PYTHONPATH=src

echo "→ clearing Claude Code's on-disk memory (the demo killer)"
rm -f "$HOME"/.claude*/projects/*MongoDB-Hack-perpetual/memory/*.md 2>/dev/null
echo "→ resetting vanilla lanes"
rm -rf "$HOME/demo-vanilla" "$HOME/demo-vanilla-2"
mkdir -p "$HOME/demo-vanilla" "$HOME/demo-vanilla-2"
echo "→ resetting Atlas to warm state (this is the slow part)"
python -m perpetual.demo reset 2>&1 | grep -aE "seeded|TOOLS KNOWN|support" | sed 's/\x1b\[[0-9;]*m//g'
echo
echo "READY.  Open your 4 terminals:"
echo "  T1  cd ~/'MongoDB Hack'/perpetual && ENABLE_TOOL_SEARCH=false claude --mcp-config scripts/mcp-demo.json --strict-mcp-config"
echo "  T2  cd ~/demo-vanilla && claude"
echo "  T3  cd ~/'MongoDB Hack'/perpetual && source .venv/bin/activate && export PYTHONPATH=src"
echo "  T4  cd ~/'MongoDB Hack'/perpetual && source .venv/bin/activate && export PYTHONPATH=src && python -m perpetual.watcher --agent-id agent-b"
