# POC-4 — Integration (end to end inside SketchUp)

> ### ✅ **DONE — gate closed PASS, 2026-08-21.** Results: [`RESULTS/POC-4_results.md`](RESULTS/POC-4_results.md).
>
> This file is the *plan*, kept as written. Three of its statements did not survive contact:
>
> - ⚠ **§3/§4's "byte-identical" is unachievable**, and never was a host problem — the same
>   translation twice on one CPython gives two files. Graded on **canonical** identity instead.
> - ⚠ **§0's "a progress signal matters more than an optimisation" was right about the need and
>   wrong about the feasibility.** No indicator can update during a synchronous main-thread walk.
> - **§3.3's synthetic 3.0 stamp was not used** — hard rule 2 says never write to `DesignPH_dict`,
>   and stubbing `Gate.stamps` proves the same wiring with no model write.


**Builds:** the wired product path — collector → bridge → translator → HBJSON + report on disk —
plus the minimal dialog UX around it.
**Depends on:** POC-1, POC-2, POC-3 all gated. ✅ **All three closed 2026-08-21; this phase then
ran and closed the same day — see the banner above.**
**Box:** ~1 agent session + one to two Ed SketchUp runs.

> ⚠ **Most of the wiring already exists.** POC-2 and POC-3 built and ran the whole path against all
> five corpus models; what is genuinely left is §1's version gate, the payload refusal, atomic
> writes, the dialog's report summary, and §3's byte-identity check. Read the four corrections below
> before starting — the corpus sweep invalidated some of this plan's assumptions.

## 0. ⚠ What the corpus sweep changed about this plan

| This plan assumes | What was measured (2026-08-21) |
|---|---|
| "refuse politely over 3 MB" | Real contract-v2 extractions are **334–501 KB**; the largest HBJSON is 686 KB (Bluff Reach). The threshold is fine — **keep the contract's "log anything approaching 1 MB" rule too**: it is what caught the 2.25 MB duplicated-library defect on the very first capture it applied to |
| step 5 writes "beside" the model | ⚠ **Never derive an output path from `model.path`.** It is the last-*saved* path, on whatever machine saved it; on 2 of 5 corpus models it names somebody else's machine, one of them a Windows path that macOS turns into a single filename. Use the save dialog's answer, or a fixed directory (`SKETCHUP_RUNTIME.md` §8.2) |
| the version gate keys on `designph_versions` | Still right, and the corpus now shows the spread it has to survive: designPH **2.1.15 → 2.2.29** across five models, and SketchUp **22 → 26** wrote them. Two files came off machines newer than the reader |
| §3's byte-identity check runs on one extraction | It has **five** real ones now, in `poc/_private/fixtures/`. Run it on all five — Adelphi masked three separate bugs in POC-2's harness by being the simplest model in the corpus |

**And one thing to add that this plan does not have:** the collector walk takes **100 ms to 9.7 s**
across the corpus, and it tracks *placements*, not model size or complexity. A progress signal
matters more than an optimisation, and a 10-second freeze with no feedback is the failure a user
will report.

---

## 1. The wiring

Replace POC-1's stub with the real path behind `Export HBJSON…`:

1. Ruby: run the collector on the active model → extraction JSON. Log size; refuse politely over
   3 MB (bridge verified to 4 MB; the margin is deliberate) with a message saying what to trim.
2. Ruby → dialog: `DphPlus.dispatch({action: "translate", payload: <extraction JSON>})`.
3. Dialog boots (or reuses — keep the dialog alive between exports; warm re-run was 5 ms vs 2.6 s
   cold) → `dph_translator.entry.translate_json()` (the POC-1 §4.1 seam — JS never calls anything
   else) → result `{hbjson, report, verdict}`.
4. JS → Ruby: result via `sketchup.on_result`. Never echo the geometry back.
5. Ruby: save-file dialog (default `<model>_export/<model>.hbjson`), write HBJSON + `.report.json`
   beside it — plus `<model>.extraction.json` when the `Diagnostics ▸ Save extraction JSON`
   checkbox (POC-1 §3) is on. UTF-8, atomically (write temp, rename). For corpus runs, outputs go
   under `poc/_private/` (gitignored — client data), per the overview §8 rule.
6. Dialog shows the verdict banner + the report summary table (counts per kind, TFA coverage,
   tier distribution, first N reported entries with reasons). Message box carries verdict + counts.

**Version gate at step 1 — a decision table, because the corpus itself breaks the simple rule**
(`designph_versions` is an array; Wellington carries two stamps; a stamp can be absent while the
data is fine):

| Found | Behaviour |
|---|---|
| all stamps parse as 2.x | proceed |
| any stamp ≥ 3 (or otherwise unrecognised, e.g. a future format) | **refuse politely, naming the stamp** |
| mixed 2.x stamps | proceed + report note |
| no stamp, but `DesignPH_dict` present on the model or any entity | proceed + report note |
| no `DesignPH_dict` anywhere | polite refusal: "not a designPH model" |

(`2.4.0 BETA` parses as 2.x → proceed.)

## 2. Failure surfacing

Every failure class must land as a visible verdict, not a hang or a console-only trace:

| Failure | Surfacing |
|---|---|
| Collector raises | Ruby rescues → message box `FAILED` + error; nothing written |
| Bridge/dialog dead | POC-1's 6 s no-request diagnostic + timer-flushed logs |
| Python exception | Caught in `boot.py`, serialised into the result, banner `FAILED` with traceback |
| Contract mismatch | Translator's own reported error (POC-3 §2) |
| Write fails | Message box with path and OS error |

The threading rules hold under every branch: worker thread + sleeping timer, queue flushed **before**
the timer is killed — losing the error that explains a failure is the named trap.

## 3. Verification

1. **Attribution check (agent, no SketchUp):** run `dph_translator.entry.translate_json()` on the
   captured Adelphi real fixture under CPython 3.11 **and** in headless Chromium 88 via
   `verify_in_chrome.py`.
   Outputs must be **byte-identical** (Phase 3 precedent). Any later SketchUp-only difference is
   then attributable to the host or the collector, never the translator.
2. **[Ed] End-to-end run** on Adelphi COPY: export with the extraction toggle on; save all three
   output files into `poc/_private/` for comparison. The identity claims, stated precisely:
   **(a)** for the *same extraction JSON*, HBJSON is byte-identical across CPython / Chromium 88 /
   SketchUp (that is what step 1 + this run establish); **(b)** for the *same unedited model*,
   extraction JSONs are identical across sessions — the path-qualified persistent ids (contract
   §2.1) are what make this hold; a diff here means id instability or live-model drift. If (a)
   fails, the translator differs per host — stop and attribute. If (b) fails, diff the extractions
   first; live-model drift is a finding, not a failure.
3. **[Ed] Failure-path runs:** (i) a blank non-designPH model → "not a designPH model" refusal;
   (ii) a **fresh synthetic model** given `designPH_version = "3.0.1"` via the Ruby console — a
   hand-made test model, never a corpus copy or real project (hard rule 2 protects real designPH
   data; a synthetic stamp on an empty model touches none) → the ≥3 refusal naming the stamp.
   No crash, no hang, in either.
4. Performance sanity vs Phase 3: boot ≤ ~3 s warm machine, export ≤ ~1 s for Adelphi. No formal
   budget — just no order-of-magnitude regression.

## 4. Gate

**PASS:** Ed's end-to-end run produces the expected HBJSON + report with a `PASSED`-family verdict;
byte-identity holds across CPython / Chromium 88 / (extraction-matched) SketchUp; failure paths
surface visibly.
**FAIL:** any silent hang or any silent output difference between hosts.

Record in `RESULTS/POC-4_results.md` with the measured timings table (mirror Phase 3's format).

## 5. Out of scope

Corpus breadth (POC-5), ph-navigator (POC-5), any preference UI, batch export, watching model edits.
