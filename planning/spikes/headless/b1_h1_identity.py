# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike B — **H1: entity identity, the join key.**

Comparing two captures of one model needs a way to say *this face here is that face there*. H1
asserts what that key is and measures that it holds, because everything above it — H4's diff, H6's
equivalence, and pholio's rule that ids come from the capture device and are never minted per
export — is graded through it.

★ **Spike A pre-answered this** (HEADLESS-B §2.1): the path-qualified id reconstructed from
`SUEntityGetPersistentID` matched the live captures on 545/545 faces and 239/239 windows, 0
unmatched. So this gate is a cheap explicit assertion rather than an open question, and it records
per-file coverage rather than discovering a scheme.

Three links the pre-spike review asked to verify on the way, and all three are checked here:

**(a) the C-side names.** `SUEntityGetID` (the session-scoped 32-bit id) *and*
`SUEntityGetPersistentID` must both exist — confirmed against the **shipped headers**, not a doc
page, because a published name is not a signature and the wrong guess passes on the first model.

**(b) persistent ids are stored in-file** only for files written by SketchUp versions that record
them. The capture files were written by SketchUp 22-26 so this is expected to hold, but it is
recorded per file: a model whose persistent ids are all zero would join everything to everything.

**(c) the contract's id is PATH-QUALIFIED**, so the C side must compose the same path of entities
in the same order. That is what the join actually tests — a leaf-only match would pass while every
placement was mislabelled.

⚠ **The fallback is a matcher, and a matcher is itself a new check.** If persistent ids ever fail
to align, joining on (dictionary fingerprint + geometry within tolerance) is allowed — but then
claim (c) is graded through something whose own misses must be counted and reported. An unmatched
entity is a finding, never a dropped row.

⚠ Third-party SDK re-host; feasibility-only evidence. See `sdk.py`.

    uv run b1_h1_identity.py --captures _private/out/captures --fixtures _private/fixtures \\
        --out _private/out/b1_identity.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from a3_header_audit import DEFAULT_HEADERS, parse_headers
from collector import RECORD_SECTIONS
from harness import captured_models, write_result

#: (a) — both must be exported and declared, and the *persistent* one is the identity.
ID_FUNCTIONS = ("SUEntityGetID", "SUEntityGetPersistentID")


def ids_of(document: dict[str, Any], section: str) -> dict[str, dict[str, Any]]:
    return {record["id"]: record for record in document[section]}


def path_parts(record_id: str) -> list[str]:
    """`kind_<ancestor pids…>_<own pid>` → the numeric parts, in order (contract §2.1)."""
    return record_id.split("_")[1:]


def coverage(document: dict[str, Any]) -> dict[str, Any]:
    """(b) + (c): are the persistent ids real, and is the path actually composed?

    A model whose persistent ids came back as zeros would produce ids like `face_0_0` — every
    entity colliding with every other — and a join would still "succeed" at 100 %. Counting the
    zeros and the path depths is what separates a real match from a degenerate one.
    """
    zero = 0
    total = 0
    depths: dict[int, int] = {}
    for section in RECORD_SECTIONS:
        for record in document[section]:
            parts = path_parts(record["id"])
            total += 1
            if any(part == "0" for part in parts):
                zero += 1
            depths[len(parts) - 1] = depths.get(len(parts) - 1, 0) + 1
    return {
        "entities": total,
        "with_a_zero_persistent_id": zero,
        "path_depths": dict(sorted(depths.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--captures", type=Path, required=True, help="headless captures")
    parser.add_argument("--fixtures", type=Path, required=True, help="the five live captures")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--headers", type=Path, default=DEFAULT_HEADERS)
    args = parser.parse_args()

    header_functions = parse_headers(args.headers)
    absent = [name for name in ID_FUNCTIONS if name not in header_functions]

    expected_models = captured_models(args.fixtures)
    models: dict[str, Any] = {}
    for name in expected_models:
        headless_path = args.captures / f"{name}.extraction.json"
        live_path = args.fixtures / f"{name}.extraction.json"
        if not headless_path.exists() or not live_path.exists():
            print(f"  SKIP {name}")
            continue
        headless = json.loads(headless_path.read_text(encoding="utf-8"))
        live = json.loads(live_path.read_text(encoding="utf-8"))

        row: dict[str, Any] = {"coverage": coverage(headless), "sections": {}}
        for section in RECORD_SECTIONS:
            mine, theirs = ids_of(headless, section), ids_of(live, section)
            row["sections"][section] = {
                "live": len(theirs),
                "headless": len(mine),
                "matched": len(set(mine) & set(theirs)),
                # ⚠ Counts as well as names: the truncated lists cannot tell you *how many* were
                # unmatched, only the first ten, and the count is what the verdict grades on.
                "unmatched_live": len(set(theirs) - set(mine)),
                "unmatched_headless": len(set(mine) - set(theirs)),
                "only_live": sorted(set(theirs) - set(mine))[:10],
                "only_headless": sorted(set(mine) - set(theirs))[:10],
            }
        models[name] = row

        unmatched = sum(
            s["unmatched_live"] + s["unmatched_headless"] for s in row["sections"].values()
        )
        totals = " · ".join(
            f"{k} {v['matched']}/{v['live']}" for k, v in row["sections"].items()
        )
        print(f"{'✅' if not unmatched else '❌'} {name}: {totals}")
        print(
            f"     paths: depths {row['coverage']['path_depths']}, "
            f"{row['coverage']['with_a_zero_persistent_id']} of "
            f"{row['coverage']['entities']} ids carry a zero persistent id"
        )

    matched = sum(s["matched"] for m in models.values() for s in m["sections"].values())
    expected = sum(s["live"] for m in models.values() for s in m["sections"].values())
    # ⚠ Both directions. An earlier version graded only `matched == sum(live)`, so a record present
    # in the headless capture and absent from the live one did not affect the verdict — in the gate
    # that establishes the join key everything above it is graded through.
    emitted = sum(s["headless"] for m in models.values() for s in m["sections"].values())
    zeros = sum(m["coverage"]["with_a_zero_persistent_id"] for m in models.values())
    # ⚠ A join is only evidence if the ids it joins on are distinguishing. A model whose paths were
    # all depth 0 with zero pids would match 100 % and mean nothing — so nesting must be exercised.
    nested = any(depth > 0 for m in models.values() for depth in m["coverage"]["path_depths"])
    passed = (
        len(models) == len(expected_models)
        and matched == expected == emitted
        and not zeros
        and not absent
        and nested
    )

    write_result(
        args.out,
        {
            "header_functions_present": {n: n not in absent for n in ID_FUNCTIONS},
            "models": models,
        },
    )
    print(
        f"\nVERDICT H1: {'PASS' if passed else 'FAIL'} — {matched}/{expected} entities join on the "
        f"path-qualified persistent id across {len(models)} models, {zeros} degenerate ids, "
        f"{'both' if not absent else 'MISSING ' + ','.join(absent)} id functions in the headers "
        f"→ {args.out}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
