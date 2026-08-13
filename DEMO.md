# Myelin — Demo Book

Three things: the 60-second video script, the 3-minute stage script, and the checklist you run before either.

Screen layout for both: **two terminals side by side, 50/50.** Left = Agent A (does the work). Right = Agent B (inherits the skill). Right terminal starts first and sits idle showing `TOOLS KNOWN: 7 — watching tools…`. That idle line is the setup for the payoff; do not skip it.

---

## A. 60-second video script

| t | Screen | Voiceover |
|---|---|---|
| **0:00–0:05** | Both terminals visible. Left prints the task: `> maya: send Dana my weekly update`. Right idles at `TOOLS KNOWN: 7 · watching tools…` | "This agent's tool list isn't code. It's a vector search result over a MongoDB collection — and the agent can write to it." |
| **0:05–0:12** | Left: `tool_search("weekly update")` → `$vectorSearch` panel showing 4 retrieved tools with scores. First step fires: `1/6 search_slack…` | "Every turn it asks Atlas what it can do. Right now it knows seven things. So it does this the long way." |
| **0:12–0:28** | Steps stream in with elapsed times: `2/6 list_my_issues ✓` `3/6 who_did_i_delegate ✓` `4/6 get_voice_profile ✓` `5/6 draft_message ✓` `6/6 send_message ✓` then `run complete · 6 calls · 24.8s`. Draft snippet flashes in Maya's voice. | "Six calls. Twenty-five seconds. It does this every Thursday, and every Thursday it costs the same." |
| **0:28–0:34** | Left: `MINER: aggregating trajectories…` then a table row: `search_slack→list_my_issues→who_did_i_delegate→get_voice_profile→draft_message→send_message  support=3  success=1.00`. | "Now the miner runs — one aggregation pipeline over the agent's own logs. Same six steps, three times, always successful." |
| **0:34–0:41** | Left: `COMPILING…` then the macro JSON scrolls, `$ref` bindings highlighted. **ElevenLabs voice line over it.** Then `INSERTED tools/weekly_update_to_boss`. Counter animates **`TOOLS KNOWN: 7 → 8`**. | *(agent voice)* "Compiling weekly_update_to_boss." — *(you)* "It named the tool. It wrote the steps. That's a document, not generated code — you can read it before it runs." |
| **0:41–0:46** | **Right terminal lights up**, unprompted: `⚡ SKILL ACQUIRED — weekly_update_to_boss (via change stream)` and `TOOLS KNOWN: 7 → 8`. Cursor never touched it. | "Second agent, second process. Change stream. No restart, no deploy." |
| **0:46–0:55** | Left: `> maya: send Dana my weekly update` again. One line: `weekly_update_to_boss(week="this week") ✓ 4.9s`. The sent message renders in full, in Maya's voice. Side badge: `6 calls → 1 · 25s → 5s`. | "Ask again. One call. Five seconds. Same message, her voice — the skill is in the database now, not the model." |
| **0:55–1:00** | Both terminals show `TOOLS KNOWN: 8`. Title card: **Myelin**. | "Agent A got the experience. Agent B got the skill." |

**Capture notes:** record at 1080p minimum, terminal font ≥ 18pt, no window chrome. Let the 25-second cold run play at real speed for the first ~6 seconds, then a subtle speed-ramp to 2x through the middle steps — the slowness is the point, but 16 seconds of scrolling is not. Never speed-ramp the warm run; its shortness has to be felt in real time.

---

## B. 3-minute stage script

Same arc, one extra beat (`$graphLookup`), and room to breathe.

### 0:00–0:20 — The claim

> "Every agent you've used has a tool list somebody typed into a file. It has those tools on day one and the same tools on day four hundred. It'll do your Thursday chore just as slowly the fiftieth time as the first."
>
> "Myelin deletes that file. The tools live in MongoDB, and the agent retrieves them with vector search — which means the tool list is writable. Watch it write to it."

*Screen: both terminals up. Point at the right one.* "Second agent, second process, idle. Remember it's there."

### 0:20–0:35 — Tool retrieval is the mechanism

Run `> maya: send Dana my weekly update`.

Pause on the `$vectorSearch` panel.

> "That's not a hardcoded list — that's a `$vectorSearch` over `tools.purpose`. Top-k becomes the model's function schema for this turn. Seven tools exist. Nobody wrote a `weekly_update` function, so it improvises."

### 0:35–1:00 — The cold run

Steps stream. Talk over them.

> "search_slack. list_my_issues. who_did_i_delegate. get_voice_profile — that's her actual sent-message corpus, so the draft sounds like her and not like an LLM. draft. send."
>
> "Six calls, twenty-five seconds. And every one of those steps just got written to a `trajectories` collection."

### 1:00–1:20 — The `$graphLookup` beat

> "One thing worth stopping on. Step three."

Run it standalone: `> maya: who did I delegate the reconciliation work to?`

Show the traversal output — Maya → `delegated_to` → John Diaz → `owns` → NWP-412.

> "That's `$graphLookup` over a `relations` collection — the workplace as a graph. Two hops: it doesn't just tell me I handed reconciliation to John, it finds the issue John opened downstream that I never touched. A flat lookup can't reach that. This is why the workplace lives in Mongo and not in a prompt."

### 1:20–1:50 — Mining and birth

> "Now the interesting part. The agent has done this ritual three times."

Trigger the miner. Show the aggregation result row.

> "That's one aggregation pipeline. Group each run's steps in order, project sliding n-grams, group by n-gram, count support and success rate. Support three, success one-point-zero. That's not machine learning, that's a query."
>
> "So it compiles it."

Macro JSON on screen. **ElevenLabs line plays: "Compiling weekly_update_to_boss."**

> "It picked the name. The steps and the `$ref` bindings came out of the observed trajectory — `s5.text` flows into `send_message.body` because that's what actually happened, three times. No code generation. That's a JSON document you can read, review, and delete."

*Point at the counter.* **"Tools known: seven, eight. That number just changed while the agent was running."**

### 1:50–2:15 — Transfer

*Right terminal has already lit up.* Let the audience notice before you say anything. Count to two.

> "I didn't touch that terminal. Change stream on the `tools` collection. Agent B was watching for macro inserts, got the document, and the document is the whole tool — steps, bindings, purpose. It didn't fetch code. It didn't restart."
>
> "**Agent A got the experience. Agent B got the skill.**"

### 2:15–2:40 — The warm run

Re-run the original request on the left.

> "One call. Five seconds. Twenty-five to five, six calls to one, and the message is identical."

*Then:*

> "And because bad habits are as easy to learn as good ones — every macro has a TTL and a fitness counter. Get used, your `expires_at` moves out. Get ignored, Mongo deletes you. Fail too often, you're quarantined and the vector index filters you out, which means you stop being retrievable, which means you stop being a tool. Natural selection, implemented as an index option."

### 2:40–3:00 — Close

> "Everything here is one database. The tools, the vector index that retrieves them, the trajectories they're mined from, the graph, the change stream that ships them, the TTL that kills them, and the LangGraph checkpoints. Skill stopped being weights and became data — and data replicates."
>
> "Agents shouldn't start cold every time. Thank you."

---

### Q&A — suggested answers

**"Why is MongoDB load-bearing? Couldn't you do this with Postgres and a queue?"**
> Five features, one system, and the demo needs all five. Vector Search *is* the tool-binding mechanism — retrieval is why an inserted document becomes a callable tool with no reload. The miner is an aggregation pipeline, so learning is a query I can run mid-demo. `$graphLookup` gives multi-hop delegation answers. Change streams are the transfer. TTL is the forgetting. Could you assemble that from four systems plus glue? Sure — and then you're reconciling four stores and the "insert a doc, gain a skill" property disappears. The reason this is 3.5 hours of work and not 3 weeks is that it's one database.

**"What's seeded and what's live?"**
> The workplace is seeded and fictional — Maya Chen at Northwind Payments, her manager, her colleagues. `messages` is Slack-export-shaped: same channel/user/ts/text/thread_ts fields a real export gives you. Swapping a real export in is a loader change, not an architecture change. We skipped OAuth on purpose for a one-afternoon build. Everything in the *learning loop* is live: real Atlas cluster, real vector retrieval per turn, real mining over trajectories written seconds earlier, real macro insert, real change stream, real TTL, real LLM calls. Drop the learned collections and it happens again from scratch — happy to do it right now.

**"How does binding work without codegen? Isn't the LLM guessing?"**
> The LLM does exactly one thing: names the tool and writes its `purpose` string. It never writes the steps. The steps and the `$ref` bindings are derived mechanically from the trajectory — we logged each call's params and results, so we *observed* that the text `draft_message` returned is the text `send_message` received. `{"$ref": "s5.text"}` is a recorded fact. The executor is about forty lines: resolve refs against a context dict, call the primitive. No `exec`, no generated Python. And if a binding is wrong anyway, the `guard` refuses the run and the fitness counter kills the macro — cheap to create, cheap to kill.

**"What happens with 500 macros?"**
> That's the fun failure mode. Retrieval quality becomes agent capability — a badly written `purpose` makes a good tool invisible. TTL and fitness are the pressure valve; the next thing we'd build is dedup at compile time (vector-search the existing macros before inserting a near-duplicate) and generalizing macros over their `input_schema` instead of minting a new one per variation.

**"Can macros call macros?"**
> Yes structurally — the executor resolves any name in the registry, and retrieved macros are in the registry. We kept the demo to primitives so the JSON fits on a slide. Recursion depth cap is the obvious guard.

---

## C. Pre-demo checklist

Run this in order, finishing no less than 5 minutes before you go up.

**T-15 — reset and rehearse once, fully**
- [ ] `make reset` — drops learned macros, trajectories, runs; keeps the seeded workplace.
- [ ] `python -m myelin.db` returns `ready` (vector indexes **queryable**, not just created — a freshly built index that isn't queryable yet is the #1 way this dies).
- [ ] Confirm seeded prior runs are present so mining support hits 3 on the stage run: `db.trajectories.distinct("run_id")` → 2 prior runs.
- [ ] Full dry run end to end. Then `make reset` again.

**T-10 — pre-warm everything**
- [ ] Pre-warm the Mongo connection and the vector index (`python -m myelin.demo warmup`) — first `$vectorSearch` after idle can take a couple of seconds and it'll look like a hang.
- [ ] One throwaway OpenRouter call and one Fireworks call to warm TLS/DNS.
- [ ] One ElevenLabs call to warm the audio path; confirm the cached line plays through **the room's** output, not the laptop speaker. Volume set on the actual PA, not on the laptop.
- [ ] Change stream: verify Agent B connects and prints `watching tools…` before you present. If B silently failed to open the cursor, the payoff beat is dead and you won't find out until 2:00.

**T-5 — screen**
- [ ] Terminal font ≥ 20pt (24pt if the room is deep). Test from the back row.
- [ ] High-contrast theme, dark background. Both terminals same size, 50/50 split, no overlap.
- [ ] `TOOLS KNOWN` counter visible in both panes at all times — that's the number the whole demo is about.
- [ ] Notifications off, Do Not Disturb on, screensaver and sleep disabled, second monitor mirrored not extended.
- [ ] Clear scrollback in both panes so the first line the audience sees is the task.

**T-2 — fallbacks**
- [ ] Wifi fallback: phone hotspot paired and tested (not just paired — actually run `warmup` over it once).
- [ ] **Hard fallback: a pre-recorded 60-second capture on the local disk**, already open in a player behind the terminals, one keystroke away. If the network dies mid-run, switch without apologizing — say "here's a capture of the same run" and keep the narration going.
- [ ] Screenshot of the compiled macro JSON saved locally, in case you need to talk through the format with no working terminal.
- [ ] Laptop plugged in.

**Failure improv, memorize these**
- Vector search returns nothing → "index just finished rebuilding" → rerun once; if it fails twice, cut to capture.
- Miner finds support 2 not 3 → you forgot the seeded prior runs; run `make reset` (which reseeds them) and rerun.
- Agent B doesn't light up → do **not** restart it on stage. Cut to the capture for that beat, then come back live for the warm run.
- LLM call times out on the naming step → the macro still compiles with a fallback name; say "it fell back to a deterministic name, the steps are the part that matters" and move on.
