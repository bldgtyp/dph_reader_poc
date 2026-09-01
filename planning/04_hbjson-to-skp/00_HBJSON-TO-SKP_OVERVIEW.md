# POC #4 — HBJSON → SketchUp: generating a FRESH designPH-ready model

```
DATE:    2026-08-31
STATUS:  ▶ SCOPED, NOT STARTED (Ed, 2026-08-31, product-shape discussion) — deliberately
         deferred behind POC #3's v-0 (Library Sync). "Not a killer day-1 feature" (Ed).
AUTHOR:  Ed May / Claude
ISSUE:   none — local-only research workflow (planning/.instructions.md)
```

## 1. The question

> **Can we generate a NEW SketchUp model from scratch out of an HBJSON — envelope geometry,
> apertures, shading, and optionally designPH classifications and libraries — such that designPH
> adopts it as a legitimate working model: classifies (or reads our classifications), assigns,
> computes, and exports to PHPP?**

**Fresh scene only — decided at scoping (Ed, 2026-08-31).** The edit-in-place variant (writing
geometry or classifications into an *existing* designPH model) is out of scope permanently, not
just deferred: it collides with designPH's own auto-classification, crosses hard rule 2's
face-level line in a way POC #3's model-level amendment deliberately did not, and risks exactly
the silent-contradiction failures the corpus record warns about. A fresh model sidesteps all of
it — the model is *ours*, with designPH invited in.

## 2. Why — and why deferred

- **It closes the interop loop**: designPH → HBJSON (POCs #1/#2), PHN library → designPH
  (POC #3), and now HBJSON → designPH — so a Rhino/honeybee-ph model, or a PHN-built model,
  can land in designPH for the PHI-required shading workflow without re-drawing.
- **Deferred** because the v-0 product is POC #3's Library Sync; this is a future capability
  spike, worked separately (Ed, 2026-08-31).

## 3. What the record already constrains

Every constraint below is measured, in `00_Context/` — this POC starts from them rather than
rediscovering them:

1. **Windows are the existential question.** designPH windows are designPH's *own* gluing
   component definitions, with formula sets and DC attributes (`DESIGNPH_DATA_MODEL.md` §9).
   Whether Ruby can instantiate designPH's shipped definitions programmatically — placed by
   the rough-opening/world-transform conventions the read side measured, glued so `glued_to`
   resolves — is the make-or-break unknown. If a scripted window is not "a designPH window",
   the POC's value drops to walls-and-roofs.
2. **The read side's conventions must be emitted in reverse**: aperture rectangle = rough
   opening; `glued_to` is the only host bond (a glued opening leaves no inner loop and makes
   `face.area` net); DC transforms are parent-relative while everything else is world. All
   already quantified — `CONSTRAINTS.md` §8.1.
3. **Which key generation does a fresh writer emit?** The read rule is a coalesce (`*ID` or
   `*Auto`, hard rule 6); a *writer* must pick one. Presumably `*ID` on a modern designPH —
   stated here as a hypothesis to verify, never assume (the version-rename rule was wrong once
   already).
4. **Libraries ride POC #3.** `CONTRACT_phn-library.md` v1 + `write_library_b.rb` already write
   assemblies/frames/glazings into a model that never carried the tables (`lb_adelphi_create`
   rehearsed exactly this). A fresh model reuses that path verbatim.
5. **The round-trip check is free.** The POC #1/#2 readers are the natural gate instrument:
   fresh `.skp` → contract-v2 capture → HBJSON, compared canonically against the input
   (normalise by name, never by shape — the canonicaliser trap is recorded).
6. **Representability is bounded**: HBJSON rooms/spaces, adjacency, and mechanical content have
   no designPH home. The loss report (hard rule 4 — name everything not carried over) is part
   of the deliverable from day one.

## 4. Open questions

| # | Question |
|---|---|
| H-1 | **The tier ladder**: is geometry-only + letting designPH auto-classify already useful, or does real value require writing classifications (area groups, assembly refs) too? |
| H-2 | **Windows** (existential): can Ruby instantiate designPH's own window components — correct definition, DC attributes, glue — such that designPH lists, edits, and exports them as its own? |
| H-3 | **Key generation**: does a fresh write emit `*ID`, and does modern designPH read a model it did not create without quirks (version stamp expectations, `tracker_data` absence, dialog init)? |
| H-4 | **Round-trip fidelity**: fresh `.skp` read back through the POC reader reproduces the input HBJSON to a stated tolerance — what is lost, and is every loss named? |
| H-5 | **Scale and orientation conventions**: units, axes, north — what must the emitted model pin down so designPH's shading/area math lands right? |

## 5. The existential probe (H-0) — the only thing pre-scoped

Cheapest possible test, before any plan exists: script a minimal fresh model from Ruby (a few
classified faces, one window DC), open it with designPH active, and see whether designPH lists,
assigns, computes, and exports it. **H-2 is graded first** — if designPH refuses scripted
windows, the POC re-scopes around walls-only or stops. PASS/FAIL of this probe decides whether
a full spike plan (H-1…H-5) gets written at all.

## 6. Rules in force

- Hard rules 3 (corpus untouched — fixtures are synthetic or fresh), 4 (report, don't guess —
  the loss report is a deliverable), and the version gate (record the designPH version graded
  against; refuse to claim generality from one).
- **Hard rule 2 posture**: a model we author is ours, but writing `DesignPH_dict` into it is
  still writing data designPH will consume — the same interop posture as POC #3. LI-1's
  licence judgment extends here and gets its own recorded line before anything ships.
- Sequencing (planning/.index.md rule): does not start until POC #3's L-C gate is recorded.

## 7. What this POC is not

Not surgery on existing designPH models (§1 — permanent), not a modeling UI, not the
full-authoring vision (that trajectory is recorded in POC #3's L-C section), not day-1, and
not started.
