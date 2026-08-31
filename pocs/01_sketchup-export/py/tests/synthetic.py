"""Synthetic extraction documents, one builder per translator case.

⚠ **These are scaffolding, not evidence.** The house lesson stands: *a synthetic model is not
evidence about real models* — a six-face model already produced one confidently wrong schema rule on
this project. Nothing here licenses a conclusion about designPH. What carries evidential weight is
POC-3b's goldens, captured from corpus copies by POC-2.

**A deviation from contract §7, deliberately.** The contract says "hand-written JSONs". These are
hand-written *builders* that return contract-shaped dicts, and every test parses them through the
same `contract.parse` a real capture goes through — so the code path is identical. The reason is
readability: `wall("w1", 8, x0=0.0, x1=4.0)` is checkable by eye, and twelve floats in a JSON file
are not. A fixture nobody can read is a fixture nobody can tell is wrong.
"""

from __future__ import annotations

from typing import Any

Point = tuple[float, float, float]


def document(**sections: Any) -> dict[str, Any]:
    """A contract-v2 envelope with whatever sections the case needs."""
    payload: dict[str, Any] = {
        "contract_version": 2,
        "generated_by": "synthetic fixture",
        "model": {"file_name": "synthetic", "designph_versions": ["2.2.29"]},
        "counts": {},
        "faces": [],
        "edges": [],
        "windows": [],
        "libraries": {},
        "tables": {},
        "unclassified": {"tagged_faces": [], "untagged_by_tag": {}},
    }
    payload.update(sections)
    return payload


# ------------------------------------------------------------------------------------------------
# Geometry — named, so a fixture reads as a building rather than as coordinates
# ------------------------------------------------------------------------------------------------


def rectangle(points: list[Point]) -> list[list[float]]:
    return [list(point) for point in points]


def wall(
    identifier: str,
    area_group: Any,
    *,
    x0: float = 0.0,
    x1: float = 4.0,
    y: float = 0.0,
    z0: float = 0.0,
    z1: float = 3.0,
    **extra: Any,
) -> dict[str, Any]:
    """A vertical rectangle in the XZ plane, wound counter-clockwise seen from -Y."""
    return face(
        identifier,
        area_group,
        [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)],
        **extra,
    )


def mirrored_wall(identifier: str, area_group: Any, **extra: Any) -> dict[str, Any]:
    """The same wall through a mirroring transform: the winding reverses with the geometry.

    No normal is shipped (contract §2.2) precisely so this case works — Python derives orientation
    from `Face3D.normal`, and a mirrored winding gives the consistent answer where a transformed
    normal would not.
    """
    return face(
        identifier,
        area_group,
        [(0.0, 0.0, 0.0), (0.0, 0.0, 3.0), (-4.0, 0.0, 3.0), (-4.0, 0.0, 0.0)],
        **extra,
    )


def floor(
    identifier: str,
    area_group: Any,
    *,
    size: float = 4.0,
    z: float = 0.0,
    **extra: Any,
) -> dict[str, Any]:
    return face(
        identifier,
        area_group,
        [(0.0, 0.0, z), (size, 0.0, z), (size, size, z), (0.0, size, z)],
        **extra,
    )


def tilted_floor(identifier: str, area_group: Any, **extra: Any) -> dict[str, Any]:
    """A group-1 face that is genuinely sloped — 2 m of fall across 4 m. Reported, never flattened:
    projecting this to its mean z would be fabrication, not noise removal."""
    return face(
        identifier,
        area_group,
        [(0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 4.0, 2.0), (0.0, 4.0, 2.0)],
        **extra,
    )


def noisy_floor(identifier: str, area_group: Any, *, spread: float = 1.2e-5, **extra: Any) -> dict[str, Any]:
    """A group-1 face that is horizontal by every modelling standard except honeybee's.

    ⚠ **This is the shape that cost 368 m².** Two of Adelphi's 40 TFA faces have a 12 µm z-spread
    with `normal.z = 0.999999999998`. `Face3D.is_horizontal` tests **z-extent** at **1e-7 m**, so
    they fail it — and since `Space.from_room` raises for the whole room, those two lost all 40.
    A normal-direction pre-filter waves them through, which is exactly what the first one did.
    """
    return face(
        identifier,
        area_group,
        [(0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 4.0, spread), (0.0, 4.0, spread)],
        **extra,
    )


def sliver(identifier: str, area_group: Any, **extra: Any) -> dict[str, Any]:
    """Adelphi's own sliver: a 1.7 cm² triangle with two vertices 0.42 mm apart."""
    return face(
        identifier,
        area_group,
        [(0.0, 0.0, 0.0), (0.81, 0.0, 0.0), (0.0, 0.00042, 0.0)],
        **extra,
    )


def spur(identifier: str, area_group: Any, **extra: Any) -> dict[str, Any]:
    """Adelphi's `face_3281_1710`: the boundary runs 0.8 m out and straight back to the same point.

    ⚠ Every edge of that spur is *long*, so a short-edge test does not find it.
    """
    return face(
        identifier,
        area_group,
        [
            (0.0, 0.0, 0.0),
            (4.0, 0.0, 0.0),
            (4.0, 4.0, 0.0),
            (4.8, 4.0, 0.0),
            (4.0, 4.0, 0.0),
            (0.0, 4.0, 0.0),
        ],
        **extra,
    )


def face(
    identifier: str,
    area_group: Any,
    points: list[Point],
    *,
    holes: list[list[Point]] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": identifier,
        "entity_id": abs(hash(identifier)) % 100000,
        "area_group": area_group,
        "outer_loop": rectangle(points),
        "inner_loops": [rectangle(hole) for hole in (holes or [])],
        "both_generations": [],
    }
    record.update(extra)
    return record


def edge(
    identifier: str,
    area_group: Any,
    *,
    start: Point = (0.0, 0.0, 0.0),
    end: Point = (4.0, 0.0, 0.0),
    connection_ref: Any = None,
    **extra: Any,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": identifier,
        "area_group": area_group,
        "connection_ref": connection_ref,
        "desc_name": None,
        "start": list(start),
        "end": list(end),
        "length_m": round(sum((a - b) ** 2 for a, b in zip(start, end, strict=True)) ** 0.5, 6),
        "both_generations": [],
    }
    record.update(extra)
    return record


def window(
    identifier: str,
    host_face_id: str | None,
    *,
    panel: list[Point] | None = None,
    host_resolution: str = "glued_to",
    d_reveal: str = "12.5",
    o_reveal: str = "11",
    **extra: Any,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": identifier,
        "designph_name": identifier.replace("window_", "Window "),
        "definition_name": "designPH_Window_Simple_1-1",
        "dynamic_attributes": {
            "frametypeid": "01ud",
            "glazingtypeid": "01ud",
            "lenx": "39.37",
            "leny": "39.37",
            "d_reveal": d_reveal,
            "o_reveal": o_reveal,
        },
        "transformation": [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0],
        # Deliberately set 0.1 m proud of the wall plane: designPH sets windows into a reveal, and
        # the translator must project rather than emit a floating aperture.
        "panel_outer_loop": rectangle(
            panel or [(1.0, -0.1, 1.0), (2.0, -0.1, 1.0), (2.0, -0.1, 2.0), (1.0, -0.1, 2.0)]
        ),
        "host_face_id": host_face_id,
        "host_resolution": host_resolution,
        "host_has_inner_loops": False,
    }
    record.update(extra)
    return record


# ------------------------------------------------------------------------------------------------
# Tables
# ------------------------------------------------------------------------------------------------


def table(tokens: list[str], rows: list[list[Any]]) -> dict[str, Any]:
    return {"tokens": tokens, "rows": rows}


def assemblies_ud(*rows: list[Any]) -> dict[str, Any]:
    """Tier 2: a header row carrying a U-value directly, and **no layers**."""
    return table(["id", "desc", "assem_num", "thk", "U_value", "int_insul"], list(rows))


def assemblies_calc(*rows: list[Any]) -> dict[str, Any]:
    """Tier 2a. ⚠ Note what is missing: **there is no U-value column at all.**"""
    return table(
        [
            "id",
            "desc",
            "R_in",
            "R_out",
            "surf2_percentage",
            "surf3_percentage",
            "additional_U_value",
            "int_insul",
        ],
        list(rows),
    )


def layer_table(*rows: list[Any], with_r_values: bool = False) -> dict[str, Any]:
    """Tier 1. Two real schemas exist — 8 columns, and 12 with `R1..R_tot` (Linde `250703`).

    Both are read **by name**, which is what `:TOKENS` is for; a positional read mixes them up.
    """
    tokens = ["id", "desc1", "lambda1", "desc2", "lambda2", "desc3", "lambda3", "thickness"]
    if with_r_values:
        tokens += ["R1", "R2", "R3", "R_tot"]
    return table(tokens, list(rows))


def vent_ud(*, room_height: float = 2.5, rows: int = 1) -> dict[str, Any]:
    return table(
        ["vent_sys_ID", "vent_type_ID", "room_height", "V_n50", "result_n50", "coeff_e", "coeff_f"],
        [[1, 1, room_height + index, 1200.0, 0.6, 0.07, 15.0] for index in range(rows)],
    )


def connections_ud(*rows: list[Any]) -> dict[str, Any]:
    return table(["id", "desc", "areaGroupID", "areaGroupName", "Psi_value", "F_rsi"], list(rows))


def full_model_document() -> dict[str, Any]:
    """One synthetic model carrying **every PH payload the POC emits**.

    It exists because of a specific trap POC-3 §11 names: Phase 3's clean schema verdict came from a
    model with *no* spaces, no thermal bridges and no aperture PH properties, so "the PH segment
    validates" had never actually been tested against what this phase adds. Six faces, because
    honeybee-schema requires a Room to have at least four.

    Shared by the test suite and `tools/validate_output.py`, so the thing validated and the thing
    tested cannot drift apart.
    """
    return document(
        model={
            "file_name": "synthetic_full",
            "designph_versions": ["2.2.29"],
            "klima_id": "US0058a",
            "klima_standort": "New York",
        },
        faces=[
            wall("host", 8, assembly_ref="01ud"),
            wall("w_north", 8, y=4.0, assembly_ref="01ud"),
            wall("w_ground", 9, x0=0.0, x1=0.0, assembly_ref="02ud"),
            wall("w_party", 18),
            floor("tfa", 1, tfa_rf=0.8),
            floor("roof", 10, z=3.0, assembly_ref="03ud"),
        ],
        edges=[edge("tb_parapet", 15, connection_ref="101ud")],
        windows=[window("win_south", "host")],
        tables={
            "assemblies_ud": assemblies_ud(
                ["01ud", "WT-1", 1, 300.0, 0.15, False],
                ["02ud", "FT-1", 2, 400.0, 0.12, True],
            ),
            "layer_table_03ud": layer_table(
                ["03ud", "Mineral wool", 0.035, None, None, None, None, 300.0],
                ["03ud", "Plywood", 0.13, None, None, None, None, 18.0],
            ),
            "connections_ud": connections_ud(["101ud", "Parapet", 15, "Ambient", 0.045, 0.82]),
            "vent_ud": vent_ud(room_height=2.6),
        },
        unclassified={
            "tagged_faces": [{"id": "u_1", "area_group": "n", "tag": "Layer0"}],
            "untagged_by_tag": {"04_SHADING_TREES": 392},
        },
    )
