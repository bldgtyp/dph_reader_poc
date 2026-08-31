# Spike L-A — results

```
DATE:    2026-08-31 (agent prep + all Ed sessions, one evening)
STATUS:  ✅ COMPLETE
GATE:    ⭐ PASS — designPH accepts foreign model-level library writes, end to end (§3)
```

**The one-paragraph version:** an assembly (with layered build-up), a frame and a glazing written
into a model's `DesignPH_dict` from outside — via designPH's own serialisation, into its own slot
conventions — are **listed by designPH's UI, assignable, computed exactly (U 0.112, Error 0.00),
survive its save byte-stable, and reach the PHPP export with names, ids and revised values
intact**, on both designPH 2.4.0 BETA and stable 2.2.29. designPH's save rewrites exactly one
model-level field (`designPH_version`); its dropdown option lists regenerate from the tables; no
entity-level dictionary needs co-updating. The dialog is a stale *view* (refresh gesture:
"Launch designPH or re-initialise model") but never a stale *writer*. A clean, strong PASS.

## 1. What is already established (agent-side, 2026-08-31)

### 1.1 The write path exists and round-trips designPH's own serialisation — rehearsed, not live

`planning/spikes/library-import/write_library.rb` (route A-1) writes one assembly + layer table,
one frame, one glazing at model level, native serialiser (`Marshal.dump` + base64), dry-run
first, one undoable operation, `LIBIMPORT`-title guard, 3.x version gate. The **offline
rehearsal** (`rehearse.py` + a stubbed `Sketchup`) ran the whole write path against the real
tables of three corpus models and both table generations — **5/5 scenarios clean**:

| scenario | exercised |
|---|---|
| `bluffreach_native` | fill `assemblies_calc 07ud`, create `layer_table_07ud` (cloned schema), fill `frames_ud 03ud`, `glazing_ud 02ud` |
| `adelphi_native` | **insert** `assemblies_ud 01ud` (old generation — no free slots exist, rows are only `83ud`–`99ud`) |
| `adelphi_both_create` | O-3 double-write: both generations + `frames_ud`/`glazing_ud` **created** with designPH's 99-row pre-allocation |
| `linde_native` | fill on the second `assemblies_calc` model; wrapped-base64 style preserved |
| `bluffreach_revise` | O-8's `DPHL.revise!`: rename + lambda retune, intended U 0.1123 → 0.1276 |

Verified per scenario: metadata rows untouched, **every non-marker data row byte-identical**,
base64 style preserved, marker values exact, provenance note in `DesignPHPlus_dict` only.
⚠ A rehearsal is not a capture: this proves our serialisation, nothing about designPH's behaviour.

### 1.2 ⭐ designPH mixes TWO base64 encodings — within one model

**Observed live** (SDK read, not the offline regex): Linde 2.2.29 stores `frames_ud` and
`glazing_ud` **newline-wrapped** (`Base64.encode64`) while its `assemblies_calc` and
`layer_table_*` are **strict**; Bluff Reach 2.2.24 and Adelphi 2.1.15 are strict throughout.
So designPH's reader must accept both (`decode64` does), and different designPH code paths use
different encoders. The writer matches the style each key already carries. *(Superseded en
route: the write script's first draft claimed "every observed blob is newline-free".)*

### 1.3 ⭐ Layer-table schemas are mixed WITHIN one model, not just across models

Linde carries 8-column (`…thickness`) and 12-column (`…R1,R2,R3,R_tot`) `layer_table_*` side by
side (offline decode; e.g. `01ud` 8-col, `02ud`/`11ud`/`12ud`/`13ud` 12-col). The doc's "the
schema is not fixed across models" (§7's Linde row) understates it — a writer must read the
**donor table's own** `:TOKENS`, and a per-model schema assumption is wrong even per-model.

### 1.4 The tooling gaps named in the plan review are closed

- `dump_model_tables.py` — SDK **live-state** dump of every model-level key (frames/glazing
  included, which contract-v2 captures deliberately omit) + `--diff` naming changed rows and
  columns; self-tested (identical copies → 0 diffs; Bluff Reach vs Adelphi → 50).
- The offline regex route confirmed **untrustworthy post-write**: Linde's `model.dat` carries a
  truncated historical `frames_ud` blob first; the rehearsal's extractor now decode-validates
  every candidate. Live reads (SketchUp or SDK) are the authoritative before/after.

### 1.5 Baselines staged

`_private/copies/` — four LIBIMPORT copies (3× Bluff Reach timings, 1× Adelphi generation test),
manifest-tracked. `_private/baseline/` — pre-state `.tables.json` + contract-v2 `.capture.json`
for each; capture counts match the known corpus numbers exactly (194/99/40 · 82/0/46).

*(§1.2 and §1.3 are folded into `00_Context/DESIGNPH_DATA_MODEL.md` §7. ✅ The `phi-rules`
corpus sync is DONE — commit `bdd9f11` in `bldgtyp/phi-rules` amends D01/D02/D05/D06/D07/D09
with the write-side facts and the licence-line amendment; the skill's routing and licence note
updated alongside.)*

## 2. The Ed sessions — IN PROGRESS (2026-08-31 evening)

### 2.1 ✅ Timing (b) — Bluff Reach copy, designPH 2.4.0 BETA over 2.2.29 base

Ed ran Session 2 first: opened `-b.skp` with designPH enabled but its dialog unopened, ran
`DPHL.write!` (clean: WROTE 4 keys, VERIFY exact), *then* opened the dialog. Screenshots + logs
in `_private/post/`.

- ⭐ **O-2 (list + compute): PASS.** `ZZ-LIBIMPORT Wall` appears in the Assemblies list as
  `07ud`, thickness 32.750 cm, and the U-/R-value calculator shows all three layers, the films
  (0.13/0.04), **U = 0.112 W/m²K, R 8.91, Error % 0.00 — the intended value exactly.**
- ⭐ **O-7b: PASS** — a write before the dialog's first open this session is simply read.
- ⭐ **O-6 (save rewrite), model level: designPH's save changed ONE field beyond our four writes**
  — `designPH_version: "2.2.24" → "2.4.0 BETA"`. Our rows round-tripped decoded-identical; no
  purge, no normalisation, no other table touched.
- ⭐ **O-4 ANSWERED: the DC dropdown option lists REGENERATE from the tables.** The capture diff
  shows every window's `_frametype_options`/`_glazingtype_options` now contains
  `ZZ-LIBIMPORT Frame=03ud` / `ZZ-LIBIMPORT Glazing=02ud` — designPH rebuilt the shadow copy
  itself. **A writer does not need to touch the option lists.**
- **O-9, first data point: no face or edge dictionary changed.** The only entity-level movement
  was ~1-ULP float noise (1e-15…1e-31) in some window *transformations* — designPH's DC refresh
  re-serialising near-zero terms, numerically irrelevant.
- Note: the dialog displays layer thickness in **m** (rounded, so 12.5 mm shows as "0.0") while
  the table stores mm — display quirk, the computation is right (total 32.750 cm shown).
- Version note: console shows base 2.2.29 loaded + Beta-GUI; the dialog banner says
  **2.4.0 BETA** — so these answers are for 2.4.0 BETA running over the 2.2.29 base install.
  The `-b` session did **not** assign the assembly to a face (calculator opened from the list);
  assignment is exercised in the timing-(a) session.

### 2.2 ✅ Timing (a) — the pre-written file, plus assignment, revise, and the clobber test

Session on `-a-written.skp` (written and verified in the designPH-disabled prep session), designPH
2.4.0 BETA. Screenshots + `-a-post-console.txt` in `_private/post/`.

- ⭐ **O-7a PASS** — the row is simply there at model open, and the assign-assembly dropdown
  itself lists `07ud [U=0.112 W/m²K]`: designPH computed the U from our layer table at load.
- ⭐ **O-2 assignment PASS** — assembly assigned to a face (`faces[117].assembly_ref 03ud→07ud`
  in the capture diff); frame assigned to a window, and designPH propagated our 0.115 m width
  into the DC as **4.5276 inches** (§8.5's DC-inches rule holding exactly) and `o_reveal` as
  11.5 (cm).
- ⭐ **O-1/O-6 ANSWERED — NO RUNTIME CLOBBER, on the strongest test we could stage.**
  `DPHL.revise!` ran mid-session with the dialog open; the open calculator kept displaying the
  **stale** pre-revise values (name without R2, λ 0.035, U 0.112) — yet the saved `-a-post.skp`
  differs from the pre-session state by exactly **three** fields: the version stamp
  (`2.2.24 → 2.4.0 BETA`), and our two revise fields (`desc → "ZZ-LIBIMPORT Wall R2"`,
  `lambda1 0.035 → 0.04`). designPH's save does **not** write the library tables back from its
  runtime copy. The dialog is a stale *view*, not a stale *writer*.
- ⚠ **The `glazingtype`/`glazingtypeid` DC pair can split.** After selecting our glazing in the
  window UI, the saved DC carries `glazingtype = 02ud` but `glazingtypeid = 01ud` (frame pair
  updated consistently, `03ud`/`03ud`). Either Apply wasn't clicked for the glazing leg or the
  id syncs only on analysis (which crashes here, next bullet). **Which of the pair the PPP
  export consumes is now an explicit L-B question.**
- ⚠ **designPH 2.4.0 BETA's "Run analysis" crashes on SketchUp 2022, and it is not our doing:**
  `NoMethodError: undefined method 'set_clipboard_data' for UI:Module` — that API exists only in
  SketchUp ≥2023. (Plus repeating `DesignPH::UI::HighlightOverlay` NameErrors on selection
  events — a second beta bug.) Consequence: the analysis-dependent legs (and possibly the PPP
  export) can't be graded on this machine's 2.4.0 BETA + SU2022 combination — a **tooling
  environment limit, not an O-2 failure.** PPP-export leg still to attempt.

### 2.3 ✅ Timing (c) — the hot swap, and the refresh gesture that resolves it

Session on `-c.skp`: dialog opened first (no ZZ rows anywhere), then `DPHL.write!` with it open.

- ⭐ **O-7c ANSWERED: a live write is NOT visible to the open dialog** — not immediately, not on
  tab switches, not on closing and re-showing the dialog (`Show designPH main dialog`). But
  **Extensions → designPH → "Launch designPH or re-initialise model" re-reads the tables**, after
  which `07ud ZZ-LIBIMPORT Wall` appears in the Assemblies list (32.750 cm, U 0.112, R 8.91) and
  the calculator opens on it correctly.
- **The full timing model, all three timings measured:** designPH reads the model tables **at
  launch / re-initialise / model open**, holds a runtime copy for display, and does **not** write
  that copy back over foreign edits on save (§2.2). So an importer may write at any moment;
  the user-facing rule is only *"re-initialise designPH (or reopen the model) after import"*.

### 2.4 ✅ The Adelphi session — O-3 answered by reframing it

Session on `adelphi_LIBIMPORT-g.skp` (designPH 2.1.15-era model, opened under 2.4.0 BETA; at
startup designPH **migrated all 46 windows** — "old format (earlier than v2.2)" alert,
`designPH_Window_Simple 1.2 → 2.2`).

- ⭐ **O-3 ANSWERED, and the question was wrong: they are not *generations*, they are two
  COEXISTING libraries.** The `assemblies_ud` insert (`01ud`, direct U 0.112) lists under
  **Assemblies (user-defined)**; the created-from-scratch `assemblies_calc` + `layer_table_01ud`
  lists under **Assemblies (user-calculated)** with the computed 32.750 cm / U 0.112 — both read
  simultaneously by 2.4.0 BETA, in separate UI sections, on one model. The corpus-wide mutual
  exclusivity (§7.0) reflects *which feature each user used*, not a schema migration. (The two
  tables are also two id namespaces: `01ud` exists in both, as two different assemblies.)
- ⭐ **Table CREATION works.** `frames_ud`/`glazing_ud` written onto a model that never carried
  them (99-row pre-allocation mimicked) are accepted, and the DC migration folded them into the
  freshly regenerated per-window option lists — which now *begin* with
  `&ZZ-LIBIMPORT Frame=01ud&` / `&ZZ-LIBIMPORT Glazing=01ud&` (O-4, created-tables path).
- **O-6 held on the noisiest possible session:** a full DC format migration rewrote every
  window's definition and DC keys (`lenx`, `area`, widths…) — and still the model-level tables
  show exactly our six writes plus the `designPH_version` stamp (`2.1.15 → 2.4.0 BETA`).
  No face or edge classification changed.
- The second write's `assemblies_ud` insert took the next free id (`02ud`) — the script's
  fill-next-slot policy composing as designed across repeat runs.

### 2.5 ✅ The PPP export — produced by stable 2.2.29, arrival validated by needle-read

Ed disabled the Beta-GUI and exported from `-a-post.skp` under **designPH 2.2.29 PRO** (banner
read off the file): `_private/post/2414_BluffReach_LIBIMPORT-a-post_PHPP10.ppp`, 156,308 bytes.
The 2.4.0-BETA export path is unusable on SketchUp 2022 (`set_clipboard_data` crash, §2.2).

⚖ **This validation read is the first act under hard rule 1 as amended 2026-08-31** (Ed's call,
risks acknowledged; `00_Context/PPP_EXPORT.md` §1): tier-1 verbatim-needle checks on an export we
produced, no structural reading.

- ⭐ **Everything we authored arrived**: `ZZ-LIBIMPORT Wall R2` ×2 (once as the reference
  `07ud-ZZ-LIBIMPORT Wall R2`), all three layer names, `ZZ-LIBIMPORT Frame` ×2 (incl. `03ud-`
  reference), `ZZ-LIBIMPORT Glazing` ×2 (incl. **`02ud-`** reference).
- **The revised name and the id-prefixed references** mean the export carried the post-revise
  assembly and resolved id → name from our rows.
- The `02ud-ZZ-LIBIMPORT Glazing` occurrence *suggests* the split `glazingtype`/`glazingtypeid`
  pair (§2.2) resolved to our glazing at export — but tier 1 cannot distinguish a library listing
  from the window's assignment; **the PHPP by-eye check settles it**.
- `MY TEST ZZ` (the O-5 CSV row): **0 occurrences — correct**, the CSV edit was made to the
  *beta's* `data/` folder and this export came from base 2.2.29. A clean accidental control for
  the two-installs finding (§2.6).
- **Second-designPH-version confirmation**: 2.2.29 read and exported rows written for/under
  2.4.0 BETA — the n>1 version rule satisfied for the acceptance claims.
- ⏳ **Open (the last leg anywhere):** Ed's by-eye look in PHPP — computed U ≈ 0.128 on the
  U-values worksheet, the assigned face on Areas, and which glazing the exported window carries.
- ~~O-5, the installed-CSV probe~~ → **done, see §2.6.**

### 2.6 ✅ O-5 — the installed-CSV route works, machine-level

Row `90ud,"MY TEST ZZ","",0.1,0.1,` added (in place of the `90ud` spacer, following the file's
own header convention) to the **beta install's** library at
`…/designPH_beta/preview features/designPH_full_2-4 BETA/designPH/data/phpp_assemblies_ud.csv`.
Fresh SketchUp session, **blank new model**, designPH opened: *Assemblies (user-defined)* lists
`90ud MY TEST ZZ 0.100 / 0.100`.

- ⭐ **designPH reads the installed CSV at session start** and it seeds the user-defined library
  for any model — the machine-level import surface is real. Together with §2.4 this completes
  the picture: *user-defined* assemblies live in the installed CSV and are snapshotted into a
  model's `assemblies_ud` (Adelphi's renamed `83ud`–`99ud` rows are exactly such a snapshot);
  *user-calculated* assemblies live only in the model (`assemblies_calc` + layer tables).
- ⚠ **Two installed copies of the library exist** — base 2.2.29 and the 2.4.0 BETA each carry
  their own `data/` folder; the one read follows whichever GUI runs. A CSV-route importer must
  target the right install (or both).
- Housekeeping: the edited CSV should be restored (or the row kept deliberately) — it now
  seeds every future designPH session on this machine.

Runbook: [`LIBRARY-A_ed-runbook.md`](LIBRARY-A_ed-runbook.md) — all sessions run 2026-08-31.
**Every open question answered:**

| # | Question | Answer |
|---|---|---|
| O-1 | Runtime-state clobber? | ✅ **None.** Tables are read at model open / launch / re-initialise; a foreign write made mid-session under an open dialog **survived designPH's save** (§2.2). The dialog is a stale view, never a stale writer |
| O-2 | Listed / assignable / computes / survives / reaches PHPP? | ⭐ **PASS on every leg**: listed by both 2.4.0 BETA and 2.2.29; assigned to faces and windows; **U = 0.112 exact, Error 0.00** in designPH's own calculator; survives save; in the `.ppp` (needle-validated) and in PHPP by eye — present *and assigned* (§2.1, §2.2, §2.5) |
| O-3 | Which table generation is read? | ✅ **Both, simultaneously — they are not generations.** `assemblies_ud` = the *user-defined* library (CSV-seeded, direct-U); `assemblies_calc` + layers = *user-calculated*. Separate UI sections, separate id namespaces (§2.4) |
| O-4 | Do dropdown option lists regenerate? | ✅ **Yes, always** — three confirmations including for tables designPH never allocated. A writer must never touch them (§2.1, §2.4) |
| O-5 | Installed-CSV route? | ✅ **Works** — read at session start, seeds the user-defined library on any model. ⚠ per-install `data/` folder (base and beta each have one) (§2.6) |
| O-6 | What does save rewrite? | ✅ **Exactly one field: `designPH_version`** — held across four session shapes including a 46-window DC format migration (§2.1–§2.4) |
| O-7 | When may the write happen? | ✅ **Any time**: (a) pre-open, (b) pre-dialog, (c) dialog open — all accepted. Visibility follows the read-at-launch rule; the refresh gesture is **"Launch designPH or re-initialise model"** (§2.3) |
| O-8 | Rename + retune after assignment? | ✅ Assignment holds (`faces[117]` still `07ud`), revised values survive save, and the export carries `07ud-ZZ-LIBIMPORT Wall R2` — confirmed assigned in PHPP by eye (§2.2, §2.5) |
| O-9 | Entity-level co-updates needed? | ✅ **None.** No face or edge key moved on any write; option lists self-regenerate; window transforms show only ~1-ULP float noise from designPH's DC refresh. One quirk found — designPH's *own UI* can split `glazingtype`/`glazingtypeid` (§2.2) — is designPH behaviour, not a write obligation |

### 2.7 ✅ The PHPP look — the last leg (Ed, by eye)

`ZZ-LIBIMPORT Wall R2` is **present and assigned** in the PHPP produced from our export. That is
definition-of-done #3 closed the licensed way: arrival needle-validated on our own `.ppp`
(§2.5), placement confirmed by eye in PHPP.

⚖ **Hard rule 1 was amended mid-spike (2026-08-31, Ed, risks acknowledged)** — from "never parse"
to "never an *input route*", with validation reads of our own exports permitted in two tiers.
The reasoning (the 2026-08-19 PHPP-namespace finding removed the "discovery" §2.4(a) prohibits)
and the load-bearing sourcing discipline are recorded in `00_Context/PPP_EXPORT.md` §1. §2.5's
needle read was the amendment's first act.

## 3. Gate — ⭐ PASS (Ed + agent, 2026-08-31)

**designPH accepts model-level library data written from outside — fully.** Definition of done:

| # | Criterion | Verdict |
|---|---|---|
| 1 | Listed, assignable, intended U in designPH's own calculator | ✅ U 0.112 / Error 0.00 — exact. *(Framed / multi-section assemblies deliberately not exercised — that is L-B's regression bar)* |
| 2 | Survives a designPH edit-and-save cycle | ✅ four session shapes, capture-diffed; save touches one field |
| 3 | Appears in the PHPP export | ✅ needle-validated + by eye in PHPP, present and assigned |
| 4 | Timing and integrity rules stated as *tested* rules | ✅ §2's O-7/O-8/O-9 rows |
| 5 | Every O-question answered in writing; contradicted docs corrected | ✅ §2 table; `00_Context` updated same-day (base64 styles, layer schemas, two-libraries reframe, writing section) |

**Evidence limits, stated:** one machine (macOS arm64, SketchUp 22.0.353); designPH 2.4.0 BETA +
stable 2.2.29; primary model written by 2.2.24, old-generation model by 2.1.15. The 2.4.0 BETA's
*analysis/export* path is broken on SketchUp 2022 (`set_clipboard_data`, SU2023+ API) — an
environment limit that shaped which version exported, not a finding about the writes.

**▶ Spike L-B is unblocked.** What L-A hands it, beyond the PASS: write the *user-calculated*
route (`assemblies_calc` + layer tables) for PHN assemblies; per-key base64 style matching;
fill-next-blank-slot id policy composes across runs; `assemblies_ud`/`assemblies_calc` are
separate namespaces (an importer should pick ONE route and say so); the
`glazingtype`/`glazingtypeid` split question; the framed/ISO-6946 regression bar; and the user
rule "re-initialise designPH after import".
