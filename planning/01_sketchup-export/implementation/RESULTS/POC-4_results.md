# POC-4 — Integration: results

**Status (2026-08-21): ✅ PASS. All four Ed runs are in and every one behaved as designed.**
Both identity claims are closed — (a) canonically identical across three hosts, (b) extractions
**byte-identical** across two sessions. Both refusals fired with the right words on the right
surfaces. The largest model in the corpus translated 194 faces, 40 apertures and **99 thermal
bridges** with nothing reported.

⚠ **One feature does not work and is recorded rather than quietly dropped: the progress signal.**
No indicator can update during a synchronous main-thread walk — §6.7.

| | |
|---|---|
| `cd pocs/01_sketchup-export && make ci` | ✅ green — 174 pytest cases, **four** Ruby suites, schema gate, real Chromium 88 |
| `cd pocs/01_sketchup-export && make identity` | ✅ **5 of 5** fixtures agree across CPython 3.11 and Chromium 88 — *canonically*, see §3 |
| **Claim (a) — same extraction, every host** | ✅ **CLOSED.** CPython 3.11, Chromium 88 and real SketchUp (×2 runs) all give canonical `77a135bffe9375d8` at 323,779 bytes (§6.2) |
| **Claim (b) — same model, two sessions** | ✅ **CLOSED, byte-identical.** 215,373 bytes each, not merely equivalent (§6.5) |
| Ed's runs | ✅ **all four done, all correct** (§6) |
| ⛔ Progress signal | **does not work, by construction** — no UI updates during main-thread work (§6.7) |

---

## 1. What was built

Against [`../POC-4_integration.md`](../POC-4_integration.md) §1–§2:

| Plan item | Where it landed |
|---|---|
| Version gate (the §1 decision table) | `pocs/01_sketchup-export/ext/dph_plus_poc/gate.rb` — a new module, pure functions over plain data |
| Payload refusal over 3 MB | `Gate.payload`, with the >1 MB notice kept |
| Atomic writes, UTF-8 | `Writer.write` — temp in the destination directory, then `rename` |
| Output path never from `model.path` | `Writer.safe_stem` / `stem_for` / `DEFAULT_DIRECTORY` |
| Dialog report summary | `app.js` `showSummary` + `#summary` in `index.html` |
| Collector raises → visible verdict | `Session#walk_model`, rescued |
| Progress signal | `Collector::Walk` progress hook → `Sketchup.status_text` |
| Byte-identity across hosts | `pocs/01_sketchup-export/tools/byte_identity.py`, `make identity` |

Two suites are new and both found real defects while being written (§4):
`ext/tests/test_gate.rb` (74 checks) and `ext/tests/test_integration.rb` (50 checks), the latter
driving a whole export against a stubbed `HtmlDialog` and reading the message boxes back — which is
how "failures surface visibly" became something with a pass/fail rather than an intention.

## 2. The version gate runs twice, and that is not redundancy

The plan's decision table has a row that is **undecidable before the walk**: *no stamp, but
`DesignPH_dict` present somewhere* proceeds, while *no stamp and nothing anywhere* refuses. The
census answers that, and the census costs the walk.

But the row that matters most has to fire **before** the walk: a designPH 3.x model must bounce off
the front door rather than be handed to a collector written against the 2.x schema. Whatever that
walk produced would be neither a translation nor a report, and an exception out of it is a worse
answer than a sentence naming the version.

So `DphPlusPoc.run` checks the stamps alone — instant, no dialog, no 18 MB Pyodide boot — and
`Session#dispatch_action` runs the full table afterwards with the census in hand. One function,
`Gate.version(stamps, evidence)`, with `evidence = nil` meaning "the walk has not run; defer".

**One extension to the plan's table**, recorded because it is a widening: the plan says refuse
`≥ 3` or unrecognised. The implementation also refuses **`< 2`**, naming the stamp as *older than
this reader supports*. A designPH 1.x schema is not one anybody here has seen, and "refuse and say
what you saw" beats "walk it and hope".

⚠ **Hard rule 6 is untouched.** The gate decides *whether to read*; it never keys the read on a
version. Past it, `collector.rb` still coalesces `*ID` ‖ `*Auto` regardless of any stamp.

### The C2 test does not stamp a model

The plan's §3.3 proposed stamping a fresh synthetic model with `designPH_version = "3.0.1"` via the
Ruby console. The runbook does **not** do that. Hard rule 2 says never write to `DesignPH_dict`, and
there is no need to bend it: the refusal reads the stamp through exactly one function, so stubbing
`Gate.stamps` proves the same wiring end to end with no model write at all. That `stamps()` really
does read a real model dictionary is covered by `test_gate.rb` and by every real export.

## 3. ⚠ The byte-identity gate could not hold as written

**POC-4's plan asked for byte-identical HBJSON across hosts. The stack cannot deliver it — and the
difference is not between hosts at all. Three consecutive runs on ONE CPython give three different
hashes.**

Two independent causes, both measured on all five fixtures. ⚠ **Neither is an upstream defect** —
that was the first write-up's claim and it was wrong; see the correction below before quoting any
of this.

| | |
|---|---|
| `honeybee_ph/_base.py:21` | every newly **constructed** PH object gets a `uuid.uuid4()`. **152 distinct** on Adelphi, appearing 301 times (`_Base` also seeds `display_name` from the identifier) — segments, sites, climates, monthly temperature sets, every space volume's floor segments |
| `honeybee_energy/properties/model.py:135,147` | materials and constructions come out of `list(set(...))`. Four lists, ordered by `PYTHONHASHSEED`, which CPython randomises per process |

**The shape of the evidence is worth keeping.** After the tool's own bug was fixed (§4), all five
fixtures came back the *same size, to the byte*, with different hashes. A float repr or a locale
moves bytes; it does not move exactly zero of them while changing 22,768 positions. That signature
is what sent the investigation at ordering rather than arithmetic, and it was right.

So the gate is **canonical equivalence**, and the canonicalisation is narrow on purpose:

- UUID-shaped strings become `«uuid:N»`, **numbered by first appearance**. Numbering rather than
  blanking keeps *aliasing* visible — a segment pointing at the wrong site is still a difference.
  ⚠ Note what is correctly *not* a difference: two fresh uuids swapped between two fields. Which
  uuid4 the generator emitted first says nothing about the model.
- **Only four named lists are sorted.** ⚠ Sorting every list would be catastrophic: `boundary`
  vertex order defines a face's orientation, so a blanket sort would call a wall and its mirror
  image identical — a silent failure in the one check whose job is catching silent failures.
  `test_byte_identity.py` pins this rule down; it is the test that makes the tool safe to trust.

Everything a *host* could plausibly change — float repr, dict ordering, encoding, locale — survives
untouched. The raw hashes are still measured and printed, so the day upstream becomes deterministic,
it is visible rather than assumed.

**Result: 5 of 5 fixtures canonically identical across CPython 3.11 and Chromium 88.**

```
fixture                              host           bytes  uuids  canonical sha256
2414_Bluff Reach_COPY                cpython3.11   686479    901  a1b49b819c1b043c
                                     chromium88    686479    901  a1b49b819c1b043c
250703 - Linde Residence_COPY        cpython3.11   158204     60  a526487394f60887
                                     chromium88    158204     60  a526487394f60887
250708_COPY                          cpython3.11   139306     60  dc8c4c9b95b89199
                                     chromium88    139306     60  dc8c4c9b95b89199
2523 Wellington_COPY                 cpython3.11   343040    325  02357ac88ef5aa29
                                     chromium88    343040    325  02357ac88ef5aa29
adelphi-designph_COPY                cpython3.11   323779    301  77a135bffe9375d8
                                     chromium88    323779    301  77a135bffe9375d8

raw byte-identity: 0 of 5
```

### ✅ Corrected — this is not an upstream bug, and the effect is small

*(2026-08-21, after Ed pushed back on the first write-up. He was right; what follows is measured
rather than asserted, and the original claim is left visible below because the way it was wrong is
the useful part.)*

**What was written first:** *"Arguably an upstream bug: an identifier that changes on every round
trip is not an identifier. `from_dict` → `to_dict` is not stable in honeybee-ph today."*

**What is actually true.** Every honeybee-ph `from_dict` reads the stored `identifier` back, and
round-tripping Adelphi's export preserves **152 of 152**, twice over:

```
original uuids : 152
after 1 round  : 152   kept from source: 152
after 2 rounds : 152   kept from round1: 152
```

So `uuid4` in `_Base.__init__` is a **constructor default for an object with no identity of its
own** — the intended behaviour, and correct. The churn is entirely ours: the translator builds fresh
PH objects on every export, from a designPH source that carries no persistent id for a site, a
climate, or a floor segment. There is nothing upstream to fix.

**And the effect is narrower than the count suggests.** Of Adelphi's 152 distinct uuids, **148
appear exactly twice** — as an object's own `identifier` and the `display_name` `_Base` seeds from
it. Exactly **one**, `ph_bldg_segment_id`, is a real cross-reference, and it resolves inside its own
file. So the 301 occurrences are overwhelmingly self-labels with no referent: **diff noise when two
exports of one model are compared, not a correctness or integrity problem.**

⚠ **The `301` figure was also loose.** It counts *occurrences* of uuid-shaped strings; the number of
objects is 152. Both are true, which is exactly the trap already written down as *ask what a number
counts before quoting it* — and it was sprung here on the very next number quoted.

**What is left open**, and it is a smaller question than the first draft implied: should a re-export
of an unedited model produce a comparable file? That matters only to something diffing successive
exports. ⚠ The first draft asserted ph-navigator was such a consumer; **that was not checked and is
not claimed here** — POC-5 should establish whether ph-navigator keys on these ids at all before
anyone spends effort on stability.

**Claim (b) is unaffected either way**: extraction JSONs carry path-qualified persistent ids and no
uuids, so the collector's re-run stability is a separate and cleaner question, which Ed's run B
answers.

## 4. What the new suites found while being written

Four defects, none of which `make ci` would have caught the day before, because nothing was testing
these paths:

| Found | What it was |
|---|---|
| The message box swallowed every error | `finish_with_error` printed only the **first** line. A collector failure carries its error class on the second line, and a Python traceback's first line is the useless `Traceback (most recent call last):`. Both reached the user as a headline and nothing else |
| The progress counter never appeared | The 5 Hz throttle was seeded with `Time.now`, which throttles away the *first* tick — so on any walk shorter than 200 ms the count never showed at all and the signal read as broken |
| `byte_identity.py` compared two different artefacts | `translate_json` returns the **envelope**, not the HBJSON. The CPython leg hashed the envelope while the browser leg hashed `hbjson`, and the tool reported 5 of 5 fixtures differing, with CPython 180 KB larger every time. ⚠ The size gap is what gave it away — **when a comparison fails on 100 % of your data, suspect the comparison**, the same rule the POC-2 reconciler taught, pointed at a new harness |
| `verify_in_chrome.py` printed `None faces` | It read `summary.faces_translated`, a flat key that no longer exists (it is `summary.faces.translated`). It had been printing `None` for as long as it was wrong, in a *detail* string nobody grades |

The last two are the same lesson in two sizes: **a number nobody checks is a number nobody reads.**

### ⚠ And one near-miss: a tool leaked client data into the committed tree

`byte_identity.py` drives `verify_in_chrome.py`, which writes a run baseline to
`planning/01_sketchup-export/implementation/RESULTS/baselines/` **by default** — a committed directory — and that baseline embeds
the first 400 characters of the translated model. Pointed at the corpus fixtures, it duly wrote real
project HBJSON into the repo. Caught by reading `git status` before committing, not by any check.

The rule it breaks is already written down (`pocs/01_sketchup-export/_private/MANIFEST.md`: client data, gitignored,
never committed); what was new is the *route* in. **A tool that composes another tool inherits its
defaults, and a default output location is a decision the composing tool has to make explicitly.**
`under_chromium` now passes `--out-dir` unconditionally, with the reason in a comment beside it.

## 5. Measured

| | |
|---|---|
| `.rbz` | 6.80 MB (was 6.77 MB); installed footprint **20.87 MB** |
| Chromium 88 cold boot | pyodide ready 1994 ms, payload staged 2022 ms, wheels unpacked 2283 ms, imports done **3606 ms** |
| Bridge echo | 1,000,000 bytes round-tripped intact (regression check, not a re-measurement) |
| Extractions | 329–514 KB across the corpus, contract v2 |
| HBJSON | 139 KB (`250708`) to **686 KB** (Bluff Reach) |
| Ruby suites | 19 server + 82 collector + 74 gate + 50 integration checks |
| pytest | 174 cases |

SketchUp-side timings — walk duration, boot, export — come out of Ed's runs and go in §6.

## 6. Ed's runs

[`POC-4_ed-runbook.md`](POC-4_ed-runbook.md). **A is done; B, C1, C2, D outstanding.**

| | |
|---|---|
| A | ✅ **PASSED WITH OMISSIONS**, SketchUp 22.0.353, 2026-08-21 — exactly the predicted numbers, and it closed claim (a) |
| B | ✅ **PASSED WITH OMISSIONS** — and it closed claim (b) in the strongest form available: the two extractions are **byte-identical** |
| C1 | ✅ **refused correctly** — and found a second visibility defect (§6.6) |
| C2 | ✅ **refused pre-walk, no dialog opened at all**, naming `"3.0.1"` (§6.7) |
| D | ✅ **194 / 40 / 99**, TFA 1491.862 m², banner correct — the fix confirmed live (§6.7) |
| D | ⬜ Bluff Reach — the slowest walk and the only thermal-bridge model; the progress signal's real test |

### 6.1 Run A — measured

| | |
|---|---|
| Verdict | `PASSED WITH OMISSIONS` — 4 of 4 checks ok |
| Faces | **82 in, 82 translated, 0 reported** |
| Apertures | **46 in, 46 translated, 0 reported** (44 clean, 2 with notes) |
| TFA | **368.476 m² covered, 0.0 lost** |
| Assembly tiers | `2-u-value` ×42, `none` ×40 — the 40 are the reported entries |
| HBJSON | **323,779 bytes** |
| Walk | **4180 ms** for **1,023,558** face visits (8037 unique × placements) |
| Boot | **2573 ms** cold — no regression on POC-1's 2577 ms |
| Translate | **180 ms** (dispatch 6.82 s → verdict 7.00 s). Plan's budget was ≤ ~1 s |
| wasm heap | 34.6 MB |
| `host_notes` | `[]` — a clean 2.1.15 model with nothing to say, which is the right answer |

### 6.2 ✅ Claim (a) is closed, on three hosts

The same extraction translated under CPython 3.11, headless Chromium 88, and **real SketchUp
22.0.353** — all three canonically identical, all three 323,779 bytes:

```
adelphi-designph_COPY   cpython3.11   323779   301 uuids   77a135bffe9375d8
                        chromium88    323779   301 uuids   77a135bffe9375d8
                        sketchup      323779   301 uuids   77a135bffe9375d8
```

Any difference SketchUp shows from here is attributable to the host or the collector, never to the
translation. That was the point of separating (a) from (b), and it is now worth what it cost.

### 6.3 ✅ And claim (b) was half-answered by accident

Run A's extraction is **content-identical to the POC-2 console capture** taken hours earlier in a
different session — every top-level field but `generated_by`, which carries a build stamp by design:

```
contract_version ==   counts ==   edges ==   faces ==   libraries ==
model ==   tables ==   unclassified ==   windows ==        generated_by !=
```

That is stronger than run B alone would have been: two sessions **and** two different code paths
(`run_collector_console.rb` and the wired dialog export) agreeing on all 82 faces, 46 windows, the
libraries, the tables and the unclassified census. Run B still narrows it — same code path, two
sessions — but the path-qualified ids have already survived a harder test than the one designed
for them.

### 6.4 ✅ Run B — claim (b) closed, and byte-identical rather than merely equivalent

Same model, same build, fresh SketchUp session. The two extractions are **identical byte for byte**:

```
contract_version ==  counts ==  edges ==  faces ==  generated_by ==
libraries ==  model ==  tables ==  unclassified ==  windows ==

raw bytes identical: True   (215,373 vs 215,373)
```

Stronger than predicted. The runbook expected `generated_by` to differ, because it was mistaken for
a per-run stamp — it carries the **build** timestamp and sha, so two runs of one build produce the
same string. Nothing in the extraction is per-run at all, which is the point: the path-qualified
persistent ids (contract §2.1) make the collector a pure function of the model.

The four HBJSONs of this model now on disk agree canonically and differ only in minted uuids:

```
leg                   bytes    raw sha           canonical sha
runA (sketchup)      323779    aef15b9091526ff8  77a135bffe9375d8
runB (sketchup)      323779    d7a4d9d933bb016f  77a135bffe9375d8
cpython3.11          323779    79fba1bf35f356f6  77a135bffe9375d8
chromium88           323779    eaaa1f18a71eecd0  77a135bffe9375d8
```

Timings held: boot 2589 ms (A: 2573), walk 4101 ms (A: 4180), translate 180 ms (A: 180).

⚠ **Run B ran on run A's build** — `make ed` was not re-run, so the banner fix below was not in it
and the banner still read `PASSED`. Confirmed by file timestamp rather than assumed. It changes
nothing about (b), which is a claim about the collector.

### 6.5 ⚠ What run A found — the banner disagreed with the message box

The dialog rendered a green **`PASSED`** while the message box beside it said **`PASSED WITH
OMISSIONS`**, with 40 assemblies unresolved. `showVerdict` was rendering `verdict.passed` — a
boolean — when the verdict has had **three** states since POC-3 §9, and `headline` carries them.

Two surfaces describing one run disagreed, and **the one that stays on screen gave the more
flattering answer.** That is the exact failure mode the three-state verdict was invented to prevent:
`PASSED` is supposed to mean everything translated, and it is meant to be rare on real models.

Fixed by reading `headline` — which is also what Ruby writes to the message box, so the two cannot
drift apart again.

⚠ **And the harness could not have caught it, for the same reason the code was wrong: it graded
`verdict.passed` too.** That was written up first as "the stub fixture has no omissions to show".
**That was wrong, and checking it makes the finding worse.** The stub fixture yields `PASSED WITH
OMISSIONS` and always has — 5 assemblies translated, 1 reported. So **every CI run since the
fixture was written rendered the wrong banner, headlessly, with no assertion looking at it.** The
failing case was on screen the whole time.

`verify_in_chrome.py` now reads the DOM back and asserts the banner equals the verdict's own
headline, plus that the summary table rendered. Verified to bite: reverting `showVerdict` to the
boolean produces

```
FAIL  banner shows the verdict's own headline  (banner 'PASSED' vs headline 'PASSED WITH OMISSIONS')
```

**A harness that only inspects the objects a UI is built from cannot see the UI.** If the claim is
about what a user sees, the assertion has to read what a user sees.

⚠ **The runbook also predicted Adelphi's walk at ~200 ms; it is 4.2 s.** The guess came from
"simplest model in the corpus" — but walk time tracks *placements*, and Adelphi visits 1,023,558
faces. The corpus range was already recorded as tracking placements rather than model size; the
prediction ignored what had been written down.

### 6.6 ✅ Run C1 — the refusal fired, and exposed a second surface left mid-flight

A blank six-face model. The two-stage gate behaved exactly as designed: the **pre-walk** check found
no stamps and, with the census unknown, correctly **deferred** rather than refusing; the walk came
back `6 faces / 0 classified / 0 edges / 0 windows in 0 ms`; the **post-walk** check found no
evidence at all and refused, naming what it looked for.

```
[dph+] walked 6 faces / 0 classified / 0 edges / 0 windows in 0 ms
[dph+] REFUSED
[dph+] This model carries no designPH data at all: no version stamp, no tagged faces or edges,
       no designPH windows and no designPH tables.
```

⚠ **And the dialog was left reading `booting…`.** The message box carried the refusal, the user
dismissed it, and the window that stays on screen was still claiming to be starting up — a session
that had finished its work looking like one in progress.

**This is the third instance of one bug this phase**, and the pattern is now the finding rather
than any individual case: *the message box and the dialog are two surfaces reporting one run, and
only the message box was ever wired to say so.* First the banner rendered a boolean instead of the
three-state headline (§6.5); now a whole branch never reached the banner at all. Both times the
transient surface was correct and the persistent one was not.

Fixed: `refuse` now pushes `DphPlus.showRefusal(...)` into the dialog, **before** `UI.messagebox` —
the box blanks the dialog while it is up, so a banner written afterwards is written to a window
nobody is looking at. It gets its own amber state rather than reusing `fail`, because a refusal is
not a failure: nothing went wrong, we declined. `test_integration.rb` now asserts the banner text,
that it matches the message box, and that it is pushed before the box.

⚠ **Worth noting for v1, not fixed here:** C1 boots the full 18 MB Pyodide runtime and *then*
refuses, because the walk only happens once the dialog signals ready. Reordering would save ~2.5 s
on a model we were never going to export — but it would also leave the user staring at nothing for
the length of the walk (4.2 s on Adelphi, 9.7 s on Bluff Reach), which is worse. A real fix shows
the dialog immediately and walks *before* booting Pyodide. Not a POC problem.

### 6.7 ✅ Runs C2 and D — and the one feature that does not work

**C2 — the version refusal.** One line in the console, `REFUSED (pre-walk)`, **no dialog opened at
all**, and a message box naming the stamp:

> This model reports a designPH version DesignPH-PLUS cannot read: `"3.0.1"` — newer than this
> reader. This reader understands designPH 2.x. Nothing was read and nothing was written.

The no-dialog part *is* the test. It is the whole reason the gate runs twice: a 3.x model bounces
off the front door before the collector, before Pyodide, before anything.

**D — Bluff Reach, the corpus's largest and only thermal-bridge model.** Everything exact:

| | |
|---|---|
| Faces | **194 in, 194 translated, 0 reported** |
| Apertures | **40 in, 40 translated, 0 reported** |
| Thermal bridges | **99 in, 99 translated, 0 reported** — the first live run of that path end to end |
| TFA | **1491.862 m² covered, 0.0 lost** |
| Assembly tiers | `none` ×140, `1-layered` ×54 |
| HBJSON | **686,479 bytes** — the same byte count as both offline legs |
| Walk | **10.9 s** over **2,556,183** face visits |
| Translate | 340 ms |
| Extraction | content-identical to the POC-2 fixture; only `generated_by` differs (newer build) |

**And the banner read `PASSED WITH OMISSIONS`** — §6.5's fix confirmed in SketchUp, with the summary
table, the TFA line, eight named omissions and "…and 132 more, all of them in the .report.json".

### ⛔ The progress signal does not work, and could not have

Ed never saw it — on a **10.9 second** walk. Two independent reasons, and only the second matters:

1. `Sketchup.status_text=` writes to the bottom-left of the **main SketchUp window**, which the
   dialog and the Ruby Console sit on top of. Wrong surface: the user is watching the dialog.
2. ⚠ **The walk is a synchronous loop on the main thread, so nothing repaints — not the status bar,
   and not the dialog either.** Ed's own words: *"The js window seems to get locked while the
   routine is running. Goes blank until after the save operation is complete."* That is
   `CONSTRAINTS.md` §3's `UI.messagebox` note generalised, and it is **hard rule 9 seen from the UI
   side**: SketchUp drives its own chrome *and* CEF from the main run loop.

**So no progress indicator of any kind can work during main-thread work.** The fix is structural,
not cosmetic — chunk the walk across `UI.start_timer` callbacks so the run loop turns over between
them, which means turning `collector.rb`'s recursion into an explicit stack. That is v1's, not the
POC's. The hook and its throttle are kept, with the code saying plainly that nothing displays.

⚠ **This is the fourth time in one phase that an assertion on a call stood in for an assertion on a
surface**, and it is the one the offline suite could never have caught — *a stub has no screen*:

| | What was asserted | What was true |
|---|---|---|
| §6.5 | `verdict.passed` | the banner showed the wrong one of three states |
| §6.5 | the harness graded `verdict.passed` too | it had rendered the wrong banner every CI run |
| §6.6 | the message box carried the refusal | the dialog was left reading `booting…` |
| §6.7 | `status_text` was **set** — and it was | nothing was ever displayed |

**When the claim is "the user sees X", the assertion has to read X off the surface** — and be shown
to fail on the code that got it wrong.

## 7. Gate

# ✅ **PASS** — closed 2026-08-21, SketchUp 22.0.353.

| Gate condition | Outcome |
|---|---|
| The expected HBJSON + report, with a `PASSED`-family verdict | ✅ runs A, B, D — all exact against the corpus predictions |
| Failure paths surface visibly | ✅ both refusals named what they saw, on both surfaces — after §6.6's fix |
| No silent hang | ✅ none; the two long waits are explained and now recorded as a constraint |
| No silent output difference between hosts | ✅ canonical identity on CPython 3.11 / Chromium 88 / SketchUp ×2 |

**The gate's wording changed once, and the change is the honest part.** The plan asked for
*byte-identical* output across hosts. That is unachievable and was never a host problem — the same
translation twice on one CPython gives two files (§3). The claim graded here is **canonical**
identity, with raw byte-identity measured, reported, and expected to be 0 for as long as
honeybee-ph mints a `uuid4` per constructed object.

**Carried into POC-5, not fixed here:** the progress signal (§6.7), the 18 MB re-download per dialog
open, and the ~2.5 s Pyodide boot spent on a model that is then refused (§6.6).
