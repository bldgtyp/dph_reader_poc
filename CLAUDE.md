# CLAUDE.md — DesignPH-PLUS

@AGENTS.md

The imported file above is canonical for this project — what it is, the hard rules, layout, corpus,
and tooling. **Read it before doing anything here.** Below is Claude-specific only.

---

## Skills to reach for

| Situation | Skill |
|---|---|
| **Anything at all, before planning work** | Not a skill — read `00_Context/CONSTRAINTS.md`. One page, every blocker |
| Anything about PHPP worksheets, cells, named ranges, or PHI criteria | `phi-rules` — **before** opening a PHPP with openpyxl, not after |
| Phius / WUFI / METr rules and limits | `phius-rules` |
| Reading or auditing a WUFI-Passive XML | `wufi-xml` |
| Editing any `.py` in `honeybee_ph`, `PHX`, `PH_units`, or anything Grasshopper-bound | `ironpython-27-compatibility` |
| Adding or changing a field on a model class, or touching `to_dict`/`from_dict` | `hbjson-serialization-contract` |
| Working with PHX model classes | `phx-model` |
| Reading the `adelphi-phpp.xlsm` | `xlsx` (+ `phi-rules` for the cell map) |
| Bulk PDF or screenshot review | `codex-computer-use` — offload, don't read them inline |
| Independent review of a diff or plan | `codex-review`, or a `fable-5`/`opus-4.8` subagent |

Do not hand-explore a PHPP workbook by dumping cells. `phi-rules` already has the per-worksheet map;
rediscovering it is the expensive way to get the same answer.

## Where the answer probably already is

`00_Context/` is now a foundation layer, not just a designPH record. Before investigating any of
these, check the file — all of it is measured, not guessed:

| Question | File |
|---|---|
| What will stop me? What is untested? | `CONSTRAINTS.md` — **read this first** |
| What does designPH store, and where? | `DESIGNPH_DATA_MODEL.md`, `DESIGNPH_FILE_FORMATS.md` |
| What can a SketchUp extension do? Ruby version, threading, the bridge, `HtmlDialog` | `SKETCHUP_RUNTIME.md` |
| Which Pyodide? What does it cost? How do I install wheels? | `PYODIDE_RUNTIME.md` |
| What does honeybee/honeybee-ph/PHX require, and what breaks? | `HONEYBEE_STACK.md` |
| What shape is the data at each hop? | `DATA_CONTRACTS.md` |
| Can we read the `.ppp`? | `PPP_EXPORT.md` — no, and the reasoning is recorded so it stays decided |
| How do I ask the *live* SketchUp model a question? | `CLAUDE_BRIDGE.md` — the eval bridge, below |

## Live SketchUp access — Claude Bridge

**Installed 2026-09-01, source-reviewed:** the [Claude Bridge](https://github.com/lairdubois/lairdubois-claude-bridge-sketchup-extension)
extension (Boris Beaulant, MIT) runs an eval server on `127.0.0.1:7857` inside SketchUp 2022.
POST Ruby, get JSON back — the value of the script's last expression. This replaces the
"write a staged script → Ed runs it → paste output back" loop for *novel live-model questions*,
and it is how POC #3 L-C ("Library Sync") development iterates against a live designPH model.
Full record + payload conventions: **`00_Context/CLAUDE_BRIDGE.md`**.

```bash
curl -s -H 'X-Claude-Bridge: 1' http://127.0.0.1:7857/ping        # always first: is it up, which model
curl -s -X POST -H 'X-Claude-Bridge: 1' --data-binary @script.rb http://127.0.0.1:7857/eval
```

The rules, all measured or inherited from the hard rules:

- **Ed starts/stops it** (toolbar button; checked = running). If `/ping` refuses, ask — never try
  to start it yourself, and never ask him to leave it running unattended (it is an eval server).
- ⛔ **Never `model.save` / `save_as` / `save_copy` in an eval.** Open **copies** only (hard rule 3).
- **Reads use the non-creating form** — `entity.attribute_dictionary('DesignPH_dict')`, no second
  arg (hard rule 2). Writes only under the POC #3 frozen contract, in scratch models, inside
  `model.start_operation(..., true)` / `commit_operation`.
- ⚠ **A native API crash in an eval kills SketchUp itself** — in-process, unrescuable, unsaved work
  lost; the client sees curl exit 52 then connection refused, which reads like "the bridge stopped".
  Measured on day one (suspect: `Sketchup::Text#attached_to`, SU2022). So: against a real project
  model, use only API calls already proven in `bt_inspector` / the POC collector; first-try
  anything new in a throwaway model.
- **Everything runs on the main thread** — a slow eval freezes the UI. Keep evals short, walk
  definitions never placements, return one structured JSON-able hash per eval (`Length` → `.to_f`),
  and remember the binding is fresh per request: no locals persist between evals.
- A leader-Text note's `t.point` **is** the snapped target vertex (measured: 0.0 mm) — Ed can point
  at geometry with the Text tool and the note + target read out safely, no `attached_to` needed.

## Working style here

- ▶ **The repo is organized as numbered POCs (reorganized 2026-08-31): `planning/NN_slug/` for the
  plans + results, `pocs/NN_slug/` for the code, `00_Context/` shared by all of them.**
  `planning/.index.md` is the master router and status table; `planning/.instructions.md` carries
  this folder's conventions.
- ▶ **POC #1 is COMPLETE (Ed, 2026-08-21) and its record is the research base for a future V-0.**
  Picking it up cold: `planning/01_sketchup-export/implementation/RESULTS/POC-5_results.md` — the
  retro; its §4 is the ranked "what v1 must do differently" list.
- ▶ **POC #2 (headless C-SDK reader, `planning/02_headless-reader/`) has Spikes A+B PASS; Spike C
  (deployment) is open.** Its spike code is `planning/spikes/headless/`, client-data scratch in
  `planning/spikes/headless/_private/` (gitignored, `MANIFEST.md`).
- ▶ **POC #3 (`planning/03_library-import/`): Spikes L-A AND L-B are both full PASSES
  (2026-08-31, one day)** — designPH accepts model-level library writes end to end (L-A), and
  **real PH-Navigator assemblies/window types reproduce their intended U-values + Error %
  EXACTLY in designPH's own calculator** (L-B: 8/8 incl. multi-section 3-path, two models, both
  base64 styles; export validated; the `phn_id` extra-column update key measured viable; the
  export consumes `glazingtype`, not `glazingtypeid`). **The durable write-side facts live in
  `00_Context/DESIGNPH_DATA_MODEL.md` §14 + §14.7, and the PHN→designPH mapping is FROZEN in
  `planning/03_library-import/CONTRACT_phn-library.md` (v1)** — read those before writing
  anything into a designPH model or building an importer. ▶ L-C is next, reshaped 2026-08-31
  (Ed): scope the v-0 **"Library Sync"** product — a pull-based SketchUp extension consuming
  PHN (PHN stays web-only; pholio stays a separate product; no honeybee inside → no AGPL
  exposure; decision + trajectory in the POC overview §4). **POC #4
  (`planning/04_hbjson-to-skp/`) is scoped but NOT started** — HBJSON → a *fresh* `.skp`,
  never surgery on an existing model, deferred behind L-C by the sequencing rule. The POC
  carries a scoped amendment to hard rule 2, and hard rule 1
  was amended 2026-08-31 (`00_Context/PPP_EXPORT.md` §1 — validation reads of our own exports
  are permitted; ⚠ the `.ppp` is UTF-16LE).
- **POC #1's code lives in `pocs/01_sketchup-export/`** (closed 2026-08-21), is
  **internal-only, and is never distributed** — the AGPL question
  (`planning/01_sketchup-export/feasibility/RESULTS/PHASE-3_licence-question.md`) blocks *release*, not internal POC work (working
  assumption, for counsel — `planning/01_sketchup-export/implementation/00_POC_OVERVIEW.md` §2.3). v1 remains blocked on that
  answer. Exploratory throwaway code still belongs under `planning/spikes/`.
- **`00_Context/` is the foundation layer, and it is load-bearing.** When you learn something durable
  about designPH, SketchUp, Pyodide or the honeybee stack, it goes there — not into a phase result
  that nobody will read again. Phase results record *what happened*; `00_Context/` records *what is
  true*.
- **Keep the record honest.** When a finding contradicts something already written in `00_Context/`
  or the PRD, *update the document* and mark what was superseded — do not silently patch or leave a
  stale claim standing. §6 of the data-model record is the worked example of this.
- **Mark inference as inference.** Much of `00_Context/` is reverse-engineered from three or four
  models. Say which claims are observed and which are inferred, and name the evidence.
- **Verify before recommending.** If a memory or an older note names a file, key, or flag, check it
  still exists in the current corpus first — designPH's schema has already changed under us once.

## Things that have bitten us

- Python's regex `.` does not match `\n`. The `.skp` length fields are raw bytes, so a 10-character
  key name encodes a `0x0A` and gets **silently skipped** without `re.DOTALL`. This hid three real
  keys and produced a wrong conclusion about the schema. Always pass `re.DOTALL`.
- **A synthetic six-face model is not evidence about real models.** `00_Context` §6's version-rename
  rule came from `designph_test~.skp` — six faces, auto-classified, never hand-assigned. It looked
  clean and it was wrong: every *real* project model does the opposite, and the rule would have read
  zero area groups off a live 2.2 project. Before generalising a schema rule, run it against the
  whole corpus baseline. Cheap models produce cheap conclusions.
- **A `*Auto` key that is present but nil is not evidence of anything.** designPH writes nil
  placeholders freely. Count non-nil values, never records.
- **pydantic 1 inflates validation error counts by expanding every union branch.** The reference
  HBJSON reports 5587 errors for 147 actually-failing objects — a 38× multiplier. Collapse by the
  failing *object* (cut the path after its last list index) before drawing any conclusion, and never
  quote the raw count as a severity signal.
- **The offline `.skp` reader can do per-entity analysis, and two phases nearly missed it.** Attribute
  records are laid out as: dictionary-name marker, that dictionary's keys, next marker. So the run of
  keys between two markers **is one entity's dictionary** — `planning/spikes/phase1/skp_blocks.py`
  groups on that boundary. Phase 0 inferred the `areaGroup`→`tempZone` mapping from population
  arithmetic and Phase 1 was planned as wholly Ed-in-SketchUp, both because "the reader reads records,
  not entities" had been written down once and then believed. Before declaring something live-only,
  check what the existing tool could be made to answer.
- **A SketchUp capability flag is not a statement about the model.** `ComponentInstance#definition.
  behavior.cuts_opening?` is `true` on all 46 designPH windows in Adelphi, yet only **1 of 16** host
  faces has an inner loop. It means "this component is able to cut", not "this host has a hole".
  Trusting it would have holed every emitted `Face3D`. ⚠ **And the obvious fix —
  `face.loops.size > 1` — is also wrong**: a glued opening reduces `face.area` *without* creating a
  loop, so it is true on only **1 of the 16** real Adelphi hosts — and 1 of 81 across all five captured models (remeasured 2026-08-28; the docs said 2). `glued_to` is the only host test, and the same
  quirk means `face.area` is **net** of windows while the loop polygon is **gross**.
- **Walking `Sketchup::Face` is not walking the model.** designPH puts thermal bridges on
  **`Sketchup::Edge`** — PHPP measures them as lengths — so a face-only traversal drops 99 of 293
  tagged entities on a real project with no error. When a live count comes in under the offline
  record count, ask which *entity type* is missing before assuming historical state.
- **A declared dependency is not an imported one, and only the import decides.** `honeybee-core`
  hard-requires `honeybee-schema` → `pydantic` → Rust `pydantic-core`; `PHX` hard-requires `lxml`
  and `xlwings`. On packaging metadata alone both subtrees are impure and Phase 2 would have written
  PHX off entirely — as its own plan had already pre-concluded. Every one of those imports is inside
  a `cli/` module or a reader we never call, and the whole HBJSON → WUFI/METr write path runs with
  all of them uninstalled. Resolve the closure, *then* ask what actually imports it, then prove it
  by installing `--no-deps` and running the thing.
- **`pip download` answers a question about your laptop, not about the package.** It resolves for
  the host platform, so `lxml` comes back as a macOS arm64 wheel — which says nothing about whether
  a pure wheel exists. Resolve with `uv pip compile --universal` and read purity off PyPI's file
  list for the resolved version.
- **A `file://` page cannot fetch its own assets, and no shim fixes it.** Stock Chromium refuses
  `fetch`, `XMLHttpRequest` *and* dynamic `import()` from `origin 'null'` under a single CORS rule.
  A `fetch`→XHR polyfill was written for Phase 3 and it does not help: XHR hits the same rule, and
  Pyodide loads `pyodide.asm.mjs` by dynamic `import()`, which is not interceptable at any level.
  Classic `<script src>` *does* load, which is what makes the failure confusing — the page comes up,
  the globals are defined, and the first symptom names a missing module. Serve over
  `http://127.0.0.1` instead; it is also the only way to set the COOP/COEP headers
  `SharedArrayBuffer` needs.
- **A compressed download size is not a bundle size.** Phase 2 budgeted ≈8.1 MB from `.tar.bz2` and
  `.whl` sizes. The `.rbz` did land at 8.07 MB — but it unpacks to **15.3 MB** in the user's Plugins
  folder, because a zip of an already-unpacked runtime is a different artifact from the runtime's own
  tarball. Two numbers, and the install footprint is the one the user feels.
- **SketchUp's `HtmlDialog` is an old Chromium, and you can find out exactly which one offline.**
  `SketchUp.app/Contents/Frameworks/Chromium Embedded Framework.framework/Resources/Info.plist`
  names it — SketchUp 2022 is CEF 88.2.4, i.e. **Chromium 88, January 2021**. A matching snapshot
  downloads from `commondatastorage.googleapis.com/chromium-browser-snapshots/Mac/<rev>/` and drives
  headlessly over CDP (use `--headless`, not `--headless=new`, below Chrome 109). That converts
  "ask Ed to click and report back" into a local loop — it is how the Pyodide version ceiling was
  found and then bracketed, with no SketchUp runs at all. Check the engine version *before*
  vendoring anything that targets a browser.
- **In SketchUp, blocking I/O must be on a worker thread, and the worker only runs because the main
  thread sleeps.** These are two halves of one rule and each half alone hangs SketchUp. Put the I/O
  on the main thread (a `UI.start_timer` callback) and a write larger than the socket send buffer
  deadlocks: SketchUp drives CEF from the app's main run loop, so CEF needs that thread to drain the
  socket it is blocked on. Put it on a `Thread` with nothing else and the thread never runs at all.
  The working shape is a worker thread doing every blocking operation plus a `UI.start_timer`
  callback whose *only* job is `sleep`, which releases the GVL. Workers must never touch the
  SketchUp API — `puts` included; queue lines and let the timer print them.
- **A Ruby `Thread` never runs in SketchUp, and the socket still binds.** SketchUp runs the Ruby VM
  on its main thread and schedules Ruby only while Ruby is executing, so a background thread parked
  in `TCPServer#accept` is starved forever. `TCPServer.new` has already done `bind` and `listen` by
  then, so the kernel queues the connection and the client waits — no error anywhere, just a blank
  `HtmlDialog` that is indistinguishable from one that refused the URL. Pump long-running work from
  `UI.start_timer`, which fires on the main thread. Cost of learning this the other way: one full
  round trip through Ed.
- **Do not re-implement half of a library's rule locally.** Three bugs in one session came from a
  local approximation of a honeybee predicate: `clean_string` (it truncates at 100 chars),
  `u_value` vs `u_factor` (the first is material-only, the second includes films — the opposite of
  the obvious reading), and `is_horizontal` (it tests **z-extent**, not orientation, at a tolerance
  of 1e-7 m). Each looked right, each was wrong in a way nothing downstream would flag. Call the
  library's own function, even when it is one line.
- **A cross-check that fires is doing its job.** The POC's face-area check flagged 16 of 82 Adelphi
  faces and the first instinct was to suppress it. It had found a real distinction: `face.area` is
  **net** of glued window openings while a polygon from the loops is **gross**, and SketchUp exposes
  no inner loop for a glued opening. Explain a firing check before silencing it. It happened again
  on the aperture fix: the containment check refused exactly one of 46 windows, and the fault was
  **ours** — `Polygon2D.is_point_inside_bound_rect`, sitting as a fast path in front of the tolerant
  `point_relationship`, takes no tolerance and refuses any window flush with its host's edge.
- **A projection hides the bug it is supposed to survive.** Flattening a window rectangle onto its
  host plane works exactly as well from 3 m away as from 3 mm, so shipping a parent-relative
  transform misplaced all 46 of Adelphi's windows with **no symptom anywhere**. Any lossy step needs
  a stated limit on how much it was allowed to absorb, and should report what it absorbed even when
  it passes.
- **Ask what the data on disk already constrains before booking a run.** The rough-opening corner
  convention looked like it needed a SketchUp session to settle. It did not: the *defective* capture
  already fixed the parent transform (local +Z onto host normal by Kabsch; local origin onto host
  plane by least squares), which scored the conventions 46/46 against 23/46 and then let the entire
  fixed pipeline be rehearsed offline. ⚠ A rehearsal is **not** a capture — it de-risks the re-run,
  it does not replace it. `planning/spikes/poc/`.
- **One example is not a census.** "a 1.7 cm² sliver and a zero-width spur" became, once counted,
  **8** faces with a sub-millimetre edge and **7** whose boundary revisits a point. And the spur is
  invisible to the obvious test: **every edge of a spur is long**, so short-edge detection misses it
  entirely.
- **Before shipping a field per entity, ask whether its values are per entity.** designPH's frame and
  glazing option lists are 44,915 characters and **byte-identical on all 46 of Adelphi's windows** —
  2.07 MB of a 2.25 MB payload against a bridge verified to 4 MB, against 45 KB deduplicated to model
  level. `distinct` is a one-line check. The contract's "log anything approaching 1 MB" rule is what
  surfaced it, on the very first capture it ever applied to — a limit that never fires teaches
  nothing.
- **"The longest name wins" is a tiebreak that reads as obviously right and is not.** designPH writes
  a placeholder option list, `&Launch designPH to edit=01ud&`, claiming the same ids as the real
  library. *Launch designPH to edit* is 23 characters; *PH Glazing* is 10 — so length picks the
  placeholder and silently un-names a 500-entry library. Merge by how many ids the **list** names.
- **One sample is not a unit table.** `lenx × leny × 0.00064516 == area` held on the single window
  anybody had ever dumped, and was written into the contract as a confirmed rule. Across the real
  model it holds on **20 of 46**. Arithmetic that "confirms" a rule at n=1 confirms nothing.
- **Ask what a number counts before quoting it.** "8037 faces" and "1,023,558 faces" are both true
  of Adelphi — unique faces, and placements × faces through a recursive walk.
- **`Sketchup::Model#path` is not the path of the file you opened.** On 2 of 5 corpus copies it
  returned where the model was last saved *on someone else's machine* — `/Users/johnmitchell/…` and
  a `C:\Users\greg\OneDrive\…` Windows path, both embedded in the `.skp`. Deriving the output
  filename from it wrote one capture into `~/Documents` with the whole Windows path as a single
  filename and lost the other to `ENOENT`. ⚠ Worse, the COPIES-ONLY guard tested the same value:
  `/Users/johnmitchell/Dropbox/…` does not start with *this* machine's `~/Dropbox`, so hard rule 3
  was not being enforced at all. A guard built on an untrustworthy value fails **open** — and
  widening it to `/Dropbox/` for any user then refused a legitimate copy on the Desktop. ⚠ **A
  negative test on an untrustworthy value is worthless whichever way you point it.** Ask a positive
  question — *is this verifiably the file I expect?* — and hand the residue to the human, who has
  the fact the API does not.
- **A reconciliation check confirmed on one model is confirmed on nothing.** The POC's baseline
  check failed on three of four real captures and the data was right every time: it compared
  `faces_tagged` (every `DesignPH_dict` carrier) against the baseline's *area-group* carriers —
  576 vs 194 on Bluff Reach, where 194 + 99 edges is the baseline exactly — and it counted
  **placements** where the offline reader counts **entities**, 2456 vs 1781 on `250708`, where 1781
  is the baseline exactly. Adelphi masked both: every one of its tagged faces has an area group, and
  none is placed twice.
- **`descName` + `descNameAuto` on one face is normal, not an anomaly.** They are an override pair —
  the user's name and the generated one — so "the key generations are mutually exclusive per face"
  is a claim about `areaGroup`/`tempZone`/`assembly` only. 70 Bluff Reach faces carry both, with
  real room names. The coalesce (user wins) was always right; the *claim* needed narrowing.
- **A parameter fitted to make a model match cannot then confirm that model.** The multi-section
  U-value was first "confirmed" by solving for the framing fraction that made a simple lambda blend
  reproduce one PHPP number — circular, and it hid the fact that the real method is ISO 6946's mean
  of two limits. The replacement is checked against seven independent assemblies *and* the Error %
  designPH prints beside its own answer.
- **A pattern that fits three numbers is not a unit.** `0.0625` and `0.09375` are exactly `1.5/24`
  and `1.5/16` — standard US stud spacings — which reads overwhelmingly as *fractions*. They are
  percentages, 0.06 % and 0.09 %, and one screenshot of designPH's own dialog settled it. Reading
  them the convincing way would have applied a hundredfold framing correction.
- **On macOS, `Sketchup.open_file` opens a new window and `active_model` follows the frontmost.** A
  batch loop over five models writes five files, named after five different models, all containing
  the *first* model's data, with no error anywhere. Collect what is already open, or verify the
  active model's path actually changed and stop if it did not.
- **Two exports of one model are not the same file, and the two failed attempts to prove otherwise
  were each diagnosed by the file *size*, not by the diff.** First the comparison hashed
  `translate_json`'s whole envelope on one leg and the `hbjson` field on the other: 180 KB apart
  every time, which is a comparison of two different artefacts, not a difference between hosts.
  Fixed, the files came back the **same size to the byte** with different hashes — the signature of
  *ordering*, and it was: `honeybee_ph` gives every newly constructed object a `uuid4` and
  `honeybee-energy` orders four lists out of a `set`. ⚠ The fix has its own trap: a canonicaliser
  that sorts *every* list reorders `boundary` vertices, which are a face's orientation — a wall and
  its mirror would compare equal, inside the tool whose job is catching silent differences.
  Normalise by name, never by shape.
- ⚠ **Do not call an upstream design decision a bug without testing the round trip.** The uuid churn
  above was written up as "an identifier that changes on every round trip is not an identifier" —
  and `Model.from_dict` → `to_dict` in fact preserves **152 of 152**, twice over. `uuid4` is a
  constructor default for an object with no identity of its own; the churn is *ours*, from building
  fresh PH objects each export. The same write-up quoted "301 uuids" when the object count is 152
  (`_Base` seeds `display_name` from the identifier) and asserted a downstream consumer that was
  never checked. **Three overstatements in one paragraph, all in the direction of the finding being
  more important than it was.** Measure the blast radius before naming a culprit — here, 148 of 152
  ids have no referent at all.
- **"Byte-identical" was one phrase covering two claims, and conflating them makes a failure
  unattributable.** *(a)* the translator behaves the same on every host, *(b)* the collector reads
  the same model the same way twice. Only (a) is about hosts; only (b) is about sessions. Naming
  them separately is what let (a) close offline while (b) waits for SketchUp.
- **A harness that reads the objects behind a UI is not testing the UI, and the gap hides in plain
  sight.** The POC's banner showed green `PASSED` on a real export with 40 unresolved assemblies,
  because it rendered `verdict.passed` while the message box rendered `verdict.headline`. The
  Chromium harness missed it by grading the same boolean — and the stub fixture has produced
  `PASSED WITH OMISSIONS` since it was written, so **the wrong banner had been rendering in every
  CI run for as long as the harness existed**. The first write-up guessed "the fixture has no
  omissions to show"; checking made the finding worse, not better. Assert on the DOM, and prove the
  new assertion fails on the old code before trusting it.
- **In the SketchUp C SDK, `SUEntityGetAttributeDictionary` is a get-or-CREATE, and the read-only
  alternative silently under-reports.** The header says so plainly — "if a dictionary with the given
  name does not exist, one is added to the entity" — so a function named `Get` **writes into
  `DesignPH_dict`**, the namespace hard rule 2 forbids. Using its success as a tagged-test reports
  every entity as tagged: 8037 faces instead of 1441 on Adelphi. And the obvious fix is also wrong:
  `SUEntityGetNumAttributeDictionaries` returns 1 while `SUEntityGetAttributeDictionaries` returns
  `SU_ERROR_NONE` **with count 0** for dictionaries that exist with keys — losing 118 of 446 tagged
  faces on Wellington, 731 of 1791 on Linde, 716 of 1781 on 250708, and **0 on Adelphi and Bluff
  Reach, which mask it entirely**. The only complete predicate is ask-by-name then `num_keys > 0`.
  ⛔ Consequence: **a C-SDK reader mutates the in-memory model as a side effect of reading it**, so
  "never save an opened model" is a load-bearing invariant, not a convention.
- **A published API name is not a signature, and the wrong guess passes on the first model.**
  `SUModelGetVersion` reads like a getter for the `SUModelVersion` enum; it actually takes
  `(major, minor, build)`. The two-arg guess returned a *believable* 22 on Adelphi — the correct
  major version for its writer — and segfaulted on the next model. `SUEntityGetType` returns its
  enum directly and is not `SU_RESULT` at all. Check declarations against the shipped headers
  (`planning/spikes/headless/a3_header_audit.py`), never against a doc page that lists only names.
- **A published *enum* is not the shipped enum, and the wrong one produces a clean zero.** The
  doxygen `SURefType` puts `Face` at 9; the shipped API 13.0 header inserts `Environment` and
  `Environments` at 8 and 9, so **`Face` is 11** and everything after `Edge` moves by two. A
  host-face type check written against the documented order rejects **every** glued host on every
  model — 0 of 239 — and reads exactly like "the glue query does not work". Parse the enums out of
  the framework's own headers; never transcribe them. (Same rule as `a3_header_audit.py` applies to
  signatures, one level down.)
- **`-0.0 == 0.0` is `True`, so `==` cannot see a signed-zero difference — but `json.dumps` can.**
  The C arithmetic reaches an exact zero from below where Ruby reaches it from above: **72
  coordinates across the corpus**, always the same direction. The symptom was five canonically
  mismatched HBJSON documents with **no locatable difference**, from a comparison walk that
  reported `None` while the hashes disagreed. ⚠ And the check written to catch it **could not
  fire**: its number-flattening helper descended lists but not dicts, and it is called on a whole
  record. A check that cannot fire is worse than no check, because it gets quoted as evidence.
- **`SUEntityGetID` is scoped to the PROCESS, not the model.** Reading thirteen other models first
  moves every one of Adelphi's 128 ids and grows the capture by 384 bytes. Contract v2 already
  calls `entity_id` session-scoped, so this is the contract being right — but it means two captures
  of one unchanged file are byte-identical only *within a process history*, and it is what made a
  concurrency check report a MISMATCH on **two plain parallel processes**, where nothing concurrent
  was happening at all. When a check fires on 100 % of your data, suspect the check.
- **An INPUT difference has to be removed from the input.** `model.file_name` legitimately differs
  between the two capture devices, and honeybee threads it into the model, the room and the
  building segment as a *substring* of derived identifiers. Two attempts to scrub it out of the
  *output* each fixed one occurrence and revealed the next — which is exactly how a canonicaliser
  grows until it can no longer fail. Align the one field in the input and say so.
- **`SUFaceGetArea` takes no transform, so it is the LOCAL area.** Ruby's collector calls
  `face.area(transform)` — world. On unscaled models the two agree and the difference is invisible;
  Adelphi has a scaled container and 14 of 82 faces came out wrong by a constant 2.96x. Use the
  library's own `SUFaceGetAreaWithTransform` rather than rescaling locally — the same rule as
  `clean_string` and `is_horizontal`, one layer down.
- **designPH's Marshal tables are BASE64, not raw binary**, so the NUL-truncation hazard an entire
  gate was designed around does not exist on that path: every value begins `BAh`, which is base64
  for Marshal's `\x04\x08` (hence the collector's `MARSHAL_PREFIX = "BAh"`).
  ⚠ **And the base64 comes in two styles, sometimes within one model** (Linde: `frames_ud`
  wrapped in 60-char lines, `assemblies_calc` strict) — a `BAh[A-Za-z0-9+/=]{40,}` regex without
  `\r\n` in the class silently truncates a wrapped blob at its first line break, and the
  60-char fragment then fails to decode, reading exactly like "table absent". It cost one wrong
  "Linde has no frames_ud" conclusion before the live SDK read contradicted it. A *writer* must
  also match the per-key style (`DESIGNPH_DATA_MODEL.md` §7, §14.2). ⚠ And the NUL check
  built to catch it *fired on healthy data* — Linde's `tfa_calc_ud` has no NUL yet decodes to 4
  complete rows, while 95-byte payloads elsewhere do have them. NUL presence is content-dependent,
  not integrity-dependent. A check that fires on healthy data is testing the wrong property.
- **Walk definitions once; walking placements does not finish.** Adelphi is 1441 tagged face
  entities behind **1,023,558 face placements**, Wellington 4,255,761 nodes. Enumerating each
  definition once is both the correct *entity* basis and ~1000x faster. Where world coordinates are
  genuinely needed, prune the placement walk to subtrees containing tagged geometry (~0.3% of the
  model) — prune the traversal, never the answer.
- **A supported Ruby API can still segfault, and in-process that means SketchUp dies.** An
  unsupported method raises a clean `NoMethodError`; a native bug in a *documented* method killed
  SketchUp 2022 outright on the Claude Bridge's first day (suspect `Sketchup::Text#attached_to`,
  unisolated — `leader_type` and `InstancePath` reads were first-used in the same eval). The two
  failure classes need opposite handling: version gaps fail loud and safe; native bugs fail fatal
  with no Ruby-level symptom. Treat "documented" as no evidence of "won't crash", and exercise new
  API surface in a throwaway model before pointing it at real work.
- SketchUp Ruby is 2.7. Endless-method syntax parses fine in your head and fails on load.
- macOS `strings(1)` has no `-e` flag; use Python for UTF-16 extraction.
- `attribute_dictionaries` returns `nil`, not an empty collection, when an entity has none.
