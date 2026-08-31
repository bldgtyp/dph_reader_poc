"""Windows → `Aperture`s, projected onto their host face.

PRD §8.2's algorithm. The rule that shapes the whole module: **never emit a floating aperture.** A
window that cannot be placed on its host is reported by name and skipped — a wrong window in the
model is worse than a missing one the report names, because only one of the two is discoverable.

Five ways a window legitimately fails to translate, all of them observed or specified:

1. `host_resolution == "unresolved"` — no `glued_to` host.
2. the host id names a face that is not in `faces` — an **unclassified host**, which the contract
   explicitly permits (§4's "referential integrity is deliberately loose").
3. the rectangle sits further off the host plane than any reveal could explain — see
   `OFF_PLANE_LIMIT_M`, which exists because of a real bug that projection silently absorbed.
4. the projected rectangle does not sit inside the host boundary.
5. ⚠ the host's boundary condition forbids apertures. honeybee raises
   `Aperture cannot be added to Face "…" with a Ground boundary condition` — so designPH area
   groups 9 and 11, which map to `Ground`, cannot carry windows. That is a *correct* refusal, and
   it is a direct interaction between this module and `facetypes`.

⚠ The rectangle itself is the **rough opening** (`lenx × leny` through the world transform), not a
face from the window definition: the definition's largest face is the *glazing*, 41 % smaller, and
it would land in the right place with the right shape and nothing to flag it. Contract §8.1.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .contract import Library, WindowRecord

#: How far outside the host boundary a projected corner may sit before the window is refused.
#: 1 mm — modelling noise, not a design decision.
CONTAINMENT_TOLERANCE_M = 0.001

#: How far *off* the host plane a window rectangle may sit before the projection is refused rather
#: than performed. A reveal is a construction depth — designPH's own `d_reveal` on Adelphi is
#: 0.32 m at the deepest — so half a metre is generous for real data and tight against the failure
#: this guards. ⚠ It is a specific failure: shipping `instance.transformation` parent-relative put
#: all 46 of Adelphi's windows **1.2–3.3 m** off their own hosts, and projection absorbed the error
#: without a word. Measured on the fixed capture the offsets are **0.000 m** — the window origin
#: lies exactly on its host plane (`planning/spikes/poc/solve_window_parent.py`), so anything past
#: a few centimetres means a transform is being read in the wrong space again.
OFF_PLANE_LIMIT_M = 0.5


def _project(loop: tuple[tuple[float, float, float], ...], host_geometry: Any) -> tuple[Any, float]:
    """The window rectangle flattened onto the host's plane, and how far it travelled to get there.

    designPH sets a window into a reveal, so its panel can sit *proud of* or *behind* the wall. That
    offset is real, and it is carried as PH reveal data (§5) rather than as geometry — an aperture
    that floats a few centimetres off its wall is not a better model, it is an invalid one.

    The distance is returned rather than discarded because **projection is lossy in exactly the way
    a transform bug is**: a rectangle a metre off its wall projects onto it just as cleanly as one a
    millimetre off. The caller refuses past `OFF_PLANE_LIMIT_M`.
    """
    from ladybug_geometry.geometry3d.face import Face3D
    from ladybug_geometry.geometry3d.pointvector import Point3D

    plane = host_geometry.plane
    points = [Point3D(*point) for point in loop]
    distance = max(plane.distance_to_point(point) for point in points)
    return Face3D([plane.project_point(point) for point in points], plane=plane), distance


def _contained(aperture_geometry: Any, host_geometry: Any) -> bool:
    """Is every projected corner inside the host boundary, or on it?

    Point-in-polygon on the host's own plane rather than a bounding box: a straddling window on an
    L-shaped wall passes a bounding-box test and is still wrong.

    ⚠ `Polygon2D.point_relationship` is the whole test, and it used to be preceded by an
    `is_point_inside_bound_rect` fast path. That pre-filter takes **no tolerance**, so it refused any
    window sitting flush with its host's edge — an ordinary thing for a window at the end of a wall,
    and the reason Adelphi's `500` was the one aperture of 46 to fail the rehearsal. Two tests of the
    same property that disagree at the boundary is the local-approximation trap again, in miniature:
    the library's own predicate already answers this, with a tolerance, and `0` (on the edge) is a
    pass.
    """
    plane = host_geometry.plane
    boundary = host_geometry.boundary_polygon2d
    return all(
        boundary.point_relationship(plane.xyz_to_xy(point), CONTAINMENT_TOLERANCE_M) >= 0
        for point in aperture_geometry.boundary
    )


def build(
    record: WindowRecord, host: Any, libraries: Mapping[str, Library] | None = None
) -> tuple[Any | None, str, dict[str, Any]]:
    """One window record + its honeybee host `Face` → `(aperture, outcome, detail)`.

    The aperture is **not** attached here; `attach` does that, so a containment failure and an
    attachment failure stay distinguishable in the report.
    """
    from honeybee.aperture import Aperture

    from .build import identifier

    detail: dict[str, Any] = {"designph_name": record.designph_name}
    if record.error is not None:
        return None, "reported-not-translated", {**detail, "reason": record.error}
    if record.panel_outer_loop is None or len(record.panel_outer_loop) < 3:
        return (
            None,
            "reported-not-translated",
            {
                **detail,
                "reason": "no window rectangle: the collector found no usable `lenx`/`leny`",
            },
        )

    try:
        geometry, off_plane = _project(record.panel_outer_loop, host.geometry)
    except Exception as error:  # noqa: BLE001 -- reporting, not handling
        return (
            None,
            "reported-not-translated",
            {
                **detail,
                "reason": f"could not project onto the host plane: {type(error).__name__}: {error}",
            },
        )

    if off_plane > OFF_PLANE_LIMIT_M:
        # Refuse rather than project. A rectangle this far out is not a reveal; it is a rectangle
        # computed in the wrong coordinate space, and projecting it would hide that perfectly.
        return (
            None,
            "reported-not-translated",
            {
                **detail,
                "off_plane_m": round(off_plane, 3),
                "reason": (
                    f"window rectangle sits {off_plane:.2f} m off host {host.identifier}'s plane, "
                    f"over the {OFF_PLANE_LIMIT_M} m limit — a reveal is centimetres, so this is a "
                    "coordinate-space error rather than a deep reveal"
                ),
            },
        )
    detail["off_plane_m"] = round(off_plane, 4)

    if not _contained(geometry, host.geometry):
        return (
            None,
            "reported-not-translated",
            {
                **detail,
                "reason": f"containment check failed on host {host.identifier}",
            },
        )

    aperture = Aperture(identifier(record.id), geometry)
    aperture.display_name = record.designph_name
    outcome = _apply_ph_properties(aperture, record, detail, libraries or {})
    sub_face = _sub_face_note(geometry, host.geometry)
    if sub_face is not None:
        detail["reason"] = "; ".join(filter(None, (detail.get("reason"), sub_face)))
        outcome = "translated-with-notes"
    return aperture, outcome, detail


def _sub_face_note(aperture_geometry: Any, host_geometry: Any) -> str | None:
    """Will honeybee's own validator call this aperture *not fully bounded*? Ask honeybee.

    `Face3D.is_sub_face` is the predicate `Face.check_apertures` runs, and therefore what
    `ValidateModel` reports. It takes **no tolerance** on the polygon-inside test, and it fails in
    two different ways on real designPH data — worth telling apart, because one is rounding and the
    other is a modelling question v1 has to answer:

    1. **Flush with the host boundary.** One of Adelphi's 46 windows sits 1 µm past its host's edge,
       which is the collector's own coordinate rounding rather than an overhang.
    2. ⚠ **The opening is modelled as an inner loop and the aperture lies in it.** honeybee expects
       an aperture to be a sub-face of the *gross* face, subtracting the opening itself — so a host
       that already carries the hole subtracts it twice. Only 2 of Adelphi's 16 hosts are modelled
       this way (a glued opening usually creates no loop at all), which is exactly why it is easy to
       miss.

    Neither is repaired here. `_contained` at 1 mm decides **whether to emit the window**; this
    decides **what a downstream validator will say about it**. Moving the geometry to please a
    checker would fabricate an area, so the report warns instead and says which case it is.
    """
    from math import radians

    from ladybug_geometry.geometry2d.polygon import Polygon2D

    if host_geometry.is_sub_face(aperture_geometry, 0.01, radians(1)):
        return None

    tail = (
        "honeybee's own sub-face check (no tolerance) will report it as 'not coplanar or fully "
        "bounded by its parent Face'. The geometry is designPH's and is emitted unchanged"
    )
    if host_geometry.has_holes:
        plane = host_geometry.plane
        flat = Polygon2D([plane.xyz_to_xy(point) for point in aperture_geometry.boundary])
        if any(not hole.is_polygon_outside(flat) for hole in host_geometry.hole_polygon2d):
            return (
                "the host already carries this opening as a modelled inner loop, and the aperture "
                f"lies inside it — so the opening is subtracted twice. {tail}"
            )
    return f"sits flush with the host boundary; {tail}"


def _apply_ph_properties(
    aperture: Any, record: WindowRecord, detail: dict[str, Any], libraries: Mapping[str, Library]
) -> str:
    """Reveal dimensions and the frame/glazing ids.

    The reveal is **PHPP shading data, not geometry**: `d_reveal` / `o_reveal` go onto the
    aperture's `ShadingDimensions` with every horizon and overhang field left `None`. That partial
    fill is why the model-level shading marker has to be worded carefully (§9): reveal dimensions
    *are* present while shading factors and context geometry are not, and the two claims must not
    read as contradicting each other.
    """
    from honeybee_ph.properties.aperture import ShadingDimensions

    dimensions = ShadingDimensions()
    dimensions.d_reveal = record.reveal("d_reveal")
    dimensions.o_reveal = record.reveal("o_reveal")
    aperture.properties.ph.shading_dimensions = dimensions
    if dimensions.d_reveal is not None:
        # honeybee-ph's own reveal depth, in metres.
        aperture.properties.ph.install_depth = dimensions.d_reveal

    # Full frame/glazing library resolution is a stretch goal: `frames_ud` and `glazing_ud` are not
    # in the contract's shipped tables. The ids travel so the report can measure how much would be
    # resolvable, and so a v1 that adds those tables has somewhere to put the answer.
    frame = record.dynamic_attributes.get("frametypeid")
    glazing = record.dynamic_attributes.get("glazingtypeid")
    aperture.properties.ph.variant_type = str(frame or "_unnamed_type_")
    detail["frametypeid"] = frame
    detail["glazingtypeid"] = glazing
    # ★ The pay-off for carrying the inline libraries (contract §5.1): a report line that reads
    # "PH Glazing (01ud)" rather than "01ud", with no CSV library on disk. Absent when the model's
    # own list does not name the id — which is itself worth seeing.
    for key, kind in (("frametypeid", "frame_types"), ("glazingtypeid", "glazing_types")):
        library = libraries.get(kind)
        label = library.label(detail[key]) if library and detail[key] is not None else None
        if label is not None:
            detail[key.replace("id", "_name")] = label
    if frame is None and glazing is None:
        detail["reason"] = "no frame or glazing id on the component"
        return "translated-with-notes"
    return "translated"


def attach(host: Any, aperture: Any) -> tuple[bool, str | None]:
    """Parent the aperture to its host face. Returns `(ok, reason)`.

    ⚠ honeybee refuses an aperture on a `Ground` or `Adiabatic` face. designPH groups 9 and 11 map
    to `Ground` (`facetypes`), so a window designPH placed in a below-grade wall is refused here —
    correctly, and loudly.
    """
    try:
        host.add_aperture(aperture)
    except (AssertionError, ValueError) as error:
        return False, f"host {host.identifier} refused the aperture: {error}"
    return True, None
