# What was removed from this export, and why

This repository is a cleaned copy of `dph_plus_testing` (BLDGTYP's working repo). Files below are
client project data, data derived from client models, or licensed third-party files. They exist in
the source repo and are referenced by its documents; they are not here.

| Removed | Why |
|---|---|
| `_adephi_st_example_files/adelphi-designph.skp`, `adelphi-rhino.3dm`, `adelphi-grasshopper.gh`, `adelphi-honeybee-json.hbjson` | a client project's models |
| `_adephi_st_example_files/adelphi-phpp.xlsm` | a PHPP workbook (PHI-licensed tool, client data) |
| `_adephi_st_example_files/adelphi-designph_PHPP10.ppp` | designPH's export; reference-by-eye only under the designPH licence, never parsed, never shared |
| `planning/RESULTS/baselines/baseline_<model>.txt`, `corpus_baseline.json`, `phase1_assemblies.json`, `phase1_face_attributes.json`, `phase3_sketchup_run.json` | attribute dumps and baselines derived from client models (names, assemblies, values) |
| `planning/RESULTS/phase1_live/` | raw SketchUp-console output from client models |
| `planning/RESULTS/phpp/*.csv` | values extracted from a client PHPP |
| `planning/RESULTS/validation/phase3_sketchup_output.hbjson` and its schema verdict | client geometry |
| `poc/_private/` | captured extractions, HBJSON, reports, screenshots from five client models (gitignored in the source repo too) |
| `poc/ext/dph_plus_poc/vendor/`, `poc/dist/`, `poc/py/.venv/` | the vendored Pyodide runtime and wheels, the built `.rbz`, the virtualenv; regenerable |

Kept: all code, all documents, the synthetic test model (`_misc_test_files/designph_test.skp`) and
its inspector dumps, the synthetic stub fixture (`poc/ext/dph_plus_poc/fixtures/stub_extraction.json`),
runtime-timing baselines from the stub fixture, and the dependency-closure audit.
