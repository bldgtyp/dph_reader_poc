# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike A — the behavioural gates: G1 (glue), G2 (typed attrs), G3 (edges), G5 (live state).

Graded against `a0_expected_answers.json`, which is derived from the five live SketchUp captures —
never against the plan's prose, and never against a number typed into this file.

⚠ Third-party SDK re-host; feasibility-only evidence. See `sdk.py`.

    uv run a4_g1_g5_behaviour.py --corpus _private/corpus \
        --expected _private/out/a0_expected.json --out _private/out/a4_behaviour.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from ctypes import byref, c_size_t
from pathlib import Path

from sdk import SDK, SUDrawingElementRef
from walk import Walker

# Capture `model.file_name` is unreliable (Wellington reports the backup's misspelling), so the
# corpus copy is matched to its expectation by FILE stem, the same rule a0 uses.
CORPUS_TO_EXPECTED = {
    "adelphi-designph_COPY.skp": "adelphi-designph_COPY.extraction.json",
    "2414_Bluff Reach_COPY.skp": "2414_Bluff Reach_COPY.extraction.json",
    "2523 Wellington_COPY.skp": "2523 Wellington_COPY.extraction.json",
    "250703 - Linde Residence_COPY.skp": "250703 - Linde Residence_COPY.extraction.json",
    "250708_COPY.skp": "250708_COPY.extraction.json",
}

AREA_GROUP_KEYS = ("areaGroupID", "areaGroupAuto")  # ⚠ no "ID" on the fallback

# ⚠ A designPH window is NOT a `DesignPH_dict` carrier. It is a SketchUp **Dynamic Component**, and
# its designPH data lives in the `dynamic_attributes` dictionary; the collector identifies one by the
# presence of the `frametypeid` key (`collector.rb:53,136`). Filtering instances on `DesignPH_dict`
# finds zero windows on Adelphi — which is what this script did until it matched the collector.
DC_DICT = "dynamic_attributes"
WINDOW_MARKER = "frametypeid"


def classify(nodes, walker: Walker):
    """Split the walk into designPH-tagged faces / edges / windows, on an ENTITY basis."""
    faces_tagged, faces_classified, edges_tagged, windows = {}, {}, {}, {}
    type_tags: Counter[str] = Counter()

    for node in nodes:
        if node.kind == "window":
            dc = walker.dictionary(node.ref, DC_DICT)
            if dc is not None and walker.typed_value(dc, WINDOW_MARKER) is not None:
                windows[node.leaf] = node
            continue

        d = walker.dictionary(node.ref)
        if d is None:
            continue
        if node.kind == "edge":
            edges_tagged[node.leaf] = node
            continue

        faces_tagged[node.leaf] = node
        for key in AREA_GROUP_KEYS:
            got = walker.typed_value(d, key)
            if got is None:
                continue
            tag, value = got
            type_tags[f"{key}:{tag}"] += 1
            # designPH marks "unclassified" with the STRING 'n'; an integer is a real area group.
            if tag == "Int32":
                faces_classified[node.leaf] = (node, value)
                break
    return faces_tagged, faces_classified, edges_tagged, windows, type_tags


def glue_hosts(sdk: SDK, walker: Walker, windows: dict) -> tuple[dict[str, int], dict[str, str]]:
    """G1: ask each tagged instance which drawing element(s) it is glued to."""
    methods: Counter[str] = Counter()
    host_of: dict[str, str] = {}
    for leaf, node in windows.items():
        n = c_size_t()
        sdk.call("SUComponentInstanceGetNumAttachedToDrawingElements", node.ref, byref(n),
                 tolerate=(2, 8, 9))
        if not n.value:
            methods["UNRESOLVED"] += 1
            continue
        arr = (SUDrawingElementRef * n.value)()
        got = c_size_t()
        sdk.call("SUComponentInstanceGetAttachedToDrawingElements", node.ref, n.value, arr, byref(got))
        if got.value:
            methods["glued_to"] += 1
            host_of[leaf] = str(walker.persistent_id(arr[0]))
        else:
            methods["UNRESOLVED"] += 1
    return dict(methods), host_of


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--expected", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--only", default=None, help="run one corpus file only")
    args = ap.parse_args()

    expected = json.loads(args.expected.read_text(encoding="utf-8"))["models"]
    sdk = SDK()
    walker = Walker(sdk)
    results: dict[str, dict] = {}

    for skp, exp_key in sorted(CORPUS_TO_EXPECTED.items()):
        if args.only and args.only not in skp:
            continue
        path = args.corpus / skp
        if not path.exists():
            print(f"  SKIP {skp}: not staged")
            continue
        exp = expected[exp_key]

        model = sdk.open_model(path)
        try:
            # ENTITY basis — see walk_entities' docstring for why this is not walk().
            nodes = list(walker.walk_entities(model))
            faces_tagged, faces_classified, edges, windows, type_tags = classify(nodes, walker)
            methods, host_of = glue_hosts(sdk, walker, windows)
        finally:
            sdk.close_model(model)

        row = {
            "face_entities_visited": sum(1 for n in nodes if n.kind == "face"),
            "entities_tagged": len(faces_tagged),
            "entities_classified": len(faces_classified),
            "edges_tagged": len(edges),
            "windows_found": len(windows),
            "hosts_resolved": len(host_of),
            "host_methods": methods,
            "distinct_host_faces": len(set(host_of.values())),
            "type_tags": dict(type_tags),
            "expected": {
                "entities_tagged": exp["entities_tagged"],
                "entities_classified": exp["entities_classified"],
                "edges_tagged": exp["edges_tagged"],
                "windows_found": exp["windows_found"],
                "hosts_resolved": exp["hosts_resolved"],
                "distinct_host_faces": exp["distinct_host_faces"],
            },
        }
        row["match"] = {
            k: (row[k] == v) for k, v in row["expected"].items()
        }
        results[skp] = row

        ok = all(row["match"].values())
        print(f"{'✅' if ok else '❌'} {skp}")
        for k, want in row["expected"].items():
            got = row[k]
            print(f"     {'ok  ' if got == want else 'DIFF'} {k:<22} sdk={got:<7} live capture={want}")
        print(f"          host methods: {methods}")

    sdk.terminate()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        {"provenance": "third-party SDK re-host — feasibility-only evidence", "models": results}, indent=1))

    tot = {k: sum(r[k] for r in results.values()) for k in
           ("entities_classified", "windows_found", "edges_tagged", "hosts_resolved")}
    want = {k: sum(r["expected"][k] for r in results.values()) for k in tot}
    all_ok = all(all(r["match"].values()) for r in results.values())
    print(
        f"\nVERDICT G1/G2/G3/G5: {'PASS' if all_ok else 'MISMATCH'} — across {len(results)} models: "
        f"classified {tot['entities_classified']}/{want['entities_classified']} · "
        f"windows {tot['windows_found']}/{want['windows_found']} · "
        f"edges {tot['edges_tagged']}/{want['edges_tagged']} · "
        f"glued hosts {tot['hosts_resolved']}/{want['hosts_resolved']} → {args.out}"
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
