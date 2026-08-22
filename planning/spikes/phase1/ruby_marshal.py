#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Read Ruby `Marshal.dump` (format 4.8) payloads without running Ruby.

designPH serialises its library tables as `Base64.encode64(Marshal.dump(table))` and stores
the result as a model-level `DesignPH_dict` string (see ../../../00_Context/DESIGNPH_FILE_FORMATS.md
section 7). Decoding them is how Phase 1 section 1.4 finds where assembly build-ups live.

Why a reader rather than `ruby -e 'Marshal.load(...)'`:

* `Marshal.load` instantiates whatever the stream names. This reader never constructs anything --
  an unknown class becomes a `RubyObject` record of its name and instance variables. That keeps a
  corpus file from being able to run code, and it degrades gracefully instead of raising
  `undefined class/module` on the first designPH type we have not seen.
* It keeps the toolchain to one language. Every other spike script here is PEP 723 + `uv run`.

Coverage is the subset designPH actually emits -- nil, booleans, Integer, Float, String, Symbol,
Array, Hash, plus object links and symlinks. Class-bearing types (`o`, `u`, `U`, `C`, `e`, `S`)
decode to a `RubyObject` naming the class, *without* constructing it. They are still consumed at
their true length so the stream stays aligned and the rest of the table decodes -- `tracker_data`
embeds a `Time`, and stopping there would have cost the whole blob.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Any

MARSHAL_MAJOR = 4
MARSHAL_MINOR = 8


class MarshalError(ValueError):
    """The stream is not readable as Marshal 4.8."""


class Symbol(str):
    """A Ruby Symbol. A `str` subclass so it compares and serialises like one.

    Kept distinct from `str` because designPH's table headers are symbols (`:id`, `:U_value`)
    while the row values beside them are strings -- conflating the two would make a decoded
    table ambiguous about which column names came from the schema.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return f":{str(self)}"


@dataclass
class RubyObject:
    """An object this reader does not construct: a custom class, or an unsupported type byte."""

    class_name: str
    ivars: dict[str, Any] = field(default_factory=dict)
    note: str | None = None


class _Reader:
    """One pass over one Marshal payload.

    Ruby keeps two back-reference tables and they are numbered independently: symbols are
    recorded in `_symbols` and reached with `;`, every other non-immediate object is recorded
    in `_objects` and reached with `@`. Both are 0-based in the order the objects are created.
    An object must be registered *before* its contents are read, or a self-referential array
    would renumber everything after it.
    """

    def __init__(self, buf: bytes) -> None:
        self.buf = buf
        self.pos = 0
        self._symbols: list[Symbol] = []
        self._objects: list[Any] = []

    # -- primitives ----------------------------------------------------------------

    def byte(self) -> int:
        if self.pos >= len(self.buf):
            raise MarshalError("stream ended mid-object")
        value = self.buf[self.pos]
        self.pos += 1
        return value

    def take(self, count: int) -> bytes:
        if self.pos + count > len(self.buf):
            raise MarshalError(f"stream ended: wanted {count} bytes at {self.pos}")
        chunk = self.buf[self.pos : self.pos + count]
        self.pos += count
        return chunk

    def long(self) -> int:
        """Ruby's packed integer: a lead byte that either *is* the value or sizes it."""
        lead = struct.unpack("b", self.take(1))[0]
        if lead == 0:
            return 0
        if 5 <= lead <= 127:
            return lead - 5
        if -128 <= lead <= -5:
            return lead + 5
        if 1 <= lead <= 4:
            return int.from_bytes(self.take(lead), "little", signed=False)
        raw = self.take(-lead)
        # Negative: sign-extend to the full width before interpreting.
        return int.from_bytes(raw + b"\xff" * (8 - len(raw)), "little", signed=True)

    # -- object table --------------------------------------------------------------

    def register(self, value: Any) -> Any:
        self._objects.append(value)
        return value

    # -- dispatch ------------------------------------------------------------------

    def read(self) -> Any:
        code = self.byte()

        if code == 0x30:  # '0'
            return None
        if code == 0x54:  # 'T'
            return True
        if code == 0x46:  # 'F'
            return False
        if code == 0x69:  # 'i'
            return self.long()
        if code == 0x3A:  # ':' new symbol
            symbol = Symbol(self.take(self.long()).decode("utf-8", "replace"))
            self._symbols.append(symbol)
            return symbol
        if code == 0x3B:  # ';' symlink
            return self._symbols[self.long()]
        if code == 0x40:  # '@' object link
            return self._objects[self.long()]
        if code == 0x22:  # '"' string
            return self.register(self.take(self.long()).decode("utf-8", "replace"))
        if code == 0x66:  # 'f' float, written as a decimal string
            return self.register(self._float(self.take(self.long()).decode("ascii", "replace")))
        if code == 0x6C:  # 'l' bignum
            return self.register(self._bignum())
        if code == 0x5B:  # '[' array
            return self._array()
        if code == 0x7B:  # '{' hash
            return self._hash()
        if code == 0x49:  # 'I' object carrying instance variables
            return self._ivars(self.read())
        if code in (0x6F, 0x53):  # 'o' plain object, 'S' struct
            return self._object_with_ivars()
        if code == 0x75:  # 'u' _dump/_load, e.g. Time
            return self._userdef()
        if code in (0x55, 0x43):  # 'U' marshal_dump/marshal_load, 'C' subclassed core type
            name = self.read()
            return self.register(RubyObject(str(name), {"value": self.read()}))
        if code == 0x65:  # 'e' extended -- a module name, then the object it wraps
            self.read()
            return self.read()

        raise MarshalError(f"unsupported type byte {code:#04x} ({chr(code)!r}) at {self.pos - 1}")

    # -- composites ----------------------------------------------------------------

    def _array(self) -> list[Any]:
        items: list[Any] = self.register([])
        for _ in range(self.long()):
            items.append(self.read())
        return items

    def _hash(self) -> dict[Any, Any]:
        pairs: dict[Any, Any] = self.register({})
        for _ in range(self.long()):
            key = self.read()
            pairs[key] = self.read()
        return pairs

    def _ivars(self, target: Any) -> Any:
        """Attach instance variables to the object just read.

        Almost every occurrence in designPH data is a String carrying `:E` (its encoding flag),
        which adds nothing worth keeping -- so plain strings are returned unchanged and only a
        `RubyObject` keeps them.
        """
        for _ in range(self.long()):
            name = self.read()
            value = self.read()
            if isinstance(target, RubyObject):
                target.ivars[str(name)] = value
        return target

    def _object_with_ivars(self) -> RubyObject:
        """`o` / `S`: a class name, then a count of name/value pairs. Named, never constructed."""
        obj = self.register(RubyObject(str(self.read())))
        for _ in range(self.long()):
            name = self.read()
            obj.ivars[str(name)] = self.read()
        return obj

    def _userdef(self) -> RubyObject:
        """`u`: a class name and an opaque, length-prefixed payload written by the class's `_dump`.

        Only that class knows how to read the payload, so it is kept as raw hex. The length
        prefix is what matters here -- consuming it exactly is what keeps the stream aligned.
        """
        name = str(self.read())
        payload = self.take(self.long())
        return self.register(
            RubyObject(name, {"__payload_hex__": payload.hex()}, note=f"opaque {name} payload")
        )

    def _bignum(self) -> int:
        sign = -1 if self.byte() == 0x2D else 1  # '-'
        words = self.long()
        return sign * int.from_bytes(self.take(words * 2), "little", signed=False)

    @staticmethod
    def _float(text: str) -> float:
        # Ruby writes non-finite floats as words, not as numerals.
        non_finite = {"inf": float("inf"), "-inf": float("-inf"), "nan": float("nan")}
        if text in non_finite:
            return non_finite[text]
        return float(text)


def loads(payload: bytes) -> Any:
    """Decode one Marshal 4.8 payload. Raises `MarshalError` on anything else."""
    if len(payload) < 2:
        raise MarshalError("payload too short to carry a Marshal header")
    major, minor = payload[0], payload[1]
    if (major, minor) != (MARSHAL_MAJOR, MARSHAL_MINOR):
        raise MarshalError(f"expected Marshal {MARSHAL_MAJOR}.{MARSHAL_MINOR}, got {major}.{minor}")
    return _Reader(payload[2:]).read()


def to_jsonable(value: Any) -> Any:
    """Convert a decoded graph into something `json.dump` accepts."""
    if isinstance(value, Symbol):
        return f":{value}"
    if isinstance(value, RubyObject):
        return {
            "__ruby_class__": value.class_name,
            **({"__note__": value.note} if value.note else {}),
            **{k: to_jsonable(v) for k, v in value.ivars.items()},
        }
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(to_jsonable(k)): to_jsonable(v) for k, v in value.items()}
    return value
