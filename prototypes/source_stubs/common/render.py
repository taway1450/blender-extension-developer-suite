"""``SourceModel`` -> ``.pyi`` stubs in the builtin layout (``bpy/types/__init__.pyi``, ``mathutils/__init__.pyi``).

One renderer for all three prototypes, so their stubs differ only by what each extracted. It applies no hand table
of the doc generator: every type comes from a fact in the model, and the few typing conventions it needs that no
source states (``bpy_prop_collection`` is generic over its items, the mathutils class a float array of a subtype
becomes, which is ``pyrna_math_object_from_array`` in ``python/intern/bpy_rna.cc``) are written here, in one place,
and named in the research note.

Every declaration carries no comment; ``facts.json`` holds where each was read.
"""

from __future__ import annotations

import ast
import keyword
import math
from dataclasses import dataclass, field
from pathlib import Path

from .model import (
    PyMethod,
    PySignature,
    RnaFunction,
    RnaProperty,
    SourceModel,
)

OPERATOR_RETURN = "set[Literal['RUNNING_MODAL', 'CANCELLED', 'FINISHED', 'PASS_THROUGH', 'INTERFACE']]"
# ``pyrna_math_object_from_array`` (python/intern/bpy_rna.cc): the mathutils class a float array becomes, by subtype
# and length. Everything else is a ``bpy_prop_array``.
_VECTOR = {2: "mathutils.Vector", 3: "mathutils.Vector", 4: "mathutils.Vector"}
_ROTATION = {3: "mathutils.Euler", 4: "mathutils.Quaternion"}
# subtype -> {array length: class}, as ``pyrna_math_object_from_array`` (bpy_rna.cc) converts a float array of one
# dimension (two for a matrix). ``axisangle`` is not converted.
MATH_SUBTYPES: dict[str, dict[int, str]] = {
    **dict.fromkeys(("coords", "translation", "direction", "velocity", "acceleration", "xyz", "xyz_length"), _VECTOR),
    "matrix": {9: "mathutils.Matrix", 16: "mathutils.Matrix"},
    "euler": _ROTATION,
    "quaternion": _ROTATION,
    "color": {3: "mathutils.Color"},
    "color_gamma": {3: "mathutils.Color"},
}
SCALAR = {"boolean": "bool", "int": "int", "float": "float", "string": "str"}
DECL_SOCKETS = {
    "Float": "NodeSocketFloat",
    "Int": "NodeSocketInt",
    "Bool": "NodeSocketBool",
    "Vector": "NodeSocketVector",
    "Color": "NodeSocketColor",
    "Rotation": "NodeSocketRotation",
    "Matrix": "NodeSocketMatrix",
    "String": "NodeSocketString",
    "Menu": "NodeSocketMenu",
    "Shader": "NodeSocketShader",
    "Geometry": "NodeSocketGeometry",
    "Object": "NodeSocketObject",
    "Material": "NodeSocketMaterial",
    "Collection": "NodeSocketCollection",
    "Texture": "NodeSocketTexture",
    "Image": "NodeSocketImage",
    "Bundle": "NodeSocketBundle",
    "Closure": "NodeSocketClosure",
    "Custom": "NodeSocketVirtual",
    "Extend": "NodeSocketVirtual",
}
BMO_SLOT_TYPES = {
    "bool": "bool",
    "int": "int",
    "flt": "float",
    "mat": "mathutils.Matrix",
    "vec": "mathutils.Vector",
}
# Slot dunders: ``PyTypeObject`` / ``PyNumberMethods`` / ``PySequenceMethods`` / ``PyMappingMethods`` field -> method
# lines (``{T}`` is the class).
SLOT_DUNDERS: dict[str, list[str]] = {
    "tp_iter": ["def __iter__(self) -> Iterator[Any]: ..."],
    "tp_iternext": ["def __next__(self) -> Any: ..."],
    "tp_call": ["def __call__(self, *args: Any, **kwargs: Any) -> Any: ..."],
    "tp_as_buffer": ["def __buffer__(self, flags: int, /) -> memoryview: ..."],
    "sq_length": ["def __len__(self) -> int: ..."],
    "mp_length": ["def __len__(self) -> int: ..."],
    "sq_item": ["def __getitem__(self, key: int, /) -> Any: ..."],
    "mp_subscript": ["def __getitem__(self, key: Any, /) -> Any: ..."],
    "sq_ass_item": ["def __setitem__(self, key: int, value: Any, /) -> None: ..."],
    "mp_ass_subscript": [
        "def __setitem__(self, key: Any, value: Any, /) -> None: ...",
        "def __delitem__(self, key: Any, /) -> None: ...",
    ],
    "sq_contains": ["def __contains__(self, key: object, /) -> bool: ..."],
    "sq_concat": ["def __add__(self, other: Any, /) -> Any: ..."],
    "sq_repeat": ["def __mul__(self, other: int, /) -> Any: ..."],
    "nb_add": ["def __add__(self, other: Any, /) -> Any: ...", "def __radd__(self, other: Any, /) -> Any: ..."],
    "nb_subtract": ["def __sub__(self, other: Any, /) -> Any: ...", "def __rsub__(self, other: Any, /) -> Any: ..."],
    "nb_multiply": ["def __mul__(self, other: Any, /) -> Any: ...", "def __rmul__(self, other: Any, /) -> Any: ..."],
    "nb_matrix_multiply": [
        "def __matmul__(self, other: Any, /) -> Any: ...",
        "def __rmatmul__(self, other: Any, /) -> Any: ...",
    ],
    "nb_true_divide": [
        "def __truediv__(self, other: Any, /) -> Any: ...",
        "def __rtruediv__(self, other: Any, /) -> Any: ...",
    ],
    "nb_floor_divide": ["def __floordiv__(self, other: Any, /) -> Any: ..."],
    "nb_remainder": ["def __mod__(self, other: Any, /) -> Any: ..."],
    "nb_power": ["def __pow__(self, other: Any, /) -> Any: ..."],
    "nb_negative": ["def __neg__(self) -> Self: ..."],
    "nb_positive": ["def __pos__(self) -> Self: ..."],
    "nb_absolute": ["def __abs__(self) -> Any: ..."],
    "nb_invert": ["def __invert__(self) -> Self: ..."],
    "nb_bool": ["def __bool__(self) -> bool: ..."],
    "nb_int": ["def __int__(self) -> int: ..."],
    "nb_float": ["def __float__(self) -> float: ..."],
    "nb_index": ["def __index__(self) -> int: ..."],
    "nb_and": ["def __and__(self, other: Any, /) -> Any: ..."],
    "nb_or": ["def __or__(self, other: Any, /) -> Any: ..."],
    "nb_xor": ["def __xor__(self, other: Any, /) -> Any: ..."],
    "nb_inplace_add": ["def __iadd__(self, other: Any, /) -> Self: ..."],
    "nb_inplace_subtract": ["def __isub__(self, other: Any, /) -> Self: ..."],
    "nb_inplace_multiply": ["def __imul__(self, other: Any, /) -> Self: ..."],
    "nb_inplace_matrix_multiply": ["def __imatmul__(self, other: Any, /) -> Self: ..."],
    "nb_inplace_true_divide": ["def __itruediv__(self, other: Any, /) -> Self: ..."],
    "tp_richcompare": [
        "def __eq__(self, other: object, /) -> bool: ...",
        "def __ne__(self, other: object, /) -> bool: ...",
        "def __lt__(self, other: Any, /) -> bool: ...",
        "def __le__(self, other: Any, /) -> bool: ...",
        "def __gt__(self, other: Any, /) -> bool: ...",
        "def __ge__(self, other: Any, /) -> bool: ...",
    ],
    "tp_hash": ["def __hash__(self) -> int: ..."],
    "tp_getattro": ["def __getattr__(self, name: str, /) -> Any: ..."],
}
PRELUDE = (
    "from __future__ import annotations\n\n"
    "from collections.abc import Callable, Iterator, Sequence\n"
    "from typing import Any, Generic, Literal, Self, TypeVar, overload\n"
)
# The C type names bpy.types re-exports (``python/intern/bpy_rna.cc``): their Python spelling.
BPY_TYPES_C = {
    "bpy_struct",
    "bpy_prop",
    "bpy_prop_array",
    "bpy_prop_collection",
    "bpy_prop_collection_idprop",
    "bpy_func",
}


def py_ident(name: str) -> str:
    return name + "_" if keyword.iskeyword(name) else name


def literal_default(source: str) -> str:
    """A default from a docstring or C source as written when it is a short Python literal, else ``...``."""
    try:
        ast.literal_eval(source)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return "..."
    return source if len(source) <= 40 else "..."


def literal(values: list[str]) -> str:
    return "Literal[" + ", ".join(repr(v) for v in values) + "]"


@dataclass
class ClassOut:
    name: str
    bases: list[str] = field(default_factory=list)
    body: dict[str, list[str]] = field(default_factory=dict)  # member -> lines (unindented)
    doc: str = ""

    def add(self, name: str, lines: list[str] | str, replace: bool = False) -> None:
        if isinstance(lines, str):
            lines = [lines]
        if replace or name not in self.body:
            self.body[name] = lines
        elif name.startswith("__"):
            pass


@dataclass
class ModuleOut:
    name: str
    classes: dict[str, ClassOut] = field(default_factory=dict)
    blocks: dict[str, list[str]] = field(default_factory=dict)  # top-level name -> lines
    imports: set[str] = field(default_factory=set)
    order: list[str] = field(default_factory=list)

    def cls(self, name: str) -> ClassOut:
        if name not in self.classes:
            self.classes[name] = ClassOut(name)
            self.order.append(name)
        return self.classes[name]

    def block(self, name: str, lines: list[str] | str) -> None:
        if isinstance(lines, str):
            lines = [lines]
        if name not in self.blocks and name not in self.classes:
            self.blocks[name] = lines
            self.order.append(name)


class Renderer:
    def __init__(self, model: SourceModel) -> None:
        self.model = model
        self.modules: dict[str, ModuleOut] = {}
        self.structs = {s.identifier: s for s in model.structs}
        # collection wrapper struct -> item struct
        self.wrapper_items: dict[str, str] = {}
        for s in model.structs:
            for p in s.properties:
                if p.type == "collection" and p.collection_srna:
                    self.wrapper_items.setdefault(p.collection_srna, p.struct_type or "bpy_struct")

    def mod(self, name: str) -> ModuleOut:
        if name not in self.modules:
            self.modules[name] = ModuleOut(name)
            parts = name.split(".")
            for i in range(1, len(parts)):
                self.mod(".".join(parts[:i]))
        return self.modules[name]

    # ----------------------------------------------------------------------------------------------------------------
    # Types

    def ref(self, qualified: str, current: str) -> str:
        """A reference to ``qualified`` (``bpy.types.Object``, ``mathutils.Vector``) from module ``current``."""
        module, _, name = qualified.rpartition(".")
        if not module or module == current:
            return name or qualified
        self.mod(current).imports.add(module.split(".")[0] if module.split(".")[0] == module else module)
        return qualified

    def struct_ref(self, identifier: str, current: str) -> str:
        if not identifier:
            return self.ref("bpy.types.bpy_struct", current)
        if "." in identifier:  # a Python class (``cycles.properties.CyclesRenderSettings``)
            return self.ref(identifier, current)
        return self.ref(f"bpy.types.{identifier}", current)

    def prop_type(self, p: RnaProperty, current: str, *, param: bool = False) -> str:
        t = p.type
        if t == "string" and p.subtype == "byte_string":
            return "bytes"
        if t in SCALAR and not p.array and not p.dynamic_array:
            return SCALAR[t]
        if t in {"boolean", "int", "float"}:
            if t == "float" and p.subtype in MATH_SUBTYPES:
                by_length = MATH_SUBTYPES[p.subtype]
                total = 1
                for n in p.array:
                    total *= n
                dims_ok = len(p.array) <= 1 or (len(p.array) == 2 and p.subtype == "matrix")
                cls = by_length.get(total) if dims_ok else None
                if cls is None and p.dynamic_array and p.subtype == "matrix":
                    cls = "mathutils.Matrix"
                if cls:
                    text = self.ref(cls, current)
                    if param:  # pyrna_py_to_array takes any sequence of the right length
                        nested = "Sequence[Sequence[float]]" if cls == "mathutils.Matrix" else "Sequence[float]"
                        text = f"{text} | {nested}"
                    return text
            text = SCALAR[t]
            for _ in p.array or [0]:
                text = f"Sequence[{text}]" if param else f"{self.ref('bpy.types.bpy_prop_array', current)}[{text}]"
            return text
        if t == "string":
            return "str"
        if t == "enum":
            identifiers = [i.identifier for i in p.items if i.identifier]
            if not identifiers and p.items_name and p.items_name in self.model.enum_items:
                identifiers = [i.identifier for i in self.model.enum_items[p.items_name] if i.identifier]
            if p.itemf or not identifiers:
                base = "str"
            else:
                base = literal(identifiers)
            return f"set[{base}]" if p.enum_flag else base
        if t == "pointer":
            target = self.struct_ref(p.struct_type, current)
            if p.never_null:  # a required parameter still takes None unless PROP_NEVER_NULL (pyrna_py_to_prop)
                return target
            return f"{target} | None"
        if t == "collection":
            item = self.struct_ref(p.struct_type, current)
            if p.collection_srna:
                return self.struct_ref(p.collection_srna, current)
            return f"{self.ref('bpy.types.bpy_prop_collection', current)}[{item}]"
        return "Any"

    def default_text(self, p: RnaProperty) -> str:
        """The default as Python source when it is a plain literal (``'TOGGLE'``, ``False``, ``(0.0, 0.0)``)."""
        value = p.default
        if isinstance(value, list) and p.type == "enum":
            return "{" + ", ".join(repr(v) for v in value) + "}" if value else "set()"
        if isinstance(value, list):
            if len(p.array) == 2 and len(value) == p.array[0] * p.array[1]:
                rows, cols = p.array
                value = tuple(tuple(value[r * cols : (r + 1) * cols]) for r in range(rows))
            else:
                value = tuple(value)
        if isinstance(value, (bool, int, float, str, tuple)) and not (isinstance(value, float) and math.isnan(value)):
            text = repr(value)
            if len(text) <= 80:
                return text
        return "..."

    # ----------------------------------------------------------------------------------------------------------------
    # RNA

    def render_structs(self) -> None:
        m = self.mod("bpy.types")
        for s in self.model.structs:
            c = m.cls(s.identifier)
            if s.identifier in self.wrapper_items:
                item = self.wrapper_items[s.identifier]
                c.bases = [f"bpy_prop_collection[{item}]"]
            else:
                c.bases = [s.base or "bpy_struct"]
            c.doc = s.description
            for p in s.properties:
                if p.identifier == "rna_type" and s.base:
                    continue  # every struct's builtin ``rna_type``, declared once on its root
                self.render_property(c, p, "bpy.types")
            for f in s.functions:
                self.render_function(c, f, "bpy.types")

    def render_property(self, c: ClassOut, p: RnaProperty, current: str) -> None:
        name = p.identifier
        if not name.isidentifier() or keyword.iskeyword(name):
            return
        t = self.prop_type(p, current)
        if p.readonly:
            c.add(name, ["@property", f"def {name}(self) -> {t}: ..."])
        else:
            c.add(name, f"{name}: {t}")

    def render_function(self, c: ClassOut, f: RnaFunction, current: str) -> None:
        name = f.identifier
        if not name.isidentifier():
            return
        outputs = [p for p in f.parameters if "output" in p.parameter_flags or p.identifier == f.returns]
        inputs = [p for p in f.parameters if p not in outputs]
        params = []
        decorator = []
        if "no_self" in f.flags and "use_self_type" in f.flags:
            decorator, params = ["@classmethod"], ["cls"]
        elif "no_self" in f.flags:
            decorator = ["@staticmethod"]
        else:
            params = ["self"]
        # pyrna_func_call takes the parameters in declaration order; a required one after an optional one can only be
        # given by keyword, so it and the rest become keyword-only.
        seen_optional = keyword_only = False
        for p in inputs:
            text = f"{py_ident(p.identifier)}: {self.prop_type(p, current, param=True)}"
            if "required" in p.parameter_flags:
                if seen_optional and not keyword_only:
                    params.append("*")
                    keyword_only = True
            else:
                seen_optional = True
                text += f" = {self.default_text(p)}"
            params.append(text)
        if not outputs:
            ret = "None"
        elif len(outputs) == 1:
            ret = self.prop_type(outputs[0], current)
        else:
            ret = "tuple[" + ", ".join(self.prop_type(p, current) for p in outputs) + "]"
        c.add(name, [*decorator, f"def {name}({', '.join(params)}) -> {ret}: ..."])

    def render_context(self) -> None:
        if not self.model.context:
            return
        c = self.mod("bpy.types").cls("Context")
        for member in self.model.context:
            if not member.name.isidentifier():
                continue
            types = []
            is_coll = any(coll for _, coll in member.types)
            for identifier, _coll in member.types:
                if identifier:
                    types.append(identifier)
            if not types:
                t = {"string": "str", "int": "int", "float": "float", "bool": "bool"}.get(member.kind, "Any")
            else:
                t = " | ".join(dict.fromkeys(types))
            if is_coll:
                t = f"Sequence[{t}]"
            elif member.nullable and types:
                t = f"{t} | None"
            c.add(member.name, ["@property", f"def {member.name}(self) -> {t}: ..."], replace=False)

    def render_operators(self) -> None:
        for op in self.model.operators:
            module, func = op.python_name
            if not func.isidentifier() or not module.isidentifier():
                continue
            mod_name = f"bpy.ops.{module}"
            self.render_operator(mod_name, func, op.properties)

    def render_operator(self, mod_name: str, func: str, properties: list[RnaProperty]) -> None:
        m = self.mod(mod_name)
        params = ["execution_context: int | str | None = None", "undo: bool | None = None", "/", "*"]
        for p in properties:
            if not p.identifier.isidentifier() or keyword.iskeyword(p.identifier):  # PROP_HIDDEN ones too
                continue
            params.append(f"{p.identifier}: {self.prop_type(p, mod_name, param=True)} = {self.default_text(p)}")
        if params[-1] == "*":
            params.pop()
        m.block(func, f"def {func}({', '.join(params)}) -> {OPERATOR_RETURN}: ...")

    # ----------------------------------------------------------------------------------------------------------------
    # Python C API

    def type_module(self) -> dict[str, tuple[str, str]]:
        """PyTypeObject variable -> (module, class name)."""
        where: dict[str, tuple[str, str]] = {}
        for mod in self.model.py_modules:
            for attr, c_name in mod.types.items():
                where.setdefault(c_name, (mod.name, attr))
        for t in self.model.py_types:
            if t.c_name in where:
                continue
            module, _, name = t.name.rpartition(".")
            if t.name in BPY_TYPES_C or name in BPY_TYPES_C:
                where[t.c_name] = ("bpy.types", name or t.name)
            elif module:
                where[t.c_name] = (module, name)
        return where

    def signature_text(
        self, sig: PySignature | None, method: PyMethod | None, *, first: str | None, current: str
    ) -> str:
        flags = set(method.flags) if method else set()
        params: list[str] = [first] if first else []
        if sig is None:
            if "noargs" in flags:
                pass
            elif "o" in flags:
                params += ["arg: Any", "/"]
            elif "keywords" in flags:
                params += ["*args: Any", "**kwargs: Any"]
            else:
                params += ["*args: Any"]
            return f"({', '.join(params)}) -> Any"
        positional_only = (
            method is not None
            and "keywords" not in flags
            and ("varargs" in flags or "o" in flags or "fastcall" in flags)
        )
        rendered = []
        saw_kwonly = False
        last_posonly = max((i for i, p in enumerate(sig.params) if p.kind == "positional_only"), default=-1)
        for index, p in enumerate(sig.params):
            t = p.type or "Any"
            if p.kind == "var_positional":
                rendered.append(f"*{p.name}: {t}")
                saw_kwonly = True
                continue
            if p.kind == "var_keyword":
                rendered.append(f"**{p.name}: {t}")
                continue
            if p.kind == "keyword_only" and not saw_kwonly:
                rendered.append("*")
                saw_kwonly = True
            text = f"{py_ident(p.name)}: {t}"
            if p.default is not None:
                text += f" = {literal_default(p.default)}"
            rendered.append(text)
            if index == last_posonly and not positional_only:
                rendered.append("/")
        if positional_only and rendered and not saw_kwonly:
            rendered.append("/")
        elif positional_only and not rendered and first:
            pass
        params += rendered
        if first and positional_only and not rendered:
            pass
        return f"({', '.join(params)}) -> {sig.returns or 'Any'}"

    def render_py_types(self) -> None:
        where = self.type_module()
        for t in self.model.py_types:
            if t.c_name not in where:
                continue
            module, name = where[t.c_name]
            if not name.isidentifier():
                continue
            m = self.mod(module)
            c = m.cls(name)
            if t.base and t.base in where:
                bmod, bname = where[t.base]
                c.bases = [bname if bmod == module else self.ref(f"{bmod}.{bname}", module)]
            if name == "bpy_prop_collection":
                c.bases.append("Generic[_T]")
                m.block("_T", "_T = TypeVar('_T')")
            c.doc = t.doc.split("\n")[0][:200]
            if t.constructor is not None:
                c.add(
                    "__init__",
                    f"def __init__{self.signature_text(t.constructor, None, first='self', current=module).replace(' -> Any', ' -> None')}: ...",
                )
            for meth in t.methods:
                if not meth.name.isidentifier():
                    continue
                decorator = []
                first = "self"
                if "class" in meth.flags:
                    decorator, first = ["@classmethod"], "cls"
                elif "static" in meth.flags:
                    decorator, first = ["@staticmethod"], None
                c.add(
                    meth.name,
                    [
                        *decorator,
                        f"def {meth.name}{self.signature_text(meth.signature, meth, first=first, current=module)}: ...",
                    ],
                )
            for gs in t.getsets:
                if not gs.name.isidentifier():
                    continue
                typ = gs.type or "Any"
                lines = ["@property", f"def {gs.name}(self) -> {typ}: ..."]
                if gs.setter:
                    lines += [f"@{gs.name}.setter", f"def {gs.name}(self, value: {typ}) -> None: ..."]
                c.add(gs.name, lines)
            for mem in t.members:
                if mem.name.isidentifier():
                    c.add(mem.name, f"{mem.name}: Any")
            for slot in t.slots:
                for line in SLOT_DUNDERS.get(slot, []):
                    dunder = line.split("(")[0].removeprefix("def ")
                    if slot == "tp_hash" and t.slots[slot] == "PyObject_HashNotImplemented":
                        c.add("__hash__", "__hash__: None")
                        continue
                    c.add(dunder, line)

    def render_py_modules(self) -> None:
        where = self.type_module()
        for mod in self.model.py_modules:
            if not mod.name or not all(part.isidentifier() for part in mod.name.split(".")):
                continue
            m = self.mod(mod.name)
            for meth in mod.methods:
                if not meth.name.isidentifier():
                    continue
                m.block(
                    meth.name,
                    f"def {meth.name}{self.signature_text(meth.signature, meth, first=None, current=mod.name)}: ...",
                )
            for attr, typ in mod.constants.items():
                if attr.isidentifier():
                    m.block(attr, f"{attr}: {typ or 'Any'}")
            for attr, c_name in mod.types.items():
                if c_name in where and where[c_name] != (mod.name, attr):
                    tmod, tname = where[c_name]
                    if attr.isidentifier():
                        m.block(attr, f"{attr} = {self.ref(f'{tmod}.{tname}', mod.name)}")
            for attr, sub in mod.submodules.items():
                if sub != f"{mod.name}.{attr}" and attr.isidentifier() and sub:
                    self.mod(sub)
                    m.imports.add(sub)

    # ----------------------------------------------------------------------------------------------------------------
    # Nodes and bmesh

    def render_nodes(self) -> None:
        m = self.mod("bpy.types")
        for node in self.model.nodes:
            if not node.idname.isidentifier():
                continue
            for side, sockets in (("inputs", node.inputs), ("outputs", node.outputs)):
                if not sockets:
                    continue
                view = f"_{node.idname}_{side}"
                c = m.cls(view)
                c.bases = ["NodeInputs" if side == "inputs" else "NodeOutputs"]
                overloads = []
                for sock in sockets:
                    if sock.dynamic:
                        continue
                    stype = DECL_SOCKETS.get(sock.type, "NodeSocket")
                    overloads += ["@overload", f"def __getitem__(self, key: Literal[{sock.name!r}], /) -> {stype}: ..."]
                if overloads:
                    overloads += ["@overload", "def __getitem__(self, key: str | int, /) -> NodeSocket: ..."]
                    c.add("__getitem__", overloads)
                nc = m.cls(node.idname)
                if not nc.bases:
                    nc.bases = ["Node"]
                nc.add(side, ["@property", f"def {side}(self) -> {view}: ..."], replace=True)

    def render_bmesh_ops(self) -> None:
        if not self.model.bmesh_ops:
            return
        m = self.mod("bmesh.ops")
        elem = {"vert": "bmesh.types.BMVert", "edge": "bmesh.types.BMEdge", "face": "bmesh.types.BMFace"}
        for op in self.model.bmesh_ops:
            if not op.name.isidentifier():
                continue
            params = [f"bm: {self.ref('bmesh.types.BMesh', 'bmesh.ops')}", "/", "*"]
            for slot in op.inputs:
                if not slot.name.isidentifier():
                    continue
                if slot.items:
                    t = literal(slot.items)
                    if "flag" in slot.subtype.split("|"):
                        t = f"set[{t}]"
                elif slot.type in BMO_SLOT_TYPES:
                    t = (
                        self.ref(BMO_SLOT_TYPES[slot.type], "bmesh.ops")
                        if "." in BMO_SLOT_TYPES[slot.type]
                        else BMO_SLOT_TYPES[slot.type]
                    )
                elif slot.type == "elem_buf":
                    kinds = [elem[k] for k in ("vert", "edge", "face") if k in slot.subtype]
                    for k in kinds:
                        self.ref(k, "bmesh.ops")
                    joined = " | ".join(kinds) or "Any"
                    t = joined if "single" in slot.subtype.split("|") else f"list[{joined}]"
                elif slot.type == "mapping":
                    t = "dict[Any, Any]"
                elif slot.type == "ptr":
                    t = {
                        "bmesh": "bmesh.types.BMesh",
                        "scene": "bpy.types.Scene",
                        "object": "bpy.types.Object",
                        "mesh": "bpy.types.Mesh",
                    }.get(slot.subtype, "Any")
                    if "." in t:
                        t = self.ref(t, "bmesh.ops")
                else:
                    t = "Any"
                params.append(f"{slot.name}: {t} = ...")
            if params[-1] == "*":
                params.pop()
            m.block(op.name, f"def {op.name}({', '.join(params)}) -> dict[str, Any]: ...")

    # ----------------------------------------------------------------------------------------------------------------
    # Python modules (``scripts/``)

    def render_python(self) -> None:
        bpy_types_extra = {}
        for src in self.model.python:
            if src.name == "_bpy_types":
                for cls in src.classes:
                    bpy_types_extra[cls.name] = cls
        rendered = set(self.modules)
        for src in self.model.python:
            if src.name in rendered:
                self.merge_python(src.name, src.stub)
            else:
                m = self.mod(src.name)
                m.blocks["__source__"] = [src.stub]
                m.order.append("__source__")
        # Python members of RNA classes (``_bpy_types``: ``Object.children``, ``bpy_struct`` helpers).
        types = self.mod("bpy.types")
        for name, cls in bpy_types_extra.items():
            if name not in types.classes:
                continue
            c = types.classes[name]
            for member in cls.members:
                if member.name.startswith("__") and member.name not in {"__getitem__", "__iter__", "__len__"}:
                    continue
                if member.kind == "property":
                    c.add(member.name, ["@property", f"def {member.name}(self) -> {member.annotation or 'Any'}: ..."])
                elif member.kind in {"method", "classmethod", "staticmethod"}:
                    dec = [] if member.kind == "method" else [f"@{member.kind}"]
                    c.add(member.name, [*dec, f"def {member.name}{member.signature}: ..."])
                elif member.annotation:
                    c.add(member.name, f"{member.name}: {member.annotation}")
        # Registered Python classes are reachable as ``bpy.types.<name>``.
        for src in self.model.python:
            if src.group not in {"startup", "modules"} or src.name.startswith("_bpy_types"):
                continue
            for cls in src.classes:
                if cls.name in types.classes or not cls.bases:
                    continue
                if any(b.split(".")[-1] in REGISTRABLE for b in cls.bases):
                    types.block(cls.name, f"from {src.name} import {cls.name} as {cls.name}")
        # Python operators.
        for src in self.model.python:
            for cls in src.classes:
                if (
                    cls.bl_idname
                    and "." in cls.bl_idname
                    and any(b.split(".")[-1] in {"Operator", "Macro"} for b in cls.bases)
                ):
                    module, _, func = cls.bl_idname.partition(".")
                    if module.isidentifier() and func.isidentifier():
                        self.render_operator(f"bpy.ops.{module}", func, cls.properties)
        # Registered properties.
        for reg in self.model.registrations:
            if reg.struct in types.classes and reg.property.identifier.isidentifier():
                prop = reg.property
                t = self.prop_type(prop, "bpy.types")
                if prop.type == "pointer" and prop.struct_type and "." in prop.struct_type:
                    t = prop.struct_type
                types.classes[reg.struct].add(prop.identifier, f"{prop.identifier}: {t}")

    def merge_python(self, module: str, stub: str) -> None:
        m = self.mod(module)
        try:
            tree = ast.parse(stub)
        except SyntaxError:
            return
        lines = stub.splitlines()
        for node in tree.body:
            text = "\n".join(lines[node.lineno - 1 : node.end_lineno])
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                m.blocks.setdefault("__imports_py__", []).append(text)
                if "__imports_py__" not in m.order:
                    m.order.insert(0, "__imports_py__")
                continue
            name = getattr(node, "name", None)
            if name is None and isinstance(node, (ast.AnnAssign, ast.Assign)):
                target = node.target if isinstance(node, ast.AnnAssign) else node.targets[0]
                name = target.id if isinstance(target, ast.Name) else None
            if name and name not in m.blocks and name not in m.classes:
                m.block(name, text)

    # ----------------------------------------------------------------------------------------------------------------

    def render(self) -> dict[str, str]:
        self.mod("bpy.types").cls("bpy_struct")
        self.render_py_types()
        self.render_py_modules()
        self.render_structs()
        self.render_context()
        self.render_operators()
        self.render_nodes()
        self.render_bmesh_ops()
        self.render_python()
        self.mod("bpy").block("context", "context: bpy.types.Context")
        self.mod("bpy").block("data", "data: bpy.types.BlendData")
        self.mod("bpy").imports.add("bpy.types")
        return {name: self.module_text(m) for name, m in sorted(self.modules.items())}

    def module_text(self, m: ModuleOut) -> str:
        out = [PRELUDE]
        for imp in sorted(m.imports):
            if imp != m.name and not imp.startswith(m.name + ".__"):
                out.append(f"import {imp}\n")
        children = sorted(n for n in self.modules if n.rpartition(".")[0] == m.name)
        for child in children:
            out.append(f"from . import {child.rpartition('.')[2]} as {child.rpartition('.')[2]}\n")
        out.append("\n")
        for name in m.order:
            if name in m.classes:
                out.append(self.class_text(m.classes[name]))
            else:
                out.append("\n".join(m.blocks[name]) + "\n")
        return "".join(out)

    def class_text(self, c: ClassOut) -> str:
        head = f"class {c.name}({', '.join(c.bases)}):" if c.bases else f"class {c.name}:"
        lines = ["", head]
        if c.doc:
            doc = c.doc.replace("\\", "\\\\").replace('"""', "'''").strip()
            lines.append(f'    """{doc}"""')
        if not c.body and not c.doc:
            lines.append("    ...")
        for member_lines in c.body.values():
            for line in member_lines:
                lines.append("    " + line)
        return "\n".join(lines) + "\n"


REGISTRABLE = {
    "Panel",
    "Menu",
    "Header",
    "Operator",
    "Macro",
    "UIList",
    "PropertyGroup",
    "AddonPreferences",
    "RenderEngine",
    "Node",
    "NodeTree",
    "NodeSocket",
    "Gizmo",
    "GizmoGroup",
    "KeyingSetInfo",
    "AssetShelf",
    "FileHandler",
}


def write_stubs(model: SourceModel, out: Path) -> list[Path]:
    """Render ``model`` into ``out`` (cleared first); the files written."""
    import shutil

    shutil.rmtree(out, ignore_errors=True)
    texts = Renderer(model).render()
    written = []
    for module, text in texts.items():
        path = out.joinpath(*module.split(".")) / "__init__.pyi"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written
