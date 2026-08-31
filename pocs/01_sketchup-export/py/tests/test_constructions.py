"""Assemblies, in four tiers.

The thing being defended here is honesty about reach. Only 254 of 532 corpus assembly references
carry a build-up; the rest resolve against designPH's *installed* CSV library, outside the model. So
the tier is recorded per face, a U-value with no build-up is reported as exactly that, and an
unresolvable reference gets **no construction at all** rather than a plausible default.
"""

from __future__ import annotations

from typing import Any

from dph_translator import constructions
from dph_translator.build import translate
from dph_translator.contract import parse

from . import synthetic as s

#: ±0.005 W/m²K — designPH rounds its stored values, and a tighter bar would fail on rounding.
U_TOLERANCE = 0.005


def assembly_entries(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = translate(parse(document))
    return {entry["id"]: entry for entry in result.report["entries"]["assembly"]["listed"]}


def test_tier_1_builds_a_layered_construction_from_the_layer_table() -> None:
    """The only tier that produces real layers. Adelphi cannot test it — it carries zero
    `layer_table_*` — which is why `250703 - Linde Residence` is on POC-2's fixture list."""
    document = s.document(
        faces=[s.wall("w", 8, assembly_ref="01ud")],
        tables={
            "assemblies_ud": s.assemblies_ud(["01ud", "WT-1", 1, 300.0, 0.15, False]),
            # 100 mm of λ=0.04 insulation + 12 mm of λ=0.25 board. Thicknesses are **mm**;
            # designPH's tables are SI/PHPP units and lambda is W/mK.
            "layer_table_01ud": s.layer_table(
                ["01ud", "EPS", 0.04, None, None, None, None, 100.0],
                ["01ud", "Plasterboard", 0.25, None, None, None, None, 12.0],
            ),
        },
    )
    entry = assembly_entries(document)["w"]
    assert entry["tier"] == "1-layered"
    assert "2 layer(s)" in entry["reason"]
    # 1 / (0.100/0.04 + 0.012/0.25) = 0.3925 W/m²K, material-only.
    assert abs(entry["u_value"] - 0.3925) < U_TOLERANCE


def test_tier_1_wins_over_a_tier_2_header_for_the_same_id() -> None:
    """A model that has both is telling you the layers; the header's U-value is the summary."""
    document = s.document(
        faces=[s.wall("w", 8, assembly_ref="01ud")],
        tables={
            "assemblies_ud": s.assemblies_ud(["01ud", "WT-1", 1, 300.0, 0.99, False]),
            "layer_table_01ud": s.layer_table(["01ud", "EPS", 0.04, None, None, None, None, 100.0]),
        },
    )
    assert assembly_entries(document)["w"]["tier"] == "1-layered"


def test_the_twelve_column_layer_table_variant_reads_the_same() -> None:
    """`250703` carries `R1..R_tot` as well. Read by NAME — a positional read mixes the two up."""
    document = s.document(
        faces=[s.wall("w", 8, assembly_ref="02ud")],
        tables={
            "layer_table_02ud": s.layer_table(
                ["02ud", "Mineral wool", 0.035, None, None, None, None, 200.0, 5.7, 0, 0, 5.7],
                with_r_values=True,
            )
        },
    )
    entry = assembly_entries(document)["w"]
    assert entry["tier"] == "1-layered"
    assert abs(entry["u_value"] - 1 / (0.2 / 0.035)) < U_TOLERANCE


def test_tier_2_makes_one_no_mass_material_from_the_u_value() -> None:
    """A U-value with no build-up is legitimate and common. Presenting it as a full assembly is the
    failure; producing a single no-mass layer that reproduces the number is not."""
    document = s.document(
        faces=[s.wall("w", 8, assembly_ref="83ud")],
        tables={"assemblies_ud": s.assemblies_ud(["83ud", "Default wall", 1, 300.0, 0.15, False])},
    )
    entry = assembly_entries(document)["w"]
    assert entry["tier"] == "2-u-value"
    assert abs(entry["u_value"] - 0.15) < U_TOLERANCE
    assert "no build-up in the model" in entry["reason"]


def test_tier_2a_a_calc_header_alone_produces_nothing() -> None:
    """⚠ `assemblies_calc`'s schema has **no U-value column** — its tokens are `id, desc, R_in,
    R_out, …`. A calc header without its layer table cannot make even a no-mass material, and
    inventing one would fabricate a number a reviewer would then check against PHPP."""
    document = s.document(
        faces=[s.wall("w", 8, assembly_ref="04ud")],
        tables={"assemblies_calc": s.assemblies_calc(["04ud", "FT-1", 0.13, 0.04, 0, 0, 0.0, False])},
    )
    entry = assembly_entries(document)["w"]
    assert entry["tier"] == "2a-header-only"
    assert entry["outcome"] == "reported-not-translated"
    assert entry["u_value"] is None


def test_tier_3_names_the_id_so_its_frequency_can_be_measured() -> None:
    """The `83ud`–`99ud` range is designPH's shipped library and lives in the plugin folder, not the
    file. Reporting each id by name is what will measure how often tier 3 actually matters."""
    entry = assembly_entries(s.document(faces=[s.wall("w", 8, assembly_ref="91ud")]))["w"]
    assert entry["tier"] == "3-unresolved-in-model"
    assert "'91ud'" in entry["reason"]


def test_a_face_with_no_reference_is_reported_not_guessed() -> None:
    entry = assembly_entries(s.document(faces=[s.wall("w", 8)]))["w"]
    assert entry["tier"] == "none"
    assert entry["outcome"] == "reported-not-translated"


def test_an_unresolved_assembly_leaves_the_face_on_honeybees_default() -> None:
    """**Never substitute a plausible default silently.** A fabricated U-value is indistinguishable
    from a real one downstream, which is the whole problem."""
    result = translate(parse(s.document(faces=[s.wall("w", 8, assembly_ref="91ud")])))
    face_entry = result.report["entries"]["face"]["listed"][0]
    assert "no construction" in face_entry["reason"]
    assert face_entry["outcome"] == "translated-with-notes"


def test_film_resistances_travel_on_the_report_not_folded_into_the_material() -> None:
    """A reviewer has to be able to see R_in and R_out. A U-value that silently includes films
    cannot be checked against PHPP, and it is out by a consistent, plausible-looking amount."""
    document = s.document(
        faces=[s.wall("w", 8, assembly_ref="05ud")],
        tables={
            "assemblies_calc": s.assemblies_calc(["05ud", "WT-2", 0.13, 0.04, 0, 0, 0.02, True]),
            "layer_table_05ud": s.layer_table(["05ud", "EPS", 0.04, None, None, None, None, 100.0]),
        },
    )
    entry = assembly_entries(document)["w"]
    assert entry["ph_values"]["R_in"] == 0.13
    assert entry["ph_values"]["R_out"] == 0.04
    assert entry["ph_values"]["additional_U_value"] == 0.02
    assert entry["ph_values"]["int_insul"] is True
    # The emitted U-value is material-only, so the films are visible but not baked in.
    assert abs(entry["u_value"] - 0.4) < U_TOLERANCE


def test_a_layer_with_no_thickness_is_dropped_and_said_so() -> None:
    document = s.document(
        faces=[s.wall("w", 8, assembly_ref="06ud")],
        tables={
            "layer_table_06ud": s.layer_table(
                ["06ud", "EPS", 0.04, None, None, None, None, 100.0],
                ["06ud", "Air gap", None, None, None, None, None, None],
            )
        },
    )
    assert "1 layer(s) had no thickness or lambda" in assembly_entries(document)["w"]["reason"]


def test_a_layer_table_with_nothing_usable_is_reported() -> None:
    document = s.document(
        faces=[s.wall("w", 8, assembly_ref="07ud")],
        tables={"layer_table_07ud": s.layer_table(["07ud", "?", None, None, None, None, None, None])},
    )
    entry = assembly_entries(document)["w"]
    assert entry["tier"] == "unresolved"
    assert entry["u_value"] is None


def test_u_value_uses_honeybees_material_only_figure() -> None:
    """⚠ honeybee's two names read the wrong way round: `u_value` is material-only and `u_factor`
    includes standard films. Measured on the vendored wheel. Reaching for `u_factor` because it
    sounds more precise puts every comparison out by the film resistances."""
    from honeybee_energy.construction.opaque import OpaqueConstruction
    from honeybee_energy.material.opaque import EnergyMaterialNoMass

    material = EnergyMaterialNoMass("m", 1 / 0.15)
    construction = OpaqueConstruction("c", [material])
    assert abs(construction.u_value - 0.15) < 1e-9
    assert construction.u_factor < construction.u_value
    resolution = constructions.Resolution("2-u-value", construction, "", {})
    assert abs(constructions.u_value_of(resolution) - 0.15) < 1e-9


# ------------------------------------------------------------------------------------------------
# Multi-section layers — PHPP's three parallel paths, and ISO 6946's mean of limits
# ------------------------------------------------------------------------------------------------


def framed_document(surf2: float) -> dict[str, Any]:
    """One 100 mm layer of λ=0.04 insulation with λ=0.13 timber through it, films 0.13 + 0.04."""
    return s.document(
        faces=[s.wall("w", 8, assembly_ref="06ud")],
        tables={
            "assemblies_calc": s.assemblies_calc(["06ud", "Framed wall", 0.13, 0.04, surf2, 0.0, 0.0, True]),
            "layer_table_06ud": s.layer_table(
                ["06ud", "Mineral Wool", 0.04, "2x4 Studs", 0.13, None, None, 100.0],
            ),
        },
    )


def test_the_section_percentage_is_a_percentage_not_a_fraction() -> None:
    """⚠ Settled against designPH 2.4.0 BETA's own U-/R-value calculator, not inferred.

    Linde's `06ud` stores `21.875` and the dialog shows **Surface percentage 2: 21.88** (with
    section 1 as the remainder, **78.12**). The same column also holds `0.0625` and `0.09375` —
    those are 0.06 % and 0.09 %, essentially unframed. Reading the column as fractions would apply
    a hundredfold framing correction to assemblies that have almost none.
    """
    entry = assembly_entries(framed_document(21.875))["w"]
    assert entry["ph_values"]["section_areas_pct"] == [78.125, 21.875, 0.0]

    negligible = assembly_entries(framed_document(0.0625))["w"]
    assert negligible["ph_values"]["section_areas_pct"] == [99.938, 0.062, 0.0]


def test_iso6946_takes_the_mean_of_the_two_limits() -> None:
    """⚠ **Not an area-weighted lambda.** ISO 6946 §6.7 brackets the answer:

    * upper — whole paths in parallel by area: 1/R = 0.8/(0.17 + 0.100/0.04) + 0.2/(0.17 + 0.100/0.13)
      → R_upper = 1.95090
    * lower — area-weighted λ per layer: λ = 0.8(0.04) + 0.2(0.13) = 0.058
      → R_lower = 0.17 + 0.100/0.058 = 1.89414

    R = 1.92252 → **U = 0.5201 W/m²K**, spread = (R_upper − R_lower) / 2R = **1.48 %**.

    An earlier attempt fitted one framing fraction to make a simple blend match a single PHPP
    number, which is circular. This is the published method, hand-checked here and checked against
    seven real assemblies in `POC-3_results.md` §10.5.
    """
    entry = assembly_entries(framed_document(20.0))["w"]
    assert abs(entry["ph_values"]["u_value_iso6946"] - 0.5201) < 1e-4
    assert abs(entry["ph_values"]["section_spread_pct"] - 1.48) < 0.01


def test_the_framed_u_value_is_higher_than_the_one_honeybee_reports() -> None:
    """The whole reason the number is reported separately. honeybee's construction carries the
    **section-1** value — a layer's conductivity is one number and `lambda1` is the one it gets — so
    it reads low on a framed assembly, in the direction that flatters the building. On Linde's
    `06ud` that is 0.0698 against designPH's 0.0750."""
    entry = assembly_entries(framed_document(21.875))["w"]
    assert entry["ph_values"]["u_value_iso6946"] > entry["u_value"]
    assert "flatter" not in entry["reason"] and "multi-section" in entry["reason"]


def test_the_division_grid_carries_the_real_areas_not_equal_columns() -> None:
    """⚠ These used to be set to equal column widths, which describes a stud bay as half timber."""
    resolution = constructions.resolve(parse(framed_document(21.875)), "06ud")
    material = resolution.construction.materials[0]
    widths = material.properties.ph.divisions.column_widths
    assert [round(w, 5) for w in widths] == [0.78125, 0.21875]


def test_a_second_lambda_with_no_area_is_ignored() -> None:
    """A `lambda2` with a zero percentage is not a framed layer, and 21 of Linde's multi-section
    layers are exactly that. Treating them as framed would overstate the blast radius fivefold."""
    entry = assembly_entries(framed_document(0.0))["w"]
    assert "section_areas_pct" not in entry["ph_values"]
    # reported rounded to 4 dp
    assert abs(entry["ph_values"]["u_value_iso6946"] - 1 / (0.17 + 0.100 / 0.04)) < 1e-4


def test_the_reported_u_value_includes_films_and_honeybees_does_not() -> None:
    """Finding 53's other half. designPH's assembly U includes `R_in`/`R_out`; honeybee's `u_value`
    is material-only. On Linde's three unframed assemblies that difference alone is 0.004–0.005
    W/m²K — enough on its own to fail a ±0.005 regression that compared the wrong pair."""
    entry = assembly_entries(framed_document(0.0))["w"]
    assert entry["ph_values"]["u_value_iso6946"] < entry["u_value"]
