# POC #3 — Library Import: writing assemblies and window types INTO a designPH model

```
DATE:    2026-08-31
STATUS:  ⭐ Spike L-A PASS (2026-08-31, scoped→run→graded in one day) — designPH accepts
         foreign model-level library writes end to end; O-1…O-9 all answered
         (RESULTS/LIBRARY-A_results.md). Durable facts: 00_Context/DESIGNPH_DATA_MODEL.md §14.
         ▶ Spike L-B is next — its brief below is revised with what L-A learned.
AUTHOR:  Ed May / Claude
ISSUE:   none — local-only research workflow (planning/.instructions.md)
```

## 1. The question

POCs #1 and #2 proved the **read** direction, twice over: designPH data comes out of a `.skp` as
valid HBJSON, inside SketchUp and with no SketchUp at all. This POC asks the **write** direction,
narrowly:

> **Can we SET designPH library data at the model level — assemblies and window types (frames +
> glazings) — such that designPH itself lists them, lets the user assign them, computes with them,
> and carries them through to the PHPP export?**

Why it matters: designPH's assembly builder and window-component editor are **laborious and
error-prone** — every layer, lambda, frame width and psi typed by hand, per model. BLDGTYP already
builds this exact data once, properly, in **PH-Navigator**. If a model-level write is accepted by
designPH, "PHN builds the library, the model imports it" replaces the most tedious and
mistake-prone part of every designPH workflow. If it is not accepted, we want to know *why* (and
whether the plugin-folder CSV route works instead) before anyone builds an importer.

**The primary deliverable of this POC is what we learn, written down (Ed, 2026-08-31).** Spike
code is throwaway — code quality, speed, and packaging do not matter at all here. What matters,
non-negotiably: every observation lands in `RESULTS/` as it is made (negative and puzzling ones
especially); durable behaviour facts flow to `00_Context/DESIGNPH_DATA_MODEL.md` (a new "writing"
section) and to `phi-rules`; and **any existing doc a finding contradicts is corrected and marked
superseded in the same pass** — the house "keep the record honest" rule. These notes are the
foundation for the real apps that follow; the code is not.

## 2. What is already known — verified against the record, 2026-08-31

All of this is **observed and measured**, not inferred, unless marked open:

1. ✅ **The data is model-level attribute-dictionary data.** designPH's whole working dataset hangs
   on `Sketchup::Model`'s `DesignPH_dict`: `assemblies_calc` (header rows) + one
   `layer_table_<id>` per assembly (build-up), `frames_ud`, `glazing_ud`, `connections_ud`, and
   friends. `00_Context/DESIGNPH_DATA_MODEL.md` §4.
2. ✅ **The encoding is plain and fully decoded.** Base64 of `Marshal.dump` of a self-describing
   `:TOKENS` table — plain Arrays/Strings/Symbols/Floats/Booleans only; **no custom Ruby class has
   ever been observed in a library table** (§7, "Known table schemas"). Every schema we need is
   recorded: assemblies, layers (3 parallel paths), frames (per-edge U/width/psi — PHPP's Windows
   worksheet column for column), glazings (g + U). §7.0.1.
3. ✅ **The dictionary is writable by anyone.** It is an ordinary SketchUp attribute dictionary —
   "Any other plugin can read *or overwrite* `DesignPH_dict`. Nothing protects it" (§3, §8.4).
   The standing read-only posture (hard rule 2) is a **chosen safety default, not a technical
   limit** — see §6 below for how this POC amends it.
4. ✅ **"Adding an entry" is designPH's own gesture.** designPH pre-allocates the `NNud` id space
   (99 rows in `frames_ud`/`glazing_ud`, 82 in `assemblies_calc`) and fills in `desc` as the user
   creates entries — blank `desc` = empty slot (§7.0). Filling a pre-allocated row is precisely
   what the plugin's UI does; we would be doing the same thing from outside.
5. ✅ **Units and semantics are recorded, including the traps.** Table values are SI/PHPP (lambda
   W/mK, thickness mm, R m²K/W) while DC values are inches (§8.5); `surf2/3_percentage` are
   **percentages, not fractions** (§7.2 — the 0.0625 trap); designPH's multi-section U-value is
   ISO 6946 §6.7 mean-of-limits *including films*, reproduced exactly against its own calculator
   (§7.2). POC-1's U-value regression method carries over unchanged.
6. ✅ **Windows join by id.** A window DC instance references `frametypeid`/`glazingtypeid` into
   exactly these tables (§9, §9.2.1). The numeric window-type library is therefore model-level
   data too.
7. ⚠ **Two assembly-table generations exist and are mutually exclusive per model** —
   `assemblies_calc` (+ `layer_table_*`, current) vs `assemblies_ud` (older, header-only schema)
   (§7.0). A writer targets the generation the model's designPH version actually reads — open
   question O-3 below. *(✅ Answered, and the framing was wrong: they are two **coexisting
   libraries** — user-defined vs user-calculated — both read at once. §14.5.)*
8. ⚠ **The DC dropdown option lists are a separate copy.** designPH writes `_frametype_options` /
   `_glazingtype_options` (`&name=id&…`) onto window components, plus a placeholder variant
   (`DESIGNPH_FILE_FORMATS.md` §2.0). Whether designPH regenerates these from the tables at
   runtime — or whether a new frame stays invisible in the window dialog until something else
   happens — is open question O-4. *(✅ Answered: they regenerate, always — three confirmations,
   including for tables the writer created. Never write them. §14.4.)*
9. ✅ **The verification tooling mostly exists — with two measured gaps** *(corrected 2026-08-31,
   during L-A build)*. `00_Context/tools/skp_decode_tables.py` decodes the tables offline; the
   headless collector emits contract-v2 captures that diff byte-precisely; the POC-1 reader
   reconciles counts. But **(a)** contract v2 deliberately ships neither `frames_ud` nor
   `glazing_ud` (`DESIGNPH_DATA_MODEL.md` §7.0), so a capture diff is blind to two of the three
   tables this POC writes; and **(b)** the offline decoder greps `model.dat`, which keeps
   historical state (§8.7) — after a table is rewritten, the first blob found for a key may be the
   *stale* one, so a post-write offline read is corroborative only. Spike L-A therefore adds one
   small tool: an SDK **live-state** model-table dumper (`planning/spikes/library-import/`), which
   is the authoritative before/after read.
10. ✅ **An alternative import surface exists**: designPH's installed CSV libraries
    (`designPH/data/phpp_assemblies_ud.csv`, `phpp_frames_ud.csv`, `phpp_glazings_ud.csv` —
    `DESIGNPH_FILE_FORMATS.md` §2), machine-level rather than model-level, same self-describing
    header convention. Whether designPH re-reads them per session is open question O-5, and this
    is the fallback route if model-level writes are rejected.
11. ⚠ **Library data is duplicated outside the model dictionary in three known places** — the
    per-window DC option lists (`_frametype_options`, names only, `DESIGNPH_FILE_FORMATS.md`
    §2.0), the DC `frametype`/`glazingtype` keys (observed duplicating the *ids* on Adelphi,
    §9.2.1 — whether they ever hold names is unverified), and the `Material`/`BackMaterial`
    stash designPH writes onto faces when it repaints (§5.1). Entity-level dictionaries otherwise
    hold **references** (`NNud` ids) and per-entity classification, not library values — which is
    the structural reason to *expect* independence, and open question O-9 is where that
    expectation gets tested rather than trusted.
12. ✅ **Assignments are by id, names travel separately.** A face's `assemblyID` is an `NNud` key
    into the tables; `desc` is a column in the table row; the face-level `descName`/`descNameAuto`
    pair is the *face's* name, not the assembly's (§5.2, §6.5). So renaming an assembly **should**
    leave every assignment intact — stated here as the hypothesis O-8 exists to verify, because
    "should" from structure has been wrong on this project before.

**The open questions the spikes must answer:**

> ⭐ **All nine ANSWERED 2026-08-31** — verdicts in
> [`RESULTS/LIBRARY-A_results.md`](RESULTS/LIBRARY-A_results.md) §2, durable rules in
> `00_Context/DESIGNPH_DATA_MODEL.md` §14. The table below stands as the questions asked.

| # | Question |
|---|---|
| O-1 | Does designPH read the model tables **at model open** (vs holding runtime state that clobbers foreign writes on its next save)? |
| O-2 | Does a row we write **appear in designPH's UI**, assign to a face/window, compute correctly, survive a designPH save, and reach the PHPP export? |
| O-3 | Which table generation does the target designPH version (2.2.29 / 2.4.0 BETA) read and write — and does writing the *other* one do anything at all? |
| O-4 | Do the window dialog's dropdown option lists regenerate from `frames_ud`/`glazing_ud`, or must they be updated too (and is *that* acceptable)? |
| O-5 | Does the installed-CSV route work as a machine-level alternative? |
| O-6 | What does designPH **rewrite** on its next save — does our data round-trip byte-stable, get normalised, or get purged? |
| O-7 | **When may (must?) the write happen** — (a) into the `.skp` before SketchUp opens it, (b) with SketchUp open but designPH's dialog not yet opened, (c) live, with the dialog already open? Does designPH see a **hot-swapped** table without a file reopen or dialog reopen? |
| O-8 | **Does a library edit break existing assignments?** Rename an assembly already assigned to faces (`desc` change), then change its layer values: does the assignment hold, does the U-value follow, do the Areas list and PHPP export follow? (Known #12 says it should — verify.) |
| O-9 | **Which entity-level dictionaries must be co-updated** when the model-level libraries change — faces, edges, window DCs — and which are functionally independent? (Known #11 names the three suspected coupling points.) |

## 3. Definition of done

> ⭐ **Met in full for Spike L-A, 2026-08-31 — gate PASS** (item-by-item grading:
> [`RESULTS/LIBRARY-A_results.md`](RESULTS/LIBRARY-A_results.md) §3). The framed/multi-section
> U-value leg of item 1 was deliberately deferred to L-B's regression bar.

The POC passes when, on a **copy** of a corpus model:

1. An assembly (with a layered build-up), a frame, and a glazing that we wrote from outside are
   **listed by designPH's own UI**, assignable, and produce the **intended U-value in designPH's
   own calculator** (tolerance: the POC-1 regression bar, Δ ≤ 0.0005 W/m²K on unframed; framed per
   ISO 6946 method §7.2);
2. They **survive a designPH edit-and-save cycle** (O-1/O-6 answered by capture diff);
3. They **appear in the PHPP export** (arrival validated by needle-read of our own export under
   hard rule 1 as amended 2026-08-31 — `PPP_EXPORT.md` §1; computed placement verified by eye in
   PHPP);
4. The **timing rules** (O-7) and **integrity rules** (O-8/O-9) are stated as tested rules, not
   expectations — when a write is allowed to happen, and what an editor of the libraries must and
   must not touch elsewhere in the model;
5. Every open question O-1…O-9 has a written answer in `RESULTS/`, including the negative ones,
   and every `00_Context` claim a finding contradicted has been corrected and marked superseded.

A **clean FAIL is also a pass for the POC**: "designPH discards foreign writes because X" is a
result worth exactly as much as a working importer, and it redirects the effort to the CSV route
or to the PHI conversation.

## 4. Spikes

Same protocol as every phase before: **do not start a spike until the previous spike's gate is
evaluated and recorded in `RESULTS/`** — the sequence exists to stop early.

### Spike L-A — the handshake *(the existential question; everything else waits on it)*

Hand-craft **one assembly + its layer table, one frame, one glazing** — realistic values, ids
chosen from empty slots — and write them into a **copy** of a corpus model at model level. Two
write routes, cheapest first:

- **A-1, in SketchUp** (no designPH loaded): a paste-into-Ruby-Console script using
  `Marshal.dump` + `Base64` — the native serialiser, zero format risk. Save-as under a new name.
- **A-2, offline** *(only if useful)*: the same write headless via the C SDK, to learn whether the
  pholio-shaped "watcher writes the model" variant is even conceivable. ⚠ Inherits POC #2's SDK
  access block and its mutate-on-read trap; A-2 is optional and never gates A-1.

The write is exercised at **three timings** (O-7), each on its own copy so the results never
contaminate each other: **(a)** already in the `.skp` before the designPH-active session opens it,
**(b)** written from the Ruby Console with SketchUp open but designPH's dialog never yet opened
this session, **(c)** written live while designPH's dialog is already open — the hot-swap case,
where "does the dialog show it without a reopen?" is itself the answer.

*(Timing (a) mechanics, since A-2 is optional: copy (a) is produced by the same A-1 console write
in a separate **prep session with the designPH extension disabled** in the Extension Manager —
write, Save As, quit, re-enable. The write physically happening "with SketchUp open" is fine; what
timing (a) isolates is that designPH first meets the data at model open, in a session whose
runtime state never saw the write happen.)*

**Target copies, chosen from measurement (2026-08-31):** the primary is a copy of
`2414_Bluff Reach` — the **only** corpus model carrying all three tables, with free user slots
`07ud`+ (`assemblies_calc`), `03ud`+ (`frames_ud`), `02ud`+ (`glazing_ud`). The O-3 old-generation
copy is Adelphi, whose `assemblies_ud` holds **only** rows `83ud`–`99ud` (the shipped-default
range, renamed in place by the user) — so there the write is an *insert* of a new `01ud` row, not
a fill, and `frames_ud`/`glazing_ud` are absent entirely, making table *creation* an optional
extra probe there.

Then the **[Ed] runbook** — the part no agent can do, one SketchUp + designPH session:

| Step | Answers |
|---|---|
| Open copy (a) with designPH active; open the assembly list and window dialog | O-2 (listed?), O-4 (dropdowns?), O-7a |
| On copies (b) and (c): run the paste-in write at the scripted moment, then look again | O-7b, O-7c (hot swap) |
| Assign the new assembly to a face; open the U-/R-value calculator on it | O-2 (computes? U-value as intended?) |
| Assign the new frame/glazing to a window | O-2, O-4 |
| **Rename the imported assembly** (a `desc` edit through our write path) *after* it is assigned; recheck the face's assignment, its U-value, and the Areas list | O-8 |
| Make one trivial designPH edit, save | O-1, O-6 |
| Export to PHPP; open in PHPP and look (by eye) | O-2 end-to-end, O-8 downstream |

Agent closes the loop offline: re-capture every saved copy (headless collector), diff against its
pre-session capture, and name **every field designPH rewrote** (O-6) — the same diff, read
per-entity, grades **O-9**: which face/edge/DC keys changed when only the model-level tables were
edited, and which stayed byte-stable. Test both table generations on suitable copies (O-3), and
probe the installed-CSV route in the same Ed session if time allows (O-5).

**Gate:** the O-2 row of the table above, graded PASS / PASS-WITH-CONDITIONS (e.g. "works, but
option lists must be written too") / FAIL-with-mechanism. Decides whether L-B exists.

> ⭐ **RUN AND PASSED, 2026-08-31 — no conditions.** Not even the anticipated ones: the option
> lists regenerate by themselves (O-4), no entity key needs co-updating (O-9), and the write may
> happen at any timing (O-7). [`RESULTS/LIBRARY-A_results.md`](RESULTS/LIBRARY-A_results.md).
> A-2 (the offline C-SDK write) was never needed and stays unrun. Spike assets:
> `planning/spikes/library-import/` — `write_library.rb` (the accepted write recipe),
> `rehearse.py` (the offline harness that caught two real defects before any SketchUp session),
> `dump_model_tables.py` (the SDK live-state before/after read, kept for L-B).

### Spike L-B — the mapping *(unblocked 2026-08-31; brief revised with L-A's findings)*

The contract from a **PH-Navigator assembly / window type** to the designPH tables. L-A settled
the *route*: PHN assemblies carry layers, so they write the **user-calculated** library —
`assemblies_calc` row + `layer_table_<id>` — never `assemblies_ud` (that is the CSV-seeded
user-defined library, a different product surface; §14.5). The contract must specify:

- **Value mapping** *(unchanged from the original brief)*: SI units, the three-path columns,
  section **percentages** (never fractions), `int_insul`, `R_in`/`R_out` films; PHN aperture
  type → `frames_ud` (per-edge U, width, psi-glazing, psi-install, `chi_GT`) + `glazing_ud`
  (g, U) — creating the window tables with designPH's 99-row pre-allocation where absent
  (accepted, measured).
- **Serialisation discipline** *(new, from L-A)*: match each key's existing base64 style; emit
  the layer-table `:TOKENS` the model already carries (8- and 12-col coexist in one model);
  never touch the DC option lists or any entity dictionary.
- **Id allocation and re-import** *(now half-answered)*: fill-next-blank-slot works and composes
  across runs — but naive re-import therefore **duplicates** rather than updates. The contract
  must pick the update key (row `desc` match? a PHN-id column designPH ignores? — test that a
  foreign extra column survives) and define collision behaviour on a slot-exhausted table.
- **The `glazingtype`/`glazingtypeid` split** *(new)*: designPH's own UI left the pair split on
  one window and the export still resolved our glazing; L-B settles which key each consumer
  reads before the contract claims either.
- **User-facing rule**: imports are invisible to an open dialog — the contract ships the
  "re-initialise designPH after import" instruction (O-7).

**Gate** *(sharpened)*: on ≥ 5 real PHN assemblies — **framed/multi-section included, the ISO
6946 mean-of-limits leg L-A deliberately deferred** — designPH's own calculator reproduces the
intended U-value to the POC-1 regression bar, on **stable 2.2.29** (the beta cannot run analysis
on SketchUp 2022) **and** the PPP export carries them (needle-validated under amended hard
rule 1, placement by eye in PHPP). The contract doc is the deliverable, in the style of
`CONTRACT_extraction-json.md` — frozen before any importer is built.

### Spike L-C — transport and product shape *(sketch only; options re-weighted by L-A)*

Simplest viable is confirmed viable: **PHN → JSON file → a paste-in / menu-item write inside
SketchUp** — `write_library.rb` is the working seed, any write timing is acceptable (O-7), and
re-initialise is the only post-step. Options to weigh, not build:

- a small extension with a menu item (one step up from the paste-in; no runtime shell — this is
  one write, not a pipeline);
- reuse of POC-1's loopback shell to pull from PHN's API live (only if the file hand-off proves
  annoying in practice);
- the **headless writer** (pholio route) — still gated on the C-SDK access + licensing blocks,
  and note the sign-flip L-A makes explicit: a *writer* must SAVE, so POC #2's load-bearing
  "never save" invariant (and its read-only binding, which cannot resolve `SUModelSaveToFile`
  by design) does not carry over — a headless write path needs its own binding and its own
  mutate-on-read reasoning;
- **the installed-CSV channel** *(new, from O-5)* — a second product surface entirely:
  machine-level seeding of the user-defined library ("PHN pushes the BLDGTYP standard library to
  every designPH install"), no model touched; per-install `data/` folders to handle.

**Gate:** a recommended v1 shape, one page.

## 5. Rules in force

- ⚠ **Hard rule 2 gets a scoped, recorded amendment for this POC — and only this shape of it:**
  writes to `DesignPH_dict` are permitted **on copies only** (hard rule 3 already forbids
  touching an original), **never on a client's working model**, **only at model level** (never
  face-level classification data), and **every write is followed by a capture diff** naming
  exactly what changed. The rule as stated in `AGENTS.md` stands for all other work until this
  POC's results justify rewording it.
- **The `.ppp` is never an input route** (hard rule 1, amended 2026-08-31 — `PPP_EXPORT.md` §1):
  L-A validates its own export by needle-read; computed placement is checked by eye in PHPP;
  extraction of designPH-computed data stays forbidden.
- **Report, don't guess** (hard rule 4) — an importer that silently skips a layer it cannot map
  is the same failure as a reader that silently drops a face.
- **Version gate** — the writer refuses a 3.x-stamped model by name, exactly like the POC-1
  reader; and it records the `designPH_version` it wrote under, since O-3 makes the answer
  version-shaped.
- **Type-check every read, count non-blank `desc`, never assume schema stability** — the
  `:TOKENS` header exists because the schema drifts (Linde's 12-column layer tables); a writer
  must emit the schema the model already carries, not the one we like.

## 6. Licensing and posture — start before the spikes, like POC #2's L-tasks

| Task | What |
|---|---|
| LI-1 | **Re-read the designPH licence** specifically for writing/interop language. Reading via the public SketchUp API was judged fine (`PPP_EXPORT.md` records where the line was drawn and why); *writing data the plugin consumes* is a deeper interop posture and gets its own explicit judgment, written down |
| LI-2 | **The PHI conversation (spike Phase 5, tabled) intersects harder here.** A tool that *authors* designPH data is a bigger conversation than a reader; if this POC passes, the drafted PHI opener (`../01_sketchup-export/feasibility/RESULTS/PHASE-0_long-lead-staging.md`) should be updated to mention it before anything ships. **[Ed]** |
| LI-3 | Everything stays **internal-only, never distributed**, same as all POC code |

## 7. Risks, named — and how each resolved (2026-08-31)

- **Runtime-state clobber** (O-1/O-6) — the most likely failure mode, and L-A is designed to
  measure it precisely rather than discover it anecdotally. *(✅ Did not exist: the dialog is a
  stale view, never a stale writer; save touches one field.)*
- **The option-list shadow copy** (O-4) — a frame that exists in the table but not in any
  dropdown *looks* like a failed write and may just be a stale list. *(✅ Regenerates itself.)*
- **Wrong-generation writes** (O-3) — writing `assemblies_ud` to a model whose designPH reads
  `assemblies_calc` would fail silently; both generations get tested deliberately. *(✅ The risk
  dissolved with the reframe — both are read, always. The surviving version of it: an importer
  writing the **user-defined** table when it means user-calculated data, §14.5.)*
- **The percent trap** (§7.2) and **DC formula staleness** (§9.2) — both already documented;
  the mapping contract cites them rather than rediscovering them. *(→ carried to L-B, joined by
  the base64-style and layer-schema disciplines and the `glazingtypeid` split.)*
- **n=1 evidence** — every acceptance claim gets checked on more than one model and more than
  one designPH version before it is written down as a rule. Adelphi alone proves nothing.
  *(Two models — 2.2.24-written and 2.1.15-written — and two designPH versions — 2.4.0 BETA and
  stable 2.2.29 — but **one machine and one SketchUp**. L-B keeps the caution.)*

## 8. What this POC is not

Not face-level writing (classifications, area groups), not geometry authoring, not a designPH
replacement, not `.ppp` writing, and not a shipped product — it answers **one** question: does
designPH accept model-level library data written from outside? Spike code goes in
[`../spikes/library-import/`](../spikes/library-import/); results in `RESULTS/`; durable findings
about designPH's behaviour go to `00_Context/DESIGNPH_DATA_MODEL.md` (a new "Writing designPH
data" section — the doc already has a §10, so number it when it lands) and to `phi-rules`, per
the house rule.
