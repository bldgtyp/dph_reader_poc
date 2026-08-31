# Phase 3 — Pyodide in SketchUp (S1)

> ✅ **CLOSED 2026-08-19 — PASS WITH CHANGES (pending Windows).** [`RESULTS/PHASE-3_results.md`](RESULTS/PHASE-3_results.md). This file is the plan as written; the architecture it decided (Pyodide 0.24.1 in HtmlDialog over loopback) carried through the whole POC unchanged.

**Box:** 2 days, hard stop
**Gate:** **the runtime architecture.** The most consequential decision in the project
**Prerequisite:** ✅ Phase 2 passed — [`RESULTS/PHASE-2_results.md`](RESULTS/PHASE-2_results.md).
The scope statement this phase asked for is its
[§2.6](RESULTS/PHASE-2_results.md#26--scope-statement-for-phase-3)

> ✅ **CLOSED — PASS WITH CHANGES (pending Windows), 2026-08-19.**
> [`RESULTS/PHASE-3_results.md`](RESULTS/PHASE-3_results.md). Pyodide adopted; real honeybee runs
> inside `HtmlDialog` and wrote HBJSON from a real designPH model. The gate was deliberately *not*
> recorded on Chrome-only evidence — Chrome is not the host under test — and the SketchUp session
> ([`RESULTS/PHASE-3_ed-runbook.md`](RESULTS/PHASE-3_ed-runbook.md)) is what closed it.
>
> **Superseded by the POC.** Everything here has been rebuilt and extended in `planning/01_sketchup-export/implementation/`; this
> file is the spike record. The runtime decision, its four constraints and the licence question it
> opened are all in `00_Context/`.
>
> The method below was split at the seam — everything not about SketchUp was answered offline and
> repeatably — because every rung of the plan's single ladder fails the same way from inside the
> dialog. See §3.1 of the results.
>
> Step 1's answer changed the architecture: **`file://` cannot work**, so the extension serves
> itself over `http://127.0.0.1`. Steps 2–5 below are otherwise as written.

---

## Objective

Determine whether real, unmodified honeybee + honeybee-ph can run inside SketchUp's `HtmlDialog` via
Pyodide — giving a zero-install, offline, serverless extension that uses the actual tested library
rather than a reimplementation.

**This is unproven.** No evidence was found that anyone has run Pyodide inside SketchUp's HtmlDialog.
The two-day box is deliberate: if it is not working by then, the answer is no.

## Why it might work

SketchUp's `HtmlDialog` (2017+) is Chromium. Pyodide is CPython compiled to WASM and runs in
Chromium. Phase 2 established that the reachable stack is pure Python — 8 wheels, all
`py3-none-any` — so every package installs with no compilation and nothing needs a wasm build.

## Why it might not

Unknowns, roughly in order of likelihood of killing it:

1. **CSP / local file loading.** Pyodide needs to fetch its own `.wasm` and `.js` assets. HtmlDialog's
   security policy for local resources is not documented for this use. Everything must be vendored —
   no CDN — since the extension must work offline.
2. **`SharedArrayBuffer` / cross-origin isolation.** Some Pyodide features require COOP/COEP headers,
   which a `file://`-ish dialog cannot set. Basic execution should not need it; verify.
3. **Memory and startup.** ≈8 MB of runtime plus wheels (measured, Phase 2 §2.5), and several
   seconds of cold start, inside a process that is also holding a large SketchUp model.
4. **The Ruby↔JS bridge.** `dialog.execute_script` / `add_action_callback` payload size limits are not
   well documented, and a full model's JSON could be large.

## Method — smallest thing that could possibly work, then grow

**Step 1 — Pyodide loads at all** (target: 2 h)
Minimal extension: one `HtmlDialog`, vendored Pyodide, run `print(1+1)`, return the result to Ruby via
`add_action_callback`. **If this fails, the spike is over.** Record the exact failure — CSP, path
resolution, or something else.

**Step 2 — the stack imports** (target: 3 h)
Vendor the 8 wheels named in [Phase 2 §2.6](RESULTS/PHASE-2_results.md#26--scope-statement-for-phase-3),
then `micropip.install(WHEEL_URLS, deps=False)` from local files, then
`import honeybee; import honeybee_ph`. Record cold-start time and peak memory.

Two things Phase 2 found that will cost time if rediscovered here:

- **`deps=False` is load-bearing.** `honeybee-core` *declares* `honeybee-schema` → `pydantic` →
  Rust `pydantic-core`, and nothing outside the `cli/` modules imports any of it. With resolution
  on, the payload roughly triples and picks up a wasm module for code we never call.
- **`pyodide-core` contains no packages at all** — 13 files, no `micropip`. Vendor `micropip`
  (113 KB) and `packaging` (94 KB) alongside our wheels, or skip `micropip` and unpack the eight
  pure wheels straight onto Pyodide's filesystem. Try `micropip` first; keep the unpack in reserve.

**Stretch, only if step 3 lands early:** add `phx-1.56.88-py3-none-any.whl` and import *only*
`PHX.from_HBJSON`, `PHX.model`, `PHX.to_WUFI_XML`, `PHX.to_METr_JSON` — Phase 2 verified that path
runs with `lxml`, `xlwings`, `pydantic` and `rich` all absent, which would put WUFI-Passive and METr
export in the browser. Never `PHX.from_WUFI_XML`, `PHX.PHPP`, or `PHX.hbjson_to_phpp`. This must not
consume the two-day box.

**Step 3 — build a trivial model in Python** (target: 3 h)
Construct a single `Room` from a hard-coded box, add one `Space` via `honeybee_ph`, call
`model.to_dict()`, return the JSON to Ruby, write it to disk. Validate against `honeybee-schema` and
`honeybee-ph-schema`. Phase 2 already ran exactly this shape on CPython 3.14 — `Room.from_box` →
`Model.from_dict(model.to_dict())` round-trips — so a failure here is a Pyodide failure, not a
library one.

⚠ **Do not use `adelphi-honeybee-json.hbjson` as a load fixture.** It no longer loads under current
`honeybee-ph`: `Model.from_dict` raises `Failed to apply ph properties to the Model: 'tfa_override'`.
It predates that key and stays a *shape* reference only (Phase 2 Finding 18).

**Step 4 — real data through the bridge** (target: 4 h)
Read the Adelphi model's tagged faces in Ruby, serialise face vertices to JSON, pass them across, and
build the Room from actual geometry. **Measure the payload** — Adelphi has 1441 tagged faces, which is
a realistic worst case and the thing most likely to expose a bridge limit.

**Step 5 — hostile conditions** (target: 2 h)
Windows as well as Mac. Cold start on a slow machine. A large model. Offline. If time allows, an older
SketchUp (2021) to confirm the HtmlDialog floor.

**[Ed / external]** There is no Windows machine in this environment, and installing the spike
extension and clicking through SketchUp is Ed's to do on Mac as well — the agent builds the `.rbz`
and the exact test script; Ed runs it. HtmlDialog is Chromium (CEF) on both platforms, but CSP and
`file://` behaviour are precisely the kind of thing that differs — **do not extrapolate Mac results
to Windows.**

## Measurements to record

| Metric | Why |
|---|---|
| Cold start to `import honeybee` complete | UX viability. >10 s is a problem |
| Warm re-run | Whether the dialog can be kept alive between exports |
| Total vendored bundle size | `.rbz` download size |
| Peak memory alongside a loaded model | Crash risk on modest machines |
| Max JSON payload through the bridge | Whether large models need chunking |
| Mac vs Windows behaviour difference | PRD requires both at v1 |

## Gate

**PASS** — steps 1–4 work on both platforms, cold start is tolerable, Adelphi's payload crosses the
bridge. Mac-only evidence is **PASS-pending-Windows**, recorded as such — not PASS. Adopt Pyodide as
the runtime. **Then immediately resolve the licence question** — vendoring
honeybee (AGPL-3.0) forces AGPL-3.0 on the extension and entangles the future hosted products
(PRD §9). Take that to counsel before writing v1.

**PASS WITH CHANGES** — it works but with a real constraint (slow cold start, payload chunking
needed, one platform flaky). Record the constraint, decide whether it is acceptable, adjust the PRD.

**FAIL** — adopt the PRD §7.1 fallback: **Ruby writes HBJSON directly.** This is a genuine
alternative, not a defeat: no server, no runtime, no AGPL entanglement, full commercial freedom for
v3. The cost is owning schema-drift maintenance, which `honeybee-ph-schema`'s CI was built for.
**Do not** respond to a failure here by reaching for a bundled Python interpreter — that option was
already rejected in PRD §7.1 and nothing in this phase would change that reasoning.

## Deliverables

- `planning/01_sketchup-export/feasibility/RESULTS/PHASE-3_results.md` with the measurement table and a clear verdict
- Working spike code under `planning/spikes/pyodide/`, kept regardless of outcome
- A PRD §7.1 rewritten from "preferred / fallback" to a single decided architecture
- If PASS: a licence question written up for counsel
