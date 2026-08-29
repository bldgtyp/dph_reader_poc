# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Minimal ctypes binding to the SketchUp C SDK — shared by every Spike A gate script.

⚠ **PROVENANCE.** The framework this loads is a **third-party re-host** of Trimble's proprietary,
EULA-gated `SketchUpAPI.framework` (`martijnberger/pyslapi` release 0.24), used here because the
official SDK is behind a Request Access form with no reported turnaround
(`planning/HEADLESS/RESULTS/HEADLESS-A_results.md` §1). Ed authorised this **for time-boxed laptop
feasibility only, in parallel with filing Trimble's form** (2026-08-28). Nothing built on it ships,
and every gate result derived through it is labelled feasibility-only evidence — it must be re-run
against the official SDK before anything is trusted. **No EULA ships in that zip**, so licensing
task L1 remains unstartable.

Design notes, all of them load-bearing:

- **Every string read goes through `SUStringGetUTF8Length` + a counted copy.** Never `c_char_p`.
  designPH's Marshal blobs contain `0x00` bytes, and a NUL-terminated read would truncate them
  silently — the worst case being a *false PASS* on a partially decoded table
  (`HEADLESS-A_sdk-feasibility.md` G4).
- **`SU*Ref` handles are structs wrapping one pointer**, not bare pointers. Passing a bare
  `c_void_p` where the ABI expects a one-field struct happens to work on arm64 for *arguments* and
  is wrong in general; the real struct type is used so the binding stays honest.
- **`SUResult` is checked on every call.** `SU_ERROR_NO_DATA` is a normal answer (an entity with no
  attribute dictionaries), not a failure, so callers can opt into tolerating specific codes.
"""

from __future__ import annotations

import ctypes
import ctypes.util
from ctypes import POINTER, byref, c_char, c_double, c_int32, c_int64, c_size_t, c_void_p
from pathlib import Path

# SUResult codes we name. The full enum is larger; these are the ones that carry meaning here.
SU_ERROR_NONE = 0
SU_ERROR_NULL_POINTER_INPUT = 1
SU_ERROR_INVALID_INPUT = 2
SU_ERROR_NULL_POINTER_OUTPUT = 3
SU_ERROR_INVALID_OUTPUT = 4
SU_ERROR_OVERWRITE_VALID = 5
SU_ERROR_GENERIC = 6
SU_ERROR_SERIALIZATION = 7
SU_ERROR_OUT_OF_RANGE = 8
SU_ERROR_NO_DATA = 9
SU_ERROR_INSUFFICIENT_SIZE = 10
SU_ERROR_UNKNOWN_EXCEPTION = 11
SU_ERROR_MODEL_INVALID = 12
SU_ERROR_MODEL_VERSION = 13
SU_ERROR_LAYER_LOCKED = 14
SU_ERROR_DUPLICATE = 15
SU_ERROR_PARTIAL_SUCCESS = 16
SU_ERROR_UNSUPPORTED = 17
SU_ERROR_INVALID_ARGUMENT = 18
SU_ERROR_ENTITY_LOCKED = 19
SU_ERROR_INVALID_OPERATION = 20

RESULT_NAMES = {v: k for k, v in list(globals().items()) if k.startswith("SU_ERROR_")}

# ⚠ There is NO version-enum map here, deliberately. `SUModelGetVersion` sounds like it returns the
# `SUModelVersion` enum (`SUModelVersion_SU2021` and friends) and it does NOT — it writes three
# ints: major, minor, build. Inferring the two-arg enum signature from the doxygen *name* passed on
# Adelphi (returning 22, which happens to be its writer's major version) and SEGFAULTED on the next
# model, because two unprovided out-pointers were being written through. A published name is not a
# signature; `a3_header_audit.py` now checks every declaration below against the shipped headers.

# SURefType — what an SUEntityRef actually is. Used to classify a walk without guessing.
REF_TYPES = {
    0: "Unknown", 1: "AttributeDictionary", 2: "Camera", 3: "ComponentDefinition",
    4: "ComponentInstance", 5: "Curve", 6: "Edge", 7: "EdgeUse", 8: "Entities", 9: "Face",
    10: "Group", 11: "Image", 12: "Layer", 13: "Loop", 14: "MeshHelper", 15: "Material",
    16: "Model", 17: "Polyline3d", 18: "Scene", 19: "Texture", 20: "TextureWriter",
    21: "TypedValue", 22: "UVHelper", 23: "Vertex", 24: "RenderingOptions", 25: "GuidePoint",
    26: "GuideLine", 27: "Schema", 28: "SchemaType", 29: "ShadowInfo", 30: "Attribute",
    31: "Text", 32: "Dimension", 33: "DimensionLinear", 34: "DimensionRadial",
    35: "DimensionStyle", 36: "Font", 37: "InstancePath", 38: "ImageRep", 39: "Overlay",
    40: "LineStyle", 41: "SectionPlane", 42: "LayerFolder", 43: "Environment",
}

# SUTypedValueType — the type tag. Hard rule 5 (type-check every attribute read) needs this.
TYPED_VALUE_TYPES = {
    0: "Empty", 1: "Byte", 2: "Short", 3: "Int32", 4: "Float", 5: "Double", 6: "Bool",
    7: "Color", 8: "Time", 9: "String", 10: "Vector3D", 11: "Array",
}


class SUResultError(RuntimeError):
    def __init__(self, fn: str, code: int) -> None:
        super().__init__(f"{fn} -> {RESULT_NAMES.get(code, f'SU_ERROR_{code}')} ({code})")
        self.fn, self.code = fn, code


def _ref(name: str) -> type[ctypes.Structure]:
    """An `SU*Ref` opaque handle: a struct wrapping a single pointer, exactly as the headers declare."""
    return type(name, (ctypes.Structure,), {"_fields_": [("ptr", c_void_p)]})


SUEntityRef = _ref("SUEntityRef")
SUModelRef = _ref("SUModelRef")
SUEntitiesRef = _ref("SUEntitiesRef")
SUFaceRef = _ref("SUFaceRef")
SUEdgeRef = _ref("SUEdgeRef")
SUVertexRef = _ref("SUVertexRef")
SULoopRef = _ref("SULoopRef")
SUComponentInstanceRef = _ref("SUComponentInstanceRef")
SUComponentDefinitionRef = _ref("SUComponentDefinitionRef")
SUGroupRef = _ref("SUGroupRef")
SUDrawingElementRef = _ref("SUDrawingElementRef")
SUOpeningRef = _ref("SUOpeningRef")
SUAttributeDictionaryRef = _ref("SUAttributeDictionaryRef")
SUTypedValueRef = _ref("SUTypedValueRef")
SUStringRef = _ref("SUStringRef")
SULayerRef = _ref("SULayerRef")


class SUPoint3D(ctypes.Structure):
    _fields_ = [("x", c_double), ("y", c_double), ("z", c_double)]

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


class SUVector3D(ctypes.Structure):
    _fields_ = [("x", c_double), ("y", c_double), ("z", c_double)]


class SUTransformation(ctypes.Structure):
    """Column-major 4x4, same layout the contract's `transformation` array carries."""

    _fields_ = [("values", c_double * 16)]

    def as_list(self) -> list[float]:
        return list(self.values)


DEFAULT_FRAMEWORK = (
    Path(__file__).parent / "_private" / "sdk" / "sketchup_importer" / "SketchUpAPI.framework" / "SketchUpAPI"
)


class SDK:
    """A loaded SketchUpAPI framework, with `SUInitialize` already called."""

    def __init__(self, framework: Path | None = None) -> None:
        self.path = Path(framework) if framework else DEFAULT_FRAMEWORK
        if not self.path.exists():
            raise SystemExit(
                f"SketchUpAPI framework not found at {self.path}\n"
                "Stage it first — see planning/HEADLESS/RESULTS/HEADLESS-A_results.md §1.1"
            )
        self.lib = ctypes.CDLL(str(self.path))
        self._configure()
        self.lib.SUInitialize()
        self._initialized = True

    # -- plumbing ---------------------------------------------------------

    def _configure(self) -> None:
        """Declare argtypes/restype for everything used. ctypes defaults to int for untyped returns,
        which silently truncates a returned pointer on 64-bit — so nothing here is left undeclared."""
        L = self.lib
        sig = [
            ("SUInitialize", [], None),
            ("SUTerminate", [], None),
            ("SUGetAPIVersion", [POINTER(c_size_t), POINTER(c_size_t)], c_int32),
            ("SUModelCreateFromFile", [POINTER(SUModelRef), ctypes.c_char_p], c_int32),
            ("SUModelRelease", [POINTER(SUModelRef)], c_int32),
            ("SUModelGetVersion",
             [SUModelRef, POINTER(c_int32), POINTER(c_int32), POINTER(c_int32)], c_int32),
            ("SUModelGetName", [SUModelRef, POINTER(SUStringRef)], c_int32),
            ("SUModelGetGuid", [SUModelRef, POINTER(SUStringRef)], c_int32),
            ("SUModelGetEntities", [SUModelRef, POINTER(SUEntitiesRef)], c_int32),
            ("SUModelGetNumComponentDefinitions", [SUModelRef, POINTER(c_size_t)], c_int32),
            ("SUModelGetComponentDefinitions",
             [SUModelRef, c_size_t, POINTER(SUComponentDefinitionRef), POINTER(c_size_t)], c_int32),
            ("SUModelGetNumGroupDefinitions", [SUModelRef, POINTER(c_size_t)], c_int32),
            ("SUModelGetGroupDefinitions",
             [SUModelRef, c_size_t, POINTER(SUComponentDefinitionRef), POINTER(c_size_t)], c_int32),
            ("SUModelGetNumAttributeDictionaries", [SUModelRef, POINTER(c_size_t)], c_int32),
            ("SUModelGetAttributeDictionaries",
             [SUModelRef, c_size_t, POINTER(SUAttributeDictionaryRef), POINTER(c_size_t)], c_int32),
            # strings — length-aware only
            ("SUStringCreate", [POINTER(SUStringRef)], c_int32),
            ("SUStringRelease", [POINTER(SUStringRef)], c_int32),
            ("SUStringGetUTF8Length", [SUStringRef, POINTER(c_size_t)], c_int32),
            ("SUStringGetUTF8", [SUStringRef, c_size_t, POINTER(c_char), POINTER(c_size_t)], c_int32),
            # entities containers
            ("SUEntitiesGetNumFaces", [SUEntitiesRef, POINTER(c_size_t)], c_int32),
            ("SUEntitiesGetFaces", [SUEntitiesRef, c_size_t, POINTER(SUFaceRef), POINTER(c_size_t)], c_int32),
            ("SUEntitiesGetNumEdges", [SUEntitiesRef, ctypes.c_bool, POINTER(c_size_t)], c_int32),
            ("SUEntitiesGetEdges",
             [SUEntitiesRef, ctypes.c_bool, c_size_t, POINTER(SUEdgeRef), POINTER(c_size_t)], c_int32),
            ("SUEntitiesGetNumInstances", [SUEntitiesRef, POINTER(c_size_t)], c_int32),
            ("SUEntitiesGetInstances",
             [SUEntitiesRef, c_size_t, POINTER(SUComponentInstanceRef), POINTER(c_size_t)], c_int32),
            ("SUEntitiesGetNumGroups", [SUEntitiesRef, POINTER(c_size_t)], c_int32),
            ("SUEntitiesGetGroups", [SUEntitiesRef, c_size_t, POINTER(SUGroupRef), POINTER(c_size_t)], c_int32),
            # entity identity + attributes
            # ⚠ returns the enum DIRECTLY; not an out-param call, and not SU_RESULT.
            ("SUEntityGetType", [SUEntityRef], c_int32),
            ("SUEntityGetID", [SUEntityRef, POINTER(c_int32)], c_int32),
            ("SUEntityGetPersistentID", [SUEntityRef, POINTER(c_int64)], c_int32),
            ("SUEntityGetNumAttributeDictionaries", [SUEntityRef, POINTER(c_size_t)], c_int32),
            ("SUEntityGetAttributeDictionaries",
             [SUEntityRef, c_size_t, POINTER(SUAttributeDictionaryRef), POINTER(c_size_t)], c_int32),
            ("SUEntityGetAttributeDictionary",
             [SUEntityRef, ctypes.c_char_p, POINTER(SUAttributeDictionaryRef)], c_int32),
            ("SUAttributeDictionaryGetName", [SUAttributeDictionaryRef, POINTER(SUStringRef)], c_int32),
            ("SUAttributeDictionaryGetNumKeys", [SUAttributeDictionaryRef, POINTER(c_size_t)], c_int32),
            ("SUAttributeDictionaryGetKeys",
             [SUAttributeDictionaryRef, c_size_t, POINTER(SUStringRef), POINTER(c_size_t)], c_int32),
            ("SUAttributeDictionaryGetValue",
             [SUAttributeDictionaryRef, ctypes.c_char_p, POINTER(SUTypedValueRef)], c_int32),
            # typed values
            ("SUTypedValueCreate", [POINTER(SUTypedValueRef)], c_int32),
            ("SUTypedValueRelease", [POINTER(SUTypedValueRef)], c_int32),
            ("SUTypedValueGetType", [SUTypedValueRef, POINTER(c_int32)], c_int32),
            ("SUTypedValueGetString", [SUTypedValueRef, POINTER(SUStringRef)], c_int32),
            ("SUTypedValueGetInt32", [SUTypedValueRef, POINTER(c_int32)], c_int32),
            ("SUTypedValueGetDouble", [SUTypedValueRef, POINTER(c_double)], c_int32),
            ("SUTypedValueGetBool", [SUTypedValueRef, POINTER(ctypes.c_bool)], c_int32),
            # faces / loops / geometry
            ("SUFaceGetArea", [SUFaceRef, POINTER(c_double)], c_int32),
            ("SUFaceGetOuterLoop", [SUFaceRef, POINTER(SULoopRef)], c_int32),
            ("SUFaceGetNumInnerLoops", [SUFaceRef, POINTER(c_size_t)], c_int32),
            ("SUFaceGetInnerLoops", [SUFaceRef, c_size_t, POINTER(SULoopRef), POINTER(c_size_t)], c_int32),
            ("SUFaceGetNormal", [SUFaceRef, POINTER(SUVector3D)], c_int32),
            ("SUFaceGetNumOpenings", [SUFaceRef, POINTER(c_size_t)], c_int32),
            ("SUFaceGetOpenings", [SUFaceRef, c_size_t, POINTER(SUOpeningRef), POINTER(c_size_t)], c_int32),
            ("SULoopGetNumVertices", [SULoopRef, POINTER(c_size_t)], c_int32),
            ("SULoopGetVertices", [SULoopRef, c_size_t, POINTER(SUVertexRef), POINTER(c_size_t)], c_int32),
            ("SUVertexGetPosition", [SUVertexRef, POINTER(SUPoint3D)], c_int32),
            ("SUEdgeGetStartVertex", [SUEdgeRef, POINTER(SUVertexRef)], c_int32),
            ("SUEdgeGetEndVertex", [SUEdgeRef, POINTER(SUVertexRef)], c_int32),
            # instances / definitions / transforms
            ("SUComponentInstanceGetDefinition",
             [SUComponentInstanceRef, POINTER(SUComponentDefinitionRef)], c_int32),
            ("SUComponentInstanceGetTransform",
             [SUComponentInstanceRef, POINTER(SUTransformation)], c_int32),
            ("SUComponentInstanceGetName", [SUComponentInstanceRef, POINTER(SUStringRef)], c_int32),
            ("SUComponentInstanceGetNumAttachedToDrawingElements",
             [SUComponentInstanceRef, POINTER(c_size_t)], c_int32),
            ("SUComponentInstanceGetAttachedToDrawingElements",
             [SUComponentInstanceRef, c_size_t, POINTER(SUDrawingElementRef), POINTER(c_size_t)], c_int32),
            ("SUComponentDefinitionGetEntities",
             [SUComponentDefinitionRef, POINTER(SUEntitiesRef)], c_int32),
            ("SUComponentDefinitionGetName", [SUComponentDefinitionRef, POINTER(SUStringRef)], c_int32),
            ("SUGroupGetEntities", [SUGroupRef, POINTER(SUEntitiesRef)], c_int32),
            ("SUGroupGetTransform", [SUGroupRef, POINTER(SUTransformation)], c_int32),
            ("SUGroupGetName", [SUGroupRef, POINTER(SUStringRef)], c_int32),
        ]
        for name, args, res in sig:
            fn = getattr(L, name, None)
            if fn is None:
                continue  # reported by `missing()`, not fatal at load time
            fn.argtypes = args
            if res is not None:
                fn.restype = res

    def missing(self, names: list[str]) -> list[str]:
        """Which of these symbols the loaded binary does not export. A doc name is not a symbol."""
        return [n for n in names if not hasattr(self.lib, n)]

    def check(self, name: str, code: int, tolerate: tuple[int, ...] = ()) -> int:
        if code != SU_ERROR_NONE and code not in tolerate:
            raise SUResultError(name, code)
        return code

    def call(self, name: str, *args: object, tolerate: tuple[int, ...] = ()) -> int:
        return self.check(name, getattr(self.lib, name)(*args), tolerate)

    # -- strings ----------------------------------------------------------

    def read_string(self, su_string: SUStringRef) -> bytes:
        """Read an `SUStringRef` as RAW BYTES via the length-aware API.

        ⚠ Returns `bytes`, not `str`, deliberately. designPH's Marshal tables come back through this
        path and contain `0x00` and arbitrary non-UTF-8 sequences; decoding here would corrupt them.
        Callers that want text decode explicitly.
        """
        length = c_size_t()
        self.call("SUStringGetUTF8Length", su_string, byref(length))
        n = length.value
        buf = (c_char * (n + 1))()
        out = c_size_t()
        self.call("SUStringGetUTF8", su_string, n + 1, buf, byref(out))
        return bytes(buf[: out.value])

    def string_out(self, fn: str, *args: object) -> bytes:
        """Call an SU function whose last out-param is an SUStringRef, and return its raw bytes."""
        s = SUStringRef()
        self.call("SUStringCreate", byref(s))
        try:
            self.call(fn, *args, byref(s))
            return self.read_string(s)
        finally:
            self.lib.SUStringRelease(byref(s))

    # -- counted list helper ---------------------------------------------

    def get_list(self, count_fn: str, get_fn: str, ref_type, *head: object, extra: tuple = ()):
        """The SDK's universal two-call idiom: GetNumX then GetX into a caller-allocated array."""
        n = c_size_t()
        self.call(count_fn, *head, *extra, byref(n))
        if n.value == 0:
            return []
        arr = (ref_type * n.value)()
        got = c_size_t()
        self.call(get_fn, *head, *extra, n.value, arr, byref(got))
        return list(arr[: got.value])

    # -- lifecycle --------------------------------------------------------

    def api_version(self) -> tuple[int, int]:
        major, minor = c_size_t(), c_size_t()
        self.lib.SUGetAPIVersion(byref(major), byref(minor))
        return major.value, minor.value

    def open_model(self, path: Path) -> SUModelRef:
        model = SUModelRef()
        self.call("SUModelCreateFromFile", byref(model), str(path).encode("utf-8"))
        return model

    def close_model(self, model: SUModelRef) -> None:
        self.lib.SUModelRelease(byref(model))

    def model_version(self, model: SUModelRef) -> tuple[int, int, int]:
        """(major, minor, build) of the SketchUp that wrote the file — NOT the `SUModelVersion` enum."""
        major, minor, build = c_int32(), c_int32(), c_int32()
        self.call("SUModelGetVersion", model, byref(major), byref(minor), byref(build))
        return major.value, minor.value, build.value

    def entity_type(self, entity: SUEntityRef) -> str:
        """`SURefType` name. Returns the enum directly — no out-param, no SUResult."""
        return REF_TYPES.get(self.lib.SUEntityGetType(entity), "?")

    def terminate(self) -> None:
        if getattr(self, "_initialized", False):
            self.lib.SUTerminate()
            self._initialized = False
