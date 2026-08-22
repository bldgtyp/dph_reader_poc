"""Thermal bridges and apertures — the two entity classes with the most ways to vanish quietly.

For bridges the count assertion **is** the test: *n in, n out-or-reported, zero silently gone*. A
face-only reader loses 99 of 293 tagged entities on a real project and reports nothing, so anything
less than a full accounting here would repeat that failure one layer up.

For apertures the rule is: never emit a floating one. A wrong window in the model is worse than a
missing window the report names, because only one of the two is discoverable.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from dph_translator.build import translate
from dph_translator.contract import parse

from . import synthetic as s


def entries(result: Any, kind: str) -> dict[str, dict[str, Any]]:
    block = result.report["entries"].get(kind, {"listed": []})
    return {entry["id"]: entry for entry in block["listed"]}


# ------------------------------------------------------------------------------------------------
# Thermal bridges
# ------------------------------------------------------------------------------------------------


def bridge_document(**tables: Any) -> dict[str, Any]:
    return s.document(
        faces=[s.wall("w", 8)],
        edges=[
            s.edge("edge_ambient", 15, connection_ref="101ud"),
            s.edge("edge_perimeter", "16", connection_ref="102ud", end=(0.0, 3.0, 0.0)),
            s.edge("edge_slab", 17, connection_ref="103ud", end=(0.0, 0.0, 2.0)),
        ],
        tables=tables,
    )


CONNECTIONS = s.connections_ud(
    ["101ud", "Parapet", 15, "Thermal Bridges Ambient", 0.045, 0.82],
    ["102ud", "Slab edge", 16, "Perimeter Thermal Bridges", 0.31, 0.71],
    ["103ud", "Footing", 17, "Thermal Bridges FS/BC", 0.12, 0.65],
)


def test_every_tagged_edge_is_accounted_for() -> None:
    result = translate(parse(bridge_document(connections_ud=CONNECTIONS)))
    assert result.report["summary"]["thermal_bridges"] == {"in": 3, "translated": 3, "reported": 0}


@pytest.mark.parametrize(
    "edge_id,group_type",
    [("edge_ambient", "15-Ambient"), ("edge_perimeter", "16-Perimeter"), ("edge_slab", "17-FS/BC")],
)
def test_the_area_group_maps_onto_honeybees_own_group_type(edge_id: str, group_type: str) -> None:
    """`PhThermalBridgeType` accepts exactly these three strings and raises on anything else."""
    result = translate(parse(bridge_document(connections_ud=CONNECTIONS)))
    assert entries(result, "thermal_bridge")[edge_id]["group_type"] == group_type


def test_the_psi_value_comes_from_connections_ud_not_the_assemblies() -> None:
    """⚠ Both namespaces use `NNud` ids, so resolving a bridge against the assembly table returns an
    unrelated row rather than an error. The contract names the field `connection_ref` for this."""
    document = bridge_document(
        connections_ud=CONNECTIONS,
        # A same-id row in the *wrong* table. Joining to it would look like success.
        assemblies_ud=s.assemblies_ud(["101ud", "NOT A BRIDGE", 1, 300.0, 0.15, False]),
    )
    result = translate(parse(document))
    hbjson = json.loads(result.hbjson)
    # The segment serialises under the MODEL's PH properties; the Room keeps only its id.
    bridges = hbjson["properties"]["ph"]["bldg_segments"][0]["thermal_bridges"]
    assert abs(bridges["edge_ambient"]["psi_value"] - 0.045) < 1e-9
    assert entries(result, "thermal_bridge")["edge_ambient"]["connection"] == "Parapet"


def test_length_is_derived_from_geometry_not_taken_from_the_collector() -> None:
    result = translate(parse(bridge_document(connections_ud=CONNECTIONS)))
    assert entries(result, "thermal_bridge")["edge_ambient"]["length_m"] == 4.0


def test_a_collector_length_that_disagrees_with_the_geometry_is_surfaced() -> None:
    """They should agree. A disagreement means a transform went wrong on one side, and averaging
    the two would hide it."""
    document = bridge_document(connections_ud=CONNECTIONS)
    document["edges"][0]["length_m"] = 9.9
    entry = entries(translate(parse(document)), "thermal_bridge")["edge_ambient"]
    assert entry["outcome"] == "translated-with-notes"
    assert "collector 9.9" in entry["reason"]


def test_a_missing_connections_table_still_keeps_the_bridge() -> None:
    """A bridge with no psi-value is still a bridge. Losing it would be worse than carrying it on
    honeybee's default — but the report has to say the number is not designPH's."""
    result = translate(parse(bridge_document()))
    entry = entries(result, "thermal_bridge")["edge_ambient"]
    assert entry["outcome"] == "translated-with-notes"
    assert "no `connections_ud`" in entry["reason"]
    assert result.report["summary"]["thermal_bridges"]["translated"] == 3


def test_an_unresolvable_connection_id_is_named() -> None:
    document = bridge_document(connections_ud=s.connections_ud(["999ud", "Other", 15, "x", 0.1, 0.8]))
    entry = entries(translate(parse(document)), "thermal_bridge")["edge_ambient"]
    assert "'101ud' not found" in entry["reason"]


def test_an_edge_outside_15_16_17_is_reported_as_an_anomaly() -> None:
    """The contract ships these deliberately: an anomalous edge is worth seeing, not something for
    Ruby to have filtered out on its own judgement."""
    document = s.document(faces=[s.wall("w", 8)], edges=[s.edge("edge_odd", 8)])
    entry = entries(translate(parse(document)), "thermal_bridge")["edge_odd"]
    assert entry["outcome"] == "reported-not-translated"
    assert "not a thermal-bridge group" in entry["reason"]


def test_edges_are_reported_even_when_there_is_no_room_to_attach_them_to() -> None:
    """A model with no translatable face still has to account for its edges."""
    document = s.document(faces=[], edges=[s.edge("edge_ambient", 15)])
    entry = entries(translate(parse(document)), "thermal_bridge")["edge_ambient"]
    assert entry["outcome"] == "reported-not-translated"


# ------------------------------------------------------------------------------------------------
# Apertures
# ------------------------------------------------------------------------------------------------


def window_document(**overrides: Any) -> dict[str, Any]:
    host_group = overrides.pop("host_group", 8)
    return s.document(
        faces=[s.wall("host", host_group)],
        windows=[s.window("window_1", "host", **overrides)],
    )


def test_a_window_is_projected_onto_its_host_plane() -> None:
    """designPH sets windows into a reveal, so the panel sits proud of the wall. That offset is
    carried as PH reveal data, not as geometry — an aperture floating 100 mm off its wall is not a
    better model, it is an invalid one."""
    result = translate(parse(window_document()))
    model = json.loads(result.hbjson)
    apertures = model["rooms"][0]["faces"][0]["apertures"]
    assert len(apertures) == 1
    # Every corner is back on the host plane (y = 0), not at the panel's y = -0.1.
    assert {round(point[1], 6) for point in apertures[0]["geometry"]["boundary"]} == {0.0}


def test_the_reveal_becomes_ph_shading_dimensions_in_metres() -> None:
    result = translate(parse(window_document()))
    model = json.loads(result.hbjson)
    ph = model["rooms"][0]["faces"][0]["apertures"][0]["properties"]["ph"]
    # 12.5 in × 0.0254 = 0.3175 m. Inches-as-Strings on the way in.
    assert abs(ph["shading_dims"]["d_reveal"] - 0.3175) < 1e-9
    assert abs(ph["shading_dims"]["o_reveal"] - 11 * 0.0254) < 1e-9
    # Horizon and overhang fields stay empty: those are a shading calculation, which the POC does
    # not do, and the model-level marker says so.
    assert ph["shading_dims"]["h_hori"] is None
    assert ph["shading_dims"]["d_over"] is None


def test_a_window_that_does_not_fit_its_host_is_refused_by_name() -> None:
    """Never emit a floating aperture. The contract guarantees `designph_name` is never null
    precisely so this line can name the window a user would recognise."""
    result = translate(
        parse(window_document(panel=[(9.0, 0.0, 1.0), (10.0, 0.0, 1.0), (10.0, 0.0, 2.0), (9.0, 0.0, 2.0)]))
    )
    entry = entries(result, "aperture")["window_1"]
    assert entry["outcome"] == "reported-not-translated"
    assert "containment check failed" in entry["reason"]
    assert entry["designph_name"] == "Window 1"


def test_a_window_larger_than_its_host_is_refused() -> None:
    result = translate(
        parse(window_document(panel=[(-1.0, 0.0, -1.0), (5.0, 0.0, -1.0), (5.0, 0.0, 4.0), (-1.0, 0.0, 4.0)]))
    )
    assert entries(result, "aperture")["window_1"]["outcome"] == "reported-not-translated"


def test_an_unresolved_host_is_reported_not_guessed() -> None:
    result = translate(parse(window_document(host_resolution="unresolved")))
    assert "`glued_to` did not resolve" in entries(result, "aperture")["window_1"]["reason"]


def test_a_host_that_is_not_among_the_translated_faces_is_reported() -> None:
    """Legal contract data: the host may be an unclassified face, which never shipped as geometry.
    The join is allowed to dangle and the translator must not crash on it."""
    document = s.document(faces=[s.wall("host", 8)], windows=[s.window("window_1", "some_other_face")])
    entry = entries(translate(parse(document)), "aperture")["window_1"]
    assert "unclassified host" in entry["reason"]


def test_a_holed_host_accepts_its_aperture_and_says_the_opening_is_counted_twice() -> None:
    """⚠ Only 2 of Adelphi's 16 host faces model the opening as an inner loop — a glued opening
    usually creates no loop at all — which is exactly why this is easy to miss.

    honeybee expects an aperture to be a sub-face of the **gross** face and subtracts the opening
    itself, so a host that already carries the hole subtracts it twice. The window is still emitted:
    it is real, and dropping it would lose more than the double subtraction costs. What is not
    allowed is staying quiet about it.
    """
    document = s.document(
        faces=[
            s.wall("host", 8, holes=[[(1.0, 0.0, 1.0), (2.0, 0.0, 1.0), (2.0, 0.0, 2.0), (1.0, 0.0, 2.0)]])
        ],
        windows=[s.window("window_1", "host", host_has_inner_loops=True)],
    )
    entry = entries(translate(parse(document)), "aperture")["window_1"]
    assert entry["outcome"] == "translated-with-notes"
    assert "subtracted twice" in entry["reason"]


@pytest.mark.parametrize("group", [9, 11])
def test_a_ground_coupled_host_refuses_the_aperture_and_says_why(group: int) -> None:
    """⚠ A direct interaction between §3's boundary conditions and §4's apertures: honeybee raises
    `Aperture cannot be added to Face … with a Ground boundary condition`. designPH groups 9 and 11
    map to Ground, so a window in a below-grade wall is refused — correctly, and loudly."""
    result = translate(parse(window_document(host_group=group)))
    entry = entries(result, "aperture")["window_1"]
    assert entry["outcome"] == "reported-not-translated"
    assert "refused the aperture" in entry["reason"]


def test_a_window_with_no_panel_rectangle_is_reported() -> None:
    document = window_document()
    document["windows"][0]["panel_outer_loop"] = None
    assert "no window rectangle" in entries(translate(parse(document)), "aperture")["window_1"]["reason"]


def test_frame_and_glazing_ids_travel_even_though_the_libraries_do_not() -> None:
    """`frames_ud` and `glazing_ud` are not in the contract's shipped tables. Carrying the ids is
    what lets a v1 that adds those tables have somewhere to put the answer."""
    entry = entries(translate(parse(window_document())), "aperture")["window_1"]
    assert entry["frametypeid"] == "01ud"
    assert entry["glazingtypeid"] == "01ud"


def test_a_rectangle_far_off_the_host_plane_is_refused_rather_than_projected() -> None:
    """⚠ The check that would have caught the parent-relative transform in one line.

    Shipping `instance.transformation` verbatim put all 46 of Adelphi's windows **1.2–3.3 m** off
    their own hosts — and projection absorbed it in silence, because a rectangle a metre out
    projects onto the plane exactly as cleanly as one a millimetre out. A reveal is centimetres;
    anything past half a metre is a coordinate-space error wearing a reveal's clothes.
    """
    document = window_document(panel=[(1.0, -2.0, 1.0), (2.0, -2.0, 1.0), (2.0, -2.0, 2.0), (1.0, -2.0, 2.0)])
    entry = entries(translate(parse(document)), "aperture")["window_1"]
    assert entry["outcome"] == "reported-not-translated"
    assert "off host" in entry["reason"] and "coordinate-space error" in entry["reason"]
    assert entry["off_plane_m"] == 2.0


def test_a_real_reveal_passes_and_its_offset_is_recorded() -> None:
    """The measured offsets on the fixed capture are 0.000 m — the window origin lies exactly on
    its host plane — so the number is worth carrying: it is the early warning, not just a gate."""
    entry = entries(translate(parse(window_document())), "aperture")["window_1"]
    assert entry["outcome"] == "translated"
    assert entry["off_plane_m"] == 0.1


def test_a_window_flush_with_its_hosts_edge_is_accepted() -> None:
    """⚠ Ordinary geometry, and it was refused. A window at the end of a wall has corners exactly on
    the host boundary; `Polygon2D.is_point_inside_bound_rect` takes no tolerance and said no, while
    the tolerant `point_relationship` on the very next line said yes. One of Adelphi's 46 windows is
    built this way. The library's predicate is the whole test — `0`, on the edge, is a pass.
    """
    flush = [(0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 0.0, 2.0), (0.0, 0.0, 2.0)]
    entry = entries(translate(parse(window_document(panel=flush))), "aperture")["window_1"]
    assert entry["outcome"] != "reported-not-translated", entry.get("reason")


def test_a_flush_window_is_emitted_and_the_report_predicts_the_validator() -> None:
    """Emitted, not repaired — and the report says in advance what `ValidateModel` will say.

    `Face3D.is_sub_face` takes no tolerance, so a corner 1 µm past the host edge (which is the
    collector's own coordinate rounding, not an overhang) reads as *not fully bounded*. Shrinking
    the window to please the checker would fabricate an area; the honest move is to warn.
    """
    flush = [(0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 0.0, 2.0), (0.0, 0.0, 2.0)]
    entry = entries(translate(parse(window_document(panel=flush))), "aperture")["window_1"]
    assert entry["outcome"] == "translated-with-notes"
    assert "not coplanar or fully bounded" in entry["reason"]


# ------------------------------------------------------------------------------------------------
# The inline frame/glazing libraries — contract v2, §5.1
# ------------------------------------------------------------------------------------------------


LIBRARIES = {
    "frame_types": ["&PH-FRAMES: average thermal quality=01ud&Alumil S.A. - SD95=1806ed04&"],
    "glazing_types": [
        # ⚠ Both shapes are real: designPH writes a placeholder on some definitions, so the
        # collector ships every distinct string and lets Python choose. A placeholder that
        # overwrote the real library would silently un-name every id.
        "&Launch designPH to edit=01ud&",
        "&PH Glazing=01ud&Double glazing 4/16mm air/4=94ud&",
    ],
}


def test_the_libraries_put_names_on_the_ids() -> None:
    """The whole point of carrying 45 KB of option list: a report line that reads
    `PH Glazing (01ud)` instead of `01ud`, with no CSV library anywhere on disk."""
    document = window_document()
    document["libraries"] = LIBRARIES
    entry = entries(translate(parse(document)), "aperture")["window_1"]
    assert entry["frametype_name"] == "PH-FRAMES: average thermal quality (01ud)"
    assert entry["glazingtype_name"] == "PH Glazing (01ud)"


def test_a_placeholder_option_list_never_overwrites_the_real_one() -> None:
    from dph_translator.contract import Library

    library = Library.from_raw(LIBRARIES["glazing_types"])
    assert library.sources == 2
    assert library.names["01ud"] == "PH Glazing"
    assert library.names["94ud"] == "Double glazing 4/16mm air/4"


def test_an_unnamed_id_simply_gets_no_name() -> None:
    """Absence is information: "the library named 3 of 46 ids" is a different situation from
    "there is no library", and only one of them means going to look for the CSVs."""
    document = window_document()
    document["libraries"] = {"frame_types": ["&Something else=99ud&"]}
    entry = entries(translate(parse(document)), "aperture")["window_1"]
    assert "frametype_name" not in entry and entry["frametypeid"] == "01ud"


def test_a_name_containing_an_equals_sign_survives() -> None:
    """`rsplit`, not `split`: a product name may contain '=', an id never does."""
    from dph_translator.contract import Library

    assert Library.from_raw(["&Glass U=0.7 triple=07ud&"]).names["07ud"] == "Glass U=0.7 triple"


def test_the_summary_counts_the_library_entries() -> None:
    document = window_document()
    document["libraries"] = LIBRARIES
    summary = translate(parse(document)).report["summary"]["libraries"]
    assert summary["frame_types"] == {"entries": 2, "sources": 1}
    assert summary["glazing_types"] == {"entries": 2, "sources": 2}
