# Run-of-show card

Everything below was dry-run end to end at 3:45 PM and worked. Times are measured, not guessed.

## Terminal layout

| | |
|---|---|
| **T1** (left, big font) | Perpetual-connected Claude Code — `cd ~/"MongoDB Hack"/perpetual` |
| **T2** (right) | Vanilla Claude Code — `cd ~/demo-vanilla` |
| **T3** (later, replaces T2) | Agent A terminal — the chore + the birth |
| **T4** (later, right) | Agent B watcher — nobody touches this one |

## Pre-flight — run this every single time before a take

```bash
cd ~/"MongoDB Hack"/perpetual && source .venv/bin/activate && export PYTHONPATH=src
rm -f ~/.claude-account2/projects/*MongoDB-Hack-perpetual/memory/*.md   # ← the demo killer
rm -rf ~/demo-vanilla ~/demo-vanilla-2 && mkdir -p ~/demo-vanilla ~/demo-vanilla-2
python -m perpetual.demo reset          # ~90s. Must end: 9 tools, support 2/3, 0 memories
```
Confirm it says **`TOOLS KNOWN: 9`** and **`ritual support: 2 / 3`**. If not, stop and re-run.

Launch commands:
```bash
# T1  (Perpetual)
ENABLE_TOOL_SEARCH=false claude --mcp-config scripts/mcp-demo.json --strict-mcp-config
# T2  (vanilla — MUST be the other directory)
cd ~/demo-vanilla && claude
```

---

# ACT 0 — "it remembers what we decided"  (~70s)

**Beat 1 — design out loud. Type into BOTH terminals (same words).**
> designing the primary pay button for our checkout screen. someone in the room said make it teal. pill shape, chunky. give me your take in 4 lines.

*Say:* "Same model both sides. Watch the left one." — T1 answers with our team's actual button conventions (tap targets, verb-first label, five states). **A banner appears: `⚡ perpetual: recalled 1 skill from Atlas`.** Nobody asked for it; typing the word *button* pulled the skill out of MongoDB.

**Beat 2 — audience improv (do not skip; this is the "not canned" proof).**
*Ask the room:* "give me a hex colour, or what the button should say." Then type into **both**:
> good. go with teal #0FB5A8, 26pt radius, 52pt tall, label 'Pay $40.00'. save that to memory so I don't explain it again tomorrow.

*(swap in whatever the room shouted — it genuinely does not matter, `save_to_memory` stores the sentence that was actually said.)*
T1 calls `save_to_memory` → it lands in Atlas with a Gemini embedding. T2 just says "noted."

**Beat 3 — kill both. On camera. Ctrl-C, Ctrl-C. Two seconds of silence.**
*Say:* "Both contexts are gone. That's every agent, every morning."

**Beat 4 — fresh sessions, both lanes (T2 opens in `~/demo-vanilla-2`), same sentence:**
> build me that pay button we designed — exact values. swiftui.

**Verified outcome:**
- **T2 (vanilla):** *"send me a screenshot or a Figma frame… a path to where the design lives."* Cold start.
- **T1 (Perpetual):** full SwiftUI with **#0FB5A8, 26pt, 52pt, "Pay $40.00"** — *and* it raises the unresolved contrast question from the earlier conversation and offers two fixes.

*Say:* **"Same model. Same question. One kept its memory in a context window that just died — the other kept it in MongoDB."**

---

# ACT 1 — "it remembers what we keep doing"  (~60s)

T3 left, T4 right. Start the watcher **first** so it sits idle at `TOOLS KNOWN: 9`.

```bash
# T4 — Agent B. Never touched again.
python -m perpetual.watcher --agent-id agent-b
# T3 — the chore
python -m perpetual.agent "send my weekly update to dana"
```
**22s, 6 tool calls.** *Say, a bit annoyed:* "Search Slack, pull my closed issues, check who I delegated to, match my writing voice, draft, send. Third time I've done this this week. It doesn't know it keeps doing this — **but its logs do.**"

```bash
# T3 — the birth
python -m perpetual.miner
```
Screen shows the aggregation result: **6-gram, support 3, RITUAL DETECTED** → **`✦ NEW TOOL BORN: weekly_update_to_dana ✦`** → macro JSON → **`TOOLS KNOWN: 9 → 10`**.
*Say:* "That's a MongoDB aggregation finding the pattern — `$setWindowFields` over its own trajectories. It named the tool. It wrote the steps. You can read them before they run."

**Then point at T4 without touching it.** Within ~1s: **`⚡ SKILL ACQUIRED`**, `TOOLS KNOWN: 9 → 10`, and it executes the macro immediately — *"6 primitive calls, 1 tool call, zero trial and error."*
*Say:* **"Different process. Change stream. Agent A got the experience — Agent B got the skill."**

```bash
# T3 — warm run
python -m perpetual.agent "send my weekly update to dana"
```
**1 tool call, ~11s** (was 6 calls, 22s).

---

# CODA — "say it, get it"  (~25s, optional if time is tight)

In T1, type:
> i do this every friday. just make it a tool.

Claude calls `compile_ritual`. **Then a SECOND, separate prompt** (hard rule — same-turn loses the tool-list refresh race):
> cool, run it.

The newborn tool is in its list and executes. No restart. *Say:* "The tool list isn't a file — it's a query against MongoDB. The database changed, so the agent's abilities changed, mid-session."

---

# The closing line

> "Skills stop being code someone deploys. They become documents — and documents replicate. One agent's Thursday afternoon becomes the whole team's permanent capability."

---

# If something breaks

| Breaks | Say this, do this |
|---|---|
| Vanilla lane accidentally guesses right | "Lucky guess on the colour — ask it the radius and the label." It won't have those. |
| Skill banner doesn't appear | Keep going; the answer still contains the conventions. Show `hooks/perpetual_retrieve.py` in Q&A. |
| Miner finds support=2 | You skipped the cold run, or reset mid-demo. `python -m perpetual.agent "send my weekly update to dana"` then re-run the miner. |
| Agent B silent >5s | `Ctrl-C`, relaunch with `--poll`. Visually identical. |
| Atlas slow / wifi dies | Everything except the Claude sessions runs on `PERPETUAL_MOCK=1`. Last resort: the recorded video. |
| Coda tool not visible | You merged the two prompts. Send a second prompt. |

# Q&A ammo

- **"Why MongoDB and not Postgres + a vector store?"** — The tool list is literally a `$vectorSearch` result; mining is `$setWindowFields`; transfer is a change stream; the delegation graph is `$graphLookup`. Four different query shapes, one database, no sync layer between them.
- **"Isn't this RAG?"** — RAG puts text in a prompt. Here retrieval output *is* the model's function schema. Delete a document and the agent loses an ability.
- **"What's seeded vs live?"** — The workplace corpus (Slack-export-shaped) is seeded; Atlas, Gemini, the mining, the compilation, the transfer are all live. Swapping a real Slack export is a loader change.
- **"Could it compile something wrong?"** — Macros are declarative JSON you can read before running, never generated code. Fitness counters + a TTL index retire tools that stop earning their place.
