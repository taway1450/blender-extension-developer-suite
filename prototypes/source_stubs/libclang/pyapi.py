"""The Python C API: ``PyTypeObject`` / ``PyMethodDef`` / ``PyGetSetDef`` / ``PyMemberDef`` / ``PyModuleDef`` globals,
and what each module init function adds to its module.

Initializers come from the lowering already mapped to field names: a positional ``PyTypeObject`` initializer is
mapped through ``PyTypeObject``'s own declaration (the ``/*tp_xxx*/`` comments are not trusted, so a wrong comment
cannot shift the slots), a designated one by its designators. ``PyDoc_STRVAR`` docstrings arrive as the
concatenated, macro-expanded value clang evaluated. Module init functions (any function calling
``PyModule_Create2`` / ``PyModule_New``) are run by the interpreter: ``PyModule_AddObject(mod, "geometry",
PyInit_mathutils_geometry())`` follows the call and gets the submodule; ``PyStructSequence`` types (``bpy.app``)
become modules whose attributes are the sequence fields plus the getsets/methods added to the type's dict.
"""

from __future__ import annotations

import re

from common.model import PyGetSet, PyMember, PyMethod, PyModule, PyType
from common.rstdoc import parse_directive, rst_type_to_python

from .interp import UNKNOWN, FuncRef, GlobalRef, Interp, Obj

METH_FLAGS = [
    (1, "varargs"),
    (2, "keywords"),
    (4, "noargs"),
    (8, "o"),
    (16, "class"),
    (32, "static"),
    (64, "coexist"),
    (128, "fastcall"),
    (512, "method"),
]
TPFLAGS = [
    (1 << 9, "METHOD_DESCRIPTOR"),
    (1 << 10, "BASETYPE"),
    (1 << 14, "HAVE_GC"),
    (1 << 12, "READY"),
    (1 << 20, "DISALLOW_INSTANTIATION"),
    (1 << 21, "IMMUTABLETYPE"),
    (1 << 3, "MANAGED_DICT"),
]
MEMBER_TYPES = {
    0: "T_SHORT",
    1: "T_INT",
    2: "T_LONG",
    3: "T_FLOAT",
    4: "T_DOUBLE",
    5: "T_STRING",
    6: "T_OBJECT",
    7: "T_CHAR",
    8: "T_BYTE",
    9: "T_UBYTE",
    10: "T_UINT",
    11: "T_USHORT",
    12: "T_ULONG",
    13: "T_STRING_INPLACE",
    14: "T_BOOL",
    16: "T_OBJECT_EX",
    17: "T_LONGLONG",
    18: "T_ULONGLONG",
    19: "T_PYSSIZET",
    20: "T_NONE",
}
SLOT_TABLES = ("tp_as_number", "tp_as_sequence", "tp_as_mapping", "tp_as_async")
_TYPE_FIELD = re.compile(r"^\s*:type:\s*(.+?)\s*$", re.MULTILINE)
VALUE_TYPES = {
    "PyLong_FromLong": "int",
    "PyLong_FromSsize_t": "int",
    "PyLong_FromUnsignedLong": "int",
    "PyLong_FromLongLong": "int",
    "PyUnicode_FromString": "str",
    "PyC_UnicodeFromBytes": "str",
    "PyUnicode_FromFormat": "str",
    "PyC_UnicodeFromStdStr": "str",
    "PyFloat_FromDouble": "float",
    "PyBool_FromLong": "bool",
    "PyBytes_FromString": "bytes",
    "PyTuple_New": "tuple[Any, ...]",
    "PyDict_New": "dict[str, Any]",
    "PyList_New": "list[Any]",
    "PyFrozenSet_New": "frozenset[str]",
    "PyC_Tuple_Pack_I32": "tuple[int, ...]",
    "PyC_Tuple_Pack_F32": "tuple[float, ...]",
    "PyC_FlagSet_AsString": "str",
    "PySet_New": "set[Any]",
}


def meth_flags(value) -> list[str]:
    if not isinstance(value, int):
        return []
    return [name for bit, name in METH_FLAGS if int(value) & bit]


def doc_type(doc: str) -> str:
    m = _TYPE_FIELD.search(doc or "")
    return rst_type_to_python(m.group(1)) if m else ""


def _s(v) -> str:
    return v if isinstance(v, str) else ""


class PyApi:
    def __init__(self, interp: Interp, model) -> None:
        self.i = interp
        self.model = model
        self.types: dict[str, PyType] = {}  # c_name -> PyType
        self.modules: dict[str, PyModule] = {}
        self.structseq: dict[str, dict] = {}  # type c_name -> desc
        self.extra: dict[str, dict] = {}  # type c_name -> {"getsets": [...], "methods": [...]}
        I = interp.intrinsics
        for name in (
            "PyModule_Create2",
            "PyModule_Create",
            "PyModule_New",
            "PyModule_AddObject",
            "PyModule_AddObjectRef",
            "PyModule_Add",
            "PyModule_AddType",
            "PyModule_AddIntConstant",
            "PyModule_AddStringConstant",
            "PyModule_GetDict",
            "PyDict_SetItemString",
            "PyDict_SetItem",
            "PyStructSequence_InitType",
            "PyStructSequence_InitType2",
            "PyStructSequence_New",
            "PyStructSequence_SetItem",
            "PyCFunction_New",
            "PyCFunction_NewEx",
            "PyCMethod_New",
            "PyDescr_NewGetSet",
            "PyDescr_NewMethod",
            "PyDescr_NewClassMethod",
            "PyType_Ready",
            "PyStructSequence_NewType",
            "PyType_FromSpec",
            "PyImport_AddModule",
        ):
            I[name] = getattr(self, name.replace("PyModule_Create2", "PyModule_Create"))
        for name, value_type in VALUE_TYPES.items():
            I[name] = self._value(value_type)
        interp.methods["member:dict"] = self._dict_member

    # ----------------------------------------------------------------------------------------------------------------
    def _value(self, typ: str):
        return lambda i, a, e, c: Obj("pyval", typ)

    def type_name(self, value) -> str:
        """The PyTypeObject global a value is (``&vector_Type`` evaluates to the global's initializer dict)."""
        if isinstance(value, dict):
            return self.i.global_names.get(id(value), "")
        if isinstance(value, GlobalRef):
            return value.name
        return ""

    def _dict_member(self, interp, base, name, e):
        if name == "tp_dict":  # ``BlenderAppType.tp_dict``: items set there become attributes of the type
            return Obj("tpdict", interp.global_names.get(id(base), ""))
        return UNKNOWN

    def module_obj(self, name: str, c_name: str = "", doc: str = "", src: str = "") -> Obj:
        mod = self.modules.get(name)
        if mod is None:
            mod = PyModule(name=name, c_name=c_name, doc=doc, src=src)
            self.modules[name] = mod
        else:
            mod.c_name = mod.c_name or c_name
            mod.doc = mod.doc or doc
        return Obj("pymod", mod)

    def PyModule_Create(self, i, a, e, call):
        d = a[0] if a else None
        if not isinstance(d, dict):
            return UNKNOWN
        name = _s(d.get("m_name"))
        if not name:
            return UNKNOWN
        h = self.module_obj(name, self.type_name(d), _s(d.get("m_doc")), i.src(call[4]))
        methods = d.get("m_methods")
        if isinstance(methods, list):
            self._add_methods(h.data.methods, methods, i)
        return h

    def PyModule_New(self, i, a, e, call):
        name = _s(a[0]) if a else ""
        return self.module_obj(name, "", "", i.src(call[4])) if name else UNKNOWN

    PyImport_AddModule = PyModule_New

    def PyModule_GetDict(self, i, a, e, call):
        return a[0] if a and isinstance(a[0], Obj) and a[0].kind == "pymod" else UNKNOWN

    def _add_methods(self, out: list[PyMethod], table: list, i: Interp, src_hint: str = "") -> None:
        seen = {m.name for m in out}
        for m in table:
            if not isinstance(m, dict):
                continue
            name = m.get("ml_name")
            if not isinstance(name, str):
                if name is None:
                    break
                continue
            if name in seen:
                continue
            seen.add(name)
            doc = _s(m.get("ml_doc"))
            _kind, _dname, sig, _ = parse_directive(doc) if doc else ("", "", None, "")
            out.append(
                PyMethod(
                    name=name,
                    c_function=m["ml_meth"].name if isinstance(m.get("ml_meth"), FuncRef) else "",
                    flags=meth_flags(m.get("ml_flags")),
                    doc=doc,
                    signature=sig,
                    src=src_hint,
                )
            )

    def _add(self, mod_h, name, value, i, call) -> None:
        if not (isinstance(mod_h, Obj) and mod_h.kind == "pymod"):
            if isinstance(mod_h, Obj) and mod_h.kind == "tpdict":
                self._add_to_type(mod_h.data, value, name)
            return
        mod: PyModule = mod_h.data
        if isinstance(value, Obj):
            if value.kind == "pymod":
                if isinstance(name, str):
                    mod.submodules[name] = value.data.name
                return
            if value.kind == "pyinst":
                desc = self.structseq.get(value.data)
                if desc is not None and isinstance(name, str):
                    sub = self.structseq_module(value.data, desc, i)
                    mod.submodules[name] = sub.name
                elif isinstance(name, str):
                    mod.constants[name] = ""
                return
            if value.kind == "pyfuncs":
                self._add_methods(mod.methods, value.data, i, i.src(call[4]))
                return
            if value.kind == "pyval" and isinstance(name, str):
                mod.constants[name] = value.data
                return
        tname = self.type_name(value)
        if tname and isinstance(name, str):
            mod.types[name] = tname
            return
        if isinstance(name, str):
            mod.constants.setdefault(name, "")

    def PyModule_AddObject(self, i, a, e, call):
        if len(a) >= 3:
            self._add(a[0], a[1], a[2], i, call)
        return 0

    PyModule_AddObjectRef = PyModule_AddObject
    PyModule_Add = PyModule_AddObject

    def PyDict_SetItemString(self, i, a, e, call):
        if len(a) >= 3:
            name = a[1]
            if isinstance(name, Obj) and name.kind == "pyval":
                name = UNKNOWN
            self._add(a[0], name, a[2], i, call)
        return 0

    PyDict_SetItem = PyDict_SetItemString

    def PyModule_AddType(self, i, a, e, call):
        if len(a) >= 2 and isinstance(a[0], Obj) and a[0].kind == "pymod":
            tname = self.type_name(a[1])
            d = a[1] if isinstance(a[1], dict) else {}
            name = _s(d.get("tp_name")).rpartition(".")[2]
            if tname and name:
                a[0].data.types[name] = tname
        return 0

    def PyModule_AddIntConstant(self, i, a, e, call):
        if len(a) >= 2 and isinstance(a[0], Obj) and a[0].kind == "pymod" and isinstance(a[1], str):
            a[0].data.constants[a[1]] = "int"
        return 0

    def PyModule_AddStringConstant(self, i, a, e, call):
        if len(a) >= 2 and isinstance(a[0], Obj) and a[0].kind == "pymod" and isinstance(a[1], str):
            a[0].data.constants[a[1]] = "str"
        return 0

    # Struct sequences / dynamic type dicts -------------------------------------------------------------------------
    def PyStructSequence_InitType(self, i, a, e, call):
        if len(a) >= 2 and isinstance(a[1], dict):
            tname = self.type_name(a[0])
            if tname:
                self.structseq[tname] = a[1]
                if isinstance(a[0], dict):
                    a[0]["tp_name"] = a[1].get("name")
                    a[0]["tp_doc"] = a[1].get("doc")
        return 0

    PyStructSequence_InitType2 = PyStructSequence_InitType

    def PyStructSequence_NewType(self, i, a, e, call):
        return UNKNOWN

    def PyStructSequence_New(self, i, a, e, call):
        tname = self.type_name(a[0]) if a else ""
        return Obj("pyinst", tname, {"items": {}}) if tname else UNKNOWN

    def PyStructSequence_SetItem(self, i, a, e, call):
        if len(a) >= 3 and isinstance(a[0], Obj) and a[0].kind == "pyinst" and isinstance(a[1], int):
            a[0].fields["items"][int(a[1])] = a[2]

    def PyCFunction_New(self, i, a, e, call):
        m = a[0] if a else None
        if isinstance(m, dict):
            return Obj("pyfuncs", [m])
        if isinstance(m, list):
            return Obj("pyfuncs", m)
        if isinstance(m, Obj) and m.kind == "anyof":
            return Obj("pyfuncs", m.data)
        return UNKNOWN

    PyCFunction_NewEx = PyCFunction_New
    PyCMethod_New = PyCFunction_New

    def PyDescr_NewGetSet(self, i, a, e, call):
        g = a[1] if len(a) > 1 else None
        if isinstance(g, dict):
            g = [g]
        if isinstance(g, Obj) and g.kind == "anyof":
            g = g.data
        return Obj("getsets", g) if isinstance(g, list) else UNKNOWN

    def PyDescr_NewMethod(self, i, a, e, call):
        return self.PyCFunction_New(i, a[1:], e, call)

    PyDescr_NewClassMethod = PyDescr_NewMethod

    def PyType_Ready(self, i, a, e, call):
        return 0

    def PyType_FromSpec(self, i, a, e, call):
        return UNKNOWN

    def _add_to_type(self, tname: str, value, name) -> None:
        extra = self.extra.setdefault(tname, {"getsets": [], "methods": []})
        if isinstance(value, Obj) and value.kind == "getsets":
            extra["getsets"].extend(value.data)
        elif isinstance(value, Obj) and value.kind == "pyfuncs":
            extra["methods"].extend(value.data)

    def structseq_module(self, tname: str, desc: dict, i: Interp, inst: Obj | None = None) -> PyModule:
        name = _s(desc.get("name")) or tname
        h = self.module_obj(name, tname, _s(desc.get("doc")))
        mod: PyModule = h.data
        fields = desc.get("fields") if isinstance(desc.get("fields"), list) else []
        for f in fields:
            if not isinstance(f, dict) or not isinstance(f.get("name"), str):
                continue
            mod.constants.setdefault(f["name"], doc_type(_s(f.get("doc"))))
        return mod

    # ----------------------------------------------------------------------------------------------------------------
    def run(self) -> None:
        # Module init functions: anything that creates a module.
        for fn in list(self.i.p.functions.values()):
            if not fn.file.startswith(("source/blender/python", "source/blender/freestyle", "intern/", "extern/")):
                continue
            if _calls_any(
                fn.body,
                (
                    "PyModule_Create2",
                    "PyModule_New",
                    "PyStructSequence_InitType",
                    "PyStructSequence_InitType2",
                    "PyModule_AddObject",
                    "PyModule_AddType",
                ),
            ):
                try:
                    self.i.call_function(fn, [UNKNOWN] * len(fn.params))
                except RecursionError:
                    self.i.warnings.append(f"python: recursion in {fn.name}")
        # Struct sequence instances: the items set by position (bpy.app.handlers = a struct sequence instance).
        # Types: every PyTypeObject global.
        for usr, g in self.i.p.globals.items():
            # ``PyTypeObject`` is a typedef of ``struct _typeobject``: clang's canonical record name.
            if g["record"] not in ("PyTypeObject", "_typeobject") or g["type"].endswith("*") or "[" in g["type"]:
                continue
            value = self.i.global_value(usr, g["name"])
            self.make_type(g, value)
        for tname, desc in self.structseq.items():
            mod = self.structseq_module(tname, desc, self.i)
            extra = self.extra.get(tname, {})
            for gs in extra.get("getsets", []):
                if isinstance(gs, dict) and isinstance(gs.get("name"), str):
                    mod.constants.setdefault(gs["name"], doc_type(_s(gs.get("doc"))))
            self._add_methods(mod.methods, extra.get("methods", []), self.i)
        self.model.py_types.extend(self.types.values())
        self.model.py_modules.extend(self.modules.values())

    def make_type(self, g: dict, value) -> None:
        if not isinstance(value, dict):
            value = {}
        c_name = g["name"]
        if c_name in self.types:
            return
        doc = _s(value.get("tp_doc"))
        t = PyType(c_name=c_name, name=_s(value.get("tp_name")), doc=doc, src=f"{g['file']}:{g['line']}")
        base = value.get("tp_base")
        t.base = self.type_name(base) if base is not None else ""
        flags = value.get("tp_flags")
        if isinstance(flags, int):
            t.flags = [name for bit, name in TPFLAGS if int(flags) & bit]
        for key, v in value.items():
            if key.startswith("tp_") and isinstance(v, FuncRef):
                t.slots[key] = v.name
            elif key in SLOT_TABLES and isinstance(v, dict):
                for sk, sv in v.items():
                    if isinstance(sv, FuncRef):
                        t.slots[sk] = sv.name
            elif key == "tp_as_buffer" and isinstance(v, dict):
                t.slots["tp_as_buffer"] = self.type_name(v) or "buffer"
        methods = value.get("tp_methods")
        if isinstance(methods, list):
            self._add_methods(t.methods, methods, self.i, t.src)
        for gs in value.get("tp_getset") if isinstance(value.get("tp_getset"), list) else []:
            if not isinstance(gs, dict):
                continue
            name = gs.get("name")
            if name is None:
                break
            if not isinstance(name, str):
                continue
            gdoc = _s(gs.get("doc"))
            t.getsets.append(
                PyGetSet(
                    name=name,
                    getter=gs["get"].name if isinstance(gs.get("get"), FuncRef) else "",
                    setter=gs["set"].name if isinstance(gs.get("set"), FuncRef) else "",
                    doc=gdoc,
                    type=doc_type(gdoc),
                    src=t.src,
                )
            )
        for mem in value.get("tp_members") if isinstance(value.get("tp_members"), list) else []:
            if not isinstance(mem, dict):
                continue
            name = mem.get("name")
            if name is None:
                break
            if not isinstance(name, str):
                continue
            tc = mem.get("type")
            t.members.append(
                PyMember(
                    name=name,
                    type_code=MEMBER_TYPES.get(int(tc), str(tc)) if isinstance(tc, int) else "",
                    readonly=bool(isinstance(mem.get("flags"), int) and int(mem["flags"]) & 1),
                    doc=_s(mem.get("doc")),
                    src=t.src,
                )
            )
        if doc:
            kind, _name, sig, _ = parse_directive(doc)
            if kind == "class" and sig is not None:
                t.constructor = sig
        self.types[c_name] = t


def _calls_any(body, names) -> bool:
    stack = [body]
    while stack:
        x = stack.pop()
        if isinstance(x, list):
            if len(x) > 2 and x[0] == "c" and x[2] in names:
                return True
            stack.extend(y for y in x if isinstance(y, list))
    return False
