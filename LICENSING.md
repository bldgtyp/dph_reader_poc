# Licensing

This repository is copyright BLDGTYP, LLC and is released under the GNU Affero General
Public License, version 3 or later (`AGPL-3.0-or-later`). The full text is in
[`LICENSE`](LICENSE). It covers the Ruby extension code, the Python translation core, the
tooling, and the documentation.

## Why AGPL

The Export path runs honeybee, honeybee-ph, and ladybug inside SketchUp through a Pyodide
payload. honeybee-core, honeybee-energy, and ladybug-core are AGPL-3.0; honeybee-ph, PHX,
and PH_units are GPL-3.0-or-later. Shipping that payload to users is conveying, so the
extension that carries it must be under a compatible license. AGPL-3.0-or-later is the
one choice that fits every dependency with no boundary refactor, and it matches the
license on PH-Navigator itself. The business model set on 2026-09-01 already assumed an
open-source plugin (`DESIGNPH-PLUS_PRD.md` section 12.1); this file makes that a license
rather than an intention.

## What it means in practice

- **Install and use freely.** Run the extension in your own SketchUp with no obligation
  to anyone.
- **Modify and redistribute: keep it open.** A modified build handed to other people, or
  run for them over a network, must come with its source under the same license.
- **Proprietary derivatives need a commercial license.** BLDGTYP offers those as sole
  copyright holder. Contact ed@bldgtyp.com.

## What this license does not cover

- **designPH and SketchUp.** Every user of this extension supplies their own designPH and
  SketchUp licenses. Nothing in this repository is derived from designPH's code or its
  `.ppp` export format (`AGENTS.md`, hard rules 1 and 2). The interoperability posture
  toward PHI is documented separately and is unchanged by this license.
- **Client models and licensed fixtures.** No designPH models, PHPP workbooks, or
  PHI-derived data are in this repository. See `DATA_REMOVED.md`.
- **The Pyodide payload.** The vendored wheels are not committed. Each carries its own
  upstream license, which this license does not alter.

## Contributions

BLDGTYP dual-licenses this code (AGPL publicly, commercial on request), which requires
BLDGTYP to hold the rights to every line. Outside contributions need a signed Contributor
License Agreement before merge. See [`CLA.md`](CLA.md).

## Status

The license choice, the CLA text, and the designPH interoperability posture are pending
review by counsel. The counsel write-up that preceded this decision is at
`planning/01_sketchup-export/feasibility/RESULTS/PHASE-3_licence-question.md`. Nothing
here is legal advice.
