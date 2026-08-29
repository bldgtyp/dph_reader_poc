#!/usr/bin/env bash
# Spike A — run every gate and print one verdict line each.
#
# ⚠ Runs against a THIRD-PARTY re-host of Trimble's SDK; feasibility-only evidence. See sdk.py.
# ⚠ Needs planning/spikes/headless/_private/ staged (gitignored client data, see its MANIFEST.md)
#    and the framework unpacked at _private/sdk/. Neither is in the repo.
#
#    ./run_gates.sh
#
# The native SDK prints libTIFF warnings to stderr while parsing embedded textures. They are noise
# from the image library, not from the model read, and are dropped here rather than silenced in the
# scripts — a gate that swallows its own stderr can hide a real error.
set -uo pipefail
cd "$(dirname "$0")"

P=_private
FAIL=0

run() {
  local label=$1; shift
  local out
  out=$(uv run "$@" 2>/dev/null | grep '^VERDICT') || true
  if [[ -z $out ]]; then
    echo "❌ $label — NO VERDICT LINE (the script failed; re-run it without 2>/dev/null)"
    FAIL=1
    return
  fi
  echo "$out"
  grep -q 'FAIL\|MISMATCH\|INCOMPLETE' <<<"$out" && FAIL=1
  return 0
}

echo "=== Spike A gates ==============================================================="
run "a3 header audit"   a3_header_audit.py --out "$P/out/a3_header_audit.json"
run "a0 expected"       a0_expected_answers.py --fixtures "$P/fixtures" \
                            --baseline "$P/baselines/corpus_baseline.json" \
                            --out "$P/out/a0_expected.json" --verify
run "a1 API surface"    a1_capi_surface.py --out "$P/out/a1_capi_surface.json" --cache "$P/out/.capi_cache"
run "a2 G0 boot"        a2_g0_boot.py --corpus "$P/corpus" --out "$P/out/a2_g0_boot.json"
run "a4 G1/G2/G3/G5"    a4_g1_g5_behaviour.py --corpus "$P/corpus" \
                            --expected "$P/out/a0_expected.json" --out "$P/out/a4_behaviour.json"
run "a5 G6/G7"          a5_g6_g7_geometry.py --corpus "$P/corpus" --fixtures "$P/fixtures" \
                            --out "$P/out/a5_geometry.json"
run "a6 G4"             a6_g4_marshal.py --corpus "$P/corpus" --fixtures "$P/fixtures" \
                            --out "$P/out/a6_marshal.json"
echo "================================================================================"
[[ $FAIL -eq 0 ]] && echo "SPIKE A: all gates green" || echo "SPIKE A: at least one gate is not green"
exit $FAIL
