# PRD v2 — PERPETUAL

**Your agent's tool list is not a file. It's a `$vectorSearch` over a MongoDB collection — and the agent writes to it.** Perpetual watches the work you repeat, compiles the ritual into a new named tool, and every other agent connected to the same Atlas cluster — including your teammate's live Claude Code session — inherits the skill seconds later. Agents stop being goldfish; skill becomes a document.

*MongoDB Persistent Context Sprint — .local Build Fest, Aug 13 2026. Team: Sharique + Rohan. Repo: `rohangandotra18/mongoDB` (public). Submission 5:00 PM.*

*v2 (2:35 PM): revised after a 3-reviewer adversarial pass (judge sim, feasibility skeptic, Claude Code integration verifier who probed the MCP claims against a real Claude Code 2.1.220 session). Changes: demo of record is our own two-terminal rendering; Claude Code/MCP becomes the verified coda, not the stage; RAG-shaped beats cut from stage; Linear + live-GitHub + suggestion engine cut; build order re-sequenced around the tool-birth moment.*

---

## 1. Problem — agents don't compound

Every agent session starts at the same competence, forever. Your agent assembled your weekly update from Slack noise and closed issues last Friday — and next Friday it will do the same 6 steps from scratch, because what it learned lives in a context window that died. Persistent *facts* (RAG) don't fix this: the agent remembers **information** but never gains **capability**.

## 2. What Perpetual is

1. **The tool list is a query result.** At plan time the agent runs `$vectorSearch` over a `tools` collection in Atlas and binds whatever comes back as its function schema. Nothing is hardcoded. Delete a document → the agent loses a hand. Insert one → it grows one.
2. **Experience is a collection.** Every run appends a trajectory document. A `$setWindowFields` n-gram aggregation — pattern discovery *in the database* — detects when the same successful action sequence has occurred 3 times.
3. **Repetition compiles into capability.** The detected ritual becomes a macro document: a readable, declarative step list with `$ref` parameter bindings derived from observed dataflow (no codegen, no `exec()`; the LLM only names it). It's inserted into `tools`, auto-embedded, and is discoverable on the very next turn. `TOOLS KNOWN: 7 → 8`.
4. **Skill transfers without experience.** A change stream on `tools` delivers the newborn tool to every other connected agent mid-flight — a different process, a different machine, your teammate's Claude Code session. *Agent A got the experience. Agent B got the skill.*
5. **Bad tools die.** Fitness counters + a TTL index reap macros that stop earning their place. Natural selection on capabilities.

**The workplace domain** (seeded, realistic): Maya Chen, staff eng at Northwind Payments. 120 Slack-export-shaped messages, 18 issues, her delegation graph (`$graphLookup`), and a 12-document voice corpus. The ritual that compiles on stage: her weekly update to her boss — search Slack, list closed issues, check delegations, fetch voice profile, draft in her voice, send. Two prior weeks are seeded as real trajectory documents, so the live run is genuinely the third repetition. Nothing about the birth is faked.

**What Perpetual is NOT:** a dashboard (none exists — terminals only), a chatbot (you don't converse with it; the artifact of a run is a *new tool*, not a reply), or RAG (retrieval's output is the model's *function schema* — it changes what the agent can DO next, not what text fills its prompt).

## 3. Surfaces — camera vs. credential

**Demo of record (the camera): our own two-terminal rendering** — Agent A and Agent B, every pixel controlled, legible from the back of a room, fully offline-capable (`PERPETUAL_MOCK=1` + Python-cosine fallback). Script already locked in `DEMO.md`: cold 6-step run → miner fires on real trajectories → macro JSON births on screen, ElevenLabs announces it, counter ticks 7→8 → warm run is 1 call/~5s in Maya's voice → Agent B's terminal lights up `SKILL ACQUIRED` unprompted.

**The credential (15-second coda): the same `tools` collection served into a real Claude Code session over MCP.** This is the user's product vision and it is **verified, not aspirational** — our reviewer probed it on the wire against Claude Code 2.1.220:

- ✅ Raw JSON-RPC-over-stdio MCP server (~90 lines, **no SDK**) connects, lists tools, executes them.
- ✅ `tools/list_changed` is honored **mid-session with no restart** — the reviewer watched a model call a tool that did not exist when its session started. Our wow moment is real.
- ⚠️ **One-turn race**: Claude Code defers the refresh while that server's tool call is in flight → we emit `list_changed` *before* returning the compile result, not after.
- ⚠️ Proactive push into an *idle* session is impossible with standard MCP (pull-only); "issue arrives live mid-session" as originally written was wrong. In-CLI surfacing = SessionStart hook banner (re-entry catch-up from a local cache file, 5s timeout) + statusline badge with `refreshInterval: 2`.
- 📋 Demo-session config: `ENABLE_TOOL_SEARCH=false`, launch via `--mcp-config --strict-mcp-config` (no consent dialog on stage), `MAX_MCP_OUTPUT_TOKENS=50000`, open `/mcp` *after* the birth (its per-server tool count is the free 7→8 visual).
- **John's transfer beat in Claude Code**: his statusline flips `perpetual: 7 tools` → `⚡ 8 — weekly_update_to_boss` with zero keystrokes (reviewer-rated best risk-adjusted option).

**Cut from the stage** (kept in README as roadmap): `whats_new`/`recall` Q&A beats (mechanically RAG — the judge sim flagged them as the two disqualifying-shaped moments), the suggestion engine (a second wow that dilutes the first), Linear connector, live GitHub polling (replaced by replay through the identical normalizer — honestly labeled), Fireworks-as-decoration, experimental Claude channels.

## 4. Scope

| Priority | Item | Notes |
|---|---|---|
| **P0** | Agent loop: `$vectorSearch` tool binding, trajectory logging | mock-first, Atlas-second |
| **P0** | Miner (`$setWindowFields` n-grams) + compiler ($ref bindings from observed dataflow) | **the differentiator — built FIRST, not last** |
| **P0** | Macro executor | ✅ already built + tested |
| **P0** | Change-stream transfer + Agent B terminal + TOOLS KNOWN counter | poll fallback pre-written |
| **P0** | Two-terminal presentation (rich prints, not a TUI framework) | |
| **P0** | Seeded corpus + voice-profile drafting | ✅ corpus done + validated |
| **P1** | MCP stdio server (raw JSON-RPC, ~90 lines) + `.mcp.json` + statusline/hook | timeboxed coda; ships only after two clean rehearsals |
| **P1** | ElevenLabs birth announcement | pre-rendered fallback; un-ignore `*.mp3` |
| **P2** | LangGraph Mongo checkpointer | README + video only |
| **OUT** | Linear, Slack/GitHub OAuth, live GitHub, suggestion engine, channels, any web UI | roadmap section |

## 5. MongoDB & partners (rubric, 25%)

**Load-bearing Atlas features:** ① Vector Search + Automated Embeddings on `tools.purpose` — retrieval AS the tool-binding mechanism (the definitive "why not Postgres"); ② `$setWindowFields` n-gram mining — learning implemented as an aggregation; ③ change streams — skill transfer between live agents; ④ `$graphLookup` — the delegation graph inside the ritual; ⑤ TTL + fitness — capabilities that die. (Vector index over `messages` too — add `messages_vec` to `ensure_indexes`, currently missing.)

**Partners, all with real jobs:** OpenRouter (agent reasoning + macro naming + voice drafting) · ElevenLabs (birth announcement) · LangChain/LangGraph (checkpointer, P2) · MCP — the integration surface MongoDB ships its own official server for. *(Fireworks cut: a logo with an invented job weakens the real four.)*

## 6. Impact (the claim we own)

Not "less context switching." The claim: **agents today don't compound — every session restarts at fixed competence. Perpetual makes skill a document.** Documents replicate: across sessions, machines, and teammates, with zero deploys. One agent's Thursday afternoon becomes the whole fleet's permanent capability. Compounding is the difference between a tool and a colleague.

## 7. Build plan (from green light, ~2:40)

Known landmines already identified by review, fixed in the first commit: venv pip repair, `seed.py` guard on empty `insert_many`, `messages_vec` index, `.gitignore` un-ignore `*.mp3`, initial commit + push (currently **zero commits**).

| Time | Track A (me, serial) | Track B (subagents, parallel) |
|---|---|---|
| 2:40–3:00 | Atlas `.env` + connect + seed + indexes queryable + first push | Agent loop (PERPETUAL_MOCK) · miner+compiler vs fixture trajectories |
| 3:00–3:25 | Integrate loop on real Atlas; **3:25 BINARY GATE: macro born from mined trajectories, live** | Two-terminal presentation + transfer watcher |
| 3:25–3:40 | Transfer beat end-to-end; rehearse once **from 15 feet away** (legibility gate) | MCP coda server (timeboxed; drop without debate if it fights) |
| 3:40–3:55 | **FEATURE FREEZE.** `--warm` reset fixture, README touch-ups, push | ElevenLabs line render |
| 3:55–4:10 | Two clean dry runs | |
| 4:10–4:30 | Record 60s video → submit (repo public, all members added) | |
| Fallbacks | Birth fails at 3:25 → hand-inserted macro, mining cut from narration (retrieval→execution→transfer = 80% of payload) · change streams balk → 2s poll · MCP balks → still frame in video or cut | |

## 8. Consistency locks (narration ≡ screen)

Tool name **`weekly_update_to_boss`** everywhere · task string "send my weekly update to dana" · counter starts at **7** (the 7 seeded primitives) · no pre-existing `weekly_update` tool anywhere (the agent must acquire a capability it provably lacked) · seeded prior trajectories = weeks of Jul 31 + Aug 7, live run = third repetition.
