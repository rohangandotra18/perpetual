# Installing Perpetual as an MCP server

There is nothing to download from a registry. The MCP server is `src/perpetual/mcp_server.py`
in this repo — a dependency-free JSON-RPC-over-stdio program. Claude Code launches it as a
subprocess and talks to it over stdin/stdout. "Installing" it means telling Claude Code the
command to run.

## Setup (about 2 minutes)

```bash
git clone https://github.com/rohangandotra18/perpetual.git
cd perpetual
uv venv .venv && source .venv/bin/activate && uv pip install -r requirements.txt
cp .env.example .env      # add your Atlas URI + Gemini key
PYTHONPATH=src python -m perpetual.db     # create collections + vector indexes
PYTHONPATH=src python -m perpetual.seed   # load the workplace corpus + skills
```

## Connecting it to Claude Code — three ways

**1. Project config (what judges get automatically).** `.mcp.json` is committed at the repo root.
Open Claude Code in this folder and it offers to enable the `perpetual` server; approve once.

```bash
cd perpetual && claude
```

**2. Explicit config file (what we use on stage — no approval dialog).**

```bash
ENABLE_TOOL_SEARCH=false claude --mcp-config scripts/mcp-demo.json --strict-mcp-config
```

`--strict-mcp-config` ignores every other MCP server you have configured, so the session shows
only Perpetual's tools.

**3. One-liner registration (persists to your user config).**

```bash
claude mcp add perpetual -- /abs/path/to/perpetual/.venv/bin/python /abs/path/to/perpetual/src/perpetual/mcp_server.py
claude mcp list     # verify it connects
```

## What you get

`/mcp` in any session lists the connected server and its tool count. The tools are not hardcoded:
`tools/list` is answered by querying the `tools` collection in MongoDB Atlas, so the tool list
changes when the database changes — including tools the agent compiles for itself at runtime,
which arrive mid-session via `notifications/tools/list_changed` with no restart.

The automatic skill retrieval is separate from MCP: `.claude/settings.json` registers a
`UserPromptSubmit` hook (`hooks/perpetual_retrieve.py`) that embeds each prompt and vector-searches
Atlas before Claude sees it.
