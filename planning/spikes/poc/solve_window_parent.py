# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
# ///
"""Recover the parent transform of Adelphi's windows from the FIRST capture, offline.

Why this exists: contract §8.1's rough-opening rule rests on an inference — that the window's
rough opening is the local rectangle `(0,0,0)→(lenx,0,0)→(lenx,leny,0)→(0,leny,0)`, i.e. that the
definition origin is a *corner* of the opening rather than its centre. The live evidence
(`DESIGNPH_DATA_MODEL.md` §9.1) shows only that the *origin* lands on its host plane. Implementing
the wrong corner convention would put every window half off its wall — plausibly, and with the
containment check as the only thing between it and the output.

The first capture shipped `instance.transformation` **parent-relative** (the §8.2 defect), and the
faces world. That is enough to solve for the parent, because the two are related:

    world = P · local,  P = [R | t] rigid

* every window's local +Z axis must map onto its host face's world normal  → Kabsch gives R
* every window's local origin must land on its host's world plane          → least squares gives t

With P recovered, every candidate rectangle convention can be tested against the real host
polygons without SketchUp. Run:

    uv run planning/spikes/poc/solve_window_parent.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

FIXTURE = Path(__file__).resolve().parents[3] / "pocs/01_sketchup-export/_private/fixtures/adelphi-designph_COPY.extraction.json"
IN_TO_M = 0.0254


def columns(flat: list[float]) -> np.ndarray:
    """SketchUp's 16 floats are COLUMN-major; translation at 12-14."""
    return np.array(flat, dtype=float).reshape(4, 4).T


def plane_of(loop: list[list[float]]) -> tuple[np.ndarray, np.ndarray]:
    """(point, unit normal) by Newell's method — robust to non-planarity and vertex order."""
    points = np.array(loop, dtype=float)
    normal = np.zeros(3)
    for i in range(len(points)):
        a, b = points[i], points[(i + 1) % len(points)]
        normal += np.cross(a, b)
    return points.mean(axis=0), normal / np.linalg.norm(normal)


def kabsch(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Rotation taking `source` rows onto `target` rows, right-handed."""
    u, _, vt = np.linalg.svd(source.T @ target)
    d = np.sign(np.linalg.det(vt.T @ u.T))
    return vt.T @ np.diag([1.0, 1.0, d]) @ u.T


def main() -> int:
    payload = json.loads(FIXTURE.read_text())
    faces = {face["id"]: face for face in payload["faces"]}

    axes, normals, origins, points_on_plane, records = [], [], [], [], []
    for window in payload["windows"]:
        host = faces.get(window["host_face_id"] or "")
        if host is None:
            continue
        matrix = columns(window["transformation"])
        point, normal = plane_of(host["outer_loop"])
        # The local rectangle lies in the definition's XY plane, so its normal is the local Z axis.
        axes.append(matrix[:3, 2])
        normals.append(normal)
        origins.append(matrix[:3, 3] * IN_TO_M)
        points_on_plane.append(point)
        records.append((window, host, matrix))

    axes = np.array(axes)
    normals = np.array(normals)
    origins = np.array(origins)
    print(f"{len(records)} of {len(payload['windows'])} windows have a translated host\n")

    # --- R: local Z onto the host normal, with the ± ambiguity resolved by iteration ------------
    signs = np.ones(len(axes))
    rotation = np.eye(3)
    for _ in range(20):
        rotation = kabsch(axes, normals * signs[:, None])
        updated = np.sign(np.einsum("ij,ij->i", axes @ rotation.T, normals))
        updated[updated == 0] = 1.0
        if np.array_equal(updated, signs):
            break
        signs = updated
    residual = np.abs(np.einsum("ij,ij->i", axes @ rotation.T, normals))
    print("R: |local +Z · host normal| after rotation — 1.0 means the planes agree")
    print(f"   min {residual.min():.6f}  mean {residual.mean():.6f}  max {residual.max():.6f}")
    print(f"   det {np.linalg.det(rotation):+.6f}   (a plan rotation keeps Z: R·[0,0,1] = "
          f"{np.round(rotation @ np.array([0.0, 0.0, 1.0]), 6).tolist()})\n")

    # --- t: every window origin lands on its host plane ----------------------------------------
    a = normals
    b = np.einsum("ij,ij->i", normals, np.array(points_on_plane)) - np.einsum(
        "ij,ij->i", normals, origins @ rotation.T
    )
    translation, *_ = np.linalg.lstsq(a, b, rcond=None)
    offsets = a @ translation - b
    print("t: signed distance from each window origin to its host plane (m)")
    print(f"   mean |d| {np.abs(offsets).mean():.4f}  max |d| {np.abs(offsets).max():.4f}")
    print(f"   t = {np.round(translation, 4).tolist()}\n")

    def world(matrix: np.ndarray, local: np.ndarray) -> np.ndarray:
        return rotation @ ((matrix @ np.append(local, 1.0))[:3] * IN_TO_M) + translation

    # Independent check: DESIGNPH_DATA_MODEL §9.1/§9.3 measured 403U's world origin IN SketchUp.
    for window, _, matrix in records:
        if window["designph_name"] == "403U":
            got = world(matrix, np.zeros(3))
            print(f"403U world origin: solved {np.round(got, 4).tolist()}")
            print("                   §9.3   [-2.9319, 7.2696, 11.2774]  <- measured in SketchUp\n")

    # --- the actual question: which rectangle convention lands inside the host? -----------------
    def corners(name: str, make) -> None:
        inside = off_plane = 0
        worst = 0.0
        for window, host, matrix in records:
            attributes = window["dynamic_attributes"]
            lenx, leny = float(attributes["lenx"]), float(attributes["leny"])
            point, normal = plane_of(host["outer_loop"])
            polygon = np.array(host["outer_loop"], dtype=float)
            # 2D frame on the host plane.
            u = polygon[1] - polygon[0]
            u = u / np.linalg.norm(u)
            v = np.cross(normal, u)
            flat = [( (p - point) @ u, (p - point) @ v) for p in polygon]
            ok = True
            for local in make(lenx, leny):
                w = world(matrix, local)
                distance = abs((w - point) @ normal)
                worst = max(worst, distance)
                if distance > 0.5:
                    ok = False
                    off_plane += 1
                    break
                if not point_in_polygon(((w - point) @ u, (w - point) @ v), flat):
                    ok = False
                    break
            inside += 1 if ok else 0
        print(f"   {name:<34} {inside:>2}/{len(records)} inside the host polygon"
              f"   (worst off-plane {worst:.3f} m)")

    print("Rectangle conventions, tested against the real host polygons:")
    corners("corner at origin, +x/+y", lambda x, y: [(0, 0, 0), (x, 0, 0), (x, y, 0), (0, y, 0)])
    corners("centred on the origin", lambda x, y: [(-x / 2, -y / 2, 0), (x / 2, -y / 2, 0),
                                                   (x / 2, y / 2, 0), (-x / 2, y / 2, 0)])
    corners("corner at origin, -x/-y", lambda x, y: [(0, 0, 0), (-x, 0, 0), (-x, -y, 0), (0, -y, 0)])
    corners("corner at origin, +x/-y", lambda x, y: [(0, 0, 0), (x, 0, 0), (x, -y, 0), (0, -y, 0)])
    return 0


def point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    """Ray casting, with a 1 mm outward tolerance to match the translator's own containment rule."""
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        x0, y0 = polygon[i]
        x1, y1 = polygon[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            crossing = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < crossing:
                inside = not inside
    if inside:
        return True
    # Within a millimetre of an edge counts as inside — modelling noise, not a design decision.
    for i in range(n):
        a = np.array(polygon[i])
        b = np.array(polygon[(i + 1) % n])
        p = np.array(point)
        t = np.clip((p - a) @ (b - a) / max((b - a) @ (b - a), 1e-12), 0.0, 1.0)
        if np.linalg.norm(p - (a + t * (b - a))) <= 0.001:
            return True
    return False


if __name__ == "__main__":
    sys.exit(main())
