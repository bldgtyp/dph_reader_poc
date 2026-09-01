# Claude Bridge — live-SketchUp eval server (dev tool)

**What:** [Claude Bridge](https://github.com/lairdubois/lairdubois-claude-bridge-sketchup-extension)
(Boris Beaulant / L'Air du Bois, MIT, v1.0.0) — a dev-only SketchUp extension exposing an HTTP
server on `127.0.0.1:7857` that evaluates Ruby inside the running SketchUp process and returns JSON.
It removes the "write a staged script, ask Ed to run it, paste output back" round trip: an agent can
ask novel questions of the *live* model directly.

Installed 2026-09-01 into `~/Library/Application Support/SketchUp 2022/SketchUp/Plugins/`
(`ladb_claude_bridge.rb` + `ladb_claude_bridge/`), after full source review. Source is two files,
~230 lines; the `.rbz` in the repo's `dist/` is byte-identical to `src/`
(sha256 `ffb4e4c5be76c068868272f6599a9f166c55db3d4607f2fd150a761632887c6f`). Ruby 2.7-clean
(newest construct is `to_h` with a block, Ruby 2.6+).

## How it works (verified by reading the source, not the docs)

- **Threading:** `TCPServer` + `accept_nonblock` polled from a repeating `UI.start_timer(0.1)` tick
  on the **main thread**. No Ruby `Thread` anywhere, so the thread-starvation trap
  (`SKETCHUP_RUNTIME.md` §5) does not apply — but every eval blocks the UI until it returns.
- **Endpoints:** `GET /ping` (SketchUp/Ruby version, active model title+path) and `POST /eval`
  (body = Ruby source; result = value of the last expression). Both **require the
  `X-Claude-Bridge: 1` header** (403 without it — CORS guard). 10 MB body cap, 3 s read timeout,
  no eval time cap.
- **Response:** `{ ok: true, result:, stdout: }` or `{ ok: false, error:, backtrace:, stdout: }`.
  `$stdout` is captured per request. Results are round-tripped through `JSON.generate`; anything
  non-JSON-able falls back to `.inspect`.
- **Fresh binding per eval** — locals do not persist between requests; constants (`Sketchup`, …)
  resolve normally. State must be re-derived or stashed in a module/global explicitly.

## Using it

Ed starts/stops it with the **Claude Bridge toolbar button** (checked = running) or
Extensions ▸ Claude Bridge. Then:

```
curl -s -H 'X-Claude-Bridge: 1' http://127.0.0.1:7857/ping
curl -s -X POST -H 'X-Claude-Bridge: 1' --data-binary @script.rb http://127.0.0.1:7857/eval
```

Payload shape:

- Return **JSON-friendly values** — map entities to hashes of primitives yourself; convert `Length`
  with `.to_f` (inches) or `.to_m`.
- **Keep evals short.** Everything runs on the main thread; a slow script freezes SketchUp. Walk
  **definitions once, never placements** (Adelphi: 1441 entities vs 1,023,558 placements).
- Batch: one eval returning a structured hash beats ten small evals.

## ⛔ Guardrails (this project's hard rules, applied to an eval server)

Eval'd code has the full SketchUp API — including save and delete. Therefore:

1. **Never call `model.save`, `save_as`, or `save_copy` in an eval. Ever.** Same load-bearing
   invariant as the C-SDK reader's. Hard rule 3 (never modify a corpus file) is one keystroke away
   otherwise — open **copies** only, as always.
2. **Reads use the non-creating form**: `entity.attribute_dictionary('DesignPH_dict')` — Ruby's
   `create` parameter defaults to `false` (unlike the C SDK's get-or-CREATE trap). Never pass
   `create: true` / a truthy second arg against designPH data (hard rule 2).
3. **Writes only under the POC #3 frozen contract** (`DESIGNPH_DATA_MODEL.md` §14), only in scratch
   models, wrapped in `model.start_operation(..., true)` / `commit_operation` for undo safety.
4. **Start/stop hygiene:** while running, *any* local process under Ed's account can execute code in
   SketchUp. Ed starts it for a session and stops it after; never ask to leave it running unattended.
5. `GET /ping` first, always — confirms the bridge is up **and which model is frontmost**. Remember
   `Sketchup::Model#path` is untrustworthy (`CLAUDE.md` gotchas) — verify the model by title *and*
   by asking Ed, not by path prefix.
6. ⚠ **An eval that segfaults kills SketchUp — the whole app, with any unsaved work** (eval runs
   in-process; the bridge cannot sandbox a native crash). Measured 2026-09-01, first session: a
   probe of a leader-Text's target crashed SketchUp 2022 outright — prime suspect
   **`Sketchup::Text#attached_to`**, not confirmed (no report in the API issue tracker; the script
   also first-used `leader_type` and `InstancePath` reads). Consequences: **against a real project
   model, stick to API calls already proven** in `bt_inspector` / the POC collector; first-try any
   new API in a scratch model — which is exactly what this session did, and why the crash cost
   nothing. To locate a leader Text's target without `attached_to`: use `t.point` (the arrow end)
   and resolve geometrically (nearest vertex/face), which is what the working replacement does.

## Relationship to the other tools

| Tool | Answers |
|---|---|
| Claude Bridge | **novel live questions**, interactively, no Ed round trip |
| BT Attribute Inspector | pre-built live reports (selection watching, surface report) |
| `tools/skp_attr_dump.py` / offline readers | historical + on-disk state, no SketchUp needed |
| Headless C-SDK reader (POC #2) | full contract-v2 captures at scale, no SketchUp seat |

It is a **development accelerator only** — never a shipping dependency, never distributed, and it
plays no part in any product architecture (Library Sync, DesignPH-PLUS, pholio).
