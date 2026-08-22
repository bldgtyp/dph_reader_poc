"""TFA, the site, and the report's own guarantees.

**TFA is a headline Passive House number.** Phase 3 produced no `Space` at all from the real Adelphi
model and nothing said so — the silent zero these tests exist to prevent. The POC's contribution is
not a clever derivation; it is *measuring* how much TFA area the honest strategy loses, which is why
coverage and loss are both in the summary whether or not anything went wrong.

The report's completeness invariant is hard rule 4 as a unit test: every face, edge and window is
either an object in the HBJSON or a row in `entries`, and the two sets are disjoint.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dph_translator import HBJSON_SCHEMA_VERSION
from dph_translator.build import translate
from dph_translator.contract import parse
from dph_translator.report import SHADING_MARKER

from . import synthetic as s

REPO = Path(__file__).resolve().parents[3]


# ------------------------------------------------------------------------------------------------
# TFA
# ------------------------------------------------------------------------------------------------


def tfa_document(*faces: dict[str, Any], room_height: float = 2.5, rows: int = 1) -> dict[str, Any]:
    return s.document(faces=list(faces), tables={"vent_ud": s.vent_ud(room_height=room_height, rows=rows)})


def test_a_horizontal_tfa_face_becomes_a_ph_space() -> None:
    result = translate(parse(tfa_document(s.floor("tfa", 1), s.wall("w", 8))))
    model = json.loads(result.hbjson)
    assert len(model["rooms"][0]["properties"]["ph"]["spaces"]) == 1
    assert result.report["summary"]["spaces"]["derived"] == 1
    assert abs(result.report["summary"]["tfa_m2_covered"] - 16.0) < 1e-6
    assert result.report["summary"]["tfa_m2_lost"] == 0.0


def test_a_sloped_tfa_face_is_named_and_its_area_counted_as_lost() -> None:
    """A genuinely sloped floor is refused, not flattened: 2 m of fall is not noise."""
    result = translate(parse(tfa_document(s.tilted_floor("tilted", 1), s.wall("w", 8))))
    entry = result.report["entries"]["tfa"]["listed"][0]
    assert entry["id"] == "tilted"
    assert "z-spread" in entry["reason"] and "flattening limit" in entry["reason"]
    assert result.report["summary"]["tfa_m2_lost"] > 0
    assert result.report["summary"]["spaces"]["derived"] == 0


def test_a_micron_of_z_spread_does_not_cost_the_room() -> None:
    """⚠ The defect that cost Adelphi 368 m², as a test.

    A 12 µm z-spread fails `Face3D.is_horizontal` at honeybee's 1e-7 m while passing any
    normal-direction test, so the first pre-filter waved it through and `Space.from_room` raised for
    the **whole room**. Two faces, forty lost. Here the noisy face is flattened and reported, and —
    the part that matters — the clean face beside it still becomes a Space.
    """
    result = translate(
        parse(tfa_document(s.noisy_floor("noisy", 1), s.floor("clean", 1, z=3.0), s.wall("w", 8)))
    )
    summary = result.report["summary"]
    assert summary["spaces"]["derived"] == 1
    assert summary["tfa_m2_lost"] == 0.0
    assert abs(summary["tfa_m2_covered"] - 32.0) < 1e-4

    entries = {entry["id"]: entry for entry in result.report["entries"]["tfa"]["listed"]}
    assert entries["noisy"]["outcome"] == "translated-with-notes"
    assert "flattened to its mean z" in entries["noisy"]["reason"]
    assert "clean" not in entries, "a face that needed nothing must not be reported as adjusted"


def test_flattening_stops_at_the_stated_threshold() -> None:
    """The line between noise removal and fabrication is 1 mm, and it is drawn explicitly."""
    result = translate(parse(tfa_document(s.noisy_floor("just_over", 1, spread=0.002))))
    entry = result.report["entries"]["tfa"]["listed"][0]
    assert entry["outcome"] == "reported-not-translated"
    assert "2.0 mm z-spread" in entry["reason"]


def test_a_face_honeybee_refuses_costs_only_itself(monkeypatch: Any) -> None:
    """`Space.from_room` raises for the **whole room**, so a refusal has to be narrowed to the face
    honeybee names — otherwise one bad polygon takes every good one with it, which is precisely how
    two 12 µm faces cost Adelphi all forty.

    The refusal is injected rather than provoked: honeybee happily extrudes Adelphi's real sliver,
    and a test that depends on finding a polygon it *won't* extrude would be testing ladybug's
    robustness rather than our narrowing.
    """
    from honeybee_ph.space import Space

    original = Space.from_room

    def refusing(hb_room: Any, height: float) -> Any:
        if any(face.identifier == "sliver" for face in hb_room.faces):
            raise ValueError(
                f"Honeybee Room '{hb_room.display_name}' Floor face 'sliver' "
                "could not be extruded into a solid volume."
            )
        return original(hb_room, height)

    monkeypatch.setattr(Space, "from_room", staticmethod(refusing))
    result = translate(parse(tfa_document(s.sliver("sliver", 1), s.floor("good", 1, z=3.0))))

    summary = result.report["summary"]
    assert summary["spaces"]["derived"] == 1
    assert abs(summary["tfa_m2_covered"] - 16.0) < 1e-9
    entries = {entry["id"]: entry for entry in result.report["entries"]["tfa"]["listed"]}
    assert entries["sliver"]["outcome"] == "reported-not-translated"
    assert "refused this face" in entries["sliver"]["reason"]


def test_an_unattributable_refusal_reports_every_candidate(monkeypatch: Any) -> None:
    """A refusal that names nobody leaves nothing to drop — so nothing is guessed at, and every
    candidate is named as lost instead of the run reporting a quiet zero."""
    from honeybee_ph.space import Space

    monkeypatch.setattr(
        Space, "from_room", staticmethod(lambda room, height: (_ for _ in ()).throw(ValueError("nope")))
    )
    result = translate(parse(tfa_document(s.floor("a", 1), s.floor("b", 1, z=3.0))))
    assert result.report["summary"]["spaces"]["derived"] == 0
    assert abs(result.report["summary"]["tfa_m2_lost"] - 32.0) < 1e-9
    assert {e["id"] for e in result.report["entries"]["tfa"]["listed"]} == {"a", "b"}


def test_degenerate_geometry_is_named_and_carried_not_dropped() -> None:
    """Adelphi contains a 1.7 cm² sliver and a zero-width spur. **Report, don't repair** — and don't
    drop either: a classified face that vanished would break `82 of 82`, the first number a reader
    checks. ⚠ Every edge of the spur is long, so a short-edge test alone does not find it."""
    result = translate(parse(s.document(faces=[s.sliver("sliver", 8), s.spur("spur", 8)])))
    entries = {entry["id"]: entry for entry in result.report["entries"]["face"]["listed"]}
    assert entries["sliver"]["outcome"] != "reported-not-translated"
    assert "cm² sliver" in entries["sliver"]["reason"]
    assert "revisits" in entries["spur"]["reason"]
    assert json.loads(result.hbjson)["rooms"][0]["faces"].__len__() == 2


def test_a_mixed_model_derives_what_it_can_and_names_what_it_cannot() -> None:
    result = translate(parse(tfa_document(s.floor("tfa", 1), s.tilted_floor("tilted", 1))))
    summary = result.report["summary"]
    assert summary["spaces"]["derived"] == 1
    assert summary["tfa_m2_covered"] > 0 and summary["tfa_m2_lost"] > 0
    assert [e["id"] for e in result.report["entries"]["tfa"]["listed"]] == ["tilted"]


def test_group_11_is_envelope_floor_not_tfa() -> None:
    """Decision D-4. Group 11 is the floor slab; using it as a TFA candidate would inflate the
    headline number with a surface PHPP counts as envelope."""
    result = translate(parse(tfa_document(s.floor("slab", 11), s.wall("w", 8))))
    assert result.report["summary"]["spaces"]["derived"] == 0
    assert result.report["summary"]["tfa_m2_covered"] == 0.0


def test_an_absent_tfa_rf_means_a_weighting_factor_of_one_not_exclusion() -> None:
    """⚠ On Adelphi only 7 of ~40 group-1 faces carry `TFA_rf`. Filtering on its presence would
    drop the other 33 and report a plausible, badly wrong number."""
    result = translate(parse(tfa_document(s.floor("tfa", 1))))
    model = json.loads(result.hbjson)
    space = model["rooms"][0]["properties"]["ph"]["spaces"][0]
    factors = [
        segment["weighting_factor"]
        for volume in space["volumes"]
        for segment in volume["floor"]["floor_segments"]
    ]
    assert factors == [1.0]
    assert abs(result.report["summary"]["tfa_m2_covered"] - 16.0) < 1e-6


def test_a_present_tfa_rf_reaches_the_floor_segment() -> None:
    result = translate(parse(tfa_document(s.floor("tfa", 1, tfa_rf=0.5))))
    model = json.loads(result.hbjson)
    space = model["rooms"][0]["properties"]["ph"]["spaces"][0]
    factors = [
        segment["weighting_factor"]
        for volume in space["volumes"]
        for segment in volume["floor"]["floor_segments"]
    ]
    assert factors == [0.5]


def test_the_ceiling_height_comes_from_vent_ud() -> None:
    result = translate(parse(tfa_document(s.floor("tfa", 1), room_height=2.8)))
    assert result.report["summary"]["spaces"]["ceiling_height_m"] == 2.8


def test_several_vent_ud_rows_use_the_first_and_say_so() -> None:
    """Averaging them would invent a building that does not exist."""
    result = translate(parse(tfa_document(s.floor("tfa", 1), room_height=2.4, rows=3)))
    assert result.report["summary"]["spaces"]["ceiling_height_m"] == 2.4
    assert any("3 rows; using the first" in note for note in result.report["notes"])


def test_no_vent_ud_falls_back_and_says_so() -> None:
    document = s.document(faces=[s.floor("tfa", 1)])
    result = translate(parse(document))
    assert any("no `vent_ud`" in note for note in result.report["notes"])
    assert result.report["summary"]["spaces"]["derived"] == 1


def test_the_real_room_keeps_its_faces_when_the_tfa_scratch_room_is_built() -> None:
    """`Room.__init__` re-parents whatever it is given. Building the TFA extrusion room from the
    real Room's faces would silently steal them — so it is built from duplicates."""
    result = translate(parse(tfa_document(s.floor("tfa", 1), s.wall("w", 8))))
    model = json.loads(result.hbjson)
    assert len(model["rooms"][0]["faces"]) == 2


# ------------------------------------------------------------------------------------------------
# Site
# ------------------------------------------------------------------------------------------------


def test_the_climate_id_is_carried_not_resolved() -> None:
    document = s.document(faces=[s.wall("w", 8)])
    document["model"]["klima_id"] = "US0058a"
    document["model"]["klima_standort"] = "New York"
    site = translate(parse(document)).report["summary"]["site"]
    assert site["klima_id"] == "US0058a"
    assert site["resolved"] is False


def test_the_report_disowns_honeybees_default_site() -> None:
    """⚠ honeybee-ph fabricates a New York site on every building segment and it serialises looking
    exactly like project data. A consumer cannot tell it is a placeholder; the report is the only
    place that can say so."""
    result = translate(parse(s.document(faces=[s.wall("w", 8)])))
    assert any("DEFAULT site" in note for note in result.report["notes"])
    assert result.report["summary"]["site"]["hb_default_site"]["latitude"] == 40.6


def test_a_model_with_no_climate_says_so() -> None:
    result = translate(parse(s.document(faces=[s.wall("w", 8)])))
    assert any("no climate identification" in note for note in result.report["notes"])


# ------------------------------------------------------------------------------------------------
# The report's own guarantees
# ------------------------------------------------------------------------------------------------


def busy_document() -> dict[str, Any]:
    """One of everything, including several things that cannot translate."""
    return s.document(
        faces=[s.wall("host", 8, assembly_ref="01ud"), s.floor("tfa", 1), s.wall("bad", "n")],
        edges=[s.edge("tb_ok", 15, connection_ref="101ud"), s.edge("tb_odd", 8)],
        windows=[s.window("win_ok", "host"), s.window("win_lost", "missing_face")],
        tables={
            "assemblies_ud": s.assemblies_ud(["01ud", "WT-1", 1, 300.0, 0.15, False]),
            "connections_ud": s.connections_ud(["101ud", "Parapet", 15, "x", 0.045, 0.82]),
            "vent_ud": s.vent_ud(),
        },
        unclassified={
            "tagged_faces": [{"id": "u_1", "area_group": "n", "tag": "Layer0"}],
            "untagged_by_tag": {"04_SHADING_TREES": 392},
        },
    )


def test_the_completeness_invariant_holds() -> None:
    """Hard rule 4, as an assertion: every face, edge and window appears either in the HBJSON or in
    `entries`, and the two sets are disjoint."""
    document = busy_document()
    result = translate(parse(document))
    expected = {r["id"] for r in document["faces"] + document["edges"] + document["windows"]}

    listed: dict[str, str] = {}
    for kind in ("face", "aperture", "thermal_bridge"):
        for entry in result.report["entries"][kind]["listed"]:
            listed[entry["id"]] = entry["outcome"]
    assert expected <= set(listed), f"unaccounted: {expected - set(listed)}"

    model = json.loads(result.hbjson)
    in_model = {face["identifier"] for face in model["rooms"][0]["faces"]}
    in_model |= {
        aperture["identifier"]
        for face in model["rooms"][0]["faces"]
        for aperture in face.get("apertures", [])
    }
    omitted = {name for name, outcome in listed.items() if outcome == "reported-not-translated"}
    # Disjoint: nothing reported-not-translated may also be in the model.
    assert not (omitted & in_model), f"both omitted and present: {omitted & in_model}"


def test_the_run_checks_its_own_completeness() -> None:
    assert any(
        check["label"] == "every entity accounted for" and check["ok"]
        for check in translate(parse(busy_document())).verdict["checks"]
    )


def test_omissions_change_the_headline_but_not_the_pass() -> None:
    """`PASSED` means everything translated, which is **rare on real models, and that is fine**. A
    translator reporting PASSED on a model it silently truncated is the worse outcome by far."""
    verdict = translate(parse(busy_document())).verdict
    assert verdict["passed"] is True
    assert verdict["headline"] == "PASSED WITH OMISSIONS"


def test_a_clean_model_says_passed_without_qualification() -> None:
    document = s.document(
        faces=[s.wall("w", 8, assembly_ref="01ud")],
        tables={"assemblies_ud": s.assemblies_ud(["01ud", "WT-1", 1, 300.0, 0.15, False])},
    )
    assert translate(parse(document)).verdict["headline"] == "PASSED"


def test_every_unclassified_face_is_named_in_the_report() -> None:
    """The 82/1441/8037 gap is the design problem. The POC reports it rather than solving it — and
    the report must be able to NAME every designPH-tagged entity it omits."""
    block = translate(parse(busy_document())).report["unclassified"]
    assert [face["id"] for face in block["tagged_faces"]] == ["u_1"]
    assert block["untagged_by_tag"] == {"04_SHADING_TREES": 392}


def test_the_shading_marker_and_the_reveal_data_do_not_contradict_each_other() -> None:
    """Reveal dimensions ARE present while shading factors and context are not. The wording has to
    carry both claims or a reader will believe one of them is wrong."""
    report = translate(parse(busy_document())).report
    assert report["shading"] == SHADING_MARKER
    assert "reveal dimensions ARE present" in report["shading_note"]
    assert "No shading factors and no context geometry" in report["shading_note"]


def test_the_shading_marker_travels_inside_the_hbjson_too() -> None:
    """Decision D-3: the disclosure rides in `model.user_data`, so the model cannot be passed on
    without it. Verified to survive `to_dict`."""
    model = json.loads(translate(parse(busy_document())).hbjson)
    assert model["user_data"]["dph_plus"]["shading"] == SHADING_MARKER


def test_the_schema_version_is_stamped() -> None:
    """honeybee leaves it null — `honeybee-schema` is deliberately not installed. Decision D-2."""
    model = json.loads(translate(parse(busy_document())).hbjson)
    assert model["version"] == HBJSON_SCHEMA_VERSION


def test_the_stamped_version_matches_the_validator_the_repo_uses() -> None:
    """A stamp that claims a version nothing validates against is worse than no stamp."""
    validator = (REPO / "planning/spikes/phase0/validate_hbjson_core.py").read_text()
    assert f"honeybee-schema=={HBJSON_SCHEMA_VERSION}" in validator


def test_the_assembly_tier_distribution_is_measured() -> None:
    """POC-3 §12 asks for this table as one of the POC's first real products."""
    tiers = translate(parse(busy_document())).report["summary"]["assembly_tiers"]
    assert tiers["2-u-value"] == 1
    assert tiers["none"] == 2
