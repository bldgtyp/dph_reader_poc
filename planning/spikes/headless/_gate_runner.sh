# Shared runner for the Spike A and Spike B gate scripts. Sourced, never executed.
#
# ⛔ **Grades on the gate's EXIT CODE, and prints its VERDICT line.** Every gate already returns
# `0 if passed else 1`; an earlier version threw that away and re-derived the result by
# substring-matching the gate's own human-readable sentence. That is the exact shape of the defect
# the POC recorded and paid for: a banner that stayed green for the life of its harness because the
# harness graded one field and the UI rendered another. Concretely, grading the prose meant a gate
# that crashed *after* printing its VERDICT line reported green, and any future gate whose failure
# wording avoided three magic tokens was invisible.
#
# The VERDICT lines are display. The exit code decides.
#
# ⚠ The native SDK prints libTIFF warnings to stderr while parsing embedded textures. They are noise
# from the image library, not from the model read, and are dropped here rather than silenced in the
# scripts — a gate that swallows its own stderr can hide a real error.

FAIL=0

run() {
  local label=$1; shift
  local out status
  out=$(uv run "$@" 2>/dev/null)
  status=$?
  if [[ $status -ne 0 ]]; then
    FAIL=1
  fi
  if grep -q '^VERDICT' <<<"$out"; then
    grep '^VERDICT' <<<"$out"
  else
    echo "❌ $label — NO VERDICT LINE (exit $status; re-run it without 2>/dev/null)"
    FAIL=1
  fi
}

finish() {
  local phase=$1
  echo "================================================================================"
  if [[ $FAIL -eq 0 ]]; then
    echo "$phase: all gates green"
  else
    echo "$phase: at least one gate is not green"
  fi
  exit $FAIL
}
