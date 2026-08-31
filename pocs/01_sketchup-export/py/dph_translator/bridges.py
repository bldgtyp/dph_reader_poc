"""Thermal bridges: tagged edges → `PhThermalBridge` on the Room's PH building segment.

⚠ **This is the entity class a face-only reader loses entirely and silently** — 99 of 293 tagged
entities on `2414 Bluff Reach.skp`. The count assertion is therefore the point of this module:
*n in, n out-or-reported, zero silently gone*.

Two traps, both about which table an id names:

* an edge's reference resolves against **`connections_ud`**, never the assembly tables. Both
  namespaces use `NNud` ids, so getting it backwards returns an unrelated row rather than an error.
  The contract names the field `connection_ref` for exactly this reason.
* `PhThermalBridge` lives in **`honeybee_energy_ph`**, not `honeybee_ph`.

The API was verified against the vendored wheel on 2026-08-19 and again here — do not rediscover it:
`PhThermalBridge(_identifier, _geometry)` where `_geometry` is a `LineSegment3D`; `length` is a
**read-only property derived from the geometry**; `psi_value`, `fRsi_value`, `quantity` and
`group_type` are settable, and `group_type` accepts exactly `"15-Ambient"`, `"16-Perimeter"`,
`"17-FS/BC"`.
"""

from __future__ import annotations

from typing import Any

from .contract import EdgeRecord, Extraction, as_float

#: PHPP area group → the `PhThermalBridgeType` string honeybee-ph accepts. Verified against
#: `PhThermalBridgeType.allowed`; anything else raises.
GROUP_TYPES: dict[int, str] = {
    15: "15-Ambient",
    16: "16-Perimeter",
    17: "17-FS/BC",
}

#: `connections_ud` tokens (`DESIGNPH_DATA_MODEL.md` §7).
PSI_TOKEN = "Psi_value"
FRSI_TOKEN = "F_rsi"

#: The collector measures the edge too. A disagreement means the transform accumulation is wrong on
#: one side, which is worth surfacing rather than averaging away.
LENGTH_TOLERANCE_M = 0.001


def _segment(record: EdgeRecord) -> Any:
    from ladybug_geometry.geometry3d.line import LineSegment3D
    from ladybug_geometry.geometry3d.pointvector import Point3D

    return LineSegment3D.from_end_points(Point3D(*record.start), Point3D(*record.end))


def build(record: EdgeRecord, extraction: Extraction) -> tuple[Any | None, str, dict[str, Any]]:
    """One edge record → `(bridge, outcome, detail)`.

    `outcome` is `"translated"`, `"translated-with-notes"` or `"reported-not-translated"`, so the
    caller can hold the report's completeness invariant without re-deciding anything.
    """
    from honeybee_energy_ph.construction.thermal_bridge import PhThermalBridge

    detail: dict[str, Any] = {}
    group = record.area_group_int
    if record.error is not None:
        return None, "reported-not-translated", {"reason": record.error}
    if group not in GROUP_TYPES:
        # The contract ships these deliberately: an edge outside 15/16/17 is an anomaly worth
        # seeing, not something for Ruby to have filtered out on its own judgement.
        return (
            None,
            "reported-not-translated",
            {"reason": f"area group {record.area_group!r} is not a thermal-bridge group (15/16/17)"},
        )

    geometry = _segment(record)
    bridge = PhThermalBridge(record.id, geometry)
    bridge.display_name = record.desc_name or record.id
    bridge.group_type = GROUP_TYPES[group]

    if record.length_m is not None and abs(record.length_m - bridge.length) > LENGTH_TOLERANCE_M:
        detail["length_mismatch"] = f"collector {record.length_m} vs geometry {round(bridge.length, 4)}"

    outcome = "translated"
    table = extraction.tables.get("connections_ud")
    connection = table.find("id", record.connection_ref) if table is not None else None
    if connection is None:
        # A bridge with no psi-value is still a bridge, and losing it would be worse than carrying
        # it with honeybee's default. But the report has to say the number is not designPH's.
        detail["reason"] = (
            f"connection {record.connection_ref!r} not found in `connections_ud`"
            if table is not None
            else "the model carries no `connections_ud` table"
        )
        outcome = "translated-with-notes"
    else:
        psi = as_float(connection.get(PSI_TOKEN))
        frsi = as_float(connection.get(FRSI_TOKEN))
        if psi is None:
            detail["reason"] = f"`connections_ud` row {record.connection_ref!r} has no {PSI_TOKEN}"
            outcome = "translated-with-notes"
        else:
            bridge.psi_value = psi
        if frsi is not None:
            bridge.fRsi_value = frsi
        detail["connection"] = str(connection.get("desc") or record.connection_ref)

    detail["group_type"] = GROUP_TYPES[group]
    detail["length_m"] = round(bridge.length, 4)
    if outcome == "translated" and "length_mismatch" in detail:
        outcome = "translated-with-notes"
        detail["reason"] = detail["length_mismatch"]
    return bridge, outcome, detail


def attach(room: Any, bridge: Any) -> None:
    """Bridges hang off the **building segment**, not off the Room's PH properties directly."""
    room.properties.ph.ph_bldg_segment.add_new_thermal_bridge(bridge)
