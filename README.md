# dph_reader_poc — reading designPH into HBJSON, the proof of concept

A proof of concept (BLDGTYP, August 2026) that reads a **designPH** model out of SketchUp and
writes valid, standard **HBJSON** (honeybee + honeybee-ph), with a translation report that names
everything it could not translate. It runs as a SketchUp 2022 extension: a Ruby collector walks the
model through Trimble's public API, a Pyodide runtime inside `HtmlDialog` runs the real honeybee-ph
stack, and the result lands on disk.

**What it proved, on five real projects (designPH 2.1.15 to 2.2.29, SketchUp 22 to 26):**

| | |
|---|---|
| Classified faces translated | 545 of 545, none rejected |
| Windows (apertures) | 239 of 239, every host resolved by `glued_to` |
| Thermal bridges (on edges) | 99 of 99 |
| TFA | derived on the three models that carry it |
| U-values vs designPH's own calculator | worst delta 0.0005 W/m²K (layered), exact (U-value-only) |
| Interchange | the HBJSON loads in Rhino/Grasshopper on an independent honeybee install, and in PH-Navigator |

The POC is **complete** (2026-08-21). Its product thesis (a standalone extension) has since been
superseded by a review-side product, Pholio, in which this reader is the model source; the research
here is that project's designPH reference.

## This copy is for review, not for running against client data

This repository is a **cleaned export** of the working repo. Removed before sharing, on purpose:

- every PHPP workbook, the `.ppp` export, and every client `.skp` / `.hbjson` / `.3dm` / `.gh`
  (the Adelphi example set and the secondary corpus);
- the per-model attribute dumps and baselines derived from client models;
- the PHPP-extracted CSVs and the captured client outputs (`poc/_private/`, already gitignored);
- the vendored Pyodide runtime and wheels (`poc/ext/dph_plus_poc/vendor/`, regenerable with
  `poc/tools/vendor_payload.py`), virtualenvs, caches, and the built `.rbz`.

See [`DATA_REMOVED.md`](DATA_REMOVED.md) for the list. The one model that ships is the synthetic
six-face `_misc_test_files/designph_test.skp`; the documents still reference the removed files by
name, and those references are correct for the source repo.

## Where to read

Start with [`AGENTS.md`](AGENTS.md) (what this is, the hard rules, the corpus, the tooling), then:

| | |
|---|---|
| [`00_Context/CONSTRAINTS.md`](00_Context/CONSTRAINTS.md) | every hard limit, blocker, and method rule; what the real-model runs settled |
| [`00_Context/DESIGNPH_DATA_MODEL.md`](00_Context/DESIGNPH_DATA_MODEL.md) | what designPH stores where, and the rules for reading it |
| [`planning/POC/RESULTS/POC-5_results.md`](planning/POC/RESULTS/POC-5_results.md) | the closing retro: verdict, measured tables, the ranked "what v1 must do differently" list |
| [`planning/POC/CONTRACT_extraction-json.md`](planning/POC/CONTRACT_extraction-json.md) | the Ruby to Python seam (frozen at v2) |
| [`poc/`](poc/.index.md) | the extension, the translator, the tests, the tools; `cd poc && make ci` is the offline gate |
| [`DESIGNPH-PLUS_PRD.md`](DESIGNPH-PLUS_PRD.md) | the original product requirements (superseded as a product thesis; still the reference for translation rules and legal posture) |

## Running it

`cd poc && make ci` runs the offline gate: ruff, mypy, pytest (174 cases), the Ruby suites against a
stubbed SketchUp API, the schema gate, and the translator in a headless Chromium 88 (the engine
SketchUp 2022 embeds; `poc/tools/verify_in_chrome.py` explains how to fetch it). It needs
`uv`, Python 3.11, Ruby 2.7+, and the vendored payload (`uv run poc/tools/vendor_payload.py`).
Installing into SketchUp 2022 (`make ed`) and exporting a real designPH model requires SketchUp,
designPH, and a model you are licensed to read.

## Licence and posture

Internal. Never distributed beyond the parties it is shared with. The extension vendors honeybee
(AGPL-3.0); the licensing question is written up for counsel in
`planning/RESULTS/PHASE-3_licence-question.md`. The reader never parses designPH's `.ppp` export
and never writes into designPH's data (`AGENTS.md`, hard rules 1 and 2).

BLDGTYP, LLC (Ed May, John Mitchell).
