# Phase 3 — Results — **gate: PASS WITH CHANGES (pending Windows)**

**Run:** 2026-08-19 · **Box:** 2 days · **Plan:** [`../PHASE-3_pyodide-spike.md`](../PHASE-3_pyodide-spike.md)
**Prerequisite:** Phase 2 — [`PHASE-2_results.md`](PHASE-2_results.md) §2.6

---

> **It works. Real honeybee + honeybee-ph runs inside SketchUp's `HtmlDialog` and writes HBJSON
> from a real designPH model.** Steps 1–4 all pass on macOS, SketchUp 2022 (22.0.353):
> boot complete in **2.6 s**, 82 of 82 classified Adelphi faces translated with **none rejected**,
> 87 KB of HBJSON on disk, and 4 MB across the bridge in both directions checksum-exact.
>
> Getting there cost four SketchUp runs and turned up four traps, none of them Pyodide's fault and
> all of them now written down: two threading (Findings 30, 32), one engine-version (34), and
> `file://` (37). The engine one outlives this phase — **SketchUp 2022 is Chromium 88**, which pins
> the runtime to **Pyodide 0.24.1** and makes PRD §7.4's version floor a technical ceiling.
> The spike extension is built, installed and exercised end to end against a stub host. The one
> failure seen in SketchUp so far was ours, not `HtmlDialog`'s — a Ruby thread that never ran
> (Finding 30). Round 2 is in [`PHASE-3_ed-runbook.md`](PHASE-3_ed-runbook.md).
>
> The gate is deliberately **left open** rather than recorded as PASS. The plan's own PASS text
> requires "steps 1–4 work on both platforms" and downgrades Mac-only evidence to
> *PASS-pending-Windows*; Chrome-only evidence is a rung below even that, because Chrome is not the
> host under test. Calling this PASS would be the exact failure `AGENTS.md` warns about — a clean
> result from the wrong sample.

## Findings

| # | Finding | Effect |
|---|---|---|
| 19 | **The whole stack runs in Chromium: Pyodide 314.0.5 + the 8 wheels + `import honeybee_ph`, cold start 2.3 s** | Steps 1–3 of the plan, minus the host. Well inside the ">10 s is a problem" line |
| 20 | ⚠ **`file://` is a hard dead end in stock Chromium — `fetch`, `XMLHttpRequest` *and* dynamic `import()` are all refused**, one CORS rule, `origin 'null'` | Kills the obvious `HtmlDialog#set_file` architecture *unless* CEF is configured otherwise. Risk 1 of the plan, confirmed and then some |
| 21 | **No JS shim can rescue `file://`.** A `fetch` polyfill was written and it does not help: XHR hits the same rule, and Pyodide loads `pyodide.asm.mjs` by dynamic `import()`, which is not interceptable at all | The reserve rung the plan implied does not exist. Recorded so it is not re-attempted |
| 22 | ✅ **A local HTTP server solves it completely** — the identical tree over `http://127.0.0.1` works first try, and can set the COOP/COEP headers a `file://` page never can | The recommended architecture, and the answer to risk 2 as well. ~70 lines of `TCPServer` in `main.rb` |
| 23 | **`--allow-file-access-from-files` makes `file://` work**, plain `fetch`, no shim | Names the exact capability. Ed's run now reads as "does CEF grant local file access", not as an unexplained failure |
| 24 | **`micropip.install(..., deps=False)` works from `emfs:` paths — but cannot bootstrap itself** | Confirms Phase 2 §2.6. `micropip` and `packaging` must be unpacked with `zipfile` first; there is no on-board installer in `pyodide-core` |
| 25 | **The `.rbz` is 8.07 MB — and 15.3 MB unpacked on disk** | Phase 2 §2.5's ≈8.1 MB budget was quoted from *compressed download* sizes and happens to hold for the zip. The install footprint is a second, larger number nobody had stated |
| 26 | **Pyodide is ~2× slower than native CPython on this workload, not 10×** | 1441 faces: `Model.from_dict` 18.2 s in Pyodide vs 9.0 s on CPython 3.14. Same wheels, byte-identical HBJSON |
| 27 | ⚠ **`Model.from_dict` is the only slow operation, and v1 never calls it** | Writing 1441 faces costs **96 ms** (`to_dict` 58 + `json.dumps` 38). Reading them back costs 18 s. The export path is fast; only the round-trip *check* is slow |
| 28 | **A Room with no Floor face is a normal designPH outcome, and `Space.from_room` raises on it** | `ValueError: … has no Floor faces`. Only area groups 1 and 11 become floors; a wall-and-roof selection has no Space. Must be reported, not raised (hard rule 4) |
| 29 | **The Ruby↔JS bridge carried 4 MB per hop with byte-exact checksums** — against a stub host, not `HtmlDialog` | Establishes the protocol works. The number that matters is still Ed's |
| 41 | ⚠ **A run nobody can grade at a glance has not reported anything.** The measured run *passed*, but its dialog ended on a 20-line `micropip` traceback and the message box said "finished" — Ed reasonably read a success as a failure | Fixed: the dialog closes with a `PASSED`/`FAILED` banner and a per-check list, and the message box carries the verdict and the face counts. The deeper fix was removing the component that produced the traceback |
| 40 | ⚠ **honeybee-energy's default construction set does not validate against published `honeybee-schema`** — 27 failing objects under 1.53.1, the same region under 2.2.0, all in `properties.energy.global_construction_set` | Upstream drift, not our output: **zero** errors touch geometry or PH under either schema. v1 should decide whether to emit a global construction set at all |
| 39 | ⚠ **`Space.from_room` also rejects a non-horizontal Floor face** — `Floor face 'face_9153' must be horizontal for World-Z extrusion`, so the real model produced **no PH Space** | A second, distinct failure from Finding 28's no-Floor-faces case, and this one fires on real designPH data. TFA/Space derivation is a v1 problem that needs solving properly, not a spike bug |
| 38 | ✅ **Steps 1–4 pass inside SketchUp 2022 on macOS** — boot 2.6 s, 82/82 faces translated, 0 rejected, 87 KB HBJSON written to disk, bridge 4 MB each way | The gate. Mac only |
| 37 | ✅ **Confirmed in SketchUp: `HtmlDialog` does not grant local file access.** `set_file` + Pyodide 0.24.1 fails with `TypeError: Failed to fetch dynamically imported module: file:///…/pyodide.asm.js`, and the XHR shim is refused too | Settles Finding 23's open question for the real host. **The loopback server is mandatory, not merely preferable** — PRD §7.1's load strategy is now decided rather than recommended |
| 36 | ✅ **Pyodide 0.24.1 runs the whole stack on Chromium 88** — verified against a real Chromium 88 snapshot at Adelphi scale: cold start **3.5 s**, 1441 faces exported in **139 ms**, HBJSON round-trips | The runtime is viable on SketchUp 2022 after all, at a four-release-old pin. `.rbz` drops to **6.87 MB** |
| 35 | ⚠ **`micropip` is coupled to the Pyodide release; the `zipfile` unpack is not.** `micropip` 0.11.1 dies on 0.24.1 with `ImportError: cannot import name 'lockfileBaseUrl'` | Phase 2 §2.5's reserve became the mechanism. **`micropip` is no longer shipped at all** — every wheel is `py3-none-any`, so unpacking *is* installing, and carrying a component that always fails cost 0.2 MB and put a traceback in front of the user on every run |
| 34 | ⚠ **SketchUp 2022 embeds Chromium 88 (CEF 88.2.4, January 2021), and modern Pyodide will not run on it.** 314.0.5 fails to parse (66 ES2022 static blocks, Chromium 94); 0.27.7 parses but its wasm needs reference types (Chromium 96): `CompileError: invalid value type 'externref'` | **The single biggest constraint found in this phase.** It caps the runtime at Pyodide 0.24.1 / CPython 3.11 for as long as SketchUp 2022 is supported. PRD §7.4's version floor is now a product decision with teeth |
| 33 | **The engine version is knowable offline** — `SketchUp.app/Contents/Frameworks/Chromium Embedded Framework.framework` names it, and a matching Chromium snapshot can be downloaded and driven headlessly | Turns "ask Ed to click" into a local test loop. Findings 34 and 36 were both settled without a SketchUp run |
| 32 | ⚠ **Blocking socket writes on SketchUp's main thread deadlock it.** Round 2 served four small assets (6/19/15/5 KB) then beachballed with no log line for the fifth | SketchUp drives CEF from the app's main run loop, so CEF needs that thread to drain a socket. Any body past the send buffer blocks the writer on a reader that cannot run. **The I/O must be on a worker thread — and the worker only gets scheduled because a `UI.start_timer` callback `sleep`s and releases the GVL.** Findings 30 and 32 are two halves of one rule |
| 31 | ✅ **A `UI.start_timer`-pumped socket serves correctly from inside SketchUp** — SketchUp 2022, macOS, verified in a browser: `index.html`, `pyodide.js` and `spike.js` all 200, page renders | Closes Finding 30. The loopback-server architecture is viable in the real host; what remains is whether `HtmlDialog` will load it |
| 30 | ⚠ **A Ruby `Thread` never runs in SketchUp.** The first SketchUp run failed with a blank dialog and a port that refused connections. `TCPServer` bound and printed a port; the thread parked in `accept` was never scheduled | SketchUp runs the Ruby VM on its main thread and only schedules Ruby while Ruby is executing. **Pump from `UI.start_timer`, never from a thread.** The socket still *binds*, so the symptom is silence, not an error |

Raw data: [`baselines/phase3_chrome_file.json`](baselines/phase3_chrome_file.json),
[`…_file-permissive.json`](baselines/phase3_chrome_file-permissive.json),
[`…_http.json`](baselines/phase3_chrome_http.json),
[`…_extension.json`](baselines/phase3_chrome_extension.json).
Spike code: [`../../../spikes/pyodide/`](../../../spikes/pyodide/.index.md).

---

## 3.1 — Method, and why it is not quite the one the plan wrote

The plan reads as a single ladder: install the extension, click, see what happens. The trouble with
that shape is that **every rung fails the same way from the outside.** If the dialog shows nothing,
the cause could be CSP, a path, a typo in `main.rb`, a missing wheel, an API misuse, or `HtmlDialog`
itself — and the only instrument for telling them apart is Ed, in SketchUp, reporting back.

So the phase was split at the seam:

1. **Everything that is not about SketchUp was answered in desktop Chrome**, automated and
   repeatable, by the *same* `spike.js` and `spike.py` the extension loads. Four configurations, one
   command: `file://`, `file://` with local file access granted, `http://127.0.0.1`, and the
   extension's own page driven by a stub `sketchup` host.
   → [`verify_in_chrome.py`](../../../spikes/pyodide/verify_in_chrome.py)
2. **A CPython control run** of the identical `spike.py`, so a slow number can be attributed to
   Pyodide rather than to honeybee.
3. **What is left for SketchUp is one question** — does `HtmlDialog` load the page and carry the
   bridge — with both load strategies wired to the same menu.

The cost of the split is a stub host, which proves wiring and not payload limits. That is stated
where it matters (Finding 29) rather than smoothed over.

## 3.2 — Step 1, restated: `file://` does not work, and cannot be made to

The plan named CSP and local file loading as the likeliest killer. It is, and the mechanism is
sharper than "CSP":

```
Access to fetch at 'file:///…/pyodide.asm.wasm' from origin 'null' has been blocked by CORS
policy: Cross origin requests are only supported for protocol schemes: chrome, chrome-extension,
chrome-untrusted, data, http, https, isolated-app.
```

Three separate mechanisms hit the same wall, and the third is the one that closes the door:

| Mechanism | On `file://` | Interceptable? |
|---|---|---|
| `<script src="…">` — classic | **works** | — |
| `fetch()` | blocked, `origin 'null'` | yes, and a shim was written |
| `XMLHttpRequest` | blocked, same rule | that *is* the shim; it fails too |
| dynamic `import()` — how Pyodide loads `pyodide.asm.mjs` | blocked | **no.** A module import is not a `fetch` call and cannot be polyfilled |

Classic scripts loading is what makes the failure confusing: the page comes up, `SPIKE` and
`loadPyodide` are both defined, and the first symptom is a `TypeError` about a dynamically imported
module. Anyone diagnosing this from the dialog alone would reasonably conclude the file was missing.

Adding `--allow-file-access-from-files` makes all of it work, with plain `fetch` and no shim
(Finding 23). So the question for SketchUp is precise: **does its CEF build enable local file
access?** If yes, `set_file` works. If no, nothing on the `file://` path ever will.

## 3.3 — The architecture this points at: a local HTTP server inside the extension

`main.rb` serves the extension folder from `TCPServer` on `127.0.0.1`, an OS-assigned port, behind a
random 32-hex path token, and shuts it down when the dialog closes. `HtmlDialog#set_url` points at
it. Everything stays offline and on the loopback interface; nothing is downloaded and nothing is
exposed off the machine.

Three reasons to prefer it even if `file://` turns out to work:

- **It is the only strategy that can set headers.** `Cross-Origin-Opener-Policy: same-origin` +
  `Cross-Origin-Embedder-Policy: require-corp` give the page cross-origin isolation, which is what
  `SharedArrayBuffer` needs — risk 2 in the plan, answered structurally instead of hoped away.
- **It does not depend on a CEF configuration flag** that Trimble could change in any release.
- Correct MIME types come for free, which `application/wasm` wants for streaming compilation.

Cost: a listening socket for the lifetime of the dialog, and hand-rolled request handling.
`WEBrick` was deliberately not used — it left Ruby's default gems at 3.0 and there is no guarantee
about what a given SketchUp build ships, whereas `TCPServer` is core.

⚠ **And it must be pumped by `UI.start_timer`, not by a `Thread`** (Finding 30). The first SketchUp
run put the accept loop in `Thread.new`, which is the obvious shape and the wrong one: SketchUp runs
the Ruby VM on its main thread and schedules Ruby only while Ruby is executing, so a thread parked in
`accept` is starved indefinitely. What makes this expensive to diagnose is that **the socket still
binds** — `TCPServer.new` does `bind` and `listen` immediately, the kernel queues connections into
the backlog, and the client simply waits forever. From the outside it is a blank dialog, which is
also what a refused `set_url` looks like.

Three things now separate those cases without another round trip:

- `handle` logs `request #N: 200 <path>` to the Ruby Console, so a loading dialog is visible.
- If the dialog has asked for nothing 6 s after opening, `run` says so explicitly — that is
  `HtmlDialog` declining the URL, not the server failing to answer.
- Menu item 3 starts the server **with no dialog at all**, to be opened in a normal browser.

The HTTP layer itself is now covered offline by
[`test_static_server.rb`](../../../spikes/pyodide/test_static_server.rb), which loads the real `main.rb`
against a stub SketchUp API and drives the real server over a real socket — status codes, MIME
types, COOP/COEP, the path token, and directory escape. It cannot cover the scheduling, because a
plain Ruby `Thread` works fine outside SketchUp; that is the whole point of the bug.

## 3.4 — Measurements

**Measured in SketchUp 2022 (22.0.353), macOS arm64, Pyodide 0.24.1** — the run of 2026-08-19 21:39,
raw file `~/Desktop/dph_phase3_copies/adelphi-designph_COPY__phase3_result_260819_213955.json`.

| Metric | Value | Against the plan's bar |
|---|---|---|
| Cold start to `import honeybee_ph` + demo model | **2.63 s** | ">10 s is a problem" — comfortable |
| ├ Pyodide runtime ready | 1.38 s | |
| ├ 10 wheels fetched over loopback | +0.23 s | |
| ├ installed (`zipfile` unpack) | +0.16 s | |
| └ imports + `Room.from_box` round trip | +0.84 s | `honeybee.room` alone is 0.59 s |
| Bridge JS → Ruby | **4 MB**, checksum-exact, 818 ms | 1 MB in 206 ms |
| Bridge Ruby → JS | **4 MB**, checksum-exact | all five sizes verified |
| Adelphi face payload, Ruby → dialog | 19.4 KB for 82 classified faces | ~0.5% of the bridge limit |
| Peak WASM heap | 28.8 MB | |
| JS heap | 82.4 MB of a 3.6 GB limit | |
| `.rbz` | **6.87 MB**, 20.9 MB installed | PRD guessed ~10 MB |
| Windows | **not tested** | no machine in this environment |

**Step 4 on the real model** — 82 classified faces of 1441 tagged:

| | |
|---|---|
| Translated | **82 of 82, none rejected** |
| Face types from area groups | 41 `Floor`, 38 `Wall`, 3 `RoofCeiling` |
| `Face3D` + `Face` construction | 6.1 ms |
| `Model.to_dict` + `json.dumps` | 11.9 ms |
| `Model.from_dict` round trip | 208.7 ms |
| HBJSON written | **87,248 bytes** |
| PH `Space` | **not created** — Finding 39 |
| Room is solid | no, by design (PRD §8.1) |

The HBJSON validates with **zero errors touching core geometry or PH properties** under
`honeybee-schema` 1.53.1 *and* 2.2.0. Both flag the same 27 objects, all inside
`properties.energy.global_construction_set` (Finding 40).
[`validation/phase3_sketchup_hbjson_core.json`](validation/phase3_sketchup_hbjson_core.json).

### The Chrome-side numbers, for comparison

Mac, headless, M-series, warm disk cache. **Not SketchUp** — these are what the offline loop measured.

| Metric | Value | Note |
|---|---|---|
| Cold start to `import honeybee_ph` complete | **2.3–2.5 s** | plan's threshold was 10 s |
| ├ Pyodide runtime ready | 1.07–1.13 s | |
| ├ 10 wheels read into the FS | +0.02 s | local files |
| ├ `micropip.install(deps=False)` | +0.35 s | |
| └ import + `Room.from_box` round trip | +0.85 s | |
| Warm re-run (same runtime, build a model again) | **5 ms** | keeping the dialog alive is clearly worth it |
| Vendored bundle — `.rbz` | **8.07 MB** | Phase 2 budgeted ≈8.1 MB |
| Vendored bundle — unpacked on disk | **15.3 MB** | new number; the install footprint |
| Peak WASM heap, 1441-face model | **74.9 MB** | 43.3 MB at rest, before any model |
| JS heap | 26–32 MB | `jsHeapSizeLimit` reported 3.5–4.2 GB |
| Max JSON per bridge hop | **4 MB, checksum-exact** | stub host; `HtmlDialog` untested |
| Mac vs Windows | **not tested** | no Windows machine in this environment |

**Build cost at Adelphi's tagged-face scale** (1441 faces, the plan's worst case):

| Operation | Pyodide | CPython 3.14 | Ratio |
|---|--:|--:|--:|
| `Face3D` + `Face` × 1441 | 45 ms | 18 ms | 2.5× |
| `Space.from_room` (480 volumes) | 46 ms | 25 ms | 1.8× |
| `Model.to_dict` | 58 ms | 44 ms | 1.3× |
| `json.dumps` (2.14 MB) | 38 ms | 21 ms | 1.8× |
| **the export path, total** | **187 ms** | **108 ms** | **1.7×** |
| `Model.from_dict` — *verification only* | 18 215 ms | 8 984 ms | 2.0× |

Two things follow. **Pyodide is not the bottleneck** — a consistent ~2× on every operation is a good
result for CPython-in-WASM, and the whole export of a worst-case model costs under 200 ms. And
**`Model.from_dict` is an upstream cost, not ours**: 9 s on native CPython for a 1441-face model is
a honeybee-ph observation worth carrying forward, but v1 writes HBJSON and never reads it back, so
it sits off the product path. The spike calls it only as a correctness assertion.

The HBJSON produced in Pyodide is **byte-identical** to CPython's — 2 139 675 bytes both times.

## 3.5 — What the SketchUp run has to establish

One session, both menu items, in the order the runbook gives them. Each answers something distinct:

| Run | Answers |
|---|---|
| **Server only, in a browser** | Can a socket inside SketchUp serve at all? Isolates the pump from the dialog — the distinction round 1 could not make |
| **Local HTTP server** | Does `HtmlDialog` accept `set_url` to loopback? Does the whole spike run inside SketchUp? What does the bridge actually carry? |
| ~~**`file://`**~~ | ✅ **Answered 2026-08-19: no.** CEF refuses it, `fetch` and XHR alike. The socket stays |
| **Report face payload size** | What a real designPH model's geometry costs on the bridge — no dialog, no Pyodide, so it works even if both dialogs fail |

Written up for Ed in [`PHASE-3_ed-runbook.md`](PHASE-3_ed-runbook.md).

## 3.6 — The open product question: which SketchUp versions

Finding 34 turns PRD §7.4's version floor from a compatibility preference into a technical ceiling.
SketchUp 2022 embeds Chromium 88, which caps the runtime at **Pyodide 0.24.1 / CPython 3.11**. Every
SketchUp release since ships a newer CEF, so the floor and the ceiling move together.

What is known: SketchUp 2022 = CEF 88.2.4 = Chromium 88 (January 2021), read off the app bundle.
What is not: the CEF in 2023, 2024, 2025 and 2026 — no other SketchUp is installed in this
environment — and, more importantly, **which versions the market actually runs**. Ed's own machine
is on 2022, which is itself a data point about PH consultants and SketchUp upgrade cycles.

This does not block Phase 3. Pyodide 0.24.1 works, the wheels are unchanged, and the bundle is
*smaller* than the modern runtime. It is a decision to take deliberately before v1 pins a runtime,
not a problem to solve now.

## 3.7 — Not answered here, deliberately

- **Windows.** No machine in this environment. The plan is explicit that Mac results must not be
  extrapolated, and `file://` handling is exactly the kind of thing that differs. Even a full Mac
  pass lands at **PASS-pending-Windows**.
- **SketchUp 2021.** The `HtmlDialog` floor claimed in PRD §7.4 is untested.
- **The PHX stretch goal.** `phx-1.56.88` is one flag away
  (`vendor_payload.py --with-phx`), but the plan is clear it must not consume the box and the box
  now belongs to Ed's run.
- **The AGPL question.** Unchanged by anything here, and not for this phase — PRD §9, after the gate.

## Gate — **PASS WITH CHANGES, pending Windows**

Against the plan's own wording. Its PASS clause is *"steps 1–4 work on both platforms, cold start is
tolerable, Adelphi's payload crosses the bridge"*, and it explicitly downgrades one-platform evidence:
*"Mac-only evidence is **PASS-pending-Windows**, recorded as such — not PASS."*

- Steps 1–4 work. ✅ On macOS only.
- Cold start is 2.6 s against a 10 s bar. ✅
- Adelphi's payload crosses the bridge with room to spare — 19 KB against a verified 4 MB. ✅
- Windows: untested, and the plan forbids extrapolating. ⚠

It is **PASS WITH CHANGES** rather than plain PASS because four constraints came out of it that the
plan did not anticipate, and every one of them changes how v1 must be built:

1. **The dialog must be served over loopback.** `file://` is refused by SketchUp's CEF, and no shim
   reaches the dynamic `import()` (Findings 20, 21, 37).
2. **The server must be a worker thread pumped by a sleeping `UI.start_timer`.** Either half alone
   hangs SketchUp, in two different ways, neither of which reports an error (Findings 30, 32).
3. **The runtime is pinned to Pyodide 0.24.1 by SketchUp 2022's Chromium 88** — and that pin is set
   by the oldest SketchUp supported, which makes PRD §7.4 a decision with a technical price
   (Findings 34, 36).
4. **`micropip` is not the installer; `zipfile` is,** and `micropip` is not shipped. It is coupled to
   the Pyodide release and fails on 0.24.1; every wheel is pure, so unpacking is installing
   (Finding 35).

**Adopt Pyodide as the runtime.** The FAIL branch — Ruby writes HBJSON directly — is not triggered:
nothing here argues the approach is unworkable, and the measured cost (6.87 MB, 2.6 s, 139 ms to
export a worst-case model) is well inside what the PRD assumed.

### Still open, and honestly so

| | |
|---|---|
| **Windows** | Untested. No machine here. Keeps the verdict at *pending-Windows* |
| **SketchUp 2021** | PRD §7.4's floor. Its CEF is older still and may not reach Pyodide 0.24.1 |
| **Which SketchUp versions to support** | §3.6 — a product decision, now with a technical price |
| **PH `Space` on real data** | Finding 39. A v1 problem, surfaced by the spike rather than caused by it |
| **The AGPL question** | Now live, because the gate passed. See [`PHASE-3_licence-question.md`](PHASE-3_licence-question.md) |

### Consequences recorded elsewhere

| Document | Change |
|---|---|
| `DESIGNPH-PLUS_PRD.md` §7.1 | Rewritten from "preferred / fallback" to **one decided architecture**: Pyodide 0.24.1, served over loopback, worker-thread server |
| `DESIGNPH-PLUS_PRD.md` §7.4 | The SketchUp floor is now a technical ceiling on the runtime, and an open product question |
| `DESIGNPH-PLUS_PRD.md` §10, S1 | Spike closed |
| `planning/01_sketchup-export/feasibility/00_OVERVIEW.md`, `planning/.index.md` | Phase 3 status |
| `CLAUDE.md` | Four lessons: `file://`, Ruby threads, main-thread I/O, and reading CEF's version offline |
| `PHASE-3_licence-question.md` | New — the AGPL question the PASS branch requires |
