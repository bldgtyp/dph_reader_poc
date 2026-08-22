# Phase 1 — SketchUp runbook **[Ed]**

Three experiments. Together they close Phase 1's gate.
Findings so far: [`PHASE-1_results.md`](PHASE-1_results.md).

**Everything here is read-only.** No script writes to `DesignPH_dict`. Run them on the copies below
anyway — hard rule 3, and run 3 deliberately edits a model through the designPH UI.

## Setup — already done

| | |
|---|---|
| Working copies | `~/Desktop/dph_phase1_copies/` — Adelphi, Bluff Reach, MacDonough |
| Output lands in | `planning/RESULTS/phase1_live/` — one `.txt` per run, written automatically |

Open the model, then **Window → Ruby Console**, and paste **one line**:

```
load '/Users/em/Desktop/dph_plus_testing/planning/spikes/phase1/live_1-2_window_hosting.rb'
```

`load` rather than pasting the whole script — the console mangles long multi-line pastes. Each script
prints to the console *and* writes its output to a file, so nothing needs copying back by hand. Just
say when a run is done and I will read the file.

---

## Run 1 — §1.2 window hosting ⚠ **the gate**

**This is the one that matters.** It is the only remaining item that can turn Phase 1 into a FAIL,
so do it first — if it fails, runs 2 and 3 are not worth your time yet.

1. Open `~/Desktop/dph_phase1_copies/adelphi-designph_COPY.skp`
2. `load '/Users/em/Desktop/dph_plus_testing/planning/spikes/phase1/live_1-2_window_hosting.rb'`

**What it asks:** do designPH's window components tell us which face they belong to, or do we have to
work it out from geometry?

| Result | What it means |
|---|---|
| `glued_to non-nil` high | **Good.** Host lookup is solved; geometric projection is only a fallback |
| `glued_to` mostly nil | Nearest-coplanar-face becomes the primary path — more work, more failure modes |
| `cuts_opening? true` **and** hosts have inner loops | PRD §8.2 needs revising: the Honeybee `Face3D` has a hole and the `Aperture` must fill it |
| `cuts_opening? false` | Windows sit on unbroken faces, as the PRD assumes |
| **`windows found: 0`** | Tell me before going further — it means the component-name match is wrong, not that the model has no windows |

Adelphi should have roughly 44 windows (the reference HBJSON has 44 apertures). A number in that
neighbourhood means the finder is working.

---

## Run 2 — §1.5 the shading filter

**Two models, and the second is the point.** `faceTypeAuto` cleanly splits Adelphi's untagged faces
into exterior and interior — but it is *absent entirely* from Bluff Reach, so a filter resting on it
alone would export nothing there. This run gathers the geometric second leg.

1. Open `adelphi-designph_COPY.skp` →
   `load '/Users/em/Desktop/dph_plus_testing/planning/spikes/phase1/live_1-5_shading_filter.rb'`
2. Open `2414_Bluff-Reach_COPY.skp` → same line again

**What it asks:** does *inside vs outside the tagged envelope's bounding box* separate real shading
context from interior clutter, on its own — and does it still work where `faceTypeAuto` is missing?

Expected, if the two signals agree: `'xo'` faces mostly `inside=false`, `'i'` faces mostly
`inside=true`. If they disagree, the filter needs a third signal and I would rather know now.

It also dumps the ten `'xi'` faces with their area, normal and tag. **`'xi'` is the last undecoded
value in the whole face-level schema** — 25 faces corpus-wide, always on an *untagged* face, never
once beside a classified one. If the ids it prints let you find them in the model, a one-line
"they're all X" from you closes it.

---

## Run 3 — §1.1 confirmation, and the half only you can do

The read side is already settled from the offline corpus: `*ID` and `*Auto` are never both populated
on one face, so the rule is `face[*ID] or face[*Auto]`. Two things that still need a live model:

**3a — confirm against live entities.** The offline reader sees `model.dat`, which keeps dictionaries
belonging to *deleted* entities. This walks live faces only.

1. Open `~/Desktop/dph_phase1_copies/2414_Bluff-Reach_COPY.skp` — the model that broke the old rule
2. `load '/Users/em/Desktop/dph_plus_testing/planning/spikes/phase1/live_1-1_generation_check.rb'`

**Expected: every `both=` count is 0.** A non-zero `both` means the precedence question is real after
all and §1.1 is not settled — it prints the conflicting value pairs so we would see immediately what
kind of conflict it is.

**3b — the write side.** Nothing offline can see which key designPH writes when a user classifies a
face. This is the only step that needs the designPH UI:

1. Select one **classified** envelope face. In the console: `BTPhase1.dump_selected`
2. Change **only** that face's area group in the designPH dialog
3. `BTPhase1.dump_selected` again
4. Repeat on an **unclassified** face — assign it an area group for the first time

Paste those four dumps back (they are short — the script prints them but does not file them, since
they are interleaved with your clicking).

**What it asks:** does designPH update `areaGroupID` in place, or write a new `areaGroupAuto`, or
migrate one to the other? Only the third would change the read rule. This is also the step that tells
us whether v2 authoring can ever coexist with designPH's own writes.

> Run 3b on the **MacDonough copy** instead if you would rather not re-classify faces on a Bluff
> Reach model you may still recognise — it is a small model (34 classified faces) and the answer is
> the same. Either way it is a copy, so nothing is at risk.

---

## If something goes wrong

- **A script errors out.** Paste the error; the line number is enough. Do not retry more than twice.
- **`windows found: 0`, or `live faces` looks far too low.** Stop and tell me — it means the
  traversal is missing nested geometry, and a wrong answer here is worse than none.
- **Anything asks you to save.** Don't. Nothing here needs a save, and a save on a copy is harmless
  but a save on a corpus file is not recoverable.
