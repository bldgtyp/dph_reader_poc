#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike L-B: map real PH-Navigator library data onto designPH's model-level tables.

    uv run planning/spikes/library-import/map_phn.py

This is the *executable form of the contract* (`planning/03_library-import/
CONTRACT_phn-library.md` — FROZEN v1, 2026-08-31): every mapping rule the contract states is
implemented here, and nowhere else. Reads `_private/phn/linde_phn_library.json` (real Linde Home data, pulled
read-only from the production PHN MCP), emits:

  * `_private/payload/lb_payload.json`   — the write payload `write_library_b.rb` consumes
  * `_private/payload/lb_expectations.md` — the per-assembly intended U-value / Error % table
                                            Ed grades designPH's own calculator against

The mapping (contract §-refs in comments):

  * PHN assembly  -> `assemblies_calc` row + `layer_table_<id>` (the USER-CALCULATED library —
    L-A §14.5: never `assemblies_ud`); films R_in/R_out from (type, exterior_condition);
    per-layer segments packed into PHPP's three parallel paths with ASSEMBLY-level section
    percentages (§7.2 — percentages, never fractions).
  * PHN frame set (distinct top/right/bottom/left component tuple) -> one `frames_ud` row
    (per-edge U, width, psi_G; psi_F from the component's perimeter install psi; chi_GT 0 —
    PHN has no chi).
  * PHN glazing -> `glazing_ud` row (g, U).

Intended U-values are computed with the ISO 6946 §6.7 mean-of-limits INCLUDING films — a port
of `pocs/01_sketchup-export/py/dph_translator/constructions.py::_iso6946_u_value`, the
implementation verified against designPH 2.4.0 BETA's own calculator on all seven of Linde's
referenced assemblies (U to ±0.0005, Error % exact).

⚠ The 3-path packing ASSUMES framing in different layers is aligned (nested columns). Where a
real assembly's framing is staggered, ISO 6946's upper limit differs. House rule: a lossy step
reports what it absorbed — the expectations table carries the U under the fully-independent
(staggered) reading beside the packed one, and the delta.
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SRC = HERE / "_private" / "phn" / "linde_phn_library.json"
OUT_DIR = HERE / "_private" / "payload"

MARKER = "ZZ "  # spike-only prefix: findable in designPH's UI, sorts last, greppable in a .ppp
WIDTH_TOL = 0.01  # mm — transcription self-check tolerance
MAX_LAYERS = 8  # measured: every corpus layer_table is 8-row pre-allocated

# Films, ISO 6946 Table 1 (R in m2K/W). Key: (assembly type, exterior_condition).
# A well-ventilated exterior layer takes R_se = the R_si value for that heat-flow direction.
FILMS: dict[tuple[str, str], tuple[float, float]] = {
    ("wall", "outdoor_air"): (0.13, 0.04),
    ("wall", "ventilated"): (0.13, 0.13),
    ("roof", "outdoor_air"): (0.10, 0.04),
    ("roof", "ventilated"): (0.10, 0.10),
    ("floor", "outdoor_air"): (0.17, 0.04),
    ("floor", "ventilated"): (0.17, 0.17),
}


def sanitize(name: str) -> str:
    """designPH's regenerated DC option lists delimit on `&` and `=` — those characters in a
    desc would corrupt every window's dropdown list. Contract rule: replace, never pass."""
    return name.replace("&", "+").replace("=", "-")


class Refuse(Exception):
    """Hard rule 4: an assembly the mapping cannot represent is REFUSED BY NAME, never skipped
    silently and never approximated without saying so."""


# ---------------------------------------------------------------------------- source checks
def validate(src: dict[str, Any]) -> None:
    for asm in src["assemblies"]:
        widths = {round(sum(w for w, _ in layer["segments"]), 6) for layer in asm["layers"]}
        if len(widths) != 1:
            raise SystemExit(f"{asm['name']}: layers disagree on total width: {widths}")
        total = sum(layer["thickness_mm"] for layer in asm["layers"])
        if abs(total - asm["total_thickness_mm"]) > WIDTH_TOL:
            raise SystemExit(
                f"{asm['name']}: layer thicknesses sum to {total}, "
                f"PHN says {asm['total_thickness_mm']} — transcription error"
            )


# ------------------------------------------------------------------- layer/section analysis
def layer_groups(layer: dict[str, Any], materials: dict[str, Any]) -> list[tuple[str, float]]:
    """Segments grouped by material -> [(material_id, fraction)], primary (largest) first."""
    total = sum(w for w, _ in layer["segments"])
    by_mat: dict[str, float] = {}
    for width, mat in layer["segments"]:
        by_mat[mat] = by_mat.get(mat, 0.0) + width
    groups = sorted(by_mat.items(), key=lambda kv: -kv[1])
    return [(mat, w / total) for mat, w in groups]


def pack_sections(
    asm: dict[str, Any], materials: dict[str, Any]
) -> tuple[float, float, list[dict[str, Any]]]:
    """Pack per-layer segment fractions into PHPP's assembly-level 3-path model.

    Returns (surf2_pct, surf3_pct, layers) where each layer dict carries desc/lambda for the
    paths it differs on (blank = fall back to lambda1, designPH's own idiom — verified both in
    real Linde tables and in the POC's regression implementation).

    Packing (contract): let F = the distinct secondary-material area fractions across layers.
      |F| = 0 -> single path.
      |F| = 1 -> section 2 = F0.  Framed layers put their secondary material in path 2.
      |F| = 2 -> section 2 = F_small, section 3 = F_big − F_small.  A layer framed at F_small
                 puts its secondary in path 2 only; one framed at F_big in paths 2 AND 3
                 (2+3 = F_big exactly).  Assumes nesting/alignment — the absorbed delta is
                 reported, not hidden.
      |F| ≥ 3, or a layer with 3+ materials -> Refuse (representable only approximately;
                 out of the spike's scope, contract records it as a stated limit).
    """
    analysed = []
    fractions: set[float] = set()
    for layer in asm["layers"]:
        groups = layer_groups(layer, materials)
        if len(groups) > 2:
            raise Refuse(f"{asm['name']}: a layer has {len(groups)} materials (max 2 mapped)")
        if len(groups) == 2:
            fractions.add(round(groups[1][1], 9))
        analysed.append(groups)

    fr = sorted(fractions)
    if len(fr) > 2:
        raise Refuse(f"{asm['name']}: {len(fr)} distinct framing fractions {fr} (max 2 packable)")
    surf2 = fr[0] if fr else 0.0
    surf3 = (fr[1] - fr[0]) if len(fr) == 2 else 0.0

    layers_out = []
    for layer, groups in zip(asm["layers"], analysed):
        primary_mat = groups[0][0]
        row = {
            "desc1": sanitize(materials[primary_mat]["name"]),
            "lambda1": materials[primary_mat]["k_w_mk"],
            "desc2": "",
            "lambda2": 0.0,
            "desc3": "",
            "lambda3": 0.0,
            "thickness_mm": round(layer["thickness_mm"], 4),
        }
        if len(groups) == 2:
            sec_mat, sec_frac = groups[1]
            name = sanitize(materials[sec_mat]["name"])
            lam = materials[sec_mat]["k_w_mk"]
            row["desc2"], row["lambda2"] = name, lam
            if len(fr) == 2 and abs(sec_frac - fr[1]) < 1e-9:
                row["desc3"], row["lambda3"] = name, lam  # occupies sections 2 AND 3
            elif abs(sec_frac - fr[0]) >= 1e-9 and len(fr) == 2:
                raise Refuse(f"{asm['name']}: fraction {sec_frac} not packable into {fr}")
        layers_out.append(row)
    return surf2 * 100.0, surf3 * 100.0, layers_out


# ----------------------------------------------------------------- ISO 6946 mean of limits
def iso6946(
    layers: list[dict[str, Any]], surf2_pct: float, surf3_pct: float, films: float
) -> tuple[float, float]:
    """Port of the POC's `_iso6946_u_value` (verified against designPH's calculator, 7/7).
    Returns (U, error_pct) for the packed 3-column model — what designPH itself will compute
    from the rows we write."""
    sections = (1.0 - (surf2_pct + surf3_pct) / 100.0, surf2_pct / 100.0, surf3_pct / 100.0)

    def lam(row: dict[str, Any], path: int) -> float:
        value = row[f"lambda{path}"]
        return value if value and value > 0 else row["lambda1"]

    upper = 0.0
    for path, fraction in enumerate(sections, start=1):
        if fraction <= 0:
            continue
        resistance = films
        for row in layers:
            resistance += (row["thickness_mm"] / 1000.0) / lam(row, path)
        upper += fraction / resistance
    r_upper = 1.0 / upper

    r_lower = films
    for row in layers:
        blended = sum(fraction * lam(row, path) for path, fraction in enumerate(sections, 1))
        r_lower += (row["thickness_mm"] / 1000.0) / blended

    total = (r_upper + r_lower) / 2.0
    return 1.0 / total, (r_upper - r_lower) / (2.0 * total) * 100.0


def iso6946_independent(
    asm: dict[str, Any], materials: dict[str, Any], films: float
) -> float:
    """The same mean-of-limits with the OPPOSITE alignment assumption: framing in different
    layers fully staggered (product measure over per-layer paths). The lower limit is
    alignment-independent; only the upper limit moves. Reported so the packing's absorbed
    delta is a number, not a hope."""
    per_layer: list[list[tuple[float, float]]] = []  # [(fraction, R_of_that_path)]
    for layer in asm["layers"]:
        groups = layer_groups(layer, materials)
        thickness = layer["thickness_mm"] / 1000.0
        per_layer.append(
            [(frac, thickness / materials[mat]["k_w_mk"]) for mat, frac in groups]
        )

    upper = 0.0
    for combo in itertools.product(*per_layer):
        weight = 1.0
        resistance = films
        for frac, r in combo:
            weight *= frac
            resistance += r
        upper += weight / resistance
    r_upper = 1.0 / upper

    r_lower = films
    for layer in per_layer:
        # area-weighted conductivity: R = thickness / Σ(frac·λ) = 1 / Σ(frac / R_path)
        r_lower += 1.0 / sum(frac / r for frac, r in layer)
    return 2.0 / (r_upper + r_lower) if (r_upper + r_lower) else 0.0


# ------------------------------------------------------------------------------- main map
def main() -> int:
    src = json.loads(SRC.read_text())
    validate(src)
    materials = src["materials"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    assemblies_out, refusals, expect_rows = [], [], []
    for asm in src["assemblies"]:
        films_pair = FILMS.get((asm["type"], asm["exterior_condition"]))
        if films_pair is None:
            refusals.append(f"{asm['name']}: no films rule for "
                            f"({asm['type']}, {asm['exterior_condition']})")
            continue
        r_in, r_out = films_pair
        try:
            surf2, surf3, layers = pack_sections(asm, materials)
        except Refuse as refusal:
            refusals.append(str(refusal))
            continue
        if len(layers) > MAX_LAYERS:
            refusals.append(f"{asm['name']}: {len(layers)} layers > the measured 8-row table")
            continue
        # Contract: emit layers OUTSIDE-first (PHN's orientation says which end that is).
        if asm["orientation"] == "last_layer_outside":
            layers = list(reversed(layers))

        u_packed, err_pct = iso6946(layers, surf2, surf3, r_in + r_out)
        u_indep = iso6946_independent(asm, materials, r_in + r_out)
        assemblies_out.append({
            "desc": MARKER + sanitize(asm["name"]),
            "phn_id": asm["id"],
            "R_in": r_in,
            "R_out": r_out,
            "surf2_percentage": round(surf2, 6),
            "surf3_percentage": round(surf3, 6),
            "additional_U_value": 0.0,
            "int_insul": False,
            "layers": layers,
            "intended_u": round(u_packed, 6),
            "intended_error_pct": round(err_pct, 4),
        })
        expect_rows.append(
            f"| {MARKER + asm['name']} | {len(layers)} | {surf2:g} / {surf3:g} "
            f"| {r_in:g} / {r_out:g} | **{u_packed:.4f}** | {err_pct:.2f} % "
            f"| {u_indep:.4f} | {abs(u_packed - u_indep):.4f} |"
        )

    frames_out = []
    for fs in src["frame_sets"]:
        edges = {side: src["frames"][pid] for side, pid in fs["edges"].items()}
        frames_out.append({
            "desc": MARKER + sanitize(fs["name"]),
            **{f"U_F{side[0].upper()}": edges[side]["u_w_m2k"]
               for side in ("left", "right", "bottom", "top")},
            **{f"width_{side[0].upper()}": edges[side]["width_m"]
               for side in ("left", "right", "bottom", "top")},
            **{f"psi_G{side[0].upper()}": edges[side]["psi_g_w_mk"]
               for side in ("left", "right", "bottom", "top")},
            **{f"psi_F{side[0].upper()}": edges[side]["psi_install_w_mk"]
               for side in ("left", "right", "bottom", "top")},
            "chi_GT": 0.0,
        })

    glazings_out = [
        {"desc": MARKER + sanitize(g["name"]), "g_value": g["g_value"], "U_value": g["u_w_m2k"]}
        for g in src["glazings"].values()
    ]

    payload = {
        "generated_by": "map_phn.py (Spike L-B)",
        "source": {"project": src["provenance"]["project"],
                   "version_etag": src["provenance"]["version_etag"]},
        "marker": MARKER.strip(),
        "assemblies": assemblies_out,
        "frames": frames_out,
        "glazings": glazings_out,
        "refusals": refusals,
    }
    payload_path = OUT_DIR / "lb_payload.json"
    payload_path.write_text(json.dumps(payload, indent=2))

    lines = [
        "# Spike L-B — intended values (what designPH's own calculator MUST show)",
        "",
        f"Source: PHN **{src['provenance']['project']}** version `Round 2 Update` "
        f"(etag `{src['provenance']['version_etag'][:16]}…`), mapped by `map_phn.py`.",
        "",
        "U includes films (designPH's convention). *U-staggered* is the same ISO 6946 mean of",
        "limits under the opposite framing-alignment assumption; **Δ** is what the 3-column",
        "packing absorbed — the mapping's stated loss, per house rule.",
        "",
        "| assembly | layers | surf2/surf3 % | R_in/R_out | intended U | Error % | U-staggered | Δ |",
        "|---|--:|---|---|---|---|---|---|",
        *expect_rows,
        "",
        f"Frames mapped: **{len(frames_out)}** · glazings: **{len(glazings_out)}** · "
        f"assemblies: **{len(assemblies_out)}** · refused: **{len(refusals)}**",
    ]
    if refusals:
        lines += ["", "## Refused (hard rule 4 — named, not skipped)", ""]
        lines += [f"- {r}" for r in refusals]
    (OUT_DIR / "lb_expectations.md").write_text("\n".join(lines) + "\n")

    print(f"payload      -> {payload_path}")
    print(f"expectations -> {OUT_DIR / 'lb_expectations.md'}")
    print(f"{len(assemblies_out)} assemblies ({len(refusals)} refused), "
          f"{len(frames_out)} frames, {len(glazings_out)} glazings")
    for row in expect_rows:
        print("  " + row)
    for r in refusals:
        print("  REFUSED: " + r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
