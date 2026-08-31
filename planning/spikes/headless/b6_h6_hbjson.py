# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike B — **H6: HBJSON canonical equivalence.**

Does the *output* — the thing a certifier, a viewer or ph-navigator actually receives — come out the
same whether the model was read inside SketchUp or headlessly? H5 compared the translator's report;
this compares the HBJSON itself.

⚠ **The gate is CANONICAL equivalence, not byte equality, and that is not a concession.** Two
exports of one model are not the same file even on one machine: `honeybee_ph` gives every newly
*constructed* PH object a `uuid4` (152 distinct on Adelphi) and `honeybee-energy` builds four of its
lists with `list(set(...))`, ordered by a per-process `PYTHONHASHSEED`. ✅ Measured, and **not** an
upstream defect: `Model.from_dict` → `to_dict` preserves 152 of 152, and only 1 of the 152 is a real
cross-reference. The effect is diff noise between re-exports, nothing more
(`00_Context/HONEYBEE_STACK.md` §4).

★ **The canonicaliser is `pocs/01_sketchup-export/tools/byte_identity.py`'s own, imported rather than copied**, so this
gate cannot drift from the POC's — and so it inherits the one property that matters:

⚠ **A canonicaliser that normalises too much is a check that cannot fail.** It renumbers UUIDs
(numbered, not blanked, so *aliasing* stays visible — a segment pointing at the wrong site is still
a difference) and sorts exactly **four named lists**. Sorting every list would be catastrophic:
`boundary` vertex order *is* a face's orientation, so a shape-sorting canonicaliser would call a
wall and its mirror identical, inside the tool whose job is catching silent differences. Normalise
by name, never by shape.

⚠ **Read the shape of a failure before the failure.** Same size, different hash is the signature of
ordering. Different size *and* different hash, with identical content, is the same thing when the
reordered members have different name lengths (`Roof_02` vs `Wall_01B`) — which is exactly what
Adelphi does.

    uv run b6_h6_hbjson.py --translations _private/out/translated --out _private/out/b6_hbjson.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from harness import captured_models
from sdk import load_module


def load_canonicaliser(repo_root: Path) -> Any:
    """Import `pocs/01_sketchup-export/tools/byte_identity.py` and use **its** `canonicalise`, never a copy.

    Two canonicalisers would drift, and the failure mode of a drifted one is a check that quietly
    stops being able to fail. The module imports cleanly without running anything.
    """
    return load_module(repo_root / "pocs" / "01_sketchup-export" / "tools" / "byte_identity.py", "byte_identity")


def unsign_zeros(document: Any) -> tuple[Any, int]:
    """Turn `-0.0` into `0.0`, and **report how many it absorbed**.

    ⚠ A stated, narrow step applied ON TOP of the imported canonicaliser, never inside it: widening
    a shared canonicaliser is how a check quietly stops being able to fail, and `byte_identity.py`'s
    is the POC's `make identity` gate as well as this one's.

    Why it is needed at all: the two readers reach a coordinate of zero from opposite sides at the
    1e-17 level, so one writes `-0.0` where the other writes `0.0` — 72 times across the corpus,
    always in that direction. `-0.0 == 0.0` is `True`, so nothing *numeric* differs; `json.dumps`
    writes two different tokens, so the hash does. The count is printed either way, because a
    normalisation that never says what it swallowed is a normalisation nobody can audit.
    """
    absorbed = 0

    def walk(node: Any) -> Any:
        nonlocal absorbed
        if isinstance(node, dict):
            return {key: walk(value) for key, value in node.items()}
        if isinstance(node, list):
            return [walk(item) for item in node]
        if isinstance(node, float) and node == 0.0 and math.copysign(1.0, node) < 0:
            absorbed += 1
            return 0.0
        return node

    return walk(document), absorbed


def digest(document: Any) -> str:
    return hashlib.sha256(json.dumps(document, sort_keys=True).encode("utf-8")).hexdigest()


def first_difference(a: Any, b: Any, path: str = "") -> str | None:
    """Where two canonical documents first disagree — the *shape* of the failure, not just that it is one."""
    if type(a) is not type(b):
        return f"{path or '<root>'}: {type(a).__name__} vs {type(b).__name__}"
    if isinstance(a, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a:
                return f"{path}.{key}: only in the live translation"
            if key not in b:
                return f"{path}.{key}: only in the headless translation"
            found = first_difference(a[key], b[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: {len(a)} items vs {len(b)}"
        for index, (x, y) in enumerate(zip(a, b, strict=True)):
            found = first_difference(x, y, f"{path}[{index}]")
            if found:
                return found
        return None
    return None if a == b else f"{path}: {str(a)[:80]!r} vs {str(b)[:80]!r}"


#: Every perturbation the comparison must catch. ⚠ Each must be **exercised at least once across
#: the corpus**, not merely "not failed": `250708` carries no constructions at all (tier 3 × 92), so
#: a per-model skip is normal and a corpus-wide skip is the self-test quietly testing nothing.
SELF_TEST_CASES = ("moved vertex", "reversed winding", "renamed construction")


def self_test(canonicaliser: Any, document: Any) -> tuple[list[str], list[str]]:
    """⚠ Prove the comparison can still FAIL before trusting it to pass.

    Returns (failures, the cases this model was able to exercise).

    This gate renumbers every UUID, sorts four lists, absorbs signed zeros and takes its model name
    from an aligned input. That is a lot of normalising, and a canonicaliser that normalises too much
    is a check that cannot fail — the POC rendered a green banner for as long as its harness existed
    by grading the wrong boolean. So the document is perturbed three ways and each must be caught.

    **A reversed winding is deliberately one of them.** `boundary` order *is* a face's orientation,
    so a canonicaliser that sorted geometry would call a wall and its mirror identical, inside the
    tool whose job is catching silent differences.

    ⚠ It runs on **every** model, and the verdict requires each case to have been exercised
    somewhere. An earlier version ran on the first model only and printed "detects a moved vertex, a
    reversed winding and a renamed construction" whenever nothing *failed* — including when a case
    had been skipped for want of a target. That is the same defect as the POC's green banner, inside
    the check written to prevent it.
    """

    def detects(mutate: Any) -> bool:
        left, _ = unsign_zeros(canonicaliser.canonicalise(document))
        right, _ = unsign_zeros(canonicaliser.canonicalise(mutate))
        return digest(left) != digest(right)

    def copy() -> Any:
        return json.loads(json.dumps(document))

    failures: list[str] = []
    exercised: list[str] = []

    faces = document.get("rooms", [{}])[0].get("faces") or []
    if faces and faces[0].get("geometry", {}).get("boundary"):
        exercised += ["moved vertex", "reversed winding"]
        moved = copy()
        moved["rooms"][0]["faces"][0]["geometry"]["boundary"][0][0] += 1e-6
        if not detects(moved):
            failures.append("a vertex moved by 1 µm was NOT detected")
        flipped = copy()
        flipped["rooms"][0]["faces"][0]["geometry"]["boundary"].reverse()
        if not detects(flipped):
            failures.append("a reversed face winding was NOT detected — geometry is being sorted")

    if document.get("properties", {}).get("energy", {}).get("constructions"):
        exercised.append("renamed construction")
        renamed = copy()
        renamed["properties"]["energy"]["constructions"][0]["display_name"] += "!"
        if not detects(renamed):
            failures.append("a renamed construction was NOT detected")

    return failures, exercised


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--translations", type=Path, required=True, help="b5's --out-dir")
    parser.add_argument("--fixtures", type=Path, required=True, help="the live captures")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args()

    canonicaliser = load_canonicaliser(args.repo_root)
    expected = captured_models(args.fixtures)
    models: dict[str, Any] = {}
    self_test_failures: list[str] = []
    self_test_exercised: set[str] = set()

    for name in expected:
        # ⚠ The NAME-ALIGNED headless translation (b5): the same headless capture with
        # `model.file_name` set to the live capture's, so the only remaining difference is what the
        # two readers read. The alignment happens in the input and is recorded there; nothing about
        # the output is normalised for it here.
        headless_path = args.translations / f"{name}.headless-aligned.hbjson.json"
        live_path = args.translations / f"{name}.live.hbjson.json"
        if not headless_path.exists() or not live_path.exists():
            print(f"  SKIP {name} — run b5_h5_translate.py first")
            continue
        headless_result = json.loads(headless_path.read_text(encoding="utf-8"))
        live_result = json.loads(live_path.read_text(encoding="utf-8"))
        headless = json.loads(headless_result["hbjson"])
        live = json.loads(live_result["hbjson"])


        raw = {"headless": digest(headless), "live": digest(live)}
        canonical_headless = canonicaliser.canonicalise(headless)
        canonical_live = canonicaliser.canonicalise(live)
        canonical = {"headless": digest(canonical_headless), "live": digest(canonical_live)}
        # Both hashes are reported: the one before the signed-zero step and the one after, so the
        # step's effect is visible rather than assumed.
        canonical_headless, absorbed_headless = unsign_zeros(canonical_headless)
        canonical_live, absorbed_live = unsign_zeros(canonical_live)
        unsigned = {"headless": digest(canonical_headless), "live": digest(canonical_live)}
        equal = unsigned["headless"] == unsigned["live"]
        difference = None if equal else first_difference(canonical_headless, canonical_live)

        failures, exercised = self_test(canonicaliser, headless)
        self_test_failures.extend(f"{name}: {f}" for f in failures)
        self_test_exercised.update(exercised)

        models[name] = {
            "bytes": {
                "headless": len(json.dumps(headless)),
                "live": len(json.dumps(live)),
            },
            "raw_sha256": raw,
            "canonical_sha256": canonical,
            "canonical_unsigned_zero_sha256": unsigned,
            "negative_zeros_absorbed": {"headless": absorbed_headless, "live": absorbed_live},
            "canonically_identical": equal,
            "first_difference": difference,
        }
        size = models[name]["bytes"]
        print(
            f"{'✅' if equal else '❌'} {name}: canonical {unsigned['headless'][:16]} vs "
            f"{unsigned['live'][:16]} · raw hashes "
            f"{'differ' if raw['headless'] != raw['live'] else 'match'} · "
            f"{size['headless']} vs {size['live']} bytes · signed zeros absorbed "
            f"{absorbed_headless}/{absorbed_live}"
        )
        if difference:
            print(f"     ⚠ first difference: {difference}")

    identical = sum(1 for row in models.values() if row["canonically_identical"])
    unexercised = sorted(set(SELF_TEST_CASES) - self_test_exercised)
    passed = (
        len(models) == len(expected)
        and identical == len(models)
        and not self_test_failures
        and not unexercised
    )
    print(
        f"{'✅' if not self_test_failures and not unexercised else '❌'} self-test: the comparison "
        f"detected {sorted(self_test_exercised)} across the corpus"
    )
    for failure in self_test_failures:
        print(f"     ⚠ {failure}")
    for case in unexercised:
        print(f"     ⚠ '{case}' was never exercised on any model — the self-test proved nothing about it")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "provenance": "third-party SDK re-host — feasibility-only evidence",
                "canonicaliser": "pocs/01_sketchup-export/tools/byte_identity.py:canonicalise (imported, not copied)",
                "self_test_failures": self_test_failures,
                "self_test_cases_exercised": sorted(self_test_exercised),
                "self_test_cases_never_exercised": unexercised,
                "models": models,
            },
            indent=1,
        )
    )
    print(
        f"\nVERDICT H6: {'PASS' if passed else 'FAIL'} — {identical}/{len(models)} models produce "
        f"canonically identical HBJSON from the headless and the live capture → {args.out}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
