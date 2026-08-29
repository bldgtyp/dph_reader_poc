# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike A, step 1 — does the published SketchUp C API expose what every gate needs?

**Why this runs before the SDK is in hand.** The SDK *binary* is no longer a public download
(2026-08-28: `extensions.sketchup.com/sketchup-sdk` serves a holding page — "not available for
public download at this time", verified while signed in on a Trimble developer account). The
*reference documentation* is still fully public, so the question "does the API expose the glue
relationship at all?" — Spike A's decisive G1 — can be answered from the docs while the binary is
blocked. It is a documentation answer, not a behavioural one, and this script labels it as such.

This is the repo's own rule pointed at a blocker: **ask what the data already on hand constrains
before booking the thing you cannot get.** The doxygen tree constrains G1, G2, G3, G4, G6 and G7.
It cannot constrain G5 (live vs historical) or G6's *semantics* (net vs gross) — only running the
thing can, and this script says so instead of implying coverage it does not have.

Harvests every `SU*` function off the doxygen struct + header pages, caches them, and reports
present/absent per gate with a verdict line.

    uv run a1_capi_surface.py --out _private/out/a1_capi_surface.json
    uv run a1_capi_surface.py --out _private/out/a1_capi_surface.json --cache .capi_cache --refresh
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

DOCS = "https://extensions.sketchup.com/developers/sketchup_c_api/sketchup"

# doxygen renders struct member functions in the right-hand cell of the member table, and free
# functions (SUInitialize and friends live in initialize.h, not on any struct) as plain `el` links
# on the header page. Harvesting only the first pattern reports SUInitialize as ABSENT — which it
# is not. Two patterns, deliberately.
MEMBER_FN = re.compile(r'memItemRight"[^>]*><a class="el" href="[^"]*">(SU[A-Za-z0-9_]+)</a>')
ANY_FN = re.compile(r'<a class="el" href="[^"]*">(SU[A-Za-z0-9_]+)</a>\s*\(')

# Header pages carrying free functions that belong to no struct.
FREE_FUNCTION_PAGES = ("initialize_8h.html",)

# What each gate in HEADLESS-A_sdk-feasibility.md §3 actually calls.
GATES: dict[str, tuple[str, list[str]]] = {
    "G0": (
        "boot: load the dylib, open a model, report its version",
        ["SUInitialize", "SUTerminate", "SUGetAPIVersion", "SUModelCreateFromFile",
         "SUModelCreateFromFileWithStatus", "SUModelGetVersion", "SUModelRelease"],
    ),
    "G1": (
        "THE DECISIVE GATE — is the window→host glue relationship queryable?",
        ["SUComponentInstanceGetAttachedToDrawingElements",
         "SUComponentInstanceGetNumAttachedToDrawingElements",
         # ⚠ points the OTHER way (things glued TO this instance). Named so the two are not confused.
         "SUComponentInstanceGetAttachedInstances",
         "SUComponentInstanceGetNumAttachedInstances",
         # the host-side cross-check
         "SUFaceGetOpenings", "SUFaceGetNumOpenings", "SUOpeningGetNumPoints", "SUOpeningGetPoints"],
    ),
    "G2": (
        "typed attribute reads, uncoerced, off every carrier type",
        ["SUEntityGetNumAttributeDictionaries", "SUEntityGetAttributeDictionaries",
         "SUEntityGetAttributeDictionary", "SUAttributeDictionaryGetValue",
         "SUAttributeDictionaryGetKeys", "SUAttributeDictionaryGetNumKeys",
         "SUAttributeDictionaryGetName", "SUTypedValueGetType", "SUTypedValueGetString",
         "SUTypedValueGetInt32", "SUTypedValueGetDouble", "SUTypedValueGetBool",
         "SUTypedValueCreate", "SUTypedValueRelease"],
    ),
    "G3": (
        "edges enumerate with their dictionaries, at depth, on an ENTITY basis",
        ["SUEntitiesGetNumEdges", "SUEntitiesGetEdges", "SUEdgeGetStartVertex", "SUEdgeGetEndVertex",
         "SUEdgeToEntity", "SUVertexGetPosition", "SUEntitiesGetNumInstances", "SUEntitiesGetInstances",
         "SUEntitiesGetNumGroups", "SUEntitiesGetGroups", "SUComponentInstanceGetDefinition",
         "SUComponentDefinitionGetEntities", "SUGroupGetEntities",
         # the two id flavours the contract emits: persistent (stable) and entity (session-local)
         "SUEntityGetPersistentID", "SUEntityGetID"],
    ),
    "G4": (
        "Marshal tables byte-clean — length-aware string reads, never a NUL-terminated copy",
        ["SUStringGetUTF8Length", "SUStringGetUTF8", "SUStringCreate", "SUStringRelease",
         "SUModelGetAttributeDictionary", "SUModelGetNumAttributeDictionaries",
         "SUModelGetAttributeDictionaries"],
    ),
    "G6": (
        "face area and loops — the net-vs-gross probe",
        ["SUFaceGetArea", "SUFaceGetAreaWithTransform", "SUFaceGetOuterLoop", "SUFaceGetNumInnerLoops",
         "SUFaceGetInnerLoops", "SULoopGetNumVertices", "SULoopGetVertices", "SUFaceGetNormal",
         "SUFaceGetPlane"],
    ),
    "G7": (
        "world transforms compose through the nesting hierarchy",
        ["SUComponentInstanceGetTransform", "SUGroupGetTransform", "SUTransformationMultiply",
         "SUComponentInstanceGetName", "SUComponentDefinitionGetName"],
    ),
    "G8": (
        "file-version coverage",
        ["SUModelGetVersion", "SUModelGetGuid", "SUModelGetName", "SUModelGetStatistics"],
    ),
}

# Gates this script CANNOT speak to. Listing them is the point: a coverage claim that quietly omits
# what it does not cover is the failure this repo calls "a harness that grades the wrong boolean".
DOCS_CANNOT_ANSWER = {
    "G5": "live-vs-historical state — only opening a real model answers it",
    "G6 (semantics)": "whether SUFaceGetArea is NET of glued openings like Ruby's face.area, or gross",
    "G1 (behaviour)": "whether the glue query actually returns the 239 hosts on real designPH models",
    "G8 (behaviour)": "whether all 15 corpus files actually open, incl. the pre-2014 sample",
}


def fetch(url: str, cache: Path | None, refresh: bool) -> str:
    if cache is not None:
        hit = cache / re.sub(r"[^A-Za-z0-9_.-]", "_", url.rsplit("/", 1)[-1])
        if hit.exists() and not refresh:
            return hit.read_text(encoding="utf-8", errors="replace")
    with urllib.request.urlopen(url, timeout=30) as r:  # noqa: S310 — fixed vendor docs host
        text = r.read().decode("utf-8", errors="replace")
    if cache is not None:
        cache.mkdir(parents=True, exist_ok=True)
        (cache / re.sub(r"[^A-Za-z0-9_.-]", "_", url.rsplit("/", 1)[-1])).write_text(text)
    return text


def harvest(cache: Path | None, refresh: bool) -> tuple[set[str], int]:
    """Every SU* function the published docs define, across all struct pages plus the free-function headers."""
    annotated = fetch(f"{DOCS}/annotated.html", cache, refresh)
    pages = sorted(set(re.findall(r'href="(struct_[a-z0-9_]+\.html)"', annotated)))
    if not pages:
        raise SystemExit("annotated.html listed no struct pages — the docs layout changed; fix the scrape")

    found: set[str] = set()
    for page in pages:
        found |= set(MEMBER_FN.findall(fetch(f"{DOCS}/{page}", cache, refresh)))
    for page in FREE_FUNCTION_PAGES:
        found |= set(ANY_FN.findall(fetch(f"{DOCS}/{page}", cache, refresh)))
    return found, len(pages)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True, help="explicit output path")
    ap.add_argument("--cache", type=Path, default=None, help="dir to cache fetched doc pages")
    ap.add_argument("--refresh", action="store_true", help="re-fetch even if cached")
    args = ap.parse_args()

    api, n_pages = harvest(args.cache, args.refresh)
    print(f"Published SketchUp C API: {len(api)} functions across {n_pages} struct pages + "
          f"{len(FREE_FUNCTION_PAGES)} free-function header(s)\nSource: {DOCS}\n")

    missing_by_gate: dict[str, list[str]] = {}
    for gate, (why, fns) in GATES.items():
        absent = [f for f in fns if f not in api]
        missing_by_gate[gate] = absent
        print(f"{gate}  {'PRESENT' if not absent else 'INCOMPLETE'}  — {why}")
        for f in fns:
            print(f"      {'ok ' if f in api else 'ABSENT'}  {f}")

    print("\nWhat this script CANNOT answer (documentation is not behaviour):")
    for gate, why in DOCS_CANNOT_ANSWER.items():
        print(f"      {gate}: {why}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "source": DOCS,
        "note": "API-surface presence only. Documentation-level evidence; no SDK binary was executed.",
        "function_count": len(api),
        "struct_pages": n_pages,
        "gates": {g: {"why": w, "required": f, "absent": missing_by_gate[g]} for g, (w, f) in GATES.items()},
        "docs_cannot_answer": DOCS_CANNOT_ANSWER,
        "all_functions": sorted(api),
    }, indent=1))

    incomplete = [g for g, m in missing_by_gate.items() if m]
    g1_ok = not missing_by_gate["G1"]
    print(
        f"\nVERDICT a1: {'ALL GATES COVERED' if not incomplete else 'INCOMPLETE: ' + ', '.join(incomplete)}"
        f" — G1 (the decisive gate) is {'ANSWERED YES at the documentation level' if g1_ok else 'NOT COVERED'};"
        f" both glue directions{'' if g1_ok else ' NOT'} published → {args.out}"
    )
    return 1 if incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
