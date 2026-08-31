# Spike L-A — Ed runbook: the handshake sessions

```
DATE:    2026-08-31
STATUS:  ✅ RUN — all sessions completed same day (order: 0, 2, 1, 3, 4, O-5 CSV, 2.2.29 export).
         Verdicts and diffs: LIBRARY-A_results.md. This file stays as the protocol record.
TIME:    ~45-60 min total, five short SketchUp sessions (0-4), one PHPP look
```

Everything below runs on **staged copies** in `planning/spikes/library-import/_private/copies/`
(made by `prep_copies.py` from the headless spike's copies — copies of copies). The write script
refuses any model whose title lacks `LIBIMPORT`, so opening the wrong file fails closed.

**The one paste file:** `planning/spikes/library-import/write_library.rb`
Pasting it prints a **dry-run plan** and writes nothing. `DPHL.write!` commits (one undo step).
`DPHL.revise!` is the O-8 edit. Every write is model-level only.

**Rules for every session:**

- **Save As** into `_private/post/` — never Save over a staged copy; the pristine copies are the
  diff baselines.
- Note the **designPH version** actually running (2.2.29 stable vs 2.4.0 BETA) — O-3 makes every
  answer version-shaped.
- Screenshot anything designPH shows about our rows (lists, calculator, dropdowns) into
  `_private/post/screenshots/` — the U-/R-value calculator screenshot settled two questions last
  POC.
- If the console throws: stop, copy the full message into `_private/post/notes.md`, move on.

The values to look for, everywhere: **`ZZ-LIBIMPORT Wall`** (assembly, intended
**U = 0.1123 W/m²K** incl. films; after `revise!`: `ZZ-LIBIMPORT Wall R2`, **U = 0.1276**),
**`ZZ-LIBIMPORT Frame`** (U 1.1 / width 0.115 / psi-G 0.031 / psi-F 0.041),
**`ZZ-LIBIMPORT Glazing`** (g 0.52 / U 0.62).

---

## Session 0 — prep: produce the timing-(a) file (designPH DISABLED)

1. Window → Extension Manager → **disable designPH** (and designPH BETA if separate). Restart
   SketchUp. (This is what makes timing (a) clean: designPH's runtime never sees the write
   happen.)
2. Open `_private/copies/2414_BluffReach_LIBIMPORT-a.skp`.
3. Paste `write_library.rb` into the Ruby Console → read the dry-run (expect: fill `07ud`,
   create `layer_table_07ud`, fill frames `03ud`, glazing `02ud`) → run `DPHL.write!`.
4. **File → Save As** → `_private/post/2414_BluffReach_LIBIMPORT-a-written.skp`. Quit.
5. Re-enable designPH. *(Agent verifies the saved file offline before Session 1 —
   `dump_model_tables.py` — so a bad write never costs a designPH session.)*

## Session 1 — timing (a): designPH meets the data at model open

Open `_private/post/2414_BluffReach_LIBIMPORT-a-written.skp` with designPH active.

| # | Do | Answers | Record |
|---|---|---|---|
| 1.1 | Open designPH's assembly list | **O-2 listed? O-7a** | is `ZZ-LIBIMPORT Wall` there? screenshot |
| 1.2 | Open the window dialog / WinTool frame+glazing dropdowns | **O-4** | are Frame/Glazing listed? (a table row missing from the dropdown = the shadow-copy problem, not a failed write) |
| 1.3 | Assign `ZZ-LIBIMPORT Wall` to any exterior wall face; open the U-/R-value calculator on it | **O-2 computes?** | does it show the layers? **U = 0.112?** screenshot |
| 1.4 | Assign `ZZ-LIBIMPORT Frame` + `Glazing` to one window | **O-2/O-4** | accepted? |
| 1.5 | Paste `write_library.rb` again → `DPHL.revise!` → recheck the face: name, U-value, Areas list | **O-8** | assignment held? **U now 0.1276?** does the Areas list show the new name? |
| 1.6 | One trivial designPH edit (e.g. reassign any other face), then **Save As** `_private/post/…-a-post.skp` | **O-1/O-6** | — |
| 1.7 | Export PPP (to `_private/post/`), open in PHPP **by eye** | **O-2 end-to-end, O-8 downstream** | did the assembly/frame/glazing arrive, with the R2 name and values? |

## Session 2 — timing (b): SketchUp open, dialog never opened

1. Open `_private/copies/2414_BluffReach_LIBIMPORT-b.skp` (designPH **enabled** but do NOT open
   its dialog/toolbar yet).
2. Paste → `DPHL.write!`.
3. Now open the designPH dialog: is `ZZ-LIBIMPORT Wall` listed? (**O-7b**) Quick assign +
   calculator check.
4. Save As `_private/post/2414_BluffReach_LIBIMPORT-b-post.skp`.

## Session 3 — timing (c): the hot swap

1. Open `_private/copies/2414_BluffReach_LIBIMPORT-c.skp`; open the designPH dialog **first**;
   glance at the assembly list (no ZZ rows).
2. Paste → `DPHL.write!` with the dialog still open.
3. Does the open dialog show the new rows — immediately, after switching tabs, after closing and
   reopening the dialog (note which)? (**O-7c**)
4. Save As `_private/post/2414_BluffReach_LIBIMPORT-c-post.skp`.

## Session 4 — O-3: the old generation (Adelphi, 2.1.15)

1. Open `_private/copies/adelphi_LIBIMPORT-g.skp`.
2. Paste → `DPHL.write!` (native: **inserts** `01ud` into `assemblies_ud` — this model has no
   `assemblies_calc`, no frames/glazing tables at all).
3. Assembly list: is the inserted row shown? Which id does designPH display it under?
4. Then `DPHL.write!(:both, :create)` — plants an `assemblies_calc`+`layer_table` **and** creates
   `frames_ud`/`glazing_ud` from scratch. Reopen the lists: **which generation's row does this
   designPH read?** Do the created window tables show up? (**O-3**, table-creation probe)
5. Save As `_private/post/adelphi_LIBIMPORT-g-post.skp`.

## Optional, time allowing — O-5: the installed-CSV route

1. Quit SketchUp. Copy
   `~/Library/Application Support/SketchUp 2022/SketchUp/Plugins/designPH/data/phpp_assemblies_ud.csv`
   to `phpp_assemblies_ud.csv.BAK`, then add one row to the original following its own header
   convention (id from an unused slot, name `ZZ-LIBIMPORT CSV Wall`).
2. Restart SketchUp, open any staged copy, open designPH: is the CSV row listed? (**O-5**)
3. Restore the `.BAK` afterwards either way.

---

## After the sessions — agent closes the loop (no Ed needed)

For every file in `_private/post/`: `dump_model_tables.py` dump + `--diff` against its
`_private/baseline/` pre-state (O-6: every field designPH rewrote, frames/glazing included);
headless `collector.py` capture + diff (O-9: which *entity-level* keys moved when only
model-level tables were edited — `entity_id` excluded as session-scoped). Both table
generations and the version stamps get read the same way. Results land in
`LIBRARY-A_results.md` with the O-1…O-9 table filled in.
