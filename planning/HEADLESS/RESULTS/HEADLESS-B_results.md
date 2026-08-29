# HEADLESS-B results — the contract-v2 identity gate

DATE: 2026-08-29
STATUS: ✅ **PASS — H1–H7 and H9 all green, H8 recorded.** ⚠ On a third-party SDK build; see §8
PLAN: [`../HEADLESS-B_contract-identity-gate.md`](../HEADLESS-B_contract-identity-gate.md)

---

## Verdict

**A headless CPython process, with no SketchUp installed and no SketchUp seat, is a drop-in
replacement for the POC's capture device.** It emits the frozen contract v2, reconciles under the
unchanged harness, matches the five live SketchUp captures with **zero unexplained differences**,
and feeds the untouched translator to the POC's own acceptance numbers — producing **canonically
identical HBJSON** on all five.

| Gate | Result |
|---|---|
| **H1** entity identity | ✅ **PASS** — **883/883** entities (545 faces · 99 edges · 239 windows) join on the path-qualified persistent id, 0 unmatched, 0 degenerate ids |
| **H2** contract-v2 emission | ✅ **PASS** — **16/16** models emit contract v2, 0 shape or leakage problems; the read-only handle refuses **6/6** writers the binary exports |
| **H3** reconciliation | ✅ **PASS** — **14/14** gradeable models under `check_extraction.py`, unchanged. ⚪ `2618 Lavoie` has no offline baseline and is named as ungradeable |
| **H4** identity vs live — claim (c) | ✅ **PASS** — **0 unexplained differences on 5/5**; worst geometry deviation anywhere **0.000000 mm** |
| **H5** the unchanged translator | ✅ **PASS** — **545/545 faces · 239/239 windows · 99/99 bridges**, TFA **368.476 / 1491.862 / 448.182 m²** |
| **H6** HBJSON equivalence | ✅ **PASS** — **5/5** canonically identical, and the comparison is shown to still fail on a moved vertex, a reversed winding and a renamed construction |
| **H7** determinism — claim (d) | ✅ **PASS** — **16/16** byte-identical across two CWDs and two `--out` paths. ⚠ Scoped: see §4 |
| **H8** cost | ✅ **RECORDED** (no threshold) — slowest **2.5 s**, heaviest **717 MB** peak RSS, whole 230 MB corpus **11.8 s**. Its concurrency *agreement* is separately **PASS**: 3/3 modes, 0 disagreements |
| **H9** unknown versions ⭐ | ✅ **PASS** — designPH **1.0.30 refused by name**, exit 2, nothing written; **2.4.0 BETA** read with every key accounted for |

```
CORPUS TOTALS, headless captures through the unchanged translator
  classified faces  545 / 545        windows          239 / 239
  thermal bridges    99 /  99        HBJSON canonical   5 /   5
  models emitted     16 /  16        unexplained diffs      0
```

Reproduce with `planning/spikes/headless/run_gates_b.sh` — one command, ~60 s, one verdict line per
gate (needs `_private/` staged and `cd poc && make venv` once). ⚠ The runner grades on each gate's
**exit code**; the verdict lines are display. An earlier version graded the prose, which is the POC
banner defect exactly — a gate that crashed after printing `PASS` reported green.

⚠ **The caveat that outranks everything below is not technical.** Every number here was produced
on a **third-party re-host** of Trimble's SDK, because the official one is behind an unanswered
access form. §8.

---

## 1. What the five live captures and the headless ones actually differ by

H4 compared in three strata — attribute payloads exact, geometry within 1 mm with the absorbed
deviation reported, derived fields exact under H1's join — and every difference landed in a named
bucket. There are four, and **none of them is a difference in what was read**:

| bucket | count | what it is |
|---|---:|---|
| `entity_id` | 883 | `SUEntityGetID`. Contract §2 calls it session-scoped, a debugging aid only; the contract joins on `id`. See §4 — it is scoped to the **process**, not the model |
| signed zero | **72** | a coordinate the C arithmetic reached as `-0.0` where Ruby reached `0.0`. Always in that direction. §3 |
| record order | 4 of 5 | the C walk emits faces, then edges, then instances, then groups; Ruby's `entities.each` interleaves. Same set, same ids, different sequence |
| `model.file_name` | 1 (Wellington) | ★ the one field where the **headless reader is right** — §2 |

**Worst geometry deviation across 545 faces, 99 edges and 239 windows: 0.000000 mm.** Not "within
tolerance" — the loop points, the areas, the panel loops and the world transforms are byte-equal.

**And the transport claim is made without a second decoder.** The contract carries designPH's
Marshal tables *decoded*, so the live captures never shipped the stored base64 and a byte-equality
claim against them is not available: Ruby's `Marshal.load` agreeing with Phase 1's construct-nothing
parser is evidence about both decoders. So the byte-level claim is made where it can be — ★ **all
63 stored blobs the C SDK returns appear VERBATIM in `model.dat`**, on all five models. If the SDK
had truncated a value, the exact byte run would not be in the file.

## 2. ★ The one field where the headless reader is deliberately better

`collector.rb` derives `model.file_name` from `Sketchup::Model#path` — the location the model was
last **saved**, which on 2 of 5 corpus copies is somebody else's machine. Wellington's live capture
is stamped `2523 Weiilington`, a backup's misspelling. A headless reader knows which file it opened.

The difference is **named, not absorbed**, and it propagates: honeybee threads the model name into
the `Model`, the `Room` and the building segment, as a **substring** of derived identifiers
(`2523_Wellington_COPY_Room`).

⚠ **Two attempts to scrub it out of the HBJSON each fixed one occurrence and revealed the next**,
which is exactly how a canonicaliser grows until it can no longer fail. The fix is that **an input
difference has to be removed from the input**: H5 writes a third, name-aligned capture — the same
headless capture with one field set to the live capture's value — and H6 compares that. One field,
changed in the input, recorded per model.

## 3. ⚠ Signed zero: a real difference that `==` cannot see

`-0.0 == 0.0` is `True`, so an ordinary field-by-field comparison absorbs it in complete silence.
`json.dumps` writes two different tokens, so it does not.

The first symptom was **five canonically-mismatched HBJSON documents with no locatable difference**
— a walk that reported `None` while the hashes disagreed. Measured: **72 disagreements across the
corpus**, every one of them headless `-0.0` against live `0.0`, at the 1e-17 level, on `outer_loop`
and `panel_outer_loop` coordinates.

A vertex at `-0.0 m` is the same vertex, and this is below every tolerance in the project. It
matters only for hashing — which is the whole basis of a watcher deciding a model changed.

⚠ **And the check written to catch it could not fire.** `numbers()` descended lists but not dicts,
and it is called on a whole *record*, which is a dict — so the bucket reported **0 on all five
models** and would have been quoted as "there are no signed-zero differences". Fixed, it reports
1 + 51 + 4 + 12 + 4 = **72**, matching an independent count exactly. *A check that cannot fire is
worse than no check, because it gets quoted as evidence.*

⚠ **And it cannot be fixed at the source, which was measured rather than assumed.** The obvious
deeper fix is for `_round6` to return an unsigned zero, on the premise that `collector.rb` emits
`0.0` there and the whole downstream apparatus exists to absorb one line. Measured across the five
models: headless `-0.0` against live `0.0` on **72** coordinates — **but both readers emit `-0.0` on
12 more**. Normalising in the collector would take 72 disagreements to **12, not to 0**, would not
remove the bucket or H6's normalisation step, and would make the capture device deliberately differ
from the reader it exists to reproduce. It stays a contract-v3 *proposal* (§9), which is where a
change of that kind belongs.

## 4. ⚠ What claim (d) actually covers — and it is narrower than "deterministic"

H7's first two legs read one model each in a fresh process, from two working directories, two
`--out` paths, and the model given absolutely on one leg and relatively on the other. **16/16
byte-identical.**

★ **Leg C is the one that says what that means.** It reads a *different model first, in the same
process*, then the model under test:

| | |
|---|---:|
| byte-identical to a fresh-process read | **0 / 15** |
| identical once `entity_id` is excluded | **15 / 15** |

`SUEntityGetID` is scoped to the **process**, not to the model. After thirteen other models every
one of Adelphi's 128 ids has moved and the capture is 384 bytes longer. The contract already calls
that field session-scoped and a debugging aid only, so this is the contract being right rather than
the reader being wrong — but the operational consequence is concrete:

⛔ **A watcher that hashes captures to detect change must exclude `entity_id`, or re-read in a fresh
process.** Contract-v3 candidate (§7).

⚠ That same field made H8's first concurrency check report a MISMATCH on **two plain parallel
processes**, where nothing concurrent was happening at all. *When a check fires on 100 % of your
data, suspect the check.*

## 5. Cost and concurrency (H8 — recorded, no threshold)

One process per model, because the capability sweep's 851 MB was a *process* high-water mark that
could not be attributed to any one file.

| model | file | wall | peak RSS | face placements |
|---|---:|---:|---:|---:|
| `2618 Lavoie` (scale probe) | **139 MB** | **2.49 s** | **717 MB** | 125,964 |
| `2414 Bluff Reach` | 10.3 MB | 1.73 s | 410 MB | **2,556,183** |
| `2536 Holmes` | 5.6 MB | 1.06 s | 274 MB | 900 |
| `250703 Linde` | 6.9 MB | 0.79 s | 192 MB | 2,466 |
| `2523 Wellington` | 6.5 MB | 0.53 s | 180 MB | 424,555 |
| `adelphi-designph` | 3.0 MB | 0.34 s | 130 MB | 1,023,558 |
| `250708` | 4.0 MB | 0.21 s | 103 MB | 2,456 |
| **whole corpus, 16 models** | **230 MB** | **11.8 s** | — | — |

⚠ **Cost tracks neither file size nor placements.** Lavoie is 13× Bluff Reach's file and reads
*faster*; Adelphi has 1,023,558 placements and reads in 0.34 s while Holmes's 900 placements take
1.06 s. What it tracks is the **entity enumeration** — every face, edge and instance of every
definition, each with an attribute-dictionary probe. Holmes carries 613 component definitions and
~206k edge entities; Lavoie ~126k faces and ~257k edges.

➕ **Concurrency, measured rather than assumed** — all three work, and all three produce captures
matching the sequential ones (`entity_id` aside):

| | wall | peak RSS | captures match |
|---|---:|---:|---|
| two models open at once in one process | 2.82 s | 761 MB | ✅ |
| two processes in parallel | 2.57 s | — | ✅ |
| **two threads in one process** | 2.47 s | 723 MB | ✅ — no errors |

⚠ The threaded leg is run **inside a subprocess on purpose**: `SUInitialize`'s thread safety is
undocumented here, and a reader that segfaults must produce data rather than take the harness down.
It did not segfault, but ⚠ **two threads is not a thread-safety proof** — it is one observation on
one build, on two models, with no contention on a shared model handle.

## 6. ⭐ New coverage the POC never had

§2.2's structural change — run the emission-side gates on **all 16** staged models, not just the
five captured — paid for itself three times:

- ⭐ **`2536 Holmes`: 42 named thermal-bridge edges**, captured and translated for the first time.
  It is the **only second bridge model in existence**, and "confirmed on one model is confirmed on
  nothing" is this repo's most-repeated lesson. 69/69 faces, 24/24 windows, **42/42 bridges**,
  TFA 312.274 m², reconciling against its offline baseline.
- ⭐ **`2618 Lavoie`, 146 MB** — the scale probe. Reads in 2.5 s at 717 MB peak.
- ⭐ **designPH 1.0.30** — refused by name (§7), which is the answer H9 wanted.
- Plus `2605 MacDonough` (34 faces, 25 windows) and five backup files, all reconciling.

## 7. H9 — and the gap it found

The plan left H9's right answer open on purpose. It is settled: **1.0.30 is refused by name.**

```
BLDGTYP-sample-pre2014_COPY.skp: REFUSED — nothing was read and nothing was written

This model reports a designPH version DesignPH-PLUS cannot read:
  '1.0.30' — older than this reader supports
This reader understands designPH 2.x. Nothing was read and nothing was written.
```

Exit code 2, no file written. `2.4.0 BETA` is **allowed** — a beta of a 2.x release reads like a 2.x
release — with every string-typed model key the offline baseline records accounted for in
`counts.tables_found`.

⚠ **And writing H9 found that the collector was not running the gate at all.** The gate existed only
in the Ruby extension. `gate.rb` is now ported as `gate.py` and applied **pre-walk** (on the stamps
alone, so an unknown generation never meets a collector written against a schema it does not have)
and **post-walk** (with the census as evidence, because "no version stamp" only means "not a
designPH model" if the walk also found nothing). H9 grades the **reader**, through its CLI, not the
gate function — the gate being right is a different claim from the reader applying it.

⚠ The first version of H9 flagged `Dashboard` as a silent partial capture. It is a **bool**, so it
cannot be a `BAh…` blob, and the contract already says so. The check now derives which keys *could*
be tables from the baseline's own recorded value types rather than an ignore-list. *A check that
fires on healthy data is testing the wrong property.*

## 8. ⛔ What is NOT established

1. ⛔ **Nothing here was run on Trimble's own SDK.** Every number is from a third-party re-host
   (`HEADLESS-A_results.md` §1). The suite is one command, so re-running it is cheap once the
   official SDK arrives — but **a PASS here is a strong feasibility result, not a commercial green
   light**.
2. ⛔ **L1 (read the SDK EULA) remains unstartable** — the EULA ships inside the gated download.
3. **macOS arm64 only.** Windows and Linux are untested — Spike C.
4. **Thread safety is observed, not proven** (§5).
5. **The 1.0.30 generation is refused, not supported.** Whether a future reader should *translate*
   it is a product question this gate does not answer.
6. **`2618 Lavoie` cannot be graded** — no offline baseline and no live capture. It proves the
   reader does not fall over at 146 MB; it proves nothing about correctness. (The 1.0.30 sample is
   a different case: the gate **refuses** it, so H2 writes it to `quarantine/` and the later gates
   never see it — the pipeline embodying H9's rule rather than contradicting it.)

## 9. Contract-v3 candidates — proposed, never applied

Spike B **proposes**; the contract changes only through its own §9 process. Two are new from this
spike and are about *comparability*, which is what a watcher needs:

| candidate | evidence | why it may matter |
|---|---|---|
| ⭐ **emit an exact zero unsigned** | 72 signed-zero disagreements, all one direction | two capture devices would then be comparable **byte-for-byte** rather than field-by-field (§3) |
| ⭐ **drop `entity_id`, or mark it excluded from comparison** | 0/15 captures byte-stable across process history; 15/15 without it | a watcher hashing captures to detect change cannot use the current document as-is (§4) |
| north correction | non-zero on 7 of 16 | solar orientation — currently emitted with no true-north reference at all |
| lat / long | real coordinates on 5 of 16 | climate. ⚠ also client data, and `geo_referenced` is `true` at `(0,0)` on Adelphi |
| tag / layer name on classified faces | v2 carries `tag` only on *unclassified* records | the shading question (PRD §7.2) |
| model GUID | stable across reads, differs between saves | change detection without hashing 146 MB |

⚠ Still open, still deliberately unmeasured: windows carry a `DesignPH_dict` with `descNameAuto` on
9 of 16 models that the contract does not read. **Measure before proposing.**

## 10. Recommendation for Spike C

**Go — with the licensing block stated first, because it is the one that decides anything.**

A headless macOS reader is a drop-in capture device: it produces the frozen contract from a real
`.skp` with no SketchUp anywhere, and its output is indistinguishable from the live one apart from
four named, explained fields. It reads the whole 230 MB corpus in **11.8 s**, peaks at **717 MB** on
a 146 MB model, and runs two-up in a process, in threads, or in parallel processes without
disagreeing with itself. For a Dropbox-watcher architecture that is comfortably fast enough on a
single worker, and the per-model memory says how many workers a box will hold.

Two things must be settled before that is worth building, and neither is technical: **the SDK is
still behind Trimble's access form**, so every number above is provisional in the way that matters
commercially; and **a working server-side path makes the AGPL §13 reframing urgent rather than
hypothetical**. L2 is actionable now and L1 is not.

The technical input Spike C most needs from here is the one thing this phase could not measure:
⛔ the reader **mutates the in-memory model as a side effect of reading it**, so *never save an
opened model* is a load-bearing invariant of any deployment, not a convention. It is enforced
structurally in this reader — the binding declares no writer and the handle refuses to resolve one —
and that property has to survive whatever Spike C wraps around it.

## 11. Deliverables

| Artifact | State |
|---|---|
| `planning/spikes/headless/collector.py` | ✅ the headless contract-v2 collector |
| `planning/spikes/headless/gate.py` | ✅ `gate.rb` ported; applied pre-walk and post-walk |
| `b1`–`b9` gate scripts + `run_gates_b.sh` | ✅ one command, one verdict line per gate |
| `sdk.py` | ✅ `read_only` handle; enums and one module loader parsed/shared from the shipped headers |
| `harness.py` · `_gate_runner.sh` | ✅ the shared gate plumbing — `captured_models` (derived from what is staged, with a floor), `run_child`, and a runner that grades on **exit codes** |
| `_private/out/captures/` | ✅ 16 contract-v2 captures (gitignored client data) |
| [`00_Context/SDK_RUNTIME.md`](../../../00_Context/SDK_RUNTIME.md) | ✅ updated — the durable record |
| [`00_Context/HEADLESS_VIABILITY.md`](../../../00_Context/HEADLESS_VIABILITY.md) | ✅ updated |
| SDK EULA (L1) | ⛔ still not obtainable |

---

## Changelog

- 2026-08-29 — written. All nine gates run; H1–H7 and H9 PASS, H8 recorded. Four findings that each
  produced a plausible wrong answer first: the documented `SURefType` order is two off in API 13.0
  (`Face` is 11, not 9) and a host-face type check against it rejects **every** glued host;
  `-0.0 == 0.0` hides a real difference from `==` and the check written to catch it could not fire;
  `entity_id` is process-scoped, which made a concurrency check fail on two plain parallel
  processes; and the collector was not running the version gate at all.
- 2026-08-29 — **cleanup pass** (four independent review agents over the diff). All nine gates
  unchanged and still green; the suite is ~60 s. Three of the four reviews independently found *a
  check that could not fail*: both shell runners graded the gates' prose and discarded their exit
  codes; H8's concurrency agreement reached no verdict at all; H6's self-test ran on one model and
  its skips did not fail. Also: H7's leg C vanished silently if a hardcoded filename was absent
  (`0 == 0` inside a PASS), H3 reclassified the harness's failures by substring, H1's PASS was
  one-directional, H5 excluded the whole `model` summary key rather than comparing the aligned
  translation it had already built, H2 wrote a capture for a model the reader must refuse into the
  directory the later gates glob, and `gated_capture` opened every file twice (a measured +46 % on
  the CLI's default path). ⚠ One finding was measured and **not** applied — see §3.
