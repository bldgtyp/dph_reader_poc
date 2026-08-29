# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike A — G0, the boot pre-gate. Nothing else runs until this passes.

Load the framework, report its architecture and API version, confirm every symbol the later gates
name is actually **exported by the binary** (a doxygen name is not a symbol), then open every staged
corpus copy and report its file-format version. That last part is G8's mechanical half, folded in
here because it is the same loop and it costs nothing.

⚠ Runs against a third-party re-host of Trimble's SDK — see `sdk.py`'s provenance note.
Feasibility-only evidence.

    uv run a2_g0_boot.py --corpus _private/corpus --out _private/out/a2_g0_boot.json
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
from pathlib import Path

from sdk import SDK, SUResultError

# Every symbol the eight gates call. Checked against the loaded binary's export table, because the
# published docs describe an SDK generation that may not be the one on disk.
REQUIRED_SYMBOLS = {
    "G0": ["SUInitialize", "SUTerminate", "SUGetAPIVersion", "SUModelCreateFromFile",
           "SUModelGetVersion", "SUModelRelease"],
    "G1": ["SUComponentInstanceGetAttachedToDrawingElements",
           "SUComponentInstanceGetNumAttachedToDrawingElements",
           "SUFaceGetOpenings", "SUFaceGetNumOpenings"],
    "G2": ["SUEntityGetAttributeDictionary", "SUEntityGetAttributeDictionaries",
           "SUEntityGetNumAttributeDictionaries", "SUAttributeDictionaryGetValue",
           "SUAttributeDictionaryGetKeys", "SUAttributeDictionaryGetNumKeys",
           "SUTypedValueGetType", "SUTypedValueGetString", "SUTypedValueGetInt32",
           "SUTypedValueGetDouble", "SUTypedValueGetBool"],
    "G3": ["SUEntitiesGetEdges", "SUEntitiesGetNumEdges", "SUEntitiesGetInstances",
           "SUEntitiesGetGroups", "SUComponentInstanceGetDefinition",
           "SUComponentDefinitionGetEntities", "SUGroupGetEntities",
           "SUEntityGetPersistentID", "SUEntityGetID", "SUEdgeGetStartVertex", "SUEdgeGetEndVertex"],
    "G4": ["SUStringGetUTF8Length", "SUStringGetUTF8", "SUModelGetAttributeDictionaries",
           "SUModelGetNumAttributeDictionaries"],
    "G6": ["SUFaceGetArea", "SUFaceGetOuterLoop", "SUFaceGetNumInnerLoops", "SULoopGetVertices",
           "SUVertexGetPosition"],
    "G7": ["SUComponentInstanceGetTransform", "SUGroupGetTransform"],
    "G8": ["SUModelGetVersion", "SUModelGetName"],
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", type=Path, required=True, help="dir of staged .skp COPIES")
    ap.add_argument("--out", type=Path, required=True, help="explicit output path")
    ap.add_argument("--framework", type=Path, default=None)
    args = ap.parse_args()

    sdk = SDK(args.framework)
    arch = subprocess.run(["lipo", "-info", str(sdk.path)], capture_output=True, text=True).stdout.strip()
    api_major, api_minor = sdk.api_version()
    print(f"framework : {sdk.path}")
    print(f"arch      : {arch}")
    print(f"host      : {platform.machine()} / CPython {platform.python_version()}")
    print(f"API       : {api_major}.{api_minor}\n")

    # -- symbols ---------------------------------------------------------
    missing: dict[str, list[str]] = {}
    for gate, names in REQUIRED_SYMBOLS.items():
        absent = sdk.missing(names)
        if absent:
            missing[gate] = absent
        print(f"symbols {gate}: {'all present' if not absent else 'MISSING ' + ', '.join(absent)}")

    # -- open every corpus copy (G8's mechanical half) --------------------
    print()
    models: dict[str, dict[str, object]] = {}
    for path in sorted(args.corpus.glob("*.skp")):
        entry: dict[str, object] = {"bytes": path.stat().st_size}
        try:
            model = sdk.open_model(path)
        except SUResultError as exc:
            entry |= {"opened": False, "error": str(exc)}
            print(f"  ❌ {path.name:<40} {exc}")
        else:
            try:
                wmaj, wmin, wbuild = sdk.model_version(model)
                # ⚠ This is the SketchUp that WROTE the file — not the designPH stamp, and not the
                # `SUModelVersion` enum, which SUModelGetVersion does not return. See a3_header_audit.
                entry |= {"opened": True, "writer_version": [wmaj, wmin, wbuild]}
                print(f"  ✅ {path.name:<40} written by SketchUp {wmaj}.{wmin}.{wbuild}")
            finally:
                sdk.close_model(model)
        models[path.name] = entry

    sdk.terminate()

    opened = sum(1 for m in models.values() if m.get("opened"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "provenance": "third-party re-host of Trimble's SDK — feasibility-only evidence, see sdk.py",
        "framework": str(sdk.path), "arch": arch, "api_version": f"{api_major}.{api_minor}",
        "host": {"machine": platform.machine(), "python": platform.python_version()},
        "missing_symbols": missing,
        "models": models,
    }, indent=1))

    passed = not missing and opened == len(models) and opened > 0
    print(
        f"\nVERDICT G0: {'PASS' if passed else 'FAIL'} — framework loads on {platform.machine()}, "
        f"API {api_major}.{api_minor}, {len(REQUIRED_SYMBOLS)} gate symbol sets "
        f"{'all present' if not missing else 'INCOMPLETE: ' + ', '.join(missing)}; "
        f"{opened}/{len(models)} corpus models opened → {args.out}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
