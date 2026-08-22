# DesignPH-PLUS — the licence question, for counsel

**Not legal advice.** This is a briefing document: the facts as measured, and the questions they
raise. Phase 3's gate passed on 2026-08-19, and the plan requires this to be resolved *before* v1 is
written — because the answer changes what gets built, not just what the LICENSE file says.

**Prepared by:** BLDGTYP (Ed May) · **Date:** 2026-08-19 ·
**Evidence:** [`PHASE-3_results.md`](PHASE-3_results.md), [`../../DESIGNPH-PLUS_PRD.md`](../../DESIGNPH-PLUS_PRD.md) §9

---

## 1. What is being built

**DesignPH-PLUS** — a free, open-source **SketchUp extension**. It reads Passive House building-envelope
data that already sits inside the user's own SketchUp file and writes it out as **HBJSON**, an open
interchange format. It is read-only; it never modifies the user's model.

Distribution: a single `.rbz` file (a zip), most likely via Trimble's Extension Warehouse and/or
GitHub. Downloaded and run entirely on the user's own machine. No server, no network access, no
telemetry.

## 2. What the architecture now is, in fact

Phase 3 settled this empirically. The extension:

1. **Bundles a complete Python runtime** — Pyodide 0.24.1, which is CPython 3.11 compiled to
   WebAssembly (≈6.9 MB compressed, 20.9 MB installed).
2. **Bundles eight third-party Python libraries** as unmodified `.whl` files (see §3).
3. **Runs a small HTTP server on the local loopback interface** (`127.0.0.1`, random port, random
   path token) for the lifetime of one dialog. This is not a design preference: SketchUp's embedded
   browser refuses to load local files directly, so serving over loopback is the only way the
   bundled runtime can load its own assets. **Nothing is exposed off the machine.**
4. **Executes the bundled libraries inside SketchUp's embedded Chromium**, passes the model's
   geometry to them as JSON, and writes the resulting HBJSON to a file the user chooses.

The extension's own code is Ruby and JavaScript. It never links to the Python libraries in the C
sense — it hands them JSON and receives JSON back. But it **ships them**, and it **executes them**,
as one installed product.

## 3. The licences actually shipped

Read from the `METADATA` of the exact wheels vendored, 2026-08-19:

| Package | Licence | Copyright holder |
|---|---|---|
| `honeybee-core` 1.64.65 | **AGPL-3.0** | Ladybug Tools LLC |
| `honeybee-energy` 1.123.23 | **AGPL-3.0** | Ladybug Tools LLC |
| `ladybug-core` 0.44.56 | **AGPL-3.0** | Ladybug Tools LLC |
| `ladybug-geometry` 1.35.3 | **AGPL-3.0** | Ladybug Tools LLC |
| `ladybug-geometry-polyskel` 1.7.52 | **AGPL-3.0** | Ladybug Tools LLC |
| `honeybee-standards` 2.0.7 | GPL-3.0 (classifier only) | Ladybug Tools LLC |
| `honeybee-ph` 1.33.48 | GPL-3.0-or-later | **BLDGTYP** |
| `ph-units` 1.5.38 | *none declared in metadata* | **BLDGTYP** |
| `micropip` 0.11.1 | MPL-2.0 | Pyodide contributors |
| Pyodide runtime 0.24.1 | MPL-2.0 | Pyodide contributors |

**The asymmetry that matters:** the AGPL exposure comes entirely from **Ladybug Tools' code**. The
two BLDGTYP packages (`honeybee-ph`, `ph-units`) are our own copyright, so we can license them
however we like — but they are not the ones carrying AGPL.

⚠ **Housekeeping, independent of any legal question:** `ph-units` publishes no licence in its
package metadata. That should be fixed whatever the outcome here.

## 4. The questions

### 4.1 The core question

**Does bundling and executing AGPL-3.0 libraries inside the extension make the extension as a whole
a "work based on" those libraries, requiring the whole thing to be licensed AGPL-3.0?**

Relevant facts for the analysis:

- The libraries are shipped **unmodified**, as separate files, in their original wheel form.
- Our code does not import, link against, or subclass them. It sends JSON across a language
  boundary and reads JSON back.
- They are nonetheless **required** for the product to function, shipped in the same archive, and
  installed as one unit. Without them the extension does nothing.
- Is this "mere aggregation" (GPL-3.0 §5, which does not propagate), or a combined work?

### 4.2 The network clause — specific to our architecture

**AGPL-3.0 §13** adds an obligation where users "interact with it remotely through a computer
network": the operator must offer them the Corresponding Source.

Our extension **does** run an HTTP server, and the AGPL libraries **do** execute behind it. But the
server is bound to loopback, is reachable only by the same person on the same machine, exists for
seconds, and is there solely because the embedded browser will not load local files.

- Does a loopback-only server, serving only its own user, engage §13 at all?
- If it does, is the obligation satisfied by shipping the source alongside — which we would do
  anyway as an open-source project?

### 4.3 Does it reach the other products?

BLDGTYP operates and plans commercial hosted products (**ph-navigator**, and others) which would
**consume the HBJSON this extension produces**. They share no code with it.

- Output of a program is normally not a derivative work of that program. Does anything about this
  arrangement disturb that?
- Is there any route by which AGPL obligations reach a separate hosted product that merely reads a
  file the extension wrote?

**This is the question that actually decides the architecture.** If the answer is "no risk to the
hosted products", the AGPL cost is low and we ship Pyodide. If there is real entanglement risk, the
alternative in §5 becomes attractive despite costing more engineering.

### 4.4 Distribution obligations

If the extension must be AGPL-3.0:

- What must accompany the `.rbz` at distribution — source offer, licence texts, notices?
- Does distributing through **Trimble's Extension Warehouse** create any conflict with its terms?
- What does it imply for outside contributors, and should we require a CLA?

### 4.5 The alternative, if the answer is unfavourable

PRD §7.1 records a fallback that was kept alive precisely for this: **the Ruby extension writes
HBJSON directly**, reimplementing only the *serialization* — not honeybee's logic — and validating
in CI against the published schemas.

- HBJSON is a **file format / JSON schema**. On the usual understanding that formats are not
  copyrightable, this route ships **no third-party code at all** and links nothing, leaving the
  extension's licence free to choose.
- Is that reasoning sound here, given that the schema is published by the same organisation that
  licenses the AGPL libraries?
- The cost is real — schema-drift maintenance forever — so we would like to know it is genuinely
  necessary before paying it.

### 4.6 Our own packages

`honeybee-ph` (GPL-3.0-or-later) and `ph-units` are BLDGTYP's copyright.

- Since we hold the copyright, may we dual-license them (e.g. also under a permissive licence) to
  give the hosted products freedom, while keeping the public versions copyleft?
- Does `honeybee-ph`'s own dependence on AGPL Ladybug packages constrain that?

## 5. What we would like out of this

In priority order:

1. **A yes/no on §4.3** — can the hosted products be affected? This decides the architecture.
2. **A recommended licence** for the extension.
3. **A view on §4.2**, because a loopback server is now a permanent part of the design.
4. **A list of what must ship** in the `.rbz` if we go AGPL.

## 6. Not in scope for this question

The **designPH licence agreement** (PRD §9) is a separate matter, already staged for Phase 5: we do
not parse designPH's `.ppp` file format, and we read only the user's own `.skp` through Trimble's
public API. That analysis is unchanged by anything in Phase 3 and should not be conflated with the
open-source licensing question above.
