# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike A, follow-on — what ELSE is in there, and where are the edges?

Spike A's eight gates asked "can the SDK reproduce what the Ruby collector already read?". They can,
545/545. This script asks the two questions that gate list could not: **what does the SDK expose
that the Ruby collector never used**, and **where does this approach break down**.

It is research, not a gate — it prints measurements, not PASS/FAIL, because most of what it measures
has no "right answer" recorded anywhere to grade against. Findings feed
`00_Context/SDK_RUNTIME.md` and `00_Context/SKETCHUP_AS_A_DATA_SOURCE.md`.

Probes, and why each one is worth a run rather than a paragraph of inference:

1. **Mutation proof.** Spike A concluded that reading an attribute dictionary by name CREATES it.
   That conclusion is load-bearing (it is why "never save an opened model" is an invariant), and it
   was inferred from a header sentence plus a wrong count. Here it is tested directly: ask one face
   for a dictionary name no designPH model can carry, and count its dictionaries either side.
2. **Which entities the enumeration loses.** Knowing it under-reports by up to 41% is not the same
   as knowing *what it drops*. Characterised by container depth and entity type.
3. **Tags/layers.** ⭐ The PRD took shading geometry *out* of v1 scope because no heuristic separates
   context from clutter, and decided v1 would ask the user which SketchUp tags are shading
   (PRD §7.2). If the SDK reads tag names, that question becomes answerable headlessly.
4. **Geo-reference.** PHPP needs a location. designPH stores its own `klima_ID`; SketchUp carries a
   real lat/long and a north angle. Whether the corpus models actually populate it is unknown.
5. **Model GUID + load status.** ⭐ A stable per-model identifier and a "this file is newer than
   your SDK" signal are both directly relevant to a watcher service.
6. **Model statistics.** A whole-model entity census in one call, without walking anything.
7. **Write surface.** Symbol presence only — never called. Recorded because it bounds what a future
   authoring path could do, and because it is the thing that makes probe 1 dangerous.
8. **Cost.** Wall time and peak RSS per model, including the 146 MB scale probe if it is staged.

⚠ Third-party SDK re-host; feasibility-only evidence. See `sdk.py`.
⚠ Probe 1 deliberately mutates the IN-MEMORY model. Nothing here ever saves. That is the point.

    uv run a7_capability_probe.py --corpus _private/corpus --out _private/out/a7_capabilities.json
"""

from __future__ import annotations

import argparse
import json
import resource
import time
from collections import Counter
from ctypes import POINTER, byref, c_bool, c_double, c_int, c_int32, c_size_t
from pathlib import Path

from sdk import SDK, SUEntitiesRef, SULayerRef, SUStringRef, _ref
from walk import Walker, _entity

SULocationRef = _ref("SULocationRef")
SUMaterialRef = _ref("SUMaterialRef")

# SUEntityType, in the order the statistics array is indexed (model_entity_type_private.h).
ENTITY_TYPES = ["Edge", "Face", "ComponentInstance", "Group", "Image",
                "ComponentDefinition", "Layer", "Material"]
MODEL_UNITS = ["Inches", "Feet", "Millimeters", "Centimeters", "Meters"]
LOAD_STATUS = {0: "Success", 1: "Success_MoreRecent — ⚠ written by a NEWER SketchUp than this SDK"}

# Never called. Presence bounds what an authoring path could do, and explains why probe 1 matters.
WRITE_SYMBOLS = ["SUModelSaveToFile", "SUModelSaveToFileWithVersion", "SUEntityAddAttributeDictionary",
                 "SUAttributeDictionarySetValue", "SUModelFixErrors", "SUModelMergeCoplanarFaces"]


def extend(sdk: SDK) -> None:
    """Declare the probe-only functions. Everything else is already in sdk.py."""
    extra = [
        ("SUModelCreateFromFileWithStatus",
         [POINTER(type(SDK.open_model.__annotations__.get("return", int))) if False else POINTER(_ref("X")),
          __import__("ctypes").c_char_p, POINTER(c_int)], c_int32),
    ]
    del extra  # the WithStatus call is wired explicitly below; kept out of the generic table
    from sdk import SUDrawingElementRef, SUModelRef

    for name, args, res in [
        ("SUDrawingElementGetLayer", [SUDrawingElementRef, POINTER(SULayerRef)], c_int32),
        ("SULayerGetName", [SULayerRef, POINTER(SUStringRef)], c_int32),
        ("SUDrawingElementGetHidden", [SUDrawingElementRef, POINTER(c_bool)], c_int32),
        ("SUModelIsGeoReferenced", [SUModelRef, POINTER(c_bool)], c_int32),
        ("SUModelGetLocation", [SUModelRef, POINTER(SULocationRef)], c_int32),
        ("SULocationGetLatLong", [SULocationRef, POINTER(c_double), POINTER(c_double)], c_int32),
        ("SUModelGetNorthCorrection", [SUModelRef, POINTER(c_double)], c_int32),
        ("SUModelGetUnits", [SUModelRef, POINTER(c_int32)], c_int32),
        ("SUModelGetStatistics", [SUModelRef, POINTER(c_int32 * 8)], c_int32),
        ("SUModelCreateFromFileWithStatus",
         [POINTER(SUModelRef), __import__("ctypes").c_char_p, POINTER(c_int32)], c_int32),
    ]:
        fn = getattr(sdk.lib, name, None)
        if fn is not None:
            fn.argtypes, fn.restype = args, res


def probe_mutation(sdk: SDK, walker: Walker, model) -> dict:
    """Does asking for a dictionary BY NAME create it? The direct test of Spike A's key claim.

    ⚠ Uses a name no designPH model can already carry, rather than hunting for a face with zero
    dictionaries — on Adelphi every one of the 8037 faces already has at least one, so the
    zero-dictionary hunt finds nothing and the probe silently declines to test anything. A test that
    quietly does not run is worse than one that fails.

    Mutates the IN-MEMORY model only. Nothing here ever saves.
    """
    from sdk import SUAttributeDictionaryRef

    victim = next((n for n in walker.walk_entities(model) if n.kind == "face"), None)
    if victim is None:
        return {"tested": False, "why": "no faces in this model"}

    probe_name = b"DPH_PLUS_MUTATION_PROBE"
    before = c_size_t()
    sdk.call("SUEntityGetNumAttributeDictionaries", _entity(victim.ref), byref(before), tolerate=(2, 8, 9))
    d = SUAttributeDictionaryRef()
    sdk.call("SUEntityGetAttributeDictionary", _entity(victim.ref), probe_name, byref(d), tolerate=(2, 8, 9))
    after = c_size_t()
    sdk.call("SUEntityGetNumAttributeDictionaries", _entity(victim.ref), byref(after), tolerate=(2, 8, 9))
    return {
        "tested": True, "probe_dictionary": probe_name.decode(), "persistent_id": victim.persistent_id,
        "dictionaries_before": before.value, "dictionaries_after": after.value,
        "created": after.value > before.value,
        "handle_returned": bool(d.ptr),
        "new_dictionary_keys": len(walker.dict_keys(d)) if d.ptr else 0,
    }


def probe_enumeration_gap(sdk: SDK, walker: Walker, model) -> dict:
    """Characterise WHICH entities the read-only enumeration loses, not just how many."""
    from sdk import SUAttributeDictionaryRef

    by_name = 0
    enumerated = 0
    lost_types: Counter[str] = Counter()
    total: Counter[str] = Counter()

    for node in walker.walk_entities(model):
        total[node.kind] += 1
        # complete predicate: ask by name, require keys
        d = SUAttributeDictionaryRef()
        sdk.call("SUEntityGetAttributeDictionary", _entity(node.ref), b"DesignPH_dict",
                 byref(d), tolerate=(2, 8, 9))
        k = c_size_t()
        if d.ptr:
            sdk.call("SUAttributeDictionaryGetNumKeys", d, byref(k), tolerate=(2, 8, 9))
        has_by_name = bool(k.value)
        if not has_by_name:
            continue
        by_name += 1

        # enumerating predicate
        n = c_size_t()
        sdk.call("SUEntityGetNumAttributeDictionaries", _entity(node.ref), byref(n), tolerate=(2, 8, 9))
        seen = False
        if n.value:
            arr = (SUAttributeDictionaryRef * n.value)()
            got = c_size_t()
            sdk.call("SUEntityGetAttributeDictionaries", _entity(node.ref), n.value, arr, byref(got))
            seen = got.value > 0
        if seen:
            enumerated += 1
        else:
            lost_types[node.kind] += 1

    return {
        "tagged_by_name": by_name, "tagged_by_enumeration": enumerated,
        "lost": by_name - enumerated,
        "lost_pct": round(100 * (by_name - enumerated) / by_name, 1) if by_name else 0.0,
        "lost_by_entity_kind": dict(lost_types), "entities_visited": dict(total),
    }


def probe_tags(sdk: SDK, walker: Walker, model) -> dict:
    """⭐ Tag (layer) names per tagged and untagged face — the shading-classification question."""
    from sdk import SUAttributeDictionaryRef, SUDrawingElementRef

    def layer_name(ref) -> str:
        layer = SULayerRef()
        if sdk.call("SUDrawingElementGetLayer", SUDrawingElementRef(ref.ptr), byref(layer),
                    tolerate=(2, 8, 9)) != 0 or not layer.ptr:
            return "<none>"
        s = SUStringRef()
        sdk.call("SUStringCreate", byref(s))
        try:
            sdk.call("SULayerGetName", layer, byref(s), tolerate=(2, 8, 9))
            return sdk.read_string(s).decode("utf-8", "replace")
        finally:
            sdk.lib.SUStringRelease(byref(s))

    tagged: Counter[str] = Counter()
    untagged: Counter[str] = Counter()
    for node in walker.walk_entities(model):
        if node.kind != "face":
            continue
        d = SUAttributeDictionaryRef()
        sdk.call("SUEntityGetAttributeDictionary", _entity(node.ref), b"DesignPH_dict",
                 byref(d), tolerate=(2, 8, 9))
        k = c_size_t()
        if d.ptr:
            sdk.call("SUAttributeDictionaryGetNumKeys", d, byref(k), tolerate=(2, 8, 9))
        (tagged if k.value else untagged)[layer_name(node.ref)] += 1
    return {
        "distinct_tags_on_designph_faces": len(tagged),
        "distinct_tags_on_other_faces": len(untagged),
        "designph_face_tags": dict(tagged.most_common(12)),
        "other_face_tags_top": dict(untagged.most_common(12)),
    }


def probe_model_facts(sdk: SDK, model) -> dict:
    """GUID, geo-reference, north angle, display units, whole-model statistics."""
    out: dict[str, object] = {}
    try:
        out["guid"] = sdk.string_out("SUModelGetGuid", model).decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        out["guid"] = f"<{type(exc).__name__}>"

    geo = c_bool()
    if sdk.call("SUModelIsGeoReferenced", model, byref(geo), tolerate=(2, 8, 9)) == 0:
        out["geo_referenced"] = bool(geo.value)
        if geo.value:
            loc = SULocationRef()
            if sdk.call("SUModelGetLocation", model, byref(loc), tolerate=(2, 8, 9)) == 0 and loc.ptr:
                lat, lon = c_double(), c_double()
                if sdk.call("SULocationGetLatLong", loc, byref(lat), byref(lon), tolerate=(2, 8, 9)) == 0:
                    out["lat_long"] = [round(lat.value, 5), round(lon.value, 5)]

    north = c_double()
    if sdk.call("SUModelGetNorthCorrection", model, byref(north), tolerate=(2, 8, 9)) == 0:
        out["north_correction_deg"] = round(north.value, 4)

    units = c_int32()
    if sdk.call("SUModelGetUnits", model, byref(units), tolerate=(2, 8, 9)) == 0:
        out["display_units"] = MODEL_UNITS[units.value] if 0 <= units.value < len(MODEL_UNITS) else units.value

    stats = (c_int32 * 8)()
    if sdk.call("SUModelGetStatistics", model, byref(stats), tolerate=(2, 8, 9)) == 0:
        out["statistics"] = dict(zip(ENTITY_TYPES, list(stats)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--only", default=None)
    args = ap.parse_args()

    sdk = SDK()
    extend(sdk)
    walker = Walker(sdk)

    print(f"write-capable symbols present (NEVER called here): "
          f"{len([s for s in WRITE_SYMBOLS if not sdk.missing([s])])}/{len(WRITE_SYMBOLS)} — "
          f"{', '.join(WRITE_SYMBOLS)}\n")

    results: dict[str, dict] = {}
    for path in sorted(args.corpus.glob("*.skp")):
        if args.only and args.only not in path.name:
            continue
        rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        t0 = time.perf_counter()

        from sdk import SUModelRef
        model = SUModelRef()
        status = c_int32(-1)
        rc = sdk.lib.SUModelCreateFromFileWithStatus(byref(model), str(path).encode("utf-8"), byref(status))
        if rc != 0:
            print(f"❌ {path.name}: SUModelCreateFromFileWithStatus rc={rc}")
            continue
        t_open = time.perf_counter() - t0

        row: dict[str, object] = {
            "file_mb": round(path.stat().st_size / 1e6, 1),
            "load_status": LOAD_STATUS.get(status.value, f"<{status.value}>"),
            "open_seconds": round(t_open, 2),
        }
        try:
            row |= probe_model_facts(sdk, model)
            t1 = time.perf_counter()
            row["enumeration_gap"] = probe_enumeration_gap(sdk, walker, model)
            row["walk_seconds"] = round(time.perf_counter() - t1, 2)
            row["tags"] = probe_tags(sdk, walker, model)
            row["mutation"] = probe_mutation(sdk, walker, model)
        finally:
            sdk.close_model(model)

        rss1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        row["peak_rss_mb_after"] = round(rss1 / 1e6, 1)   # macOS reports bytes
        row["total_seconds"] = round(time.perf_counter() - t0, 2)
        results[path.name] = row

        g = row["enumeration_gap"]
        m = row["mutation"]
        st = row.get("statistics", {})
        print(f"── {path.name}  ({row['file_mb']} MB, {row['load_status'].split(' —')[0]})")
        print(f"     model    guid={str(row.get('guid'))[:36]}  geo={row.get('geo_referenced')}"
              f"{'  ' + str(row.get('lat_long')) if row.get('lat_long') else ''}"
              f"  north={row.get('north_correction_deg')}  units={row.get('display_units')}")
        print(f"     census   {', '.join(f'{k}={v:,}' for k, v in st.items() if v)}   ⚠ PLACEMENTS, not entities")
        print(f"     enum gap {g['lost']}/{g['tagged_by_name']} tagged entities lost "
              f"({g['lost_pct']}%) by kind {g['lost_by_entity_kind'] or '—'}")
        print(f"     mutation {'CREATED a dictionary' if m.get('created') else 'no change'} "
              f"({m.get('dictionaries_before')}→{m.get('dictionaries_after')} dicts on one face, "
              f"handle={m.get('handle_returned')}, keys={m.get('new_dictionary_keys')})"
              f"{'' if m.get('tested') else '  NOT TESTED: ' + str(m.get('why'))}")
        print(f"     tags     {row['tags']['distinct_tags_on_designph_faces']} on designPH faces, "
              f"{row['tags']['distinct_tags_on_other_faces']} on the rest")
        print(f"     cost     open {row['open_seconds']}s · walk {row['walk_seconds']}s · "
              f"total {row['total_seconds']}s · peak RSS {row['peak_rss_mb_after']} MB")

    sdk.terminate()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        {"provenance": "third-party SDK re-host — feasibility-only evidence",
         "write_symbols_present": [s for s in WRITE_SYMBOLS if not sdk.missing([s])],
         "models": results}, indent=1))
    print(f"\n→ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
