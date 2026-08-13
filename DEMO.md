# Perpetual — Demo Book

The show is a conversation, not a recital. Everything below is written as **things you say**, not lines you read. If you paraphrase, you're doing it right. The only words that must be typed exactly are the ones marked `TYPE:`.

**The arc, in one breath:** it remembers what we *decided* → it learns what we keep *doing* → and you can tell it to turn a habit into a tool, out loud, right there.

| | Act | What the audience actually sees |
|---|---|---|
| **Act 0** | Cold start, A/B | Two Claude sessions design a button with the audience. Both get killed on camera. Fresh sessions. **Two rendered buttons side by side** — one guessed, one exact. |
| **Act 1** | Birth + transfer | The agent does a 6-step chore the slow way, mines its own logs, compiles a new tool. `TOOLS KNOWN 9 → 10`. A second terminal nobody touched gains the tool. |
| **Coda** | Say it, get it | "I do this every Friday — just make it a tool." `compile_ritual`. Next prompt, the newborn tool runs. |

---

## HARD RULES (verified today — do not improvise around these)

1. **Two-prompt coda rule.** `compile_ritual` births the macro; the newborn tool is visible on the **NEXT** prompt. Same-turn use loses the tools-list refresh race. Script the coda as two prompts. No session restart needed.
2. **Vanilla-different-directory rule.** The no-MCP lane must run in a **different directory** (`~/demo-vanilla`). Inside the project folder, Claude Code can search its own on-disk transcripts and reconstruct the spec — which kills the contrast.
   - *Derived guard (same reason, not separately verified): the **fresh** vanilla session must open in a **third, empty** directory (`~/demo-vanilla-2`), because the first vanilla session left both a transcript **and** `button.html` on disk in `~/demo-vanilla`. Either would leak the spec.*
3. **Clear Claude Code's own file memory before the show.** `rm -f ~/.claude*/projects/*MongoDB-Hack-perpetual/memory/*.md` — if a rehearsal left a spec in Claude's on-disk memory, the "fresh" session will recall it from a FILE instead of Atlas and the whole point collapses. Verified failure mode; check it every rehearsal.
4. **Reset before the show, not during.** `PYTHONPATH=src python -m perpetual.demo reset` is the warm known-good state. It clears `memories` too (`src/perpetual/seed.py:36`) — which is exactly what you want: a rehearsal button spec left in `memories` would compete with the live one at recall time.
5. **Counters.** 9 primitives → `TOOLS KNOWN: 9` (the `tools` collection). Birth takes it to **9 → 10**. The new tool is named **`weekly_update_to_dana`**. Claude's MCP `tools/list` is always **one higher** because `compile_ritual` is appended (10 before birth, 11 after) — narrate `TOOLS KNOWN`, not `/mcp`.
6. **Support math.** After `reset`, ritual support = 2. One live cold run makes it 3, which is what lets the miner fire on stage. Check with `PYTHONPATH=src python -m perpetual.demo birth-check`.
7. **Session commands.**
   ```bash
   # Perpetual-connected Claude Code (run from the project dir)
   ENABLE_TOOL_SEARCH=false claude --mcp-config scripts/mcp-demo.json --strict-mcp-config

   # vanilla lane
   cd ~/demo-vanilla && claude

   # terminals
   PYTHONPATH=src python -m perpetual.agent "send my weekly update to dana"   # cold, 6 steps, ~26s
   PYTHONPATH=src python -m perpetual.miner                                   # births weekly_update_to_dana
   PYTHONPATH=src python -m perpetual.watcher                                 # Agent B, change stream
   PYTHONPATH=src python -m perpetual.demo reset | status | birth-check
   ```

---

# ACT 0 — "It remembers what we decided"

**Screen:** two Claude Code sessions, 50/50. **LEFT = vanilla** (`~/demo-vanilla`, no MCP). **RIGHT = Perpetual** (MCP config above). Two browser windows pre-positioned behind them, one per lane, so `open` lands somewhere visible.

Both lanes have full tools in interactive mode. Both can write and open HTML. That's deliberate — for the first ninety seconds the two lanes are **equally capable**, which is what makes the ending land.

### Beat 0 — pre-roll (on screen before the clock starts)

Have the opening design turn already sitting on both screens. It's setup, not payoff, and you don't want ten seconds of dead air.

`TYPE:` (both lanes, same words)
> we're putting a primary CTA button in the Northwind Pay checkout. give me two or three directions — i want warm, not corporate

### Beat 1 — decide out loud (~20s, live)

Talk to it the way you'd talk to a coworker. Pick a direction by name, don't spec it.

> "Second one. Coral, full pill, keep it chunky."

`TYPE:` (both lanes)
> yeah do #2. coral #FF6B5A, full pill, 52 high, white label semibold 17

### Beat 2 — THE IMPROV SLOT (~15s, must be live)

Turn to the room. This is the beat that proves nothing is canned, so sell it.

> "I need a label. Somebody shout — what does this button say?"

Take the first clear shout. Weird is better than sensible — "SEND IT", "YEET", "PAY THE MAN". If two people shout, pick the funnier one and repeat it into the mic so the recording has it.

`TYPE:` (both lanes — substitute the shouted label)
> label is "«SHOUTED LABEL»", all caps. light haptic + 150ms scale to 0.97 on press. now build me a quick html preview and open it

Both lanes write `button.html` and open it. **Two identical buttons appear.** Say so:

> "Same model, same everything. Right now these two are the same product."

*Room dead? Say "fine, I'll be the audience — «pick something absurd»" and move. The value doesn't matter to the system; see the fallback note in the 3-minute script.*

### Beat 3 — save it, casually (~10s)

Do not announce a feature. Ask for it the way you'd ask anyone.

`TYPE:` (both lanes)
> nice. save that to memory so i don't have to explain it again tomorrow

- **Left (vanilla):** says "noted" / offers to write a file. It has nowhere to put it.
- **Right (Perpetual):** calls `save_to_memory` → the spec lands in Atlas with a Gemini embedding.

> "One of them just wrote that to a database. The other one was polite about it."

### Beat 4 — kill them, on camera (~8s)

Ctrl-C the left. Ctrl-C the right. Slowly. Then **stop talking for two full seconds.**

> "That's it. That conversation is gone. That's every agent session you've ever had."

### Beat 5 — fresh sessions, casual ask (~25s)

Open a fresh vanilla in the **third, empty** directory (`~/demo-vanilla-2`) and a fresh Perpetual session. Type the same thing in both, phrased like a person who assumes you remember:

`TYPE:` (both lanes)
> build the «SHOUTED LABEL» button we designed for Northwind Pay — exact values — and open the html preview

- **Left:** hits the wall. "That context isn't carried over here" → placeholders, a generic blue rounded rectangle.
- **Right:** calls `recall_memory` (`$vectorSearch` over `memories`), then writes the exact button.

### Beat 6 — THE PAYOFF (visual, ~10s)

Bring both browser windows forward, side by side. Don't narrate over the first second — let them look.

**Left: a generic blue rounded rect. Right: the coral pill, «SHOUTED LABEL», 52 tall, pressing to 0.97.**

> "Same model. Same question. One kept it in a context window that just died. The other kept it in MongoDB."
>
> "That's what 'no cold start' means."

*If the clock is generous:* `TYPE:` on the right → `now the SwiftUI ButtonStyle for it`. Verified: it produces every value exact — #FF6B5A, 26pt radius, 52pt, 17pt, 8% shadow, 0.97/150ms — **and flags honestly which values were never specified.** That honesty is worth a sentence: "it knows what it wasn't told."

**Hand-off line into Act 1:**
> "Okay — remembering a decision is table stakes. Watch it remember a *skill*."

---

# ACT 1 — "It learns what we keep doing"

**Screen:** two terminals, 50/50. Left = Agent A (does the work). Right = Agent B, already running `perpetual.watcher`, idle at `TOOLS KNOWN: 9 · watching tools…`. **Point at the right one before you start anything.**

> "Second agent, second process, doing nothing. Just remember it's there."

### Beat 1 — the chore, the slow way (~30s)

`TYPE:` (left)
```bash
PYTHONPATH=src python -m perpetual.agent "send my weekly update to dana"
```

Talk over the steps. Don't read them; react to them.

> "It's asking Atlas what it can do — that's a `$vectorSearch`, not a hardcoded list. Nobody wrote a `weekly_update` function, so it's improvising."
>
> "Slack. Issues. Who I delegated to. My voice profile — that's my actual sent messages, which is why the draft doesn't sound like an LLM. Draft. Send."
>
> "Six calls. Twenty-six seconds."

### Beat 2 — the motivation (the "third time this week" moment)

Land this one flat and a little annoyed. It's the human beat of the whole demo.

> "Here's the thing. That's the **third time this week** I've asked for that. Same six steps, every time. And it'll be twenty-six seconds again on Friday, and again next Thursday, forever."
>
> "It doesn't know that it keeps doing this. But its logs do."

### Beat 3 — mining and birth (~20s)

`TYPE:` (left)
```bash
PYTHONPATH=src python -m perpetual.miner
```

> "One aggregation pipeline over its own trajectories. Group each run's steps in order, slide an n-gram over them, count support and success rate. Support three, success one-point-oh. That's not machine learning, that's a query."

Macro JSON scrolls. *(ElevenLabs: "Compiling weekly_update_to_dana.")*

> "It picked the name. It did **not** write the steps — the steps and the `$ref` bindings came out of what actually happened, three times. No code generation. That's a document you can read before you run it."

*Point at the counter.* **"Tools known: nine. Ten. That changed while it was running."**

### Beat 4 — transfer (~15s)

The right terminal has already lit up: `⚡ SKILL ACQUIRED — weekly_update_to_dana`, `TOOLS KNOWN: 9 → 10`. **Shut up and count to two.** Let them find it.

> "I didn't touch that terminal. Change stream on the `tools` collection. It didn't fetch code, it didn't restart — the document *is* the tool."
>
> "**Agent A got the experience. Agent B got the skill.**"

### Beat 5 — warm run (~10s)

`TYPE:` (left) — same request, word for word
```bash
PYTHONPATH=src python -m perpetual.agent "send my weekly update to dana"
```

One line: `weekly_update_to_dana(...) ✓`.

> "One call. Five seconds. Same message."

*If you have room:* "And because bad habits learn as easily as good ones — every macro has a TTL and a fitness counter. Get used, you live longer. Get ignored, Mongo deletes you. Fail, you're quarantined, the vector index stops returning you, and you stop being a tool. Natural selection as an index option."

---

# CODA — "Just make it a tool"

Back on the Perpetual Claude Code session. This is the part that makes it feel like a product instead of a pipeline. Say it like you're delegating, not demonstrating.

**Prompt 1** — `TYPE:`
> i do this every friday. just make it a tool

Claude calls `compile_ritual`. Output: `⚡ Compiled new tool 'weekly_update_to_dana' … TOOLS KNOWN: 9 → 10`.

> "It mined its own history and minted a tool. In a chat window."

**Prompt 2** (the two-prompt rule — **do not merge these**) — `TYPE:`
> cool, run it

Claude now has `weekly_update_to_dana` in its tool list and calls it directly.

> "New tool, same session, no restart. I asked for a habit and got a capability."

---

# A. 60-second video script

Cut for camera. Voiceover written to be *spoken*, fast, at a normal human pitch — no announcer voice.

| t | Screen | Voiceover |
|---|---|---|
| **0:00–0:06** | Split screen, two Claude sessions. Fast cut through the design chat; land on the improv turn with the shouted label visible. | "Two Claude sessions. Same model. We design a button — the label came from the room, five seconds ago." |
| **0:06–0:11** | Both lanes render the same button in a browser. Then: `save_to_memory` fires on the right, left says "noted." | "Both build it. Both look right. Then I ask them to remember it — and only one of them has anywhere to put it." |
| **0:11–0:16** | Ctrl-C both. Black terminals. **Hold one full beat of silence — no VO.** | *(silence)* |
| **0:16–0:24** | Fresh sessions. Same typed request. Left flails into placeholders; right calls `recall_memory`, `$vectorSearch` panel flashes. | "Kill both. Ask again, cold. One of them lost the conversation. The other one queries it back out of MongoDB." |
| **0:24–0:30** | **Two rendered buttons, side by side.** Generic blue vs. exact coral pill with the shouted label. Hold it. | "Generic. Exact. Same model — the memory is just in a database." |
| **0:30–0:38** | Cut to terminals. Cold run streams 6 steps, `run complete · 6 calls · 26s`. Right terminal idle at `TOOLS KNOWN: 9`. | "Second thing. This chore takes six tool calls and twenty-six seconds. It'll take twenty-six seconds forever — nothing here ever gets better." |
| **0:38–0:45** | `MINER: aggregating…` → support row → macro JSON → `INSERTED tools/weekly_update_to_dana`, counter animates **9 → 10**. ElevenLabs line over it. | *(agent voice)* "Compiling weekly_update_to_dana." — "So it mines its own logs. One aggregation. Three repeats, all successful — it compiles them into a tool and writes it back." |
| **0:45–0:51** | Right terminal lights up untouched: `⚡ SKILL ACQUIRED`, `9 → 10`. Cursor visibly never moves. | "Second agent, second process. Change stream. No restart, no deploy — it just knows how now." |
| **0:51–0:57** | Warm run, one line, `✓`. Badge: `6 calls → 1 · 26s → 5s`. | "Ask again. One call. Five seconds." |
| **0:57–1:00** | Title card: **Perpetual — no cold start.** | "Agent A got the experience. Agent B got the skill." |

**Capture notes:** 1080p+, terminal font ≥ 18pt, no window chrome. Let the cold run play real-speed for ~4s then ramp to 2x — the slowness is the point, but sixteen seconds of scrolling isn't. **Never** speed-ramp the warm run or the silent beat at 0:11. The two-buttons shot at 0:24 is the thumbnail; frame it before you shoot anything else.

---

# B. 3-minute stage script (with fallbacks)

Every risky beat has a line you say *without apologizing*. Memorize the fallbacks, not the narration.

| t | Beat | Say | If it breaks |
|---|---|---|---|
| **0:00–0:12** | The claim | "Every agent you've used starts every conversation from zero, and does your Thursday chore just as slowly the fiftieth time as the first. Both of those are memory problems. We put memory in MongoDB." | — |
| **0:12–0:35** | Act 0 beats 1–2, **improv** | Pick direction, then: "Somebody shout — what does the button say?" | **No shout / mumble:** "Fine, I'll do it — «absurd label»." **Say why it doesn't matter:** "It doesn't matter what you pick. Nothing is keyed to a value — `save_to_memory` stores whatever sentence I said, embeds it, and `recall_memory` is a vector search over that. You could have shouted anything." |
| **0:35–0:50** | Preview + save | "Same product right now." → "save that to memory so I don't explain it tomorrow." | **`open` doesn't surface the browser:** don't chase windows — read the hex out of the code pane instead: "fine, look at the values." **`save_to_memory` errors:** rerun once; if it fails twice, cut to capture for Act 0 and go live again at Act 1. |
| **0:50–0:58** | Kill both, silence | "That's it. That conversation is gone." *(2s silence)* | — |
| **0:58–1:20** | Fresh sessions, ask, **payoff** | "Same model. Same question. One kept it in a context window that just died." | **Vanilla accidentally gets it right:** you're in the wrong directory — say "it found my transcript on disk, which is honestly the point: without a memory layer the only fallback is grepping your own history," then show the Perpetual lane's `recall_memory` call as the mechanism. **Recall returns nothing:** "index is still warming" → rerun once → else capture. |
| **1:20–1:30** | Hand-off | "Remembering a decision is table stakes. Watch it remember a skill." | — |
| **1:30–1:55** | Cold run + "third time this week" | "Six calls, twenty-six seconds. Third time this week I've asked for that. It doesn't know it keeps doing this — its logs do." | **Run hangs > 35s:** keep talking about `$vectorSearch` as the tool-binding mechanism; if it's still hung at 40s, Ctrl-C and cut to capture for this beat only. |
| **1:55–2:15** | Miner + birth | "One aggregation. Support three, success one-point-oh. Not machine learning — a query." *Point:* "Nine. Ten." | **Support is 2, not 3:** you skipped the live cold run or reset late — say "let me give it its third repetition" and rerun the agent once; `demo birth-check` confirms. **Naming LLM times out:** "it fell back to a deterministic name — the steps are the part that matters." **ElevenLabs silent:** ignore it completely, never acknowledge missing audio. |
| **2:15–2:30** | Transfer | *(silence, count 2)* "I didn't touch that terminal. Change stream. Agent A got the experience, Agent B got the skill." | **B doesn't light up:** do **not** restart it on stage. "Here's that beat from a capture" → play it → come back live for the warm run. |
| **2:30–2:40** | Warm run | "One call. Five seconds. Same message." | **Warm run errors:** "the macro guard refused — that's the safety story, it won't half-send" → move to the close. |
| **2:40–2:52** | Coda (first thing to cut) | "I do this every Friday — just make it a tool." → `compile_ritual` → **new prompt** → "cool, run it." | **Behind schedule:** cut entirely and say the close. **Tool not visible:** you merged the prompts — send one more prompt, it'll be there. |
| **2:52–3:00** | Close | "Tools, the vector index that retrieves them, the trajectories they're mined from, the change stream that ships them, the TTL that kills them — one database. Skill stopped being weights and became data. And data replicates." → "Agents shouldn't start cold. Thank you." | — |

**Cut order under time pressure:** coda → TTL/fitness aside → `$graphLookup` aside → the SwiftUI extension. Never cut: the improv, the silence after the kill, the two-button payoff, the transfer beat.

### Optional aside — `$graphLookup` (only if you're ahead)

`TYPE:` `PYTHONPATH=src python -m perpetual.agent "who did I delegate the reconciliation work to?"`

> "Two hops. Not just 'I handed it to John' — it finds the issue John opened downstream that I never touched. A flat lookup can't reach that. This is why the workplace lives in Mongo and not in a prompt."

---

# C. Pre-demo checklist

Finish no less than five minutes before you go up.

**T-20 — directories (this is the #1 way Act 0 dies)**
- [ ] `~/demo-vanilla` exists, **empty**, no `button.html`, no prior transcripts.
- [ ] `~/demo-vanilla-2` exists, **empty** — this is where the *fresh* vanilla session opens.
- [ ] `rm -f ~/demo-vanilla/button.html ~/demo-vanilla-2/*` after every rehearsal. A leftover preview file is a spoiler sitting on disk.

**T-15 — reset and one full dry run**
- [ ] `PYTHONPATH=src python -m perpetual.demo reset` — clears learned macros, trajectories **and `memories`**, keeps the seeded workplace.
- [ ] `PYTHONPATH=src python -m perpetual.db` returns `ready` — vector indexes **queryable**, not merely created. A freshly built index that isn't queryable yet is the #1 way Act 1 dies.
- [ ] `PYTHONPATH=src python -m perpetual.demo birth-check` → support **2**. (One live run on stage makes 3.)
- [ ] Full dry run, both acts. Then `reset` again **and** clear the vanilla dirs again.

**T-10 — pre-warm**
- [ ] `make warmup` — Atlas ping + each vector index reports **queryable** (not a collection-scan fallback). First `$vectorSearch` after idle takes seconds and reads as a hang.
- [ ] One throwaway Gemini call to warm TLS/DNS.
- [ ] One ElevenLabs call; confirm it plays through **the room's** PA, not the laptop speaker. Volume set on the PA.
- [ ] Start `perpetual.watcher` and **see** `watching tools…` before you present. If the change stream cursor silently failed to open, the payoff is dead and you won't learn that until 2:15.
- [ ] Open both Perpetual and vanilla sessions once to warm MCP startup, then kill them.

**T-5 — screen**
- [ ] Terminal font ≥ 20pt (24pt in a deep room). Read it from the back row yourself.
- [ ] Dark, high contrast. Panes exactly 50/50, no overlap.
- [ ] Two browser windows pre-positioned, one per lane, so `open` lands somewhere the audience can see. Know the keystroke that brings both forward at once.
- [ ] `TOOLS KNOWN` visible in both terminals at all times — that number is the whole demo.
- [ ] DND on, notifications off, sleep/screensaver disabled, second display **mirrored** not extended.
- [ ] Clear scrollback everywhere; first line the audience sees is the task.

**T-2 — fallbacks**
- [ ] Hotspot paired **and** actually exercised once (run a warmup over it).
- [ ] **Pre-recorded 60-second capture on local disk**, already open in a player behind the terminals, one keystroke away. If the network dies, switch without apologizing: "here's a capture of the same run," keep narrating.
- [ ] Screenshot of the compiled macro JSON, and a screenshot of the two-button payoff, saved locally.
- [ ] Laptop plugged in.

**Memorize these four**
- Vanilla lane answers correctly → wrong directory → reframe as "grepping your own history is the alternative to a memory layer," pivot to the `recall_memory` call.
- Vector search empty → "index just finished rebuilding" → rerun once → else capture.
- Miner support 2 → run the agent once more, live.
- Agent B dark → capture for that beat only, then back live.

---

# D. Q&A — answers, not slides

**"Why is MongoDB load-bearing? Couldn't you do this with Postgres and a queue?"**
> Five features, one system, and the demo needs all five. Vector Search *is* the tool-binding mechanism — retrieval is why an inserted document becomes a callable tool with no reload. The miner is an aggregation pipeline, so learning is a query I can run mid-demo. `$graphLookup` gives multi-hop delegation answers. Change streams are the transfer. TTL is the forgetting. Assemble that from four systems plus glue and you're reconciling four stores, and the "insert a doc, gain a skill" property disappears. The reason this is one afternoon and not three weeks is that it's one database.

**"What's seeded and what's live?"**
> The workplace is seeded and fictional — Maya Chen at Northwind Payments, her manager, her colleagues; `messages` is Slack-export-shaped, same fields a real export gives you. Swapping a real export in is a loader change, not an architecture change; we skipped OAuth on purpose. Everything in the *learning loop* is live: real Atlas, real vector retrieval at the start of each run, real mining over trajectories written seconds earlier, real macro insert, real change stream, real TTL, real LLM calls. And the button you just watched it recall was specified by someone in this room ninety seconds ago. Drop the learned collections and it all happens again from zero — happy to do that right now.

**"How does binding work without codegen? Isn't the LLM guessing?"**
> The LLM does exactly one thing: names the tool and writes its `purpose`. It never writes the steps. Steps are copied from the trajectory. The one `$ref` is a known producer→consumer pair encoded as a `DATAFLOW` table — we observed that `send_message.body` is always the `text` `draft_message` just produced. `{"$ref": "s4.text"}` is that fact. The executor is about forty lines: resolve refs against a context dict, call the primitive. No `exec`, no generated Python. If a binding is wrong anyway, the `guard` refuses the run and the fitness counter kills the macro — cheap to create, cheap to kill.

**"What happens with 500 macros?"**
> That's the fun failure mode: retrieval quality becomes agent capability, so a badly written `purpose` makes a good tool invisible. TTL and fitness are the pressure valve. Next thing we'd build is dedup at compile time — vector-search the existing macros before inserting a near-duplicate — and generalizing macros over their `input_schema` instead of minting one per variation.

**"Can macros call macros?"**
> Not in this build. `execute_macro` only looks up names in the primitive registry — a step whose `tool` is another macro raises `unknown primitive`. Linear primitive sequences are the 80% case and the JSON stays auditable. Nested macros are an obvious next step, with a recursion depth cap.

**"Isn't this just RAG over a notes file?"**
> Act 0 is, roughly — and that part is table stakes, which is why it's only the first minute. Act 1 is the claim: the thing being retrieved isn't a note, it's an *executable tool the agent wrote about itself*, and retrieving it is what makes it callable. The tool list is a query result. That's the part you can't do with a notes file.


## Act 0.5 — "it pulls the skill by itself" (added 3:15 PM, verified)

Optional 20-second beat, best placed right after the memory payoff. No tool call, no slash command:
you just type something ordinary and the right know-how arrives.

Type: `I'm about to add a Pay Now button to the checkout screen — anything I should know?`

A banner appears above Claude's reply: `⚡ perpetual: recalled 1 skill from Atlas`, and Claude answers
already knowing the team's button conventions (44pt tap targets, one primary per screen, verb-first
labels naming the outcome). Nothing was invoked — a `UserPromptSubmit` hook embedded the sentence with
Gemini and ran a **hybrid retrieval in MongoDB**: `$vectorSearch` over `skills.embedding` fused with a
deterministic match on each skill's `triggers` array. The word "button" guarantees the hit; the semantics
catch the cases where the word never appears.

Proof line worth saying out loud: *"watch — I never say the word 'update' here."*
Type: `I need to tell my manager what I got done this week` → the leadership-writing skill loads at 0.87
on meaning alone. **Verified scores:** button prompt 0.90 (vector + trigger), incident 0.80, leadership
0.87, delegation 0.83.

Why it matters for the pitch: skills, memories, and the macros the agent **compiled itself** all live in
the same vector space, so an invented skill is retrieved by the exact same mechanism as a human-written
one. That is the difference between a database the agent queries and a database the agent thinks with.
