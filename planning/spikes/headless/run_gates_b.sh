#!/usr/bin/env bash
# Spike B — run every gate and print one verdict line each.
#
# ⚠ Runs against a THIRD-PARTY re-host of Trimble's SDK; feasibility-only evidence. See sdk.py.
# ⚠ Needs planning/spikes/headless/_private/ staged (gitignored client data, see its MANIFEST.md)
#    and the framework unpacked at _private/sdk/. Neither is in the repo.
# ⚠ H5 needs the POC's own interpreter: `cd pocs/01_sketchup-export && make venv` once, first.
#
#    ./run_gates_b.sh
#
# ORDER MATTERS. H2 writes the captures every later gate reads; H5 writes the translations H6
# compares. Running one gate on stale inputs from another is the kind of green nobody should trust.
#
# The native SDK prints libTIFF warnings to stderr while parsing embedded textures. They are noise
# from the image library, not from the model read, and are dropped here rather than silenced in the
# scripts — a gate that swallows its own stderr can hide a real error.
set -uo pipefail
cd "$(dirname "$0")"

# shellcheck source=_gate_runner.sh
source "$(dirname "$0")/_gate_runner.sh"

P=_private

echo "=== Spike B gates ==============================================================="
run "H2 emission"        b2_h2_emission.py --corpus "$P/corpus" --out-dir "$P/out/captures" \
                             --out "$P/out/b2_emission.json"
run "H1 identity join"   b1_h1_identity.py --captures "$P/out/captures" --fixtures "$P/fixtures" \
                             --out "$P/out/b1_identity.json"
run "H3 reconciliation"  b3_h3_reconcile.py --captures "$P/out/captures" \
                             --baseline "$P/baselines/corpus_baseline.json" \
                             --out "$P/out/b3_reconcile.json"
run "H4 identity diff"   b4_h4_identity_diff.py --captures "$P/out/captures" \
                             --fixtures "$P/fixtures" --corpus "$P/corpus" \
                             --out "$P/out/b4_identity.json"
run "H5 translator"      b5_h5_translate.py --captures "$P/out/captures" --fixtures "$P/fixtures" \
                             --out-dir "$P/out/translated" --out "$P/out/b5_translate.json"
run "H6 HBJSON"          b6_h6_hbjson.py --translations "$P/out/translated" \
                             --fixtures "$P/fixtures" --out "$P/out/b6_hbjson.json"
run "H7 determinism"     b7_h7_determinism.py --corpus "$P/corpus" --work "$P/out/determinism" \
                             --out "$P/out/b7_determinism.json"
run "H8 cost"            b8_h8_cost.py --corpus "$P/corpus" --captures "$P/out/captures" \
                             --work "$P/out/cost" --out "$P/out/b8_cost.json"
run "H9 versions"        b9_h9_versions.py --corpus "$P/corpus" --captures "$P/out/captures" \
                             --baseline "$P/baselines/corpus_baseline.json" \
                             --out "$P/out/b9_versions.json"
finish "SPIKE B"
