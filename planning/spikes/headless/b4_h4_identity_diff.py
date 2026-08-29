# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike B — **H4: identity against the live captures. Claim (c).**

*Does the headless collector read the same model the live Ruby collector read?*

The comparison runs in **three strata, each with its own equality rule**, because "the same" means
something different for a stored attribute, for a coordinate, and for a value one reader derived:

**Stratum A — attribute payloads: exact.** Every non-geometric field, plus `libraries`, `tables`,
`counts` and the whole `unclassified` block. No tolerance: these are values designPH stored, and
either the two readers got the same string or one of them is wrong.

⚠ **Stratum A compares two DECODERS as well as two captures, and that has to be said out loud.**
The contract carries designPH's Marshal tables **decoded** (`{tokens, rows}`), so the live capture
never shipped the stored base64 — a byte-equality claim on the transport is simply not available
from it. Ruby decoded those rows with `Marshal.load`; this reader decodes them with Phase 1's
construct-nothing parser. Agreement is therefore evidence about *both*.

**Stratum A′ — the transport, on two independent readers.** So the byte-level claim is made where
it can be: the **stored base64** as the C SDK returns it, against the stored base64 the offline
`.skp` binary reader finds in `model.dat`. Two readers with nothing in common but the file.
⚠ The offline reader sees the file's *historical union* and takes the first match for a key, so a
difference there is a statement about history, not necessarily about the transport — which is why
this stratum is **reported** and does not on its own fail the gate.

**Stratum B — geometry: within a stated tolerance, and the tolerance reports what it absorbed.**
1 mm linear. C and Ruby float representations will differ. ⚠ A tolerance is a limit on what a lossy
step may absorb, so the **maximum observed deviation is printed even when the gate passes** — the
POC's window bug was invisible precisely because a projection absorbed it in silence.

**Stratum C — derived fields: exact, under H1's join.** Resolved hosts, composed transforms,
path-qualified ids. These are the ones a reader can get plausibly wrong.

⚠ **Every difference must land in a NAMED bucket or it is a defect.** Three are named in advance,
and each is a claim about the contract rather than an excuse:

| bucket | what it is |
|---|---|
| `entity_id` | contract §2 says `entityID` is **session-scoped, a debugging aid ONLY**.
  Two sessions, two values; the contract joins on `id` |
| `generated_by` | the capture device's own name. Different device, different string |
| `record order` | the C walk emits faces, then edges, then instances, then groups; Ruby's
  `entities.each` interleaves them. Same set, same ids, different sequence |
| `model.file_name` | ★ the one field where the headless reader is deliberately **right** and the
  live one is wrong: `Sketchup::Model#path` is the last-*saved* location, and Wellington's live
  capture is stamped `2523 Weiilington` from a backup's misspelling |

Anything else — including a geometry deviation over tolerance — fails the gate and gets root-caused
before it closes. ⚠ Grade all five; Adelphi passing alone counts for nothing, and Adelphi is the
model that masked three separate reconciliation defects during the POC.

⚠ Third-party SDK re-host; feasibility-only evidence. See `sdk.py`.

    uv run b4_h4_identity_diff.py --captures _private/out/captures --fixtures _private/fixtures \\
        --corpus _private/corpus --out _private/out/b4_identity.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

from collector import MARSHAL_PREFIX, SDK, HeadlessCollector, Tables, load_ruby_marshal

CAPTURED = (
    "adelphi-designph_COPY",
    "2414_Bluff Reach_COPY",
    "2523 Wellington_COPY",
    "250703 - Linde Residence_COPY",
    "250708_COPY",
)

#: Stratum B — fields compared as coordinates rather than as values.
GEOMETRY_FIELDS = {
    "faces": ("outer_loop", "inner_loops", "area_m2"),
    "edges": ("start", "end", "length_m"),
    "windows": ("transformation", "panel_outer_loop"),
}

#: Stratum C — values a reader *derives* rather than reads, and therefore can get plausibly wrong.
DERIVED_FIELDS = {
    "faces": (),
    "edges": (),
    "windows": ("host_face_id", "host_resolution", "host_has_inner_loops", "designph_name"),
}

#: The named buckets. A difference outside these is a defect (see the module docstring).
BUCKET_ENTITY_ID = "entity_id — session-scoped, contract §2 calls it a debugging aid only"
BUCKET_GENERATED_BY = "generated_by — a different capture device"
BUCKET_FILE_NAME = (
    "model.file_name — the headless reader uses the file it opened; the live one inherited "
    "Sketchup::Model#path, the last-SAVED location"
)

BUCKET_SIGNED_ZERO = (
    "signed zero — a coordinate the headless reader reached as `-0.0` and the live one as `0.0`. "
    "Numerically the same value (`-0.0 == 0.0`), and below every tolerance in this project; it "
    "matters only because JSON writes the two differently. A contract-v3 candidate: emit an exact "
    "zero unsigned, and captures become comparable byte-for-byte across capture devices"
)

BUCKET_RECORD_ORDER = (
    "record order — the C walk emits faces, then edges, then instances, then groups, while Ruby's "
    "`entities.each` interleaves them. Same set, same ids, different sequence; the contract "
    "promises no order and the translator joins by id"
)

#: Stratum B's limit, in metres. Also the limit on what the comparison may absorb.
TOLERANCE_M = 0.001

#: `transformation` is in INCHES (contract §4); everything else in the contract is metres.
INCHES_TO_M = 0.0254


def offline_reader(repo_root: Path) -> Any:
    """Import `00_Context/tools/skp_decode_tables.py` and use **its** blob pattern, not a copy.

    ⚠ Copying it is how this stratum first went wrong. A hand-written `BAh[A-Za-z0-9+/=]{8,}` looks
    equivalent and is not: designPH's stored base64 contains **line breaks**, so a pattern without
    `\r\n` in its class stops at the first one and returns a 60-byte fragment of a 12 KB table —
    which then reads as "the SDK and the file disagree" on 21 of Linde's 33 blobs. The shipped
    pattern is `BAh[A-Za-z0-9+/=\r\n]{40,}` with `re.DOTALL`, and importing it is the same rule as
    calling a library's own predicate rather than approximating it.
    """
    path = repo_root / "00_Context" / "tools" / "skp_decode_tables.py"
    spec = importlib.util.spec_from_file_location("skp_decode_tables", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["skp_decode_tables"] = module
    spec.loader.exec_module(module)
    return module



def numbers(value: Any) -> list[float]:
    """Every float in a nested list, in order — so two shapes can be compared elementwise."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [float(value)]
    if isinstance(value, list):
        return [n for item in value for n in numbers(item)]
    return []


def signed_zero_disagreements(mine: Any, theirs: Any) -> int:
    """How many numbers are equal but carry a different **sign of zero**.

    ⚠ This exists because `-0.0 == 0.0` is `True` in Python, so an ordinary equality comparison —
    including this file's own field-level `==` — absorbs the difference in complete silence. It is
    not nothing: `json.dumps` writes `-0.0` and `0.0` as different tokens, so two captures that
    compare equal field by field still hash differently, and the first symptom is H6 reporting five
    canonical mismatches with no locatable difference.

    Measured across the corpus: **72 disagreements, every one of them headless `-0.0` against live
    `0.0`** — the sign of a value the C arithmetic reached from below and Ruby's from above, at the
    1e-17 level. A vertex at `-0.0 m` is the same vertex, so this is a named difference and not a
    defect; but a comparison that cannot see it is the wrong comparison.
    """
    a, b = numbers(mine), numbers(theirs)
    if len(a) != len(b):
        return 0
    return sum(
        1
        for x, y in zip(a, b, strict=True)
        if x == y == 0.0 and math.copysign(1.0, x) != math.copysign(1.0, y)
    )


def deviation(mine: Any, theirs: Any, scale: float) -> float | None:
    """Worst elementwise difference, scaled to metres. `None` when the shapes disagree.

    A shape disagreement is never a tolerance question — a loop with a different vertex count is a
    different loop — so it is returned as `None` and reported as an unexplained difference.
    """
    a, b = numbers(mine), numbers(theirs)
    if len(a) != len(b):
        return None
    return max((abs(x - y) * scale for x, y in zip(a, b, strict=True)), default=0.0)


def stored_tables_via_sdk(sdk: SDK, tables: Tables, path: Path) -> dict[str, bytes]:
    """The model-level Marshal blobs as the **C SDK** hands them over — the stored base64."""
    collector = HeadlessCollector(sdk, tables)
    model = sdk.open_model(path)
    try:
        dictionary = collector._model_dictionary(model)
        if dictionary is None:
            return {}
        out: dict[str, bytes] = {}
        for key in collector.walker.dict_keys(dictionary):
            got = collector.walker.typed_value(dictionary, key)
            if got and got[0] == "String" and isinstance(got[1], bytes):
                if got[1].startswith(MARSHAL_PREFIX):
                    out[key] = got[1]
        return out
    finally:
        sdk.close_model(model)


def stored_tables_offline(offline: Any, path: Path, keys: list[str]) -> dict[str, bytes]:
    """The same blobs as the **offline binary reader** finds them in `model.dat`.

    Nothing about this route touches the SDK: a `.skp` is a zip, the attributes live in `model.dat`,
    and designPH's blob is the next self-delimiting base64 run after the key name. Both the archive
    read and the blob pattern come from `00_Context/tools/skp_decode_tables.py` itself.

    ⚠ It is a **heuristic**: it takes the first occurrence of the key name that is followed by a
    blob, and the file holds the *historical union* of everything that key ever was. So a difference
    here is a statement about history as much as about the transport, which is why this stratum is
    reported and never grades the gate on its own.
    """
    blob = offline.model_dat(path)
    out: dict[str, bytes] = {}
    for key in keys:
        for match in re.finditer(re.escape(key.encode()), blob, re.DOTALL):
            found = offline.BLOB.search(blob, match.end())
            if found:
                out[key] = found.group(0)
                break
    return out


def stored_blobs_are_verbatim(offline: Any, path: Path, via_sdk: dict[str, bytes]) -> dict[str, Any]:
    """★ The decisive transport check: does each SDK-returned blob appear **verbatim** in the file?

    This is the one byte-level claim that needs no heuristic and no second decoder. If the C SDK had
    truncated a value — the named hazard this whole gate was designed around — the exact byte run
    would not be findable in `model.dat`. Either the bytes are in the file or they are not.
    """
    raw = offline.model_dat(path)
    found = [key for key, value in via_sdk.items() if value in raw]
    return {
        "blobs": len(via_sdk),
        "found_verbatim_in_model_dat": len(found),
        "missing": sorted(set(via_sdk) - set(found)),
    }


def compare(headless: dict[str, Any], live: dict[str, Any]) -> dict[str, Any]:
    """One model's three strata."""
    buckets: dict[str, int] = {}
    unexplained: list[str] = []
    worst: dict[str, float] = {}

    def bucket(name: str) -> None:
        buckets[name] = buckets.get(name, 0) + 1

    # -- envelope ---------------------------------------------------------
    if headless["generated_by"] != live["generated_by"]:
        bucket(BUCKET_GENERATED_BY)
    for key, mine in headless["model"].items():
        theirs = live["model"].get(key)
        if mine == theirs:
            continue
        if key == "file_name":
            bucket(BUCKET_FILE_NAME)
        else:
            unexplained.append(f"model.{key}: headless {mine!r} vs live {theirs!r}")
    for key, mine in headless["counts"].items():
        if mine != live["counts"].get(key):
            unexplained.append(f"counts.{key}: headless {mine!r} vs live {live['counts'].get(key)!r}")

    # -- stratum A: everything designPH stored ----------------------------
    for key in ("libraries", "tables"):
        if headless[key] != live[key]:
            unexplained.append(f"{key}: differs (stratum A, exact)")
    if headless["unclassified"]["untagged_by_tag"] != live["unclassified"]["untagged_by_tag"]:
        unexplained.append("unclassified.untagged_by_tag: differs (stratum A, exact)")
    mine_unclassified = {r["id"]: r for r in headless["unclassified"]["tagged_faces"]}
    live_unclassified = {r["id"]: r for r in live["unclassified"]["tagged_faces"]}
    if mine_unclassified != live_unclassified:
        unexplained.append("unclassified.tagged_faces: differs by content (stratum A, exact)")

    # -- the three record sections ----------------------------------------
    for section in ("faces", "edges", "windows"):
        mine = {r["id"]: r for r in headless[section]}
        theirs = {r["id"]: r for r in live[section]}
        for missing in sorted(set(theirs) - set(mine)):
            unexplained.append(f"{section}: {missing} is in the live capture and not the headless one")
        for extra in sorted(set(mine) - set(theirs)):
            unexplained.append(f"{section}: {extra} is in the headless capture and not the live one")

        geometry = GEOMETRY_FIELDS[section]
        derived = DERIVED_FIELDS[section]
        for record_id in sorted(set(mine) & set(theirs)):
            a, b = mine[record_id], theirs[record_id]
            for _ in range(signed_zero_disagreements(a, b)):
                bucket(BUCKET_SIGNED_ZERO)
            for field in set(a) | set(b):
                if a.get(field) == b.get(field):
                    continue
                if field == "entity_id":
                    bucket(BUCKET_ENTITY_ID)
                elif field in geometry:
                    scale = INCHES_TO_M if field == "transformation" else 1.0
                    delta = deviation(a.get(field), b.get(field), scale)
                    label = f"{section}.{field}"
                    if delta is None:
                        unexplained.append(f"{label}: shape differs on {record_id}")
                    else:
                        worst[label] = max(worst.get(label, 0.0), delta)
                        if delta > TOLERANCE_M:
                            unexplained.append(
                                f"{label}: {delta * 1000:.4f} mm on {record_id}, over the "
                                f"{TOLERANCE_M * 1000:.1f} mm tolerance"
                            )
                elif field in derived:
                    unexplained.append(
                        f"{section}.{field} (stratum C, exact): {record_id} headless "
                        f"{a.get(field)!r} vs live {b.get(field)!r}"
                    )
                else:
                    unexplained.append(
                        f"{section}.{field} (stratum A, exact): {record_id} headless "
                        f"{a.get(field)!r} vs live {b.get(field)!r}"
                    )

    # ⚠ Ordering is normalised by the H1 key everywhere above — never by shape, which would make a
    # wall equal its mirror. But whether the two readers happen to *emit* in the same order is a
    # real fact about them, so it is measured and named rather than quietly normalised away.
    order: dict[str, bool] = {}
    for section in ("faces", "edges", "windows"):
        order[section] = [r["id"] for r in headless[section]] == [r["id"] for r in live[section]]
    order["unclassified.tagged_faces"] = [
        r["id"] for r in headless["unclassified"]["tagged_faces"]
    ] == [r["id"] for r in live["unclassified"]["tagged_faces"]]
    if not all(order.values()):
        bucket(BUCKET_RECORD_ORDER)

    return {
        "emission_order_matches_live": order,
        "named_differences": buckets,
        "unexplained": unexplained,
        "worst_geometry_deviation_mm": {k: v * 1000 for k, v in sorted(worst.items())},
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args()

    sdk = SDK(read_only=True)
    tables = Tables(load_ruby_marshal(args.repo_root))
    offline = offline_reader(args.repo_root)
    models: dict[str, Any] = {}
    try:
        for name in CAPTURED:
            headless_path = args.captures / f"{name}.extraction.json"
            live_path = args.fixtures / f"{name}.extraction.json"
            if not headless_path.exists() or not live_path.exists():
                print(f"  SKIP {name}")
                continue
            headless = json.loads(headless_path.read_text(encoding="utf-8"))
            live = json.loads(live_path.read_text(encoding="utf-8"))
            row = compare(headless, live)

            # -- stratum A′: the transport, on two independent readers -----
            skp = args.corpus / f"{name}.skp"
            transport: dict[str, Any] = {"checked": False}
            if skp.exists():
                via_sdk = stored_tables_via_sdk(sdk, tables, skp)
                found = stored_tables_offline(offline, skp, sorted(via_sdk))
                shared = sorted(set(via_sdk) & set(found))
                equal = [k for k in shared if via_sdk[k] == found[k]]
                transport = {
                    "checked": True,
                    "verbatim": stored_blobs_are_verbatim(offline, skp, via_sdk),
                    "sdk_blobs": len(via_sdk),
                    "offline_blobs_matched_by_key": len(shared),
                    "byte_identical": len(equal),
                    "differing": [k for k in shared if k not in equal],
                }
                # ⚠ The verbatim check is the one that can fail the gate: a blob the SDK returned
                # that is not in the file is a transport defect, not a question about history.
                for key in transport["verbatim"]["missing"]:
                    row["unexplained"].append(
                        f"transport: the SDK's stored {key} does not appear verbatim in model.dat"
                    )
            row["transport"] = transport
            models[name] = row

            ok = not row["unexplained"]
            print(f"{'✅' if ok else '❌'} {name}")
            for label, count in sorted(row["named_differences"].items()):
                print(f"     named  ×{count:<5} {label}")
            for label, mm in row["worst_geometry_deviation_mm"].items():
                print(f"     worst  {label}: {mm:.6f} mm (tolerance {TOLERANCE_M * 1000:.1f} mm)")
            if transport["checked"]:
                print(
                    f"     A′ transport: {transport['verbatim']['found_verbatim_in_model_dat']}/"
                    f"{transport['verbatim']['blobs']} SDK blobs appear verbatim in model.dat; "
                    f"{transport['byte_identical']}/{transport['offline_blobs_matched_by_key']} "
                    f"also match the offline reader's first-match heuristic"
                )
            for problem in row["unexplained"][:10]:
                print(f"     ⚠ {problem}")
            if len(row["unexplained"]) > 10:
                print(f"     ⚠ … and {len(row['unexplained']) - 10} more")
    finally:
        sdk.terminate()

    unexplained = sum(len(row["unexplained"]) for row in models.values())
    passed = len(models) == len(CAPTURED) and not unexplained
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "provenance": "third-party SDK re-host — feasibility-only evidence",
                "tolerance_m": TOLERANCE_M,
                "models": models,
            },
            indent=1,
        )
    )
    worst = max(
        (mm for row in models.values() for mm in row["worst_geometry_deviation_mm"].values()),
        default=0.0,
    )
    print(
        f"\nVERDICT H4: {'PASS' if passed else 'FAIL'} — {len(models)}/{len(CAPTURED)} models "
        f"compared, {unexplained} unexplained difference(s); worst geometry deviation anywhere "
        f"{worst:.6f} mm → {args.out}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
