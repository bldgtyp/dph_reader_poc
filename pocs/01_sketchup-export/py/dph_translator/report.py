"""The translation report — a first-class output, written beside the HBJSON.

Two house rules meet here and neither is optional:

* **Report, don't guess** (hard rule 4). Every face, edge and window is accounted for: it is either
  an object in the HBJSON or a row in `entries`, and the two sets are disjoint. That is the
  *completeness invariant*, and it is asserted as a unit test rather than hoped for. Silent data
  loss is the failure mode that would most damage a free tool's reputation.
* **End with a verdict.** A run nobody can grade at a glance has not reported anything. The verdict
  shape is fixed — `{"passed": bool, "checks": [{"label", "ok", "detail"}]}` — because the dialog
  banner, the closing message box and the Chromium harness all render it.

Entries are keyed by the contract's **path-qualified `id`** (§2.1), never by `entity_id`: the
session-scoped id is a debugging aid, and POC-5's re-run diffs depend on the stable one.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

#: How many entries of one kind travel. The true count is always alongside, so a truncated list
#: reads as a truncation and not as a short list.
MAX_ENTRIES_PER_KIND = 200

#: The three outcomes an entity can have. Anything not `translated` carries a human-readable reason.
TRANSLATED = "translated"
WITH_NOTES = "translated-with-notes"
OMITTED = "reported-not-translated"

#: PRD §7.2. The marker is explicit so a consumer cannot mistake an incomplete model for a complete
#: one — and the wording has to survive next to the aperture reveal data, which *is* present.
SHADING_MARKER = "not-computed"
SHADING_NOTE = (
    "No shading factors and no context geometry. Aperture reveal dimensions ARE present "
    "(ShadingDimensions, reveal fields only) — they are PHPP inputs, not a shading calculation."
)


@dataclass(frozen=True)
class Entry:
    """One entity's outcome. `kind` is the entity class, not the failure class."""

    id: str
    kind: str
    outcome: str
    reason: str | None = None
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        record: dict[str, Any] = {"id": self.id, "kind": self.kind, "outcome": self.outcome}
        if self.reason:
            record["reason"] = self.reason
        record.update(self.detail)
        return record


@dataclass
class Report:
    """Accumulates entries, summary counts, and the things that are not entity-shaped."""

    entries: list[Entry] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    unclassified: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def add(
        self,
        entity_id: str,
        kind: str,
        outcome: str,
        reason: str | None = None,
        **detail: Any,
    ) -> None:
        self.entries.append(Entry(id=entity_id, kind=kind, outcome=outcome, reason=reason, detail=detail))

    def note(self, text: str) -> None:
        self.notes.append(text)

    def count(self, kind: str | None = None, outcome: str | None = None) -> int:
        return sum(
            1
            for entry in self.entries
            if (kind is None or entry.kind == kind) and (outcome is None or entry.outcome == outcome)
        )

    def omitted_ids(self) -> set[str]:
        return {entry.id for entry in self.entries if entry.outcome == OMITTED}

    def translated_ids(self) -> set[str]:
        return {entry.id for entry in self.entries if entry.outcome != OMITTED}

    @property
    def has_omissions(self) -> bool:
        return self.count(outcome=OMITTED) > 0

    def to_dict(self) -> dict[str, Any]:
        by_kind: dict[str, list[Entry]] = {}
        for entry in self.entries:
            by_kind.setdefault(entry.kind, []).append(entry)
        return {
            "summary": dict(self.summary),
            "shading": SHADING_MARKER,
            "shading_note": SHADING_NOTE,
            "notes": list(self.notes),
            "unclassified": dict(self.unclassified),
            "entries": {
                kind: {
                    "count": len(items),
                    "outcomes": _tally(items),
                    "listed": [item.to_dict() for item in items[:MAX_ENTRIES_PER_KIND]],
                    "truncated": len(items) > MAX_ENTRIES_PER_KIND,
                }
                for kind, items in sorted(by_kind.items())
            },
        }


def _tally(items: list[Entry]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.outcome] = counts.get(item.outcome, 0) + 1
    return counts


def verdict(checks: Iterable[tuple[str, bool, str]], *, omissions: bool = False) -> dict[str, Any]:
    """Build the verdict from `(label, ok, detail)` triples.

    Three states, per POC-3 §9: `FAILED` is a contract error or an exception; `PASSED WITH
    OMISSIONS` is anything reported-not-translated; `PASSED` is everything translated — which is
    **rare on real models, and that is fine**. A translator that reports `PASSED` on a model it
    silently truncated would be the worse outcome by a wide margin.
    """
    graded = [{"label": label, "ok": bool(ok), "detail": detail} for label, ok, detail in checks]
    passed = all(check["ok"] for check in graded)
    return {
        "passed": passed,
        "headline": ("PASSED WITH OMISSIONS" if omissions else "PASSED") if passed else "FAILED",
        "checks": graded,
    }


def failure(label: str, message: str) -> dict[str, Any]:
    """A verdict for a run that could not start — a bad contract version, unreadable geometry."""
    return verdict([(label, False, message)])
