# POC-5 — Ed's smoke-test runbook **[Ed]** — the standing one

**Status: standing instrument — 2026-08-21.** The POC closed without needing a first formal run of
this file (nine graded sessions across POC-1/-2/-4 served as the smoke evidence —
[`POC-5_results.md`](POC-5_results.md) §5). It remains the *repeatable* smoke test POC-5 §3 asked
for: the document you (or future-you, six months from now) run any time a build changes — including
a future V-0's — and want to know whether the tool still works on real models. Results log in
[`POC-5_results.md`](POC-5_results.md) §5.

⚠ **Everything here is read-only against designPH data** (hard rule 2) and **COPIES ONLY** (hard
rule 3). Never open a corpus original in SketchUp for POC work, and never save a model —
even if SketchUp offers on close.

---

## 0. One-time setup (skip if already done)

| | |
|---|---|
| Install | `cd /Users/em/Desktop/dph_plus_testing/poc && make ed`, then **quit and reopen SketchUp 2022** — the extension is only re-read at launch |
| Copies | the five model copies live in `~/Desktop/dph_poc_copies/`. If one is missing, re-copy it from the source listed in `poc/_private/MANIFEST.md` — copy the file in Finder, never open the original |
| Output | make a fresh dated folder per smoke run: `mkdir -p ~/Desktop/dph_poc_copies/SMOKE-<date>` |

**Before trusting any run: check the build is current.** `make ed` prints the build stamp; the
dialog's message box repeats it via `generated_by`. POC-4's run B silently ran on run A's build —
confirmed only by file timestamp afterwards. One `make ed` + restart costs a minute; diagnosing a
stale build costs more.

## 1. The export, per model

For each model (any subset; §2 says which ones test what):

1. Open the COPY in SketchUp 2022, by hand. ⚠ Never batch — `Sketchup.open_file` does not switch
   documents on macOS, and `model.path` cannot tell you which model is frontmost
   (`SKETCHUP_RUNTIME.md` §8.1–8.2). One model at a time, close before the next.
2. *(Optional, for anything you'll want diagnosed later)* **Extensions ▸ DesignPH-PLUS POC ▸
   Diagnostics ▸ Save extraction JSON** — tick it. The extraction is what makes a bad output
   attributable to collector vs translator.
3. **Extensions ▸ DesignPH-PLUS POC ▸ Export HBJSON…** — when the save panel appears, save into the
   smoke folder under the suggested name.
4. Read the two surfaces and compare with §2's expected numbers.

**What a correct run looks like, in order:**

| Where | What |
|---|---|
| *(nothing during the walk)* | ⛔ **known limitation** — the dialog goes blank and no progress shows while the walk runs (4 s on Adelphi, 11 s on Bluff Reach). That is recorded, structural, and carried to v1 (`POC-4_results.md` §6.7). A blank dialog during the wait is *not* a failure — a blank dialog 60 s after is |
| Dialog banner | **amber `PASSED WITH OMISSIONS`** on every corpus model — green `PASSED` means *everything* translated and no real model achieves it (the omissions are genuine: TFA markers and library-only assemblies carry no honeybee construction) |
| Below the banner | the summary table — faces / apertures / thermal bridges, each `in / translated / reported` — then the TFA line, then named omissions |
| Message box | the **same** headline and counts (the two surfaces must agree — POC-4 §6.5), plus the output file paths |
| Folder | `<name>.hbjson` + `<name>.report.json` (+ `.extraction.json` if ticked) |

## 2. Expected numbers, per model

From the reconciled corpus captures (2026-08-21). **A mismatch is a finding, not a formality** —
these counts also match the offline baselines exactly, so a drift here is a real regression.

| Model copy | faces | apertures | bridges | TFA m² | walk (approx) | tests what |
|---|---|---|---|---|---|---|
| `adelphi-designph_COPY` | 82 | 46 | 0 | 368.476 | ~4 s | the primary; tier-2 assemblies; the PHPP-adjacent baseline |
| `2414_Bluff Reach_COPY` | 194 | 40 | **99** | 1491.862 | ~11 s | **thermal bridges** — the only model that exercises the edge path |
| `2523 Wellington_COPY` | 103 | 57 | 0 | 448.182 | ~2 s | two historical version stamps; tier-1 assemblies |
| `250703 - Linde Residence_COPY` | 74 | 47 | 0 | **0** *(correct — no group-1 faces)* | <1 s | **tier-1 multi-section framing** — the U-value regression model |
| `250708_COPY` | 92 | 49 | 0 | **0** *(correct)* | <1 s | all-`*Auto` keys; resolves **nothing** in-model (92 × tier 3) and is not broken |

All five verdicts: `PASSED WITH OMISSIONS`. Every `reported` column: **0** (reported *entries* exist
— assemblies without constructions — but no face, aperture, or bridge fails to translate).

**Minimum useful smoke set when short on time:** Adelphi + Bluff Reach. Between them: both key
generations, apertures at scale, thermal bridges, TFA, and the slowest walk.
⚠ **Never grade a change on Adelphi alone** — it is the simplest model in the corpus and it has
already masked three reconciler bugs (`POC-2_results.md` §0.2).

## 3. What "looks wrong" looks like

Read the HBJSON in a viewer (ph-navigator per §4, or Rhino/Grasshopper via honeybee) and scan for
these — each is a real failure mode this project has already had once:

| Symptom | Probable cause |
|---|---|
| Windows floating off their walls, or clustered near the origin | a transform bug — the parent-relative `transformation` did exactly this to all 46 Adelphi windows with **no error anywhere** (`CONSTRAINTS.md` §8.1) |
| Windows all the same size, or ~40 % smaller than the openings | the glazing was read instead of the rough opening |
| Faces in the wrong place / a mirrored wing | transform composition or winding — the canonicaliser deliberately never masks this |
| Thermal-bridge count 0 on Bluff Reach | an edge-walk regression — faces-only traversal loses all 99 **silently** |
| TFA 0 on Adelphi / Wellington / Bluff Reach | the horizontality or winding regression (POC-3 §9 defect 2) |
| A green `PASSED` on a real model | the banner is lying — it must read the three-state headline (`POC-4_results.md` §6.5) |
| Banner and message box disagree | the same class of bug, third occurrence — report it with a screenshot |

## 4. The ph-navigator check

Two POC exports live in **JM Test Project (BT 1299)** on www.ph-nav.com, uploaded through your
browser session 2026-08-21: `adelphi-designph_COPY` and `2414_Bluff Reach_COPY.cpython` (both
deletable from the file list whenever). ⚠ **Read `POC-5_results.md` §3.2 before grading Adelphi** —
its envelope does **not** render, by a known ph-navigator limitation (no-mass constructions are
skipped as "air boundaries"), so only the 40 TFA markers show. That is Finding 71, not a fresh bug.

1. Open www.ph-nav.com ▸ JM Test Project ▸ **Model** tab.
2. **Grade Bluff Reach** (the real render test): the massing reads as the building; **apertures sit
   on their host walls** (not floating — §3 row 1); 194 surfaces; clicking a face shows its
   `NNud_construction` with a plausible U-value; the FLOOR AREAS / SPACES lenses look sane.
3. **Grade Adelphi for what it can show**: the 40 marker plates sit in the right plan positions and
   stack at the right storey heights; Spaces shows 1 space at **368.5 m²** floor area.
4. Paste the verdict (a sentence is fine, screenshots welcome) into `POC-5_results.md` §5.

## 5. Where results go

Append to [`POC-5_results.md`](POC-5_results.md) §5: date, build stamp, which models, verdicts, and
anything from §3's table. A run with nothing to report is still a row — "all five green, counts
exact" is the evidence the next change is graded against.

If something surprising turns up: **stop and send it** — the message box text, the Ruby Console,
and the `.report.json`. Do not work around it mid-session; that rule has paid for itself twice.
