"""Climate identification onto the model's PH properties.

Deliberately shallow: designPH stores a **dataset id** (`klima_ID`, e.g. `"US0058a"`) and a display
name (`Klima_Standort`), and that is all it stores. Resolving either against an actual climate
dataset is out of POC scope — a wrong climate is a wrong energy model, and guessing one from an id
we have no library for would be exactly the kind of plausible fabrication the report exists to
prevent.

So: carry the identifiers, and report their absence.
"""

from __future__ import annotations

from typing import Any

from .contract import ModelInfo


def _default_site(model: Any) -> dict[str, Any]:
    """What honeybee-ph put there on its own, recorded so the report can disown it."""
    if not model.rooms:
        return {}
    try:
        location = model.rooms[0].properties.ph.ph_bldg_segment.site.location
        return {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "display_name": location.display_name,
        }
    except Exception:  # noqa: BLE001 -- a diagnostic must never fail a translation
        return {}


def apply(model: Any, info: ModelInfo) -> tuple[dict[str, Any], list[str]]:
    """Stamp the climate identifiers onto the honeybee `Model`. Returns `(recorded, notes)`."""
    recorded: dict[str, Any] = {
        "klima_id": info.klima_id,
        "klima_standort": info.klima_standort,
        "resolved": False,
        "hb_default_site": _default_site(model),
    }
    notes: list[str] = [
        # ⚠ Measured, not assumed: honeybee-ph populates a **default site** on every building
        # segment — New York, 40.6/-73.8, climate zone 1 — and it serialises into the HBJSON looking
        # exactly like project data. Nothing we do removes it, and a consumer reading the file has
        # no way to tell it is a placeholder. Saying so in the report is the only mitigation the POC
        # has; making it configurable is a v1 job.
        "⚠ the HBJSON carries honeybee-ph's DEFAULT site (New York), not designPH's climate — "
        "designPH stores only a dataset id, which is recorded here instead",
    ]
    if info.klima_id is None and info.klima_standort is None:
        notes.append("the model carries no climate identification (`klima_ID`/`Klima_Standort`)")
        return recorded, notes

    notes.append(
        f"climate {info.klima_id or '?'} ({info.klima_standort or 'unnamed'}) is carried as an "
        "identifier only — no dataset was resolved"
    )
    segment = model.rooms[0].properties.ph.ph_bldg_segment if model.rooms else None
    if segment is not None and info.klima_standort:
        # The building segment is where honeybee-ph keeps per-segment PH settings; the location
        # name is the only field designPH gives us that maps onto anything there.
        try:
            segment.display_name = f"{segment.display_name} — {info.klima_standort}"
        except Exception:  # noqa: BLE001 -- a naming nicety must never fail a translation
            notes.append("could not name the building segment after the climate location")
    return recorded, notes
