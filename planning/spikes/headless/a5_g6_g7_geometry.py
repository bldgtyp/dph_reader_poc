# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike A — G6 (`SUFaceGetArea` semantics) and G7 (world transforms).

Both gates need the **placement** walk, not the entity walk: a face inside a definition has no
single world position, and the whole point of G7 is that transforms compose down the nesting.

**G6 — net or gross?** In live SketchUp `face.area` is NET of glued window openings while the loop
polygon is GROSS; they differ on exactly the host faces. Whether the SDK's standalone deserializer
reproduces that is unknown, and the plan's decision is that a headless collector records the SDK's
value **verbatim** either way — recomputing SketchUp's own subtraction would be re-implementing half
a library's rule. So this gate does not grade right/wrong; it **measures and names** the semantics,
and the 81 known host faces are the probe set.

**G7 — do world transforms land within 1 mm** of what the live collector recorded for the same
window? This is the gate that catches the parent-relative-transform trap that put Adelphi's 46
windows 1.2-3.3 m off their hosts, and it is the one an axis-aligned toy model cannot test.

⚠ Third-party SDK re-host; feasibility-only evidence. See `sdk.py`.

    uv run a5_g6_g7_geometry.py --corpus _private/corpus --fixtures _private/fixtures \
        --out _private/out/a5_geometry.json
"""

from __future__ import annotations

import argparse
import json
import math
from ctypes import byref, c_double, c_size_t
from pathlib import Path

from sdk import SDK, SUEntitiesRef, SUFaceRef, SULoopRef, SUTransformation
from walk import INCHES_TO_M, Walker, apply

SQ_IN_TO_SQ_M = 0.00064516
DC_DICT, WINDOW_MARKER = "dynamic_attributes", "frametypeid"

CORPUS_TO_CAPTURE = {
    "adelphi-designph_COPY.skp": "adelphi-designph_COPY.extraction.json",
    "2414_Bluff Reach_COPY.skp": "2414_Bluff Reach_COPY.extraction.json",
    "2523 Wellington_COPY.skp": "2523 Wellington_COPY.extraction.json",
    "250703 - Linde Residence_COPY.skp": "250703 - Linde Residence_COPY.extraction.json",
    "250708_COPY.skp": "250708_COPY.extraction.json",
}


def polygon_area_3d(pts: list[tuple[float, float, float]]) -> float:
    """Area of a planar polygon in 3-space, via the magnitude of the summed cross products.

    Works for any planar polygon in any orientation — no projection onto a chosen axis, which is the
    step that would silently collapse a vertical face to zero.
    """
    if len(pts) < 3:
        return 0.0
    cx = cy = cz = 0.0
    for i in range(len(pts)):
        x1, y1, z1 = pts[i]
        x2, y2, z2 = pts[(i + 1) % len(pts)]
        cx += y1 * z2 - z1 * y2
        cy += z1 * x2 - x1 * z2
        cz += x1 * y2 - y1 * x2
    return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)


def collect(sdk: SDK, walker: Walker, model) -> tuple[dict, dict]:
    """Placement walk → {path-qualified id: record} for classified faces and designPH windows."""
    faces: dict[str, dict] = {}
    windows: dict[str, dict] = {}

    def interesting(kind: str, ref) -> bool:
        """Tagged geometry only — what the pruning index keeps a subtree for."""
        if kind == "window":
            dc = walker.dictionary(ref, DC_DICT)
            return dc is not None and walker.typed_value(dc, WINDOW_MARKER) is not None
        return walker.dictionary(ref) is not None

    keep = walker.interesting_containers(model, interesting)

    for node in walker.walk_pruned(model, keep):
        if node.kind == "window":
            dc = walker.dictionary(node.ref, DC_DICT)
            if dc is None or walker.typed_value(dc, WINDOW_MARKER) is None:
                continue
            # The contract ships the ACCUMULATED world transform, in inches, column-major.
            windows[node.id] = {"transformation": list(node.world)}
            continue
        if node.kind != "face":
            continue

        d = walker.dictionary(node.ref)
        if d is None:
            continue
        group = None
        for key in ("areaGroupID", "areaGroupAuto"):
            got = walker.typed_value(d, key)
            if got and got[0] == "Int32":
                group = got[1]
                break
        if group is None:
            continue

        # WORLD area, matching the collector's `face.area(transform)`. `SUFaceGetArea` without a
        # transform is the LOCAL area and differs on any scaled container.
        area = c_double()
        sdk.call("SUFaceGetArea", node.ref, byref(area))
        world_area = c_double()
        wt = SUTransformation()
        wt.values[:] = list(node.world)
        sdk.call("SUFaceGetAreaWithTransform", node.ref, byref(wt), byref(world_area))
        outer = SULoopRef()
        sdk.call("SUFaceGetOuterLoop", node.ref, byref(outer))
        pts = walker.loop_points(outer, node.world)
        n_open = c_size_t()
        sdk.call("SUFaceGetNumOpenings", node.ref, byref(n_open), tolerate=(2, 8, 9))
        faces[node.id] = {
            "sdk_local_area_m2": area.value * SQ_IN_TO_SQ_M,
            "sdk_area_m2": world_area.value * SQ_IN_TO_SQ_M,
            "loop_area_m2": polygon_area_3d(pts),
            "outer_loop": pts,
            "num_openings": n_open.value,
        }
    return faces, windows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--fixtures", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--tolerance-mm", type=float, default=1.0)
    args = ap.parse_args()

    tol_m = args.tolerance_mm / 1000.0
    sdk = SDK()
    walker = Walker(sdk)
    out: dict[str, dict] = {}

    for skp, capture_name in sorted(CORPUS_TO_CAPTURE.items()):
        path, cap_path = args.corpus / skp, args.fixtures / capture_name
        if not path.exists() or not cap_path.exists():
            print(f"  SKIP {skp}")
            continue
        cap = json.loads(cap_path.read_text(encoding="utf-8"))
        live_faces = {f["id"]: f for f in cap["faces"]}
        live_windows = {w["id"]: w for w in cap["windows"]}

        model = sdk.open_model(path)
        try:
            faces, windows = collect(sdk, walker, model)
        finally:
            sdk.close_model(model)

        # -- G7: window world transforms, translation compared in metres ---
        deltas, unmatched = [], 0
        for wid, live in live_windows.items():
            got = windows.get(wid)
            if got is None:
                unmatched += 1
                continue
            a, b = got["transformation"], live["transformation"]
            deltas.append(
                math.dist([a[12], a[13], a[14]], [b[12], b[13], b[14]]) * INCHES_TO_M
            )

        # -- G7: classified face loop vertices --------------------------
        face_dev, face_unmatched = [], 0
        for fid, live in live_faces.items():
            got = faces.get(fid)
            if got is None:
                face_unmatched += 1
                continue
            mine, theirs = got["outer_loop"], live["outer_loop"]
            if len(mine) != len(theirs):
                face_dev.append(float("inf"))
                continue
            face_dev.append(max(math.dist(p, q) for p, q in zip(mine, theirs)))

        # -- G6: net vs gross on the faces that host windows ------------
        net_gross = []
        for fid, got in faces.items():
            live = live_faces.get(fid)
            if live is None:
                continue
            net_gross.append({
                "id": fid,
                "sdk_area": got["sdk_area_m2"],
                "sdk_loop_area": got["loop_area_m2"],
                "live_face_area": live["area_m2"],
                "num_openings": got["num_openings"],
            })
        differing = [r for r in net_gross if abs(r["sdk_area"] - r["sdk_loop_area"]) > 1e-4]
        vs_live = [r for r in net_gross if abs(r["sdk_area"] - r["live_face_area"]) > 1e-4]
        openings = sum(1 for r in net_gross if r["num_openings"])

        row = {
            "windows_compared": len(deltas), "windows_unmatched": unmatched,
            "window_max_delta_m": max(deltas, default=0.0),
            "faces_compared": len(face_dev), "faces_unmatched": face_unmatched,
            "face_max_vertex_delta_m": max(face_dev, default=0.0),
            "faces_with_openings_reported": openings,
            "faces_sdk_area_differs_from_own_loop": len(differing),
            "faces_sdk_area_differs_from_live_face_area": len(vs_live),
        }
        out[skp] = row

        g7_ok = (not unmatched and not face_unmatched
                 and row["window_max_delta_m"] <= tol_m and row["face_max_vertex_delta_m"] <= tol_m)
        print(f"{'✅' if g7_ok else '❌'} {skp}")
        print(f"     G7 windows : {len(deltas)} matched, {unmatched} unmatched, "
              f"max translation delta {row['window_max_delta_m'] * 1000:.4f} mm")
        print(f"     G7 faces   : {len(face_dev)} matched, {face_unmatched} unmatched, "
              f"max vertex delta {row['face_max_vertex_delta_m'] * 1000:.4f} mm")
        print(f"     G6 area    : SUFaceGetArea differs from its own outer loop on "
              f"{len(differing)}/{len(net_gross)}; from the live face.area on {len(vs_live)}/{len(net_gross)}; "
              f"SUFaceGetNumOpenings > 0 on {openings}")

    sdk.terminate()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        {"provenance": "third-party SDK re-host — feasibility-only evidence",
         "tolerance_mm": args.tolerance_mm, "models": out}, indent=1))

    wmax = max((r["window_max_delta_m"] for r in out.values()), default=0.0)
    fmax = max((r["face_max_vertex_delta_m"] for r in out.values()), default=0.0)
    unm = sum(r["windows_unmatched"] + r["faces_unmatched"] for r in out.values())
    net = sum(r["faces_sdk_area_differs_from_live_face_area"] for r in out.values())
    passed = not unm and wmax <= tol_m and fmax <= tol_m
    print(
        f"\nVERDICT G7: {'PASS' if passed else 'FAIL'} — worst window translation delta "
        f"{wmax * 1000:.4f} mm, worst face vertex delta {fmax * 1000:.4f} mm, "
        f"{unm} unmatched (tolerance {args.tolerance_mm} mm)"
    )
    print(
        f"VERDICT G6: MEASURED — SUFaceGetArea disagrees with the live SketchUp face.area on "
        f"{net} classified faces across the corpus → {args.out}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
