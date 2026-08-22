"""The contract layer -- parsing, and the type-checking that hard rule 5 requires."""

from __future__ import annotations

from typing import Any

import pytest

from dph_translator.contract import (
    CONTRACT_VERSION,
    ContractError,
    as_positive_int,
    as_text,
    parse,
)


class TestAsPositiveInt:
    """`areaGroupID` is a String on 1359 of 1441 faces in the primary corpus model, most often
    `'n'`. Every one of these cases occurs in real data."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            (8, 8),
            ("8", 8),
            (" 8 ", 8),
            ("10", 10),
            ("n", None),  # designPH's "not assigned"
            ("", None),
            (None, None),
            (0, None),
            ("0", None),
            (-1, None),
            (8.5, None),  # a float here means a misread upstream, not a value to round
            (True, None),  # bool is an int subclass; it is never an area group
            ([], None),
        ],
    )
    def test_coercion(self, value: Any, expected: int | None) -> None:
        assert as_positive_int(value) == expected


@pytest.mark.parametrize(
    "value,expected", [("x", "x"), ("  x  ", "x"), ("", None), ("   ", None), (None, None), (3, None)]
)
def test_as_text(value: Any, expected: str | None) -> None:
    assert as_text(value) == expected


def test_parse_reads_the_stub_fixture(stub_extraction: dict[str, Any]) -> None:
    extraction = parse(stub_extraction)
    assert extraction.contract_version == CONTRACT_VERSION
    assert len(extraction.faces) == 6
    assert extraction.model.klima_id == "US0058a"
    assert "assemblies_ud" in extraction.tables


def test_face_records_keep_raw_values_and_expose_a_checked_int(
    stub_extraction: dict[str, Any],
) -> None:
    faces = {face.id: face for face in parse(stub_extraction).faces}
    # The fixture carries the same area group as both a String and an Integer, on purpose.
    assert faces["face_stub_wall_south"].area_group == "8"
    assert faces["face_stub_wall_east"].area_group == 8
    assert faces["face_stub_wall_south"].area_group_int == 8
    assert faces["face_stub_wall_east"].area_group_int == 8


def test_inner_loops_are_carried_not_flagged(stub_extraction: dict[str, Any]) -> None:
    faces = {face.id: face for face in parse(stub_extraction).faces}
    assert len(faces["face_stub_wall_south"].inner_loops) == 1
    assert len(faces["face_stub_wall_south"].inner_loops[0]) == 4
    assert faces["face_stub_roof"].inner_loops == ()


def test_wrong_contract_version_is_a_hard_error(minimal_extraction: dict[str, Any]) -> None:
    minimal_extraction["contract_version"] = 99
    with pytest.raises(ContractError, match="contract_version"):
        parse(minimal_extraction)


def test_missing_faces_list_is_a_hard_error(minimal_extraction: dict[str, Any]) -> None:
    del minimal_extraction["faces"]
    with pytest.raises(ContractError, match="faces"):
        parse(minimal_extraction)


def test_non_numeric_geometry_costs_one_face_not_the_document(
    minimal_extraction: dict[str, Any],
) -> None:
    """Granularity is the point. A bad coordinate on one face of 1441 must not kill the other 1440
    -- the report has to be able to name it and carry on (hard rule 4)."""
    minimal_extraction["faces"].append(
        {"id": "face_bad", "area_group": 8, "outer_loop": [[0, 0, 0], [1, 0, "oops"], [1, 1, 0]]}
    )
    extraction = parse(minimal_extraction)
    assert len(extraction.faces) == 2
    assert extraction.faces[0].error is None
    assert "not numeric" in str(extraction.faces[1].error)


def test_a_face_that_is_not_an_object_still_travels_with_an_id(
    minimal_extraction: dict[str, Any],
) -> None:
    minimal_extraction["faces"].append("not an object")
    faces = parse(minimal_extraction).faces
    assert faces[1].id == "face_1"
    assert faces[1].error == "record is not an object"


def test_an_undecodable_table_is_kept_apart_from_an_absent_one(
    minimal_extraction: dict[str, Any],
) -> None:
    """Ruby ships an undecodable Marshal blob as `{"error": …}`. It must not masquerade as a table
    -- but nor may it look like a table the model simply does not have, which is the *normal* case
    (Adelphi has no `connections_ud` at all). One is a collector bug; the other is a Tuesday."""
    minimal_extraction["tables"] = {"vent_ud": {"error": "bad blob"}}
    extraction = parse(minimal_extraction)
    assert extraction.tables == {}
    assert extraction.table_errors == {"vent_ud": "bad blob"}


def test_edges_windows_and_unclassified_are_read_by_the_contract_layer(
    stub_extraction: dict[str, Any],
) -> None:
    """They are not translated yet, but they are *typed* here rather than string-keyed out of `raw`
    at the call site -- so POC-3 gives them behaviour without moving their readers."""
    extraction = parse(stub_extraction)
    assert extraction.edges == ()
    assert extraction.windows == ()
    assert [face.id for face in extraction.unclassified] == ["face_stub_unclassified"]
    assert extraction.unclassified[0].tag == "Layer0"
    assert extraction.untagged_by_tag == {"Layer0": 1}


def test_census_invariant_is_checked_not_assumed(stub_extraction: dict[str, Any]) -> None:
    """Contract §6.1: classified + tagged-unclassified must equal the collector's own tally. A
    mismatch is how a whole missing entity type announces itself."""
    assert parse(stub_extraction).census_mismatch() is None
    stub_extraction = dict(stub_extraction)
    stub_extraction["counts"] = dict(stub_extraction["counts"], faces_tagged=99)
    assert "99" in str(parse(stub_extraction).census_mismatch())


def test_tables_are_read_by_name(stub_extraction: dict[str, Any]) -> None:
    table = parse(stub_extraction).tables["assemblies_ud"]
    assert table.column("U_value") == 4
    assert table.column("no_such_column") is None
    assert table.rows[0][table.column("id")] == "01ud"
