# POC-5 — Corpus Validation and Smoke Test (the POC verdict)

> ### ✅ **DONE — gate closed PASS, 2026-08-21, and the POC closed with it.** Results: [`RESULTS/POC-5_results.md`](RESULTS/POC-5_results.md).
>
> This file is the *plan*, kept as written. What moved in execution:
>
> - **§2's feasibility warning was right**: ph-navigator's asset upload is browser-session-only
>   (session cookie, no bearer path), so the upload ran through Ed's own browser session — and it
>   surfaced **Finding 71**: the viewer skips any face whose construction uses a no-mass material.
> - **§3's "one batched SketchUp session" was not needed**: Ed closed the gate on the nine sessions
>   already graded in POC-1/-2/-4; the runbook stands as the regression instrument for future builds.
> - **§4.3's expected member "TFA for non-horizontal floors" was refuted** — 0.0 m² lost corpus-wide.

**Builds:** no new product code — the evidence that the POC works, and the list of what v1 must do
differently.
**Depends on:** POC-4 gated.
**Box:** ~1 agent session + one Ed SketchUp session (batched) + Ed's ph-navigator check.

> ⚠ **§1's sweep already happened, in POC-2.** All five models are captured, reconciled and
> translated (`RESULTS/POC-2_results.md` §0.1). What is left of this phase is the part POC-2 could
> not do: **ph-navigator, Ed's smoke test, and the "what v1 must do differently" list** — which is
> the POC's actual product and already has a great deal to say. Re-running the sweep is only worth
> it if POC-4 changes the output.
>
> ⚠ **And "one batched SketchUp session" is not available.** `Sketchup.open_file` does not switch
> documents on macOS, so each model is opened by hand; and ⚠ `Sketchup::Model#path` cannot identify
> which one is open, so the operator names it (`SKETCHUP_RUNTIME.md` §8.1–8.2). Budget it as five
> manual opens, not a loop.

---

## 1. The corpus sweep ✅ *(done in POC-2, 2026-08-21)*

**[Ed] One batched SketchUp session**, runbook staged by the agent: export each model COPY with the
`Diagnostics ▸ Save extraction JSON` toggle on (POC-1 §3 / POC-4 §1.5), all outputs into
`poc/_private/` (client data — gitignored).

| Model | Why it is in the sweep |
|---|---|
| `adelphi-designph.skp` COPY | Primary; every downstream check keys off it |
| `2414_Bluff Reach.skp` COPY | **Mandatory** — the thermal-bridge model (99 edges) |
| `250708.skp` COPY (Linde) | All-`*Auto` assemblies — the coalesce regression, live |
| `250703 - Linde Residence.skp` COPY | **Mandatory** — the only model with `layer_table_*` (25): the tier-1 path, live |
| `2523 Wellington.skp` COPY | Two version stamps, both key generations, never purged |
| ~~`2536 Holmes.skp` or `2605 MacDonough.skp` COPY~~ | A model with `descName` overrides at scale. ⚠ **Not needed — Bluff Reach already covers it**: 70 of its faces carry both `descName` and `descNameAuto`, which is how that pair was established as an *override*, not a contradiction (POC-2 finding 69) |

✅ **What the sweep actually produced**, all reconciled PASS: 545/545 classified faces, 239/239
windows, 99/99 thermal bridges, TFA on the three models that carry group-1 faces, and all four
assembly tiers exercised — including `250708`, which resolves **nothing** in-model and is not broken.
Per-model numbers: `RESULTS/POC-2_results.md` §0.1.

Per model, automated (`poc/tools/check_extraction.py` + a new `check_export.py`):

1. Extraction counts reconcile with the Phase 0/1 baselines (POC-2's harness, re-run live).
2. HBJSON validates — **zero errors touching core geometry or PH** (existing validator scope).
3. **Report completeness**: every extracted record is in the HBJSON or the report. No exceptions.
4. U-value spot-checks (Adelphi, per POC-3 §5 tolerance).
5. Verdicts are `PASSED`/`PASSED WITH OMISSIONS` — a `FAILED` anywhere fails the sweep.

## 2. The downstream consumer — ph-navigator

PRD §11 criterion 2, scoped to the POC: the Adelphi HBJSON **loads and renders** in ph-navigator.

- ⚠ **Verify upload feasibility before the sweep session**: the `phn` tooling is project-scoped and
  token-gated, so creating a scratch project + uploading may itself be an Ed action. The agent
  checks this first; if agent-side upload is not possible, the upload folds into Ed's batched
  session rather than becoming an unplanned extra round-trip.
- Upload to a scratch project, never a client project.
- Grade: geometry renders and face counts look right; apertures appear on their hosts; no loader
  error. Note how ph-navigator treats the `global_construction_set` (feeds decision D-1) and the
  `user_data` marker.
- **[Ed]** grades the render.

## 3. Ed's smoke-test runbook

A standing document (`RESULTS/POC-5_ed-smoke-runbook.md`) so the smoke test is repeatable, not a
one-off: install path, the sweep's six model copies, what to click, what each verdict means, what "looks
wrong" examples to watch for (apertures floating off walls, faces in wrong places = transform bugs,
missing thermal-bridge counts), and where to paste results.

## 4. The retro — the POC's actual product

`RESULTS/POC-5_results.md` closes the POC with:

1. **The verdict** against the [overview §7 definition of done](00_POC_OVERVIEW.md), item by item.
2. **Measured tables:** per-model translation coverage; TFA covered vs lost (POC-3 §7's number);
   assembly tier distribution (how often tier 3 would have been needed); reported-entry taxonomy.
3. **"What v1 must do differently"** — every place the POC's honest-but-blunt strategy (report
   instead of solve) hurt on real models, ranked. Expected members, to be confirmed or refuted:
   TFA derivation for non-horizontal floors; tier-3 assembly resolution; the shading-tag UI; frame/
   glazing library resolution; the unclassified-face workflow.
4. **`00_Context/` updates** for anything durable learned (docs-pass), and PRD deltas where a POC
   finding contradicts it.
5. **The unwind check on the two standing assumptions** (overview §2): did anything built here make
   the designPH-3.0 or PHI assumption more expensive to unwind than planned? (The answer should be
   "no — the collector is still the blast radius"; if not, say so loudly.)

## 5. Gate

**PASS:** overview §7 items 1–6 all hold.
**PASS WITH CHANGES:** holds except for named, understood exceptions (e.g. one secondary model
refuses on a version-gate technicality) — recorded, not waved through.
**FAIL:** silent loss found anywhere in the sweep — that is the reputation-killing failure mode the
whole plan exists to prevent, and it stops the POC until understood.

After the gate: hand the retro to Ed. v1 planning (and the un-tabling of Phases 4/5) starts from it.
