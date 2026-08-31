"""Assemblies → honeybee constructions, in four tiers, honestly.

⚠ **An assembly reference does not always resolve inside the model.** Only 254 of 532 corpus
references carry a build-up; the rest resolve against designPH's *installed* CSV library, which
lives in the plugin folder and not in the `.skp`. A translator that promises layers per surface
will be wrong more often than it is right (`PHASE-1_assembly-resolution.md`).

So the tier a face resolved through is **recorded per face**, and a U-value with no build-up is
reported as exactly that. Presenting it as a full assembly is the failure mode; not producing one is
not.

| Tier | Source | Emitted |
|---|---|---|
| 1 | `layer_table_<id>` | Layered `OpaqueConstruction` |
| 2 | `assemblies_ud` header (has `U_value`) | One `EnergyMaterialNoMass` from the U-value |
| 2a | `assemblies_calc` header **only** | ⚠ Nothing. That schema has no U-value column at all |
| 3 | designPH's installed CSV library | Out of POC scope. Reported as `unresolved-in-model` |
| — | nothing | Reported. The face keeps honeybee's default; **never substitute a plausible one** |
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contract import Extraction, Table, as_float

#: Surface film resistances are **not** folded into the emitted materials. A reviewer has to be able
#: to see the numbers designPH stored, and a U-value that silently includes films cannot be checked
#: against PHPP. They travel on the report instead.
FILM_TOKENS = ("R_in", "R_out")

#: designPH mirrors PHPP's three parallel construction paths per layer.
LAYER_PATHS = (("desc1", "lambda1"), ("desc2", "lambda2"), ("desc3", "lambda3"))

#: The area of each path, as a **percentage**, stored on the *assembly* header rather than the
#: layer. ⚠ Section 1 is the remainder: designPH's own dialog shows `78.12 / 21.88 / 0.00`, and only
#: sections 2 and 3 are stored (`DESIGNPH_DATA_MODEL.md` §7.2).
SECTION_TOKENS = ("surf2_percentage", "surf3_percentage")

#: `EnergyMaterialNoMass` takes an R-value, and honeybee rejects anything at or below zero.
MIN_R_VALUE = 0.001


@dataclass(frozen=True)
class Resolution:
    """What one `assembly_ref` resolved to, and how far it got."""

    tier: str
    construction: Any | None
    detail: str
    #: Numbers a reviewer needs but that are deliberately kept out of the materials.
    ph_values: dict[str, Any]


def _layer_table(extraction: Extraction, reference: Any) -> Table | None:
    return extraction.tables.get(f"layer_table_{str(reference).strip()}")


def _header(extraction: Extraction, reference: Any) -> tuple[str, Any] | None:
    """The assembly's header row, and which table it came from.

    `assemblies_ud` is checked first because it is the one that carries a `U_value`.
    """
    for name in ("assemblies_ud", "assemblies_calc"):
        table = extraction.tables.get(name)
        if table is None:
            continue
        record = table.find("id", reference)
        if record is not None:
            return name, record
    return None


def _sections(header: tuple[str, Any] | None) -> tuple[float, ...]:
    """Path areas as fractions `(f1, f2, f3)`, from the assembly header.

    ⚠ **The stored values are percentages**, confirmed against designPH 2.4.0 BETA's own U-/R-value
    calculator: Linde's `06ud` stores `21.875` and the dialog shows `Surface percentage 2: 21.88`.
    That matters because the same column also holds values like `0.0625` and `0.09375` — those are
    0.06 % and 0.09 %, i.e. *negligible* framing, not 6 % and 9 %. Reading them as fractions would
    apply a hundredfold framing correction to assemblies that have essentially none.

    Section 1 is the **remainder** and is never stored: the dialog's `78.12` is `100 − 21.88`.
    """
    if header is None:
        return (1.0, 0.0, 0.0)
    _, record = header
    rest = [max((as_float(record.get(token)) or 0.0) / 100.0, 0.0) for token in SECTION_TOKENS]
    first = 1.0 - sum(rest)
    if first <= 0:
        # Nonsense areas: fall back to a single path rather than emit negative weights.
        return (1.0, 0.0, 0.0)
    return (first, *rest)


def _iso6946_u_value(
    rows: list[Any], sections: tuple[float, ...], films: float
) -> tuple[float, float] | None:
    """designPH's own multi-section U-value, and the spread it reports as *Error %*.

    ⚠ **This is not an area-weighted lambda.** ISO 6946 §6.7 brackets the answer between two limits
    and takes their mean:

    * **upper** — each section is a complete path, its resistances summed, the paths combined in
      parallel by area. Heat cannot cross between sections.
    * **lower** — each *layer* gets an area-weighted conductivity, and the layers are summed. Heat
      crosses freely.

    `R = (R_upper + R_lower) / 2`, and `(R_upper − R_lower) / 2R` is the *Error %* designPH prints.

    Verified against designPH 2.4.0 BETA on all seven of Linde's referenced assemblies — every U to
    ±0.0005 W/m²K, and `06ud`'s error to **2.75 %**, the figure in the dialog. An earlier attempt
    here fitted a single framing fraction to make a simple lambda blend match one PHPP number; that
    was circular, and it is the reason this function is checked against seven assemblies and a
    published method rather than one.
    """
    measured = [(as_float(r.get("thickness")), r) for r in rows]
    usable = [(t / 1000.0, r) for t, r in measured if t is not None and t > 0]
    if not usable:
        return None

    def conductivity(record: Any, path: int) -> float | None:
        value = as_float(record.get(f"lambda{path}"))
        return value if value and value > 0 else as_float(record.get("lambda1"))

    upper = 0.0
    for path, fraction in enumerate(sections, start=1):
        if fraction <= 0:
            continue
        resistance = films
        for thickness, record in usable:
            lam = conductivity(record, path)
            if not lam or lam <= 0:
                return None
            resistance += thickness / lam
        upper += fraction / resistance
    if upper <= 0:
        return None
    r_upper = 1.0 / upper

    r_lower = films
    for thickness, record in usable:
        blended = 0.0
        for path, fraction in enumerate(sections, start=1):
            lam = conductivity(record, path)
            if not lam or lam <= 0:
                return None
            blended += fraction * lam
        if blended <= 0:
            return None
        r_lower += thickness / blended

    total = (r_upper + r_lower) / 2.0
    return 1.0 / total, (r_upper - r_lower) / (2.0 * total) * 100.0


def _layer_material(record: Any, index: int, reference: str, sections: tuple[float, ...]) -> Any | None:
    """One `layer_table_*` row → one `EnergyMaterial`, with the parallel paths as a division grid.

    designPH stores up to three `desc`/`lambda` pairs per layer — PHPP's three-path construction,
    mirrored exactly. Path 1 is the base material; paths 2 and 3 become extra columns on
    `EnergyMaterialPhProperties.divisions`, which is honeybee-ph's own representation of a
    mixed-material layer (a stud bay, typically).
    """
    from honeybee_energy.material.opaque import EnergyMaterial

    thickness = as_float(record.get("thickness"))
    conductivity = as_float(record.get("lambda1"))
    if not thickness or thickness <= 0 or not conductivity or conductivity <= 0:
        return None

    # designPH stores layer thickness in **mm** (its tables are SI/PHPP units); honeybee wants m.
    thickness_m = thickness / 1000.0
    name = str(record.get("desc1") or f"{reference}_layer_{index}")
    material = EnergyMaterial(
        f"{reference}_L{index}_{name}"[:100],
        thickness_m,
        conductivity,
        # designPH stores no density or specific heat. These are honeybee-required and are
        # **placeholders that affect no steady-state U-value** — PHPP is quasi-steady-state and
        # never uses them. Recorded here so nobody later reads them as data.
        density=1.0,
        specific_heat=1000.0,
    )
    material.display_name = name

    _apply_divisions(material, record, sections, name, reference, index)
    return material


def _apply_divisions(
    material: Any, record: Any, sections: tuple[float, ...], name: str, reference: str, index: int
) -> None:
    """Put the parallel paths on honeybee-ph's division grid, **at their real areas**.

    ⚠ These used to be set to equal column widths, which describes a stud bay as half timber. The
    areas are designPH's own (`surf2_percentage` / `surf3_percentage` on the assembly header), and
    a framed layer is typically 6–22 % of the surface, not 50 %.

    ⚠ And note what the grid does *not* fix: `Divisions.get_equivalent_conductivity` is an
    area-weighted average of conductivity, which is ISO 6946's **lower** resistance limit. designPH
    and PHPP report the **mean of the upper and lower limits** (`_iso6946_u_value`), so a consumer
    that reads the grid still gets the optimistic bound. That is why the assembly's real U-value
    travels on the report rather than being inferred downstream.
    """
    from honeybee_energy.material.opaque import EnergyMaterial

    extra = [
        (str(record.get(desc) or f"{name}_section_{i + 2}"), as_float(record.get(lam)))
        for i, (desc, lam) in enumerate(LAYER_PATHS[1:])
        if as_float(record.get(lam)) and sections[i + 1] > 0
    ]
    if not extra:
        return
    widths = [sections[0]] + [sections[i + 1] for i in range(len(extra))]
    divisions = material.properties.ph.divisions
    divisions.set_column_widths(widths)
    divisions.set_row_heights([1.0])
    for column, (label, conductivity) in enumerate(extra, start=1):
        section = EnergyMaterial(
            f"{reference}_L{index}_s{column + 1}_{label}"[:100],
            material.thickness,
            conductivity,
            density=1.0,
            specific_heat=1000.0,
        )
        section.display_name = label
        divisions.set_cell_material(column, 0, section)


def _tier_one(
    extraction: Extraction,
    reference: Any,
    report_values: dict[str, Any],
    header: tuple[str, Any] | None = None,
) -> Resolution | None:
    from honeybee_energy.construction.opaque import OpaqueConstruction

    table = _layer_table(extraction, reference)
    if table is None:
        return None
    reference_text = str(reference).strip()
    sections = _sections(header)
    materials = []
    skipped = []
    for index, record in enumerate(table.records()):
        material = _layer_material(record, index, reference_text, sections)
        if material is None:
            skipped.append(str(record.get("desc1") or index))
        else:
            materials.append(material)
    if not materials:
        return Resolution("unresolved", None, f"layer_table_{reference_text} has no usable layer", {})

    construction = OpaqueConstruction(f"{reference_text}_construction"[:100], materials)
    construction.display_name = str(reference_text)
    detail = f"{len(materials)} layer(s) from layer_table_{reference_text}"
    if skipped:
        detail += f"; {len(skipped)} layer(s) had no thickness or lambda and were dropped"

    # designPH's own U-value for the assembly, reported alongside honeybee's. The two differ for
    # **two independent reasons**, and both are worth a reviewer seeing:
    #
    #   * **films.** honeybee's `u_value` is material-only (Finding 53); designPH's includes
    #     `R_in`/`R_out`. On Linde's single-section assemblies that alone is 0.004-0.005 W/m²K.
    #   * **framing.** For a multi-section assembly honeybee reports the **section-1** value,
    #     because a layer's conductivity is one number and `lambda1` is the one it got. On `06ud`
    #     that is 0.0688 against designPH's 0.0750 — 8 % low, flattering the building.
    #
    # Neither can be pushed into the material without inventing a conductivity, so the real figure
    # travels on the report, named.
    films = sum(as_float(report_values.get(token)) or 0.0 for token in FILM_TOKENS)
    computed = _iso6946_u_value(list(table.records()), sections, films)
    if computed is not None:
        u_value, spread = computed
        report_values = {**report_values, "u_value_iso6946": round(u_value, 4)}
        if sections[1:] != (0.0, 0.0):
            report_values["section_areas_pct"] = [round(f * 100, 3) for f in sections]
            report_values["section_spread_pct"] = round(spread, 2)
            detail += (
                f"; multi-section: designPH's U is {u_value:.4f} W/m²K (ISO 6946 mean of limits, "
                f"±{spread:.2f}%) — honeybee reports the section-1 value from this build-up"
            )
    return Resolution("1-layered", construction, detail, report_values)


def _tier_two(header: tuple[str, Any], reference: Any, report_values: dict[str, Any]) -> Resolution:
    """A U-value with no build-up. Legitimate, common, and **not** a layered assembly."""
    from honeybee_energy.construction.opaque import OpaqueConstruction
    from honeybee_energy.material.opaque import EnergyMaterialNoMass

    table_name, record = header
    reference_text = str(reference).strip()
    u_value = as_float(record.get("U_value"))
    if not u_value or u_value <= 0:
        # ⚠ `assemblies_calc`'s schema has **no U-value column** — its tokens are
        # `id, desc, R_in, R_out, …`. A calc header on its own cannot make even a no-mass material,
        # and pretending otherwise would invent a number.
        return Resolution(
            "2a-header-only",
            None,
            f"`{table_name}` header for {reference_text!r} carries no U-value",
            report_values,
        )

    material = EnergyMaterialNoMass(f"{reference_text}_nomass"[:100], max(1.0 / u_value, MIN_R_VALUE))
    material.display_name = str(record.get("desc") or reference_text)
    construction = OpaqueConstruction(f"{reference_text}_construction"[:100], [material])
    construction.display_name = str(record.get("desc") or reference_text)
    return Resolution(
        "2-u-value",
        construction,
        f"U={u_value} W/m²K from `{table_name}`, no build-up in the model",
        report_values,
    )


def resolve(extraction: Extraction, reference: Any) -> Resolution:
    """Resolve one face's `assembly_ref` as far as the model allows."""
    if reference is None or not str(reference).strip():
        return Resolution("none", None, "the face carries no assembly reference", {})

    header = _header(extraction, reference)
    values: dict[str, Any] = {}
    if header is not None:
        _, record = header
        for token in FILM_TOKENS:
            film = as_float(record.get(token))
            if film is not None:
                values[token] = film
        for token in ("additional_U_value", "int_insul", "thk"):
            if token in record:
                values[token] = record[token]

    layered = _tier_one(extraction, reference, values, header)
    if layered is not None:
        return layered
    if header is not None:
        return _tier_two(header, reference, values)
    # designPH's shipped default library (`83ud`–`99ud`) lives in the plugin folder, not the file.
    # Reporting these by id is what will measure how often tier 3 actually matters.
    return Resolution(
        "3-unresolved-in-model",
        None,
        f"{str(reference).strip()!r} resolves only against designPH's installed CSV library",
        values,
    )


def u_value_of(resolution: Resolution) -> float | None:
    """The emitted construction's U-value **excluding** surface films — the comparable figure.

    ⚠ **honeybee's two names are the opposite way round from the obvious reading, and it is silent
    about it.** Measured on the vendored wheel:

    | | material-only | with standard films |
    |---|---|---|
    | `OpaqueConstruction.u_value` | ✅ | |
    | `OpaqueConstruction.u_factor` | | ✅ |

    A no-mass material built from `R = 1/0.15` reports `u_value == 0.15` and `u_factor == 0.1464`.
    designPH's `U_value` column is the material-only figure, so `u_value` is what the §5 regressions
    compare against — and reaching for `u_factor` because it sounds more precise would put every
    comparison out by the film resistances, consistently, in the direction that looks plausible.
    """
    if resolution.construction is None:
        return None
    return float(resolution.construction.u_value)
