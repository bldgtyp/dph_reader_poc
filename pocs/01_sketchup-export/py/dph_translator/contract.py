"""Parsing the extraction JSON -- the Ruby → Python seam.

The contract (`planning/01_sketchup-export/implementation/CONTRACT_extraction-json.md`) is
deliberately loose about *types* and
strict about *presence*: Ruby stays dumb and passes designPH's values through raw, so `area_group`
may arrive as `"8"`, `8`, `"n"` or `null` on faces of the same model. **Every read is type-checked
here** (hard rule 5) -- one place to get it wrong, not one per call site.

What this module does NOT do: judge. It turns JSON into typed records and reports what it could not
read. Deciding that a face is a Wall, or that an assembly is unresolvable, belongs to `translate`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

#: The only contract version this translator understands. A mismatch is a hard, reported error --
#: no compatibility shims in a POC (contract §9).
#:
#: **v2** (2026-08-21) moved the frame/glazing option lists out of every window's
#: `dynamic_attributes` and into a model-level `libraries` block. They are library data, they were
#: byte-identical on all 46 of Adelphi's windows, and repeating them cost **2.07 MB of a 2.25 MB
#: payload** against a bridge verified to 4 MB.
CONTRACT_VERSION = 2

Point = tuple[float, float, float]

#: designPH's Dynamic Component values are inches even when the model displays metres.
INCH_TO_M = 0.0254


class ContractError(Exception):
    """The payload is not a contract document this translator can read."""


@dataclass(frozen=True)
class ModelInfo:
    """`model` -- identification, all of it optional except the file name."""

    file_name: str
    designph_versions: tuple[str, ...] = ()
    klima_id: str | None = None
    klima_standort: str | None = None


@dataclass(frozen=True)
class FaceRecord:
    """One classified face. Geometry is metres, world coordinates, SketchUp winding order.

    `area_group`, `temp_zone` and `assembly_ref` are held **raw**, exactly as designPH stored them.
    Use `area_group_int` rather than casting at the call site.
    """

    id: str
    area_group: Any
    outer_loop: tuple[Point, ...] = ()
    inner_loops: tuple[tuple[Point, ...], ...] = ()
    desc_name: str | None = None
    temp_zone: Any = None
    assembly_ref: Any = None
    tfa_rf: Any = None
    area_m2: float | None = None
    both_generations: tuple[str, ...] = ()
    #: Why this record could not be read, when it could not. The face still travels -- it has an id,
    #: so the report can name it (hard rule 4) -- it just has no usable geometry.
    error: str | None = None

    @property
    def area_group_int(self) -> int | None:
        """The area group as a positive integer, or `None` when it is not one.

        `'n'` -- "not assigned" -- is by far the most common value in a real model (1359 of 1441
        faces on Adelphi), so a failed parse is the normal case, not an error.
        """
        return as_positive_int(self.area_group)


@dataclass(frozen=True)
class EdgeRecord:
    """A tagged edge. Area groups 15/16/17 are thermal bridges, which PHPP measures as lengths.

    `connection_ref` is named apart from a face's `assembly_ref` deliberately: it resolves against
    `connections_ud`, a different table. Both namespaces use `NNud` ids, so joining it to the
    assemblies by accident returns an unrelated row rather than an error.
    """

    id: str
    area_group: Any
    connection_ref: Any = None
    desc_name: str | None = None
    start: Point = (0.0, 0.0, 0.0)
    end: Point = (0.0, 0.0, 0.0)
    #: The collector's own measurement. `PhThermalBridge.length` is derived from geometry, so this
    #: is a cross-check and never an input.
    length_m: float | None = None
    both_generations: tuple[str, ...] = ()
    error: str | None = None

    @property
    def area_group_int(self) -> int | None:
        return as_positive_int(self.area_group)


@dataclass(frozen=True)
class WindowRecord:
    """A designPH window: a Dynamic Component, so its data is in `dynamic_attributes`, raw.

    ⚠ Units are **per field** and nothing has been converted: `lenx`/`leny`/`d_reveal`/`o_reveal`/
    `framedepth`/`revealdepth` are inches-as-Strings, `framewidth*` are inches-as-Floats,
    `instcill`/`insthead`/`instleft`/`instright` are `"0"`/`"1"` flags.

    ⚠ **`area` is a stale Dynamic-Component formula output and nothing may compute from it.** It
    equals `lenx × leny × 0.00064516` on only 20 of Adelphi's 46 windows, with ratios from 0.44 to
    1.66 — instance scaling and frame deduction are both ruled out by measurement. It travels so a
    report can say what the model claims (`DESIGNPH_DATA_MODEL.md` §9.2).
    """

    id: str
    #: Never empty. Every report line has to be able to name its window.
    designph_name: str
    definition_name: str | None = None
    dynamic_attributes: Mapping[str, Any] = field(default_factory=dict)
    #: The **accumulated world** transform as `to_a` — column-major, translation at 12–14, in
    #: INCHES. ⚠ Not `instance.transformation`, which is parent-relative while every other geometry
    #: field here is world; mixing them put Adelphi's windows 1.2–3.3 m off their hosts (§8.2).
    transformation: tuple[float, ...] = ()
    #: The **rough opening** in world metres — `lenx × leny` from the definition origin, through the
    #: world transform. `None` means the collector could not read a size, not that it did not try.
    panel_outer_loop: tuple[Point, ...] | None = None
    host_face_id: str | None = None
    host_resolution: str = "unresolved"
    host_has_inner_loops: bool = False
    error: str | None = None

    def reveal(self, key: str) -> float | None:
        """`d_reveal` / `o_reveal` in **metres**. Inches-as-Strings on the way in."""
        value = as_float(self.dynamic_attributes.get(key))
        return None if value is None else value * INCH_TO_M


@dataclass(frozen=True)
class Table:
    """A decoded Marshal table: self-describing header plus rows, values untouched.

    designPH's own table values are already SI/PHPP units (lambda, Psi, mm) and stay that way.
    Only *SketchUp geometry* was converted to metres.
    """

    tokens: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]

    def column(self, token: str) -> int | None:
        """Index of `token`, or `None`. Read tables by NAME -- `layer_table_*` has an 8-column and
        a 12-column variant, and a positional read silently mixes them up."""
        return self.tokens.index(token) if token in self.tokens else None

    def records(self) -> tuple[Mapping[str, Any], ...]:
        """Rows zipped against `tokens`, so every downstream read is by name.

        This is what makes the 8-column and 12-column `layer_table_*` variants the same code path.
        A short row simply has fewer keys; a long one keeps its extras out of the way.
        """
        return tuple(dict(zip(self.tokens, row, strict=False)) for row in self.rows)

    def find(self, key_token: str, value: Any) -> Mapping[str, Any] | None:
        """The first record whose `key_token` matches `value`, compared as text.

        designPH ids arrive as Strings everywhere, but a table cell could be anything — the same
        type instability that makes hard rule 5 a rule.
        """
        wanted = str(value).strip()
        for record in self.records():
            if str(record.get(key_token, "")).strip() == wanted:
                return record
        return None


@dataclass(frozen=True)
class Library:
    """designPH's frame or glazing library, as it travels inline in the model.

    A SketchUp Dynamic-Component option list: `&<name>=<id>&<name>=<id>&`. Adelphi's frame list is
    **39,685 characters** — some 500 entries down to real manufacturer products — and
    `DESIGNPH_FILE_FORMATS.md` §3 otherwise has these living only in designPH's installed CSVs. It
    carries no U-values or g-values, but it **names the ids**, which is the difference between a
    report line saying `01ud` and one saying `PH Glazing (01ud)`.

    ⚠ The collector ships every *distinct* raw string it saw and does not choose between them —
    deduplicating is not a judgement call, picking a winner is, and that is this class's job.
    designPH writes a placeholder (`&Launch designPH to edit=01ud&`) on some definitions, so the real
    library is not always the only list, and both claim `01ud`.

    ⚠ **The tiebreak is the size of the list, not the length of the name.** "Longer name wins" is the
    obvious rule and it is wrong here: *Launch designPH to edit* is longer than *PH Glazing*, so the
    placeholder would win and silently un-name the whole library. A placeholder names exactly one id;
    a real library names hundreds — so the richer list wins, wholesale.
    """

    names: Mapping[str, str] = field(default_factory=dict)
    #: How many distinct raw option strings the collector saw. >1 is normal, not a warning.
    sources: int = 0

    @classmethod
    def from_raw(cls, values: Sequence[Any]) -> Library:
        parsed = [cls._entries(value) for value in values if isinstance(value, str)]
        names: dict[str, str] = {}
        # Poorest list first, so the richest overwrites it. Merged rather than discarded: a shorter
        # list may still name an id the long one does not.
        for entries in sorted(parsed, key=len):
            names.update(entries)
        return cls(names=names, sources=len(parsed))

    @staticmethod
    def _entries(value: str) -> dict[str, str]:
        entries: dict[str, str] = {}
        for entry in value.split("&"):
            if "=" not in entry:
                continue
            # `rsplit`, because a product name may well contain '=' and an id never does.
            name, identifier = (part.strip() for part in entry.rsplit("=", 1))
            if identifier and name:
                entries[identifier] = name
        return entries

    def label(self, identifier: Any) -> str | None:
        """`"PH Glazing (01ud)"`, or `None` when the library cannot name it."""
        key = str(identifier).strip()
        name = self.names.get(key)
        return f"{name} ({key})" if name else None


@dataclass(frozen=True)
class UnclassifiedFace:
    """A designPH-tagged face whose area group does not classify it.

    1359 of Adelphi's 1441 tagged faces are these. They carry no geometry — they exist so the report
    can **name** every tagged entity the translation omits, which is what hard rule 4 asks for.
    """

    id: str
    area_group: Any
    tag: str | None = None


@dataclass(frozen=True)
class Extraction:
    """One whole extraction document.

    `raw` is kept for anything not modelled at all — it is a fallback, not the way in. Nothing
    outside this module should reach into it.
    """

    contract_version: int
    generated_by: str
    model: ModelInfo
    faces: tuple[FaceRecord, ...]
    edges: tuple[EdgeRecord, ...] = ()
    windows: tuple[WindowRecord, ...] = ()
    unclassified: tuple[UnclassifiedFace, ...] = ()
    untagged_by_tag: Mapping[str, int] = field(default_factory=dict)
    #: `frame_types` / `glazing_types` — designPH's own libraries, carried inline in the model.
    libraries: Mapping[str, Library] = field(default_factory=dict)
    tables: Mapping[str, Table] = field(default_factory=dict)
    #: Tables Ruby shipped as `{"error": …}`, by name. Absent ≠ undecodable, and the difference is
    #: the difference between a normal model and a collector bug (contract §5).
    table_errors: Mapping[str, str] = field(default_factory=dict)
    counts: Mapping[str, Any] = field(default_factory=dict)
    raw: Mapping[str, Any] = field(repr=False, default_factory=dict)

    def census_mismatch(self) -> str | None:
        """Contract §6.1's invariant: `len(tagged_faces) + len(faces) == counts.faces_tagged`.

        Returns the discrepancy as a sentence, or `None` when it holds or cannot be checked. A
        mismatch means the collector's walk and its own census disagree — which is how a whole
        missing entity type announces itself.
        """
        tagged = self.counts.get("faces_tagged")
        if not isinstance(tagged, int) or isinstance(tagged, bool):
            return None
        accounted = len(self.faces) + len(self.unclassified)
        if accounted == tagged:
            return None
        return (
            f"census: {len(self.faces)} classified + {len(self.unclassified)} tagged-unclassified "
            f"= {accounted}, but the collector counted {tagged} tagged faces"
        )


# ------------------------------------------------------------------------------------------------
# Type-checked readers. Everything above is built through these.
# ------------------------------------------------------------------------------------------------


def as_positive_int(value: Any) -> int | None:
    """`8`, `"8"` and `" 8 "` → 8. `"n"`, `None`, `0`, `-1`, `8.5` → `None`.

    Deliberately strict about floats: designPH ids and area groups are integers, and a float here
    means the field was misread upstream rather than that it should be rounded.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        try:
            parsed = int(value.strip(), 10)
        except ValueError:
            return None
        return parsed if parsed > 0 else None
    return None


def as_text(value: Any) -> str | None:
    """A non-empty string, or `None`. Blank and whitespace-only both mean "absent"."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def as_point(value: Any) -> Point:
    """`[x, y, z]` of numbers → a tuple of floats."""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 3:
        raise ContractError(f"expected a point of 3 numbers, got {value!r}")
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except (TypeError, ValueError) as error:
        raise ContractError(f"point {value!r} is not numeric: {error}") from error


def as_loop(value: Any) -> tuple[Point, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ContractError(f"expected a loop (list of points), got {type(value)!r}")
    return tuple(as_point(point) for point in value)


def as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------------------------------------
# Parsing
# ------------------------------------------------------------------------------------------------


def _parse_face(record: Any, index: int) -> FaceRecord:
    """One face record. **A malformed face is a reportable face, never a dead document.**

    Granularity matters here: an unreadable coordinate on face 900 of 1441 must cost that one face,
    named in the report, not the other 1440 (hard rule 4). Only document-level problems -- a wrong
    contract version, no `faces` list at all -- are fatal, and those are `parse`'s business.
    """
    if not isinstance(record, Mapping):
        return FaceRecord(id=f"face_{index}", area_group=None, error="record is not an object")
    identifier = as_text(record.get("id")) or f"face_{index}"
    try:
        outer_loop = as_loop(record.get("outer_loop") or ())
        inner_loops = tuple(as_loop(loop) for loop in (record.get("inner_loops") or ()))
    except ContractError as error:
        return FaceRecord(id=identifier, area_group=record.get("area_group"), error=str(error))
    return FaceRecord(
        id=identifier,
        area_group=record.get("area_group"),
        outer_loop=outer_loop,
        inner_loops=inner_loops,
        desc_name=as_text(record.get("desc_name")),
        temp_zone=record.get("temp_zone"),
        assembly_ref=record.get("assembly_ref"),
        tfa_rf=record.get("tfa_rf"),
        area_m2=as_float(record.get("area_m2")),
        both_generations=tuple(str(name) for name in (record.get("both_generations") or ())),
    )


def _parse_table(record: Any) -> Table | str:
    """A `Table`, or the reason there is none.

    Ruby ships a Marshal blob it could not decode as `{"error": …}`. Contract §5 says such a blob is
    *reported*, not dropped -- and the distinction matters downstream: "table absent from the model"
    is the documented normal case, while "the collector's decode failed" is a bug. Returning the
    reason rather than `None` keeps the two apart.
    """
    if not isinstance(record, Mapping):
        return f"table is {type(record).__name__}, not an object"
    if "error" in record:
        return str(record["error"])
    tokens = tuple(str(token) for token in (record.get("tokens") or ()))
    rows = tuple(
        tuple(row)
        for row in (record.get("rows") or ())
        if isinstance(row, Sequence) and not isinstance(row, (str, bytes))
    )
    return Table(tokens=tokens, rows=rows)


def _section(payload: Mapping[str, Any], name: str) -> list[Any]:
    records = payload.get(name)
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        return []
    return list(records)


def _parse_edge(record: Any, index: int) -> EdgeRecord:
    """Same granularity rule as `_parse_face`: a malformed edge is reportable, not fatal."""
    if not isinstance(record, Mapping):
        return EdgeRecord(id=f"edge_{index}", area_group=None, error="record is not an object")
    identifier = as_text(record.get("id")) or f"edge_{index}"
    try:
        start = as_point(record.get("start"))
        end = as_point(record.get("end"))
    except ContractError as error:
        return EdgeRecord(id=identifier, area_group=record.get("area_group"), error=str(error))
    return EdgeRecord(
        id=identifier,
        area_group=record.get("area_group"),
        connection_ref=record.get("connection_ref"),
        desc_name=as_text(record.get("desc_name")),
        start=start,
        end=end,
        length_m=as_float(record.get("length_m")),
        both_generations=tuple(str(name) for name in (record.get("both_generations") or ())),
    )


def _parse_window(record: Any, index: int) -> WindowRecord:
    if not isinstance(record, Mapping):
        return WindowRecord(
            id=f"window_{index}", designph_name=f"window_{index}", error="record is not an object"
        )
    identifier = as_text(record.get("id")) or f"window_{index}"
    attributes = record.get("dynamic_attributes")
    panel = record.get("panel_outer_loop")
    error: str | None = None
    loop: tuple[Point, ...] | None = None
    if panel is not None:
        try:
            loop = as_loop(panel)
        except ContractError as problem:
            error = str(problem)
    return WindowRecord(
        id=identifier,
        # The contract guarantees this is never null; falling back to the id keeps that promise
        # even against a collector that broke it, because a report line with no name is useless.
        designph_name=as_text(record.get("designph_name")) or identifier,
        definition_name=as_text(record.get("definition_name")),
        dynamic_attributes=attributes if isinstance(attributes, Mapping) else {},
        transformation=tuple(
            float(v) for v in (record.get("transformation") or ()) if isinstance(v, (int, float))
        ),
        panel_outer_loop=loop,
        host_face_id=as_text(record.get("host_face_id")),
        host_resolution=as_text(record.get("host_resolution")) or "unresolved",
        host_has_inner_loops=bool(record.get("host_has_inner_loops")),
        error=error,
    )


def _parse_unclassified(
    record: Any,
) -> tuple[tuple[UnclassifiedFace, ...], Mapping[str, int]]:
    if not isinstance(record, Mapping):
        return (), {}
    faces = tuple(
        UnclassifiedFace(
            id=as_text(entry.get("id")) or "unclassified_face",
            area_group=entry.get("area_group"),
            tag=as_text(entry.get("tag")),
        )
        for entry in (record.get("tagged_faces") or ())
        if isinstance(entry, Mapping)
    )
    by_tag = record.get("untagged_by_tag")
    counts = (
        {str(tag): int(n) for tag, n in by_tag.items() if isinstance(n, int) and not isinstance(n, bool)}
        if isinstance(by_tag, Mapping)
        else {}
    )
    return faces, counts


def parse(payload: Mapping[str, Any]) -> Extraction:
    """Turn a decoded extraction document into typed records.

    Raises `ContractError` only for what makes the **document** unreadable: a wrong contract
    version, or no `faces` list. Individual malformed records survive as reportable ones -- see
    `_parse_face`. Values designPH owns are passed through raw for `translate` to judge.
    """
    if not isinstance(payload, Mapping):
        raise ContractError("payload is not a JSON object")

    version = payload.get("contract_version")
    if version != CONTRACT_VERSION:
        raise ContractError(
            f"contract_version {version!r}; this translator reads only version {CONTRACT_VERSION}"
        )

    model_raw = payload.get("model")
    model_raw = model_raw if isinstance(model_raw, Mapping) else {}
    model = ModelInfo(
        file_name=as_text(model_raw.get("file_name")) or "untitled",
        designph_versions=tuple(str(stamp) for stamp in (model_raw.get("designph_versions") or ())),
        klima_id=as_text(model_raw.get("klima_id")),
        klima_standort=as_text(model_raw.get("klima_standort")),
    )

    faces_raw = payload.get("faces")
    if faces_raw is None:
        raise ContractError("payload has no `faces` list")
    if not isinstance(faces_raw, Sequence) or isinstance(faces_raw, (str, bytes)):
        raise ContractError("`faces` is not a list")

    tables_raw = payload.get("tables")
    tables_raw = tables_raw if isinstance(tables_raw, Mapping) else {}
    tables: dict[str, Table] = {}
    table_errors: dict[str, str] = {}
    for name, record in tables_raw.items():
        parsed = _parse_table(record)
        if isinstance(parsed, Table):
            tables[str(name)] = parsed
        else:
            table_errors[str(name)] = parsed

    unclassified, untagged_by_tag = _parse_unclassified(payload.get("unclassified"))
    libraries_raw = payload.get("libraries")
    libraries = {
        str(name): Library.from_raw(values)
        for name, values in (libraries_raw.items() if isinstance(libraries_raw, Mapping) else ())
        if isinstance(values, Sequence) and not isinstance(values, (str, bytes))
    }
    counts = payload.get("counts")
    return Extraction(
        contract_version=CONTRACT_VERSION,
        generated_by=as_text(payload.get("generated_by")) or "unknown",
        model=model,
        faces=tuple(_parse_face(record, index) for index, record in enumerate(faces_raw)),
        edges=tuple(_parse_edge(r, i) for i, r in enumerate(_section(payload, "edges"))),
        windows=tuple(_parse_window(r, i) for i, r in enumerate(_section(payload, "windows"))),
        unclassified=unclassified,
        untagged_by_tag=untagged_by_tag,
        libraries=libraries,
        tables=tables,
        table_errors=table_errors,
        counts=counts if isinstance(counts, Mapping) else {},
        raw=payload,
    )
