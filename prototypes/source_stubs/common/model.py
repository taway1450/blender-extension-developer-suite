"""The facts a source reader extracts from Blender's source, in one shape for all three tools.

Each prototype (``regex/``, ``libclang/``, ``makesrna/``) fills a ``SourceModel`` its own way; ``render.py`` turns
any ``SourceModel`` into ``.pyi`` stubs, so two prototypes' stubs differ only by what they extracted. Every fact
records where it was read (``src``: ``path:line`` relative to the source tree, or a makesrna note) so a reader can
check it.

The RNA part mirrors what ``RNA_def_*`` defines (``source/blender/makesrna/RNA_define.hh``); names follow RNA's
own (``PROP_FLOAT``, ``PROP_COLOR``, ``PARM_REQUIRED``) lowercased and without their prefix.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints

# --------------------------------------------------------------------------------------------------------------------
# RNA


@dataclass
class EnumItem:
    identifier: str
    name: str = ""
    description: str = ""
    value: int | None = None
    icon: str = ""


@dataclass
class RnaProperty:
    """A property of a struct, a parameter of an RNA function, or an operator property."""

    identifier: str
    # boolean, int, float, string, enum, pointer, collection
    type: str
    subtype: str = "none"  # color, translation, matrix, filepath, ... (``PROP_*`` subtype, lowercased)
    unit: str = "none"
    name: str = ""  # UI name
    description: str = ""
    # Fixed array dimensions (``RNA_def_property_array`` / ``multi_array``): [] for a scalar.
    array: list[int] = field(default_factory=list)
    dynamic_array: bool = False  # array length from a function (``RNA_def_property_dynamic_array_funcs``)
    default: Any = None  # Python literal value, when known
    hard_min: float | None = None
    hard_max: float | None = None
    soft_min: float | None = None
    soft_max: float | None = None
    max_length: int | None = None  # string
    # Enum
    items: list[EnumItem] = field(default_factory=list)
    items_name: str = ""  # a shared item array (``rna_enum_object_type_items``) when known
    enum_flag: bool = False  # PROP_ENUM_FLAG: a set of identifiers
    itemf: str = ""  # the item function (dynamic enum) when set
    # Pointer / collection
    struct_type: str = ""  # pointed-to struct identifier (``RNA_def_property_struct_type``)
    collection_srna: str = ""  # the wrapper struct of a collection (``RNA_def_property_srna``)
    typef: str = ""  # pointer type function (the type depends on the data: ``rna_Object_data_typef``)
    poll: str = ""
    # Flags
    readonly: bool = False  # PROP_EDITABLE cleared (and no editable function)
    editable_func: str = ""
    never_null: bool = False  # PROP_NEVER_NULL
    flags: list[str] = field(default_factory=list)  # all PROP_* flags set, lowercased (``animatable``, ...)
    parameter_flags: list[str] = field(default_factory=list)  # required, output, rnaptr, pyfunc_optional, ...
    getter: str = ""
    setter: str = ""
    deprecated: bool = False
    src: str = ""


@dataclass
class RnaFunction:
    identifier: str
    description: str = ""
    # FUNC_* flags lowercased: no_self, use_self_type, register, register_optional, use_context, use_reports, ...
    flags: list[str] = field(default_factory=list)
    c_function: str = ""
    parameters: list[RnaProperty] = field(default_factory=list)
    # Identifier of the parameter set with ``RNA_def_function_return`` (outputs are parameters flagged ``output``).
    returns: str = ""
    src: str = ""


@dataclass
class RnaStruct:
    identifier: str
    base: str = ""  # "" for a struct without base (bpy_struct)
    name: str = ""
    description: str = ""
    nested: str = ""  # ``RNA_def_struct_nested``: the struct this one is nested in (its ``id_data`` owner chain)
    name_property: str = ""
    refine: str = ""  # refine function name
    path_func: str = ""
    register: str = ""  # register function (a Python-subclassable struct)
    idprops: bool = False  # ``RNA_def_struct_idprops_func``: supports custom properties
    flags: list[str] = field(default_factory=list)  # STRUCT_* lowercased (id, undo, ...)
    dna: str = ""
    properties: list[RnaProperty] = field(default_factory=list)
    functions: list[RnaFunction] = field(default_factory=list)
    src: str = ""


# --------------------------------------------------------------------------------------------------------------------
# Operators defined in C (``wmOperatorType``)


@dataclass
class Operator:
    idname: str  # "OBJECT_OT_select_all"
    name: str = ""
    description: str = ""
    flags: list[str] = field(default_factory=list)  # OPTYPE_* lowercased: register, undo, internal, ...
    properties: list[RnaProperty] = field(default_factory=list)
    callbacks: list[str] = field(default_factory=list)  # exec, invoke, modal, poll, ui, ... (those set)
    src: str = ""

    @property
    def python_name(self) -> tuple[str, str]:
        """``OBJECT_OT_select_all`` -> (``object``, ``select_all``)."""
        module, _, func = self.idname.partition("_OT_")
        return module.lower(), func


# --------------------------------------------------------------------------------------------------------------------
# The Python C API (``PyTypeObject``, ``PyMethodDef``, ``PyGetSetDef``, ``PyMemberDef``, ``PyModuleDef``)


@dataclass
class PyParam:
    name: str
    type: str = ""  # Python syntax
    default: str | None = None  # source text; None: required
    kind: str = "normal"  # positional_only, normal, keyword_only, var_positional, var_keyword


@dataclass
class PySignature:
    """A signature read from a docstring (``.. method:: name(a, b=1)`` with its ``:type:`` / ``:rtype:`` fields)."""

    params: list[PyParam] = field(default_factory=list)
    returns: str = ""


@dataclass
class PyMethod:
    name: str
    c_function: str = ""
    # METH_* lowercased: noargs, o, varargs, keywords, fastcall, class, static, coexist
    flags: list[str] = field(default_factory=list)
    doc: str = ""
    signature: PySignature | None = None
    src: str = ""


@dataclass
class PyGetSet:
    name: str
    getter: str = ""
    setter: str = ""  # "" for read-only
    doc: str = ""
    type: str = ""  # from the docstring's ``:type:``
    src: str = ""


@dataclass
class PyMember:
    name: str
    type_code: str = ""  # T_INT, Py_T_OBJECT_EX, ...
    readonly: bool = False
    doc: str = ""
    src: str = ""


@dataclass
class PyType:
    c_name: str  # the PyTypeObject variable: ``vector_Type``
    name: str = ""  # tp_name: ``mathutils.Vector`` (or ``Vector``)
    doc: str = ""
    base: str = ""  # tp_base, as a PyTypeObject variable name
    # The slots set (``tp_iter``, ``sq_item``, ``mp_subscript``, ``nb_add``, ``tp_as_buffer``, ``tp_richcompare``, ...)
    slots: dict[str, str] = field(default_factory=dict)
    methods: list[PyMethod] = field(default_factory=list)
    getsets: list[PyGetSet] = field(default_factory=list)
    members: list[PyMember] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)  # Py_TPFLAGS_* (BASETYPE, ...)
    constructor: PySignature | None = None
    src: str = ""


@dataclass
class PyModule:
    name: str  # m_name: ``mathutils``, ``bpy.app`` (submodules are often named by their parent)
    c_name: str = ""  # the PyModuleDef variable
    doc: str = ""
    methods: list[PyMethod] = field(default_factory=list)
    # Names added to the module: attribute -> PyTypeObject variable / submodule / constant description
    types: dict[str, str] = field(default_factory=dict)
    submodules: dict[str, str] = field(default_factory=dict)  # attribute -> module name
    constants: dict[str, str] = field(default_factory=dict)  # attribute -> Python type (int, str, ...)
    src: str = ""


# --------------------------------------------------------------------------------------------------------------------
# Other facts


@dataclass
class ContextMember:
    name: str
    # (RNA struct identifier, is_collection) pairs the callbacks set; "" type for a non-RNA value
    types: list[tuple[str, bool]] = field(default_factory=list)
    nullable: bool = True  # every pointer member can be missing in some context
    kind: str = "pointer"  # pointer, collection, property, string, int, ...
    editors: list[str] = field(default_factory=list)  # files / editors that set it
    src: str = ""


@dataclass
class NodeSocket:
    name: str
    type: str  # decl type: Float, Vector, Color, Shader, Geometry, ...
    identifier: str = ""
    subtype: str = ""
    dynamic: bool = False  # declared in a loop, a condition or a panel the reader couldn't follow
    src: str = ""


@dataclass
class NodeDecl:
    idname: str  # "ShaderNodeBsdfPrincipled"
    inputs: list[NodeSocket] = field(default_factory=list)
    outputs: list[NodeSocket] = field(default_factory=list)
    src: str = ""


@dataclass
class BmeshSlot:
    name: str
    type: str  # BMO_OP_SLOT_* lowercased: bool, int, flt, ptr, mat, vec, elem_buf, mapping
    subtype: str = ""  # element types (vert|edge|face), map value type, pointer type
    doc: str = ""


@dataclass
class BmeshOp:
    name: str
    doc: str = ""
    inputs: list[BmeshSlot] = field(default_factory=list)
    outputs: list[BmeshSlot] = field(default_factory=list)
    src: str = ""


@dataclass
class PyClassMember:
    """A member of a Python class read with ``ast`` (``scripts/``)."""

    name: str
    kind: str  # attribute, method, classmethod, staticmethod, property
    annotation: str = ""  # an attribute's annotation / a property's return annotation
    signature: str = ""  # ``(self, x: int = ...) -> bool`` for a method
    value: str = ""  # an unannotated attribute's value source (for its type)
    src: str = ""


@dataclass
class PyClass:
    module: str
    name: str
    bases: list[str] = field(default_factory=list)  # as written, resolved to dotted names where imported
    members: list[PyClassMember] = field(default_factory=list)
    doc: str = ""
    # For a registrable class: its bl_idname / bl_label / properties (annotations calling ``bpy.props``)
    bl_idname: str = ""
    properties: list[RnaProperty] = field(default_factory=list)
    src: str = ""


@dataclass
class Registration:
    """``bpy.types.Scene.my_prop = PointerProperty(type=MySettings)`` in a Python module."""

    struct: str  # bpy.types struct identifier
    property: RnaProperty
    module: str = ""
    src: str = ""


@dataclass
class PyModuleSource:
    """A Python module of ``scripts/`` read with ``ast``: its stub text and the facts it registers."""

    name: str
    path: str  # relative to the source tree
    stub: str  # the rendered ``.pyi`` text
    classes: list[PyClass] = field(default_factory=list)
    package: bool = False
    group: str = ""  # modules, startup, addons_core, cycles


# --------------------------------------------------------------------------------------------------------------------


@dataclass
class Coverage:
    """What one prototype read, per area: counts, and what it could not reach."""

    counts: dict[str, int] = field(default_factory=dict)
    unreachable: dict[str, str] = field(default_factory=dict)  # area -> why
    warnings: list[str] = field(default_factory=list)
    seconds: dict[str, float] = field(default_factory=dict)


@dataclass
class SourceModel:
    tool: str  # regex, libclang, makesrna
    source: str = ""  # source tree path
    commit: str = ""
    structs: list[RnaStruct] = field(default_factory=list)
    operators: list[Operator] = field(default_factory=list)
    py_types: list[PyType] = field(default_factory=list)
    py_modules: list[PyModule] = field(default_factory=list)
    context: list[ContextMember] = field(default_factory=list)
    nodes: list[NodeDecl] = field(default_factory=list)
    bmesh_ops: list[BmeshOp] = field(default_factory=list)
    # Shared item arrays: ``rna_enum_object_type_items`` -> items (``RNA_enum_items.hh`` / ``rna_*.cc``)
    enum_items: dict[str, list[EnumItem]] = field(default_factory=dict)
    python: list[PyModuleSource] = field(default_factory=list)
    registrations: list[Registration] = field(default_factory=list)
    coverage: Coverage = field(default_factory=Coverage)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=1, default=_json_default), encoding="utf-8")

    @classmethod
    def read(cls, path: Path) -> SourceModel:
        return from_dict(cls, json.loads(path.read_text(encoding="utf-8")))


def _json_default(value: Any) -> Any:
    if isinstance(value, (set, frozenset)):
        return sorted(value, key=repr)
    if isinstance(value, bytes):
        return value.decode("latin-1")
    return repr(value)


def from_dict(cls: type, data: Any) -> Any:
    """Rebuild a dataclass tree from ``asdict`` output."""
    hints = get_type_hints(cls)
    kwargs = {}
    for f in fields(cls):
        if f.name not in data:
            continue
        kwargs[f.name] = _convert(hints[f.name], data[f.name])
    return cls(**kwargs)


def _convert(tp: Any, value: Any) -> Any:
    if value is None:
        return None
    origin = get_origin(tp)
    if origin is list:
        (inner,) = get_args(tp)
        return [_convert(inner, v) for v in value]
    if origin is dict:
        _, inner = get_args(tp)
        return {k: _convert(inner, v) for k, v in value.items()}
    if origin is tuple:
        return tuple(value)
    if origin is not None:  # X | None
        for arg in get_args(tp):
            if arg is not type(None):
                return _convert(arg, value)
    if is_dataclass(tp):
        return from_dict(tp, value)
    return value
