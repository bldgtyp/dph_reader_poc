# Spike L-B — Ed runbook: real PHN libraries into designPH

```
DATE:    2026-08-31
STATUS:  ✅ RUN — all three sessions completed the same evening. Verdicts and diffs:
         LIBRARY-B_results.md. This file stays as the protocol record.
GATE:    designPH's own calculator reproduces the intended U (±0.0005) AND the Error % on the
         framed assemblies, on STABLE 2.2.29; the PPP export carries them (needle + by eye)
         — ⭐ PASSED on every leg
```

Everything runs on **staged copies** in `planning/spikes/library-import/_private/copies/`
(`prep_copies_b.py`). The write script refuses any model whose title lacks `LIBIMPORT`.

**The one paste file:** `planning/spikes/library-import/write_library_b.rb`
Pasting prints a **dry-run plan** and writes nothing. `DPHLB.write!` commits (one undo step).
It reads the payload from `_private/payload/lb_payload.json` — real **Linde Home** PHN data:
**8 assemblies (6 framed/multi-section), 9 frame types, 2 glazings**, all `ZZ `-prefixed.

**⚠ Version: run everything on STABLE 2.2.29 (Beta-GUI disabled)** — the gate names stable, and
2.4.0 BETA's analysis/export is broken on SketchUp 2022 (L-A §14.6). Note the version banner in
`notes.md` anyway.

**Rules for every session** (same as L-A): Save As into `_private/post/`, never over a staged
copy; screenshot every calculator view of a ZZ row into `_private/post/screenshots/`; console
errors verbatim into `_private/post/notes.md`, then move on.

**The grading sheet is `_private/payload/lb_expectations.md`** — print it or keep it beside
SketchUp. Per assembly it names the intended **U** and the **Error %** designPH must print
beside it. The two headline framed cases:

| assembly | intended U | Error % | why it matters |
|---|---|---|---|
| `ZZ F-GR (Garage)` | **0.0730** | 2.59 % | two distinct framing fractions → all three PHPP paths in use (surf2 9.375 / surf3 12.5) |
| `ZZ R-VT (Vaulted)` | **0.0622** | 3.96 % | two fractions, 7 layers |
| `ZZ W-CS (Crawlspace)` | **0.2607** | 0.00 % | unframed control |

---

## Session 1 — Bluff Reach: the gate session (write → grade → assign → export)

Open `_private/copies/2414_BluffReach_LIBIMPORT-lb.skp`, designPH 2.2.29 active.

| # | Do | Answers | Record |
|---|---|---|---|
| 1.1 | Paste `write_library_b.rb` → read the dry-run (expect: assemblies `07ud…14ud`, layer tables to match, frames `03ud,04ud,06ud…12ud`, glazings `02ud,03ud`) → `DPHLB.write!` | — | console output |
| 1.2 | Extensions → designPH → **Launch designPH or re-initialise model** (the L-A refresh gesture) | — | — |
| 1.3 | Assemblies (user-calculated) list: all **8 ZZ rows** present, with U values shown in the list? | **B-1 listed** | screenshot |
| 1.4 | Open the U-/R-value calculator on EACH ZZ assembly; grade **U and Error %** against the expectations sheet | ⭐ **B-1, the gate** | screenshot each; note any mismatch to the 4th decimal |
| 1.5 | While the calculator is open on `ZZ F-GR` or `ZZ R-VT`: do the surface percentages read **9.375 / 12.5** (F-GR) — and which end of the layer list does the dialog label as outside? (F-GR should start GWB if inside-first, OSB if outside-first) | **B-4** | screenshot |
| 1.6 | Window dialog: are the 9 ZZ frames + 2 ZZ glazings in the dropdowns? | §14.4 regen | quick look |
| 1.7 | Assign `ZZ W-EC (Ext. Conditioned)` to an exterior wall face; assign `ZZ smartwin compact Tilt-Turn` + `ZZ smartwin \| 6SKN…` to one window (click Apply) | **B-1 assign, B-3 setup** | which window (so the diff can find it) |
| 1.8 | One trivial designPH edit, then **Save As** `_private/post/2414_BluffReach_LIBIMPORT-lb-post.skp` | O-6 recheck | — |
| 1.9 | **Export PPP** to `_private/post/` (2.2.29) | **gate leg 2** | — |
| 1.10 | Open the PPP in PHPP **by eye**: U-values worksheet — are the ZZ assemblies there with the §-computed U? Windows worksheet — which **glazing** does the assigned window carry? | **B-1 end-to-end, B-3** | note the glazing name PHPP shows |

## Session 2 — Linde: second model, second base64 style

Open `_private/copies/250703_Linde_LIBIMPORT-lb.skp`, designPH 2.2.29.

1. Paste → `DPHLB.write!` (expect assemblies `08ud,09ud,10ud,29ud…33ud`; frames `06ud…14ud`;
   glazings `01ud,02ud`).
2. Re-initialise designPH; spot-check **three** assemblies in the calculator against the sheet —
   include `ZZ F-GR` (the 3-path case). (**B-1 on n=2**)
3. Save As `_private/post/250703_Linde_LIBIMPORT-lb-post.skp`. *(B-5 — wrapped style survival —
   is graded offline from this file; nothing to do in-session.)*

## Session 3 — the extra-column probe (update key)

Open `_private/copies/2414_BluffReach_LIBIMPORT-xc.skp`, designPH 2.2.29.

1. Paste → **`DPHLB.write!(:probe)`** — same payload PLUS a foreign `phn_id` column appended to
   `assemblies_calc` (token + one cell per row).
2. Re-initialise designPH: does the assemblies list still show all 8 ZZ rows, and does the
   calculator still compute one of them correctly? (**B-2 read-tolerance** — a designPH that
   chokes on an extra column answers the update-key question negatively right here)
3. One trivial designPH edit, Save As `_private/post/2414_BluffReach_LIBIMPORT-xc-post.skp`.
   *(B-2's second half — does the column survive the save — is graded offline.)*

---

## After the sessions — agent closes the loop (no Ed needed)

For every `-post.skp`: `dump_model_tables.py --diff` against its `_private/baseline/` pre-state
(byte-level: what designPH rewrote; **B-5** wrapped-style survival; **B-2** `phn_id` column
survival); `collector.py` capture + diff (entity level: the assigned face/window on `-lb-post`,
nothing else expected to move; `entity_id` excluded as process-scoped). Needle-read the exported
`.ppp` for every ZZ name (hard rule 1 as amended — our own export, verbatim needles only).
Verdicts land in `LIBRARY-B_results.md`; the contract's §9 open questions get answered rows;
on a full pass the contract moves DRAFT → FROZEN v1.
