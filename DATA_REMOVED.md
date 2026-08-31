# What was removed from this export, and why

This repository is a cleaned copy of `dph_plus_testing` (BLDGTYP's working repo). Files below are
client project data, data derived from client models, or licensed third-party files. They exist in
the source repo and are referenced by its documents; they are not here.

| Removed | Why |
|---|---|
| `corpus/adelphi/adelphi-designph.skp`, `adelphi-rhino.3dm`, `adelphi-grasshopper.gh`, `adelphi-honeybee-json.hbjson` | a client project's models |
| `corpus/adelphi/adelphi-phpp.xlsm` | a PHPP workbook (PHI-licensed tool, client data) |
| `corpus/adelphi/adelphi-designph_PHPP10.ppp` | designPH's export; reference-by-eye only under the designPH licence, never parsed, never shared |
| `planning/01_sketchup-export/feasibility/RESULTS/baselines/baseline_<model>.txt`, `corpus_baseline.json`, `phase1_assemblies.json`, `phase1_face_attributes.json`, `phase3_sketchup_run.json` | attribute dumps and baselines derived from client models (names, assemblies, values) |
| `planning/01_sketchup-export/feasibility/RESULTS/phase1_live/` | raw SketchUp-console output from client models |
| `planning/01_sketchup-export/feasibility/RESULTS/phpp/*.csv` | values extracted from a client PHPP |
| `planning/01_sketchup-export/feasibility/RESULTS/validation/phase3_sketchup_output.hbjson` and its schema verdict | client geometry |
| `pocs/01_sketchup-export/_private/` | captured extractions, HBJSON, reports, screenshots from five client models (gitignored in the source repo too) |
| `pocs/01_sketchup-export/ext/dph_plus_poc/vendor/`, `pocs/01_sketchup-export/dist/`, `pocs/01_sketchup-export/py/.venv/` | the vendored Pyodide runtime and wheels, the built `.rbz`, the virtualenv; regenerable |

Kept: all code, all documents, the synthetic test model (`corpus/synthetic/designph_test.skp`) and
its inspector dumps, the synthetic stub fixture (`pocs/01_sketchup-export/ext/dph_plus_poc/fixtures/stub_extraction.json`),
runtime-timing baselines from the stub fixture, and the dependency-closure audit.
