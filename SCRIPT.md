# PERPETUAL — the demo script

*Final. Rewritten 4:41 PM after live rehearsal. Everything here was run and verified.*

**The one-liner (open with this):**
> "Your agent's tool list isn't a file. It's a vector search over a MongoDB collection — and the agent writes to it."

---

## SETUP — 2 terminals, side by side, same folder

Perpetual is installed globally now. Both lanes can sit in **the same directory** — the only difference is Perpetual on or off. That's the cleanest possible claim: nobody can say you rigged it with paths.

```
LEFT  (Perpetual ON)     cd ~/"MongoDB Hack"/perpetual  →  ./t1
RIGHT (Perpetual OFF)    ~/t2
```

Before every take:
```
cd ~/"MongoDB Hack"/perpetual && ./go
```
Must print **`TOOLS KNOWN: 9`** and **`ritual support: 2 / 3`**. If not, run it again.

---

# ACT 1 — "it remembers what we decided"  (~45s)

**Type into BOTH windows:**
> what are OUR team's rules for a primary button? quote them, and say where you got them.

**Verified result:**
- **RIGHT:** *"I can't find any documented rules for a primary button anywhere I have access to."*
- **LEFT:** quotes six exact rules — *"from MongoDB Atlas long-term memory, a semantic-search hit on 'Team convention — Designing buttons', **relevance 0.92**"*

> **SAY:** "Same folder. Same model. Same question. One of them has Perpetual."

**Then, audience improv — ask the room for a colour.** Type into BOTH:
> ok for checkout use teal #0FB5A8, 26pt radius, 52pt tall, label 'Pay $40.00'. save that to memory so I don't explain it again tomorrow.

> **SAY:** "Whatever you just shouted — it stores the sentence I actually said. Nothing here is pre-baked."

**Kill both sessions on camera.** `/exit`, `/exit`. Two seconds of silence.

> **SAY:** "Both contexts are gone. That's every agent, every morning."

**Relaunch both. Same question to both:**
> build me that pay button we designed — exact values. swiftui.

**Verified result:** LEFT writes SwiftUI with `#0FB5A8`, 26pt, 52pt, "Pay $40.00". RIGHT asks you to paste the spec.

> **SAY THIS — it is the honest version and it is stronger:**
> "Claude Code does keep a local memory file. Fine. Perpetual's memory is in a database — so it's shared. Different project, different machine, different agent. And it doesn't just remember facts. Watch."

---

# ACT 2 — "it remembers what we keep DOING"  ← the part nobody else has  (~60s)

Two terminals. **Start the watcher first** and never touch it again.

```
RIGHT:  python -m perpetual.watcher --agent-id agent-b
LEFT:   python -m perpetual.agent "send my weekly update to dana"
```

25 seconds, 6 tool calls scroll past.

> **SAY (slightly annoyed):** "Search Slack. Pull my closed issues. Check who I delegated to. Match my writing voice. Draft. Send. Third time this week. It doesn't know it keeps doing this — **but its logs do.**"

```
LEFT:   python -m perpetual.miner
```

Screen shows: **6-gram · support 3 · RITUAL DETECTED** → **`✦ NEW TOOL BORN: weekly_update_to_dana ✦`** → the macro JSON with `"$ref": "s4.text"` → **`TOOLS KNOWN: 9 → 10`**

> **SAY:** "That's a MongoDB aggregation — `$setWindowFields` over its own trajectories — finding the pattern. It named the tool. It wrote the steps. You can read them before they ever run."

**Now point at the right terminal. Don't touch it.** Within one second:
**`⚡ SKILL ACQUIRED: weekly_update_to_dana`** → `TOOLS KNOWN: 9 → 10` → it executes the macro immediately: *"6 primitive calls, 1 tool call — zero trial and error."*

> **SAY:** "Different process. A change stream pushed it. **Agent A got the experience. Agent B got the skill.**"

```
LEFT:   python -m perpetual.agent "send my weekly update to dana"
```
**1 tool call.** Was 6.

---

# CLOSE

> "A memory file can remember what you decided. It cannot hand a *capability* to another agent on another machine. Skills stop being code somebody deploys — they become documents. And documents replicate. One agent's Thursday afternoon becomes the whole team's permanent capability."

---

# 60-SECOND VIDEO CUT

Skip Act 1 entirely. Record **Act 2 only** — it is self-contained, needs no Claude Code sessions, and it is the part no other team will have.

| Time | Screen | Voiceover |
|---|---|---|
| 0:00–0:05 | Two terminals, right idle at `TOOLS KNOWN: 9` | "This agent's tools aren't in a file. They're rows in MongoDB." |
| 0:05–0:20 | Cold run, 6 calls *(speed-ramp 2×)* | "Six steps to write one weekly update. It's done this three times." |
| 0:20–0:35 | Miner: RITUAL DETECTED → NEW TOOL BORN → 9 → 10 | "A MongoDB aggregation finds the pattern in its own logs and compiles a new tool. It named it. It wrote the steps." |
| 0:35–0:45 | Right terminal lights up, untouched | "Change stream. Second agent, different process — it just gained a skill it never learned." |
| 0:45–0:55 | Warm run: 1 call | "Same request. One call now." |
| 0:55–1:00 | Hold on `TOOLS KNOWN: 10` | "Agent A got the experience. Agent B got the skill." |

---

# IF IT BREAKS

| Problem | Do this |
|---|---|
| Right lane somehow knows the spec | You forgot `~/t2` (it sets `PERPETUAL_OFF=1`). |
| Miner says support = 2 | You skipped the cold run. Run the agent once, then the miner. |
| Miner says "no ritual" | Already born this session. `./go` and start over — one birth per reset. |
| Agent B silent > 5s | Ctrl-C, relaunch with `--poll`. Looks identical. |
| Everything is slow | `export PERPETUAL_MOCK=1` — full loop runs offline in ~2s. |

# Q&A

- **"Doesn't Claude Code already have memory?"** — Yes, a local file, per project, on one laptop. Ours is a database: shared across machines and agents, semantically searched, and it stores *skills*, not just facts. A file can't hand a compiled tool to another process.
- **"Why MongoDB, not Postgres + a vector store?"** — The tool list *is* a `$vectorSearch`. Mining is `$setWindowFields`. Transfer is a change stream. The delegation graph is `$graphLookup`. Four query shapes, one database, no sync layer.
- **"Isn't this RAG?"** — RAG puts text in a prompt. Here retrieval output *is* the model's function schema. Delete a document, the agent loses an ability.
- **"What's seeded vs live?"** — The Slack-shaped workplace corpus is seeded. Atlas, Gemini, the mining, the compilation, the transfer — all live, right now, on stage.
