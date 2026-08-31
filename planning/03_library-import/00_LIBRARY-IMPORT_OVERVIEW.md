# POC #3 — Library Import: writing assemblies and window types INTO a designPH model

```
DATE:    2026-08-31
STATUS:  Scoped — outline drafted, awaiting Ed's review; no spike started
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
   question O-3 below.
8. ⚠ **The DC dropdown option lists are a separate copy.** designPH writes `_frametype_options` /
   `_glazingtype_options` (`&name=id&…`) onto window components, plus a placeholder variant
   (`DESIGNPH_FILE_FORMATS.md` §2.0). Whether designPH regenerates these from the tables at
   runtime — or whether a new frame stays invisible in the window dialog until something else
   happens — is open question O-4.
9. ✅ **The verification tooling already exists.** `00_Context/tools/skp_decode_tables.py` decodes
   the tables offline; the headless collector emits contract-v2 captures that diff byte-precisely;
   the POC-1 reader reconciles counts. A before/after write can be audited to the field with zero
   new tooling.
10. ✅ **An alternative import surface exists**: designPH's installed CSV libraries
    (`designPH/data/phpp_assemblies_ud.csv`, `phpp_frames_ud.csv`, `phpp_glazings_ud.csv` —
    `DESIGNPH_FILE_FORMATS.md` §2), machine-level rather than model-level, same self-describing
    header convention. Whether designPH re-reads them per session is open question O-5, and this
    is the fallback route if model-level writes are rejected.

**The open questions the spikes must answer:**

| # | Question |
|---|---|
| O-1 | Does designPH read the model tables **at model open** (vs holding runtime state that clobbers foreign writes on its next save)? |
| O-2 | Does a row we write **appear in designPH's UI**, assign to a face/window, compute correctly, survive a designPH save, and reach the PHPP export? |
| O-3 | Which table generation does the target designPH version (2.2.29 / 2.4.0 BETA) read and write — and does writing the *other* one do anything at all? |
| O-4 | Do the window dialog's dropdown option lists regenerate from `frames_ud`/`glazing_ud`, or must they be updated too (and is *that* acceptable)? |
| O-5 | Does the installed-CSV route work as a machine-level alternative? |
| O-6 | What does designPH **rewrite** on its next save — does our data round-trip byte-stable, get normalised, or get purged? |

## 3. Definition of done

The POC passes when, on a **copy** of a corpus model:

1. An assembly (with a layered build-up), a frame, and a glazing that we wrote from outside are
   **listed by designPH's own UI**, assignable, and produce the **intended U-value in designPH's
   own calculator** (tolerance: the POC-1 regression bar, Δ ≤ 0.0005 W/m²K on unframed; framed per
   ISO 6946 method §7.2);
2. They **survive a designPH edit-and-save cycle** (O-1/O-6 answered by capture diff);
3. They **appear in the PHPP export** (verified by eye in PHPP — the `.ppp` is never parsed, hard
   rule 1);
4. Every open question O-1…O-6 has a written answer in `RESULTS/`, including the negative ones.

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

Then the **[Ed] runbook** — the part no agent can do, one SketchUp + designPH session:

| Step | Answers |
|---|---|
| Open the written copy with designPH active; open the assembly list and window dialog | O-2 (listed?), O-4 (dropdowns?) |
| Assign the new assembly to a face; open the U-/R-value calculator on it | O-2 (computes? U-value as intended?) |
| Assign the new frame/glazing to a window | O-2, O-4 |
| Make one trivial designPH edit, save | O-1, O-6 |
| Export to PHPP; open in PHPP and look (by eye) | O-2 end-to-end |

Agent closes the loop offline: re-capture the saved model (headless collector), diff against the
pre-session capture, and name **every field designPH rewrote** (O-6). Test both table generations
on suitable copies (O-3), and probe the installed-CSV route in the same Ed session if time allows
(O-5).

**Gate:** the O-2 row of the table above, graded PASS / PASS-WITH-CONDITIONS (e.g. "works, but
option lists must be written too") / FAIL-with-mechanism. Decides whether L-B exists.

### Spike L-B — the mapping *(only after L-A passes)*

The contract from a **PH-Navigator assembly / window type** to the designPH tables:

- PHN assembly (layers: material + conductivity + thickness; framed layers) →
  `assemblies_calc` row + `layer_table_<id>` rows — SI units, the three-path columns, section
  **percentages** (never fractions), `int_insul`, `R_in`/`R_out` films;
- PHN aperture type → `frames_ud` (per-edge U, width, psi-glazing, psi-install, `chi_GT`) +
  `glazing_ud` (g, U);
- id allocation policy (first blank slot vs stable PHN-keyed ids; collision behaviour on
  re-import).

**Gate:** on ≥ 5 real PHN assemblies (framed included), designPH's own calculator reproduces the
intended U-value to the POC-1 regression bar. The contract doc is the deliverable, in the style of
`CONTRACT_extraction-json.md` — frozen before any importer is built.

### Spike L-C — transport and product shape *(sketch only)*

How the data physically travels: simplest viable is **PHN → JSON file → the import script** (no
runtime shell needed — this is one write, not a pipeline). Options to weigh, not build: a menu
item in a small extension; reuse of POC-1's loopback shell to pull from PHN's API live; the
headless writer (pholio route, gated on the SDK questions). **Gate:** a recommended v1 shape,
one page.

## 5. Rules in force

- ⚠ **Hard rule 2 gets a scoped, recorded amendment for this POC — and only this shape of it:**
  writes to `DesignPH_dict` are permitted **on copies only** (hard rule 3 already forbids
  touching an original), **never on a client's working model**, **only at model level** (never
  face-level classification data), and **every write is followed by a capture diff** naming
  exactly what changed. The rule as stated in `AGENTS.md` stands for all other work until this
  POC's results justify rewording it.
- **Never parse the `.ppp`** (hard rule 1) — the PHPP-export check in L-A is by eye, in PHPP.
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

## 7. Risks, named

- **Runtime-state clobber** (O-1/O-6) — the most likely failure mode, and L-A is designed to
  measure it precisely rather than discover it anecdotally.
- **The option-list shadow copy** (O-4) — a frame that exists in the table but not in any
  dropdown *looks* like a failed write and may just be a stale list.
- **Wrong-generation writes** (O-3) — writing `assemblies_ud` to a model whose designPH reads
  `assemblies_calc` would fail silently; both generations get tested deliberately.
- **The percent trap** (§7.2) and **DC formula staleness** (§9.2) — both already documented;
  the mapping contract cites them rather than rediscovering them.
- **n=1 evidence** — every acceptance claim gets checked on more than one model and more than
  one designPH version before it is written down as a rule. Adelphi alone proves nothing.

## 8. What this POC is not

Not face-level writing (classifications, area groups), not geometry authoring, not a designPH
replacement, not `.ppp` writing, and not a shipped product — it answers **one** question: does
designPH accept model-level library data written from outside? Spike code goes in
[`../spikes/library-import/`](../spikes/); results in `RESULTS/`; durable findings
about designPH's behaviour go to `00_Context/DESIGNPH_DATA_MODEL.md` (a new §10, "writing") and
to `phi-rules`, per the house rule.
