"""Area 3: the Python C API of ``source/blender/python``, audaspace's and freestyle's bindings.

Read from the static tables, all positional or designated brace initializers:

- ``PyTypeObject`` (CPython's slot order), ``PyNumberMethods`` / ``PySequenceMethods`` / ``PyMappingMethods`` /
  ``PyBufferProcs`` (the slots they set), plus ``T.tp_field = ...`` assignments made at runtime;
- ``PyMethodDef`` / ``PyGetSetDef`` / ``PyMemberDef`` rows, ``PyModuleDef``, ``PyStructSequence_Field`` /
  ``PyStructSequence_Desc`` (struct sequences become types whose fields are read-only attributes);
- docstrings from ``PyDoc_STRVAR`` (macros expanded, literals joined), parsed with ``rstdoc.parse_directive``;
- the argument parsers of the C functions: ``_keywords[] = {"", "x", nullptr}`` with the ``_PyArg_Parser`` format
  (``|`` optional, ``$`` keyword-only, an empty keyword is positional-only) give each parameter its kind;
- what module init functions add: ``PyModule_AddObject[Ref]`` / ``PyModule_AddType`` / ``PyModule_Add*Constant`` /
  ``PyModule_AddIntMacro`` / ``PyDict_SetItemString`` on a variable bound to ``PyModule_Create(&def)``.
"""

from __future__ import annotations

import re
from typing import Any

from ctok import CFile, Tok, Tree, VarDef, match_close, split_commas, string_value
from macro import expand

from common.model import PyGetSet, PyMember, PyMethod, PyModule, PyParam, PySignature, PyType, SourceModel
from common.rstdoc import parse_directive, rst_type_to_python

TP_FIELDS = [
    "tp_name",
    "tp_basicsize",
    "tp_itemsize",
    "tp_dealloc",
    "tp_vectorcall_offset",
    "tp_getattr",
    "tp_setattr",
    "tp_as_async",
    "tp_repr",
    "tp_as_number",
    "tp_as_sequence",
    "tp_as_mapping",
    "tp_hash",
    "tp_call",
    "tp_str",
    "tp_getattro",
    "tp_setattro",
    "tp_as_buffer",
    "tp_flags",
    "tp_doc",
    "tp_traverse",
    "tp_clear",
    "tp_richcompare",
    "tp_weaklistoffset",
    "tp_iter",
    "tp_iternext",
    "tp_methods",
    "tp_members",
    "tp_getset",
    "tp_base",
    "tp_dict",
    "tp_descr_get",
    "tp_descr_set",
    "tp_dictoffset",
    "tp_init",
    "tp_alloc",
    "tp_new",
    "tp_free",
    "tp_is_gc",
    "tp_bases",
    "tp_mro",
    "tp_cache",
    "tp_subclasses",
    "tp_weaklist",
    "tp_del",
    "tp_version_tag",
    "tp_finalize",
    "tp_vectorcall",
    "tp_watched",
]
SUB_TABLES = {
    "PyNumberMethods": [
        "nb_add",
        "nb_subtract",
        "nb_multiply",
        "nb_remainder",
        "nb_divmod",
        "nb_power",
        "nb_negative",
        "nb_positive",
        "nb_absolute",
        "nb_bool",
        "nb_invert",
        "nb_lshift",
        "nb_rshift",
        "nb_and",
        "nb_xor",
        "nb_or",
        "nb_int",
        "nb_reserved",
        "nb_float",
        "nb_inplace_add",
        "nb_inplace_subtract",
        "nb_inplace_multiply",
        "nb_inplace_remainder",
        "nb_inplace_power",
        "nb_inplace_lshift",
        "nb_inplace_rshift",
        "nb_inplace_and",
        "nb_inplace_xor",
        "nb_inplace_or",
        "nb_floor_divide",
        "nb_true_divide",
        "nb_inplace_floor_divide",
        "nb_inplace_true_divide",
        "nb_index",
        "nb_matrix_multiply",
        "nb_inplace_matrix_multiply",
    ],
    "PySequenceMethods": [
        "sq_length",
        "sq_concat",
        "sq_repeat",
        "sq_item",
        "was_sq_slice",
        "sq_ass_item",
        "was_sq_ass_slice",
        "sq_contains",
        "sq_inplace_concat",
        "sq_inplace_repeat",
    ],
    "PyMappingMethods": ["mp_length", "mp_subscript", "mp_ass_subscript"],
    "PyBufferProcs": ["bf_getbuffer", "bf_releasebuffer"],
    "PyAsyncMethods": ["am_await", "am_aiter", "am_anext", "am_send"],
}
MODULE_FIELDS = ["m_base", "m_name", "m_doc", "m_size", "m_methods", "m_slots", "m_traverse", "m_clear", "m_free"]
NULLS = {"nullptr", "NULL", "0", "nullptr_t"}
CONST_TYPES = {
    "PyModule_AddIntConstant": "int",
    "PyModule_AddStringConstant": "str",
    "PyModule_AddIntMacro": "int",
    "PyModule_AddStringMacro": "str",
}
VALUE_TYPES = [
    ("PyLong_From", "int"),
    ("PyFloat_From", "float"),
    ("PyUnicode_From", "str"),
    ("PyBool_From", "bool"),
    ("PyBytes_From", "bytes"),
    ("PyTuple_", "tuple[Any, ...]"),
    ("PyDict_New", "dict[str, Any]"),
    ("PyList_New", "list[Any]"),
    ("PyC_UnicodeFrom", "str"),
    ("PyFrozenSet_New", "frozenset[Any]"),
    ("PySet_New", "set[Any]"),
    ("Py_RETURN_NONE", "None"),
    ("PyC_FrozenSetFromStrings", "frozenset[str]"),
    ("PyErr_NewException", "type[Exception]"),
    ("PyDictProxy_New", "types.MappingProxyType[str, Any]"),
    ("PyCFunction_New", "Callable[..., Any]"),
]
FMT_UNIT = re.compile(r"\||\$|e[st]#?|[A-Za-z][#*!&]?|\(|\)")


def python_files(tree: Tree) -> list[str]:
    return tree.glob(
        "source/blender/python/**/*.cc",
        "source/blender/python/**/*.c",
        "source/blender/python/**/*.hh",
        "source/blender/freestyle/intern/python/**/*.cpp",
        "extern/audaspace/bindings/python/*.cpp",
    )


def last_ident(toks: list[Tok]) -> str:
    """``(PyCFunction)(void (*)(void))func`` / ``&T`` -> the last identifier that is not a cast keyword."""
    ids = [
        t.text
        for t in toks
        if t.kind == "id"
        and t.text
        not in {
            "void",
            "PyCFunction",
            "getter",
            "setter",
            "PyObject",
            "reinterpret_cast",
            "static_cast",
            "PyCFunctionWithKeywords",
            "const",
            "char",
            "Py_ssize_t",
            "PyTypeObject",
            "struct",
        }
    ]
    return ids[-1] if ids and ids[-1] not in NULLS else ""


class PyReader:
    def __init__(self, tree: Tree, model: SourceModel, extra: dict[str, Any]) -> None:
        self.tree = tree
        self.model = model
        self.extra = extra
        self.files: list[CFile] = [tree.file(r) for r in python_files(tree)]
        self.docs: dict[str, dict[str, str]] = {}  # file rel -> doc variable -> text
        self.global_docs: dict[str, str] = {}
        self.types: dict[str, PyType] = {}
        self.type_file: dict[str, CFile] = {}
        self.methods: dict[tuple[str, str], list[PyMethod]] = {}  # (file, array) -> rows
        self.getsets: dict[tuple[str, str], list[PyGetSet]] = {}
        self.members: dict[tuple[str, str], list[PyMember]] = {}
        self.sub_slots: dict[tuple[str, str], dict[str, str]] = {}
        self.modules: dict[str, PyModule] = {}  # PyModuleDef variable -> module
        self.module_fields: dict[str, dict[str, str]] = {}
        self.module_names: dict[str, list[str]] = {}
        self.returns_type_object: dict[str, str] = {}  # function -> the PyTypeObject it returns
        self.structseq_fields: dict[tuple[str, str], list[tuple[str, str]]] = {}
        self.structseq_desc: dict[str, tuple[str, str, str, CFile]] = {}  # desc var -> (name, doc var, fields var)
        self.functions: dict[str, list] = {}
        self.warnings: list[str] = []
        self.arg_kinds = 0

    # -- helpers

    def expand(self, f: CFile, toks: list[Tok], pos: int) -> list[Tok]:
        return expand(toks, lambda n: self.tree.macro(f, n, pos), set(), pos)

    def string(self, f: CFile, toks: list[Tok]) -> str | None:
        """A string expression: literals (macros expanded), ``PyDoc_STR(..)``, ``N_(..)``, a doc variable."""
        if not toks:
            return None
        if len(toks) == 1 and toks[0].text in NULLS:
            return None
        if len(toks) == 1 and toks[0].kind == "id":
            return self.doc(f, toks[0].text)
        toks = self.expand(f, toks, toks[0].pos)
        strs = [t for t in toks if t.kind == "str"]
        if not strs:
            ids = [t.text for t in toks if t.kind == "id"]
            if len(ids) == 1:
                return self.doc(f, ids[0])
            return None
        return "".join(string_value(t.text) for t in strs)

    def doc(self, f: CFile, name: str) -> str | None:
        d = self.docs.get(f.rel, {})
        if name in d:
            return d[name]
        return self.global_docs.get(name)

    def rows(self, f: CFile, var: VarDef) -> list[list[list[Tok]]]:
        toks = self.expand(f, var.init, var.pos)
        out = []
        for part in split_commas(toks):
            if not part or part[0].text != "{":
                continue
            close = match_close(part, 0)
            out.append(split_commas(part[1:close]))
        return out

    def fields(self, f: CFile, init: list[Tok], order: list[str], pos: int) -> dict[str, list[Tok]]:
        """Positional or designated (``.tp_name = ``) initializer fields."""
        toks = self.expand(f, init, pos)
        parts = split_commas(toks)
        out: dict[str, list[Tok]] = {}
        k = 0
        for part in parts:
            if not part:
                continue
            if len(part) >= 3 and part[0].text == "." and part[2].text == "=":
                out[part[1].text] = part[3:]
                continue
            if (
                part[0].text in {"PyVarObject_HEAD_INIT", "PyObject_HEAD_INIT", "PyModuleDef_HEAD_INIT", "{"}
                and k == 0
                and order[0] in {"tp_name", "m_base"}
            ):
                # ``PyVarObject_HEAD_INIT(nullptr, 0)`` is often followed by tp_name without a comma.
                if len(part) > 1 and part[1].text in {"(", "{"}:
                    part = part[match_close(part, 1) + 1 :]
                elif part[0].text == "{":
                    part = part[match_close(part, 0) + 1 :]
                else:
                    part = part[1:]
                if order[0] == "m_base":
                    k = 1
                if not part:
                    continue
            if k < len(order):
                out[order[k]] = part
            k += 1
        return out

    # -- passes

    def read_docs(self) -> None:
        for f in self.files:
            d = self.docs.setdefault(f.rel, {})
            toks = f.tokens
            for start, end in f.statements:
                t = toks[start]
                if (
                    t.text in {"PyDoc_STRVAR", "BPY_PROPDEF_DOC_STRVAR"}
                    and start + 1 < end
                    and toks[start + 1].text == "("
                ):
                    close = match_close(toks, start + 1)
                    args = split_commas(toks[start + 2 : close])
                    if len(args) >= 2 and args[0]:
                        text = self.string(f, [x for a in args[1:] for x in a]) or ""
                        d[args[0][0].text] = text
            for name, var in f.variables.items():
                if (
                    not var.braced
                    and ("char" in var.type_text)
                    and var.init
                    and all(x.kind in {"str", "id"} for x in var.init)
                ):
                    s = self.string(f, var.init)
                    if s is not None:
                        d.setdefault(name, s)
            for name, text in d.items():
                self.global_docs.setdefault(name, text)

    def read_tables(self) -> None:
        for f in self.files:
            # ``PyTypeObject BPy_BMesh_Type;`` filled field by field at runtime.
            toks = f.tokens
            for start, end in f.statements:
                words = [t.text for t in toks[start:end]]
                if (
                    len(words) >= 2
                    and words[-2] == "PyTypeObject"
                    and toks[end - 1].kind == "id"
                    and "extern" not in words
                    and "*" not in words
                ):
                    name = words[-1]
                    if name not in self.types:
                        self.types[name] = PyType(c_name=name, src=f.src(toks[start].pos))
                        self.type_file[name] = f
            for name, var in f.variables.items():
                tt = var.type_text
                key = (f.rel, name)
                if not var.braced:
                    continue
                if "PyMethodDef" in tt:
                    self.methods[key] = self.method_rows(f, var)
                elif "PyGetSetDef" in tt:
                    self.getsets[key] = self.getset_rows(f, var)
                elif "PyMemberDef" in tt:
                    self.members[key] = self.member_rows(f, var)
                elif "PyStructSequence_Field" in tt:
                    rows = []
                    for r in self.rows(f, var):
                        n = self.string(f, r[0]) if r else None
                        if n:
                            rows.append((n, self.string(f, r[1]) or "" if len(r) > 1 else ""))
                    self.structseq_fields[key] = rows
                elif "PyStructSequence_Desc" in tt:
                    flds = self.fields(f, var.init, ["name", "doc", "fields", "n_in_sequence"], var.pos)
                    self.structseq_desc[name] = (
                        self.string(f, flds.get("name", [])) or "",
                        last_ident(flds.get("doc", [])),
                        last_ident(flds.get("fields", [])),
                        f,
                    )
                elif "PyModuleDef" in tt and "PyModuleDef_Slot" not in tt:
                    self.module_def(f, name, var)
                elif "PyTypeObject" in tt:
                    self.type_def(f, name, var)
                else:
                    for table, order in SUB_TABLES.items():
                        if table in tt:
                            flds = self.fields(f, var.init, order, var.pos)
                            self.sub_slots[key] = {
                                k: last_ident(v)
                                for k, v in flds.items()
                                if v
                                and not (len(v) == 1 and v[0].text in NULLS)
                                and not k.startswith("was_")
                                and k != "nb_reserved"
                            }

    def method_rows(self, f: CFile, var: VarDef) -> list[PyMethod]:
        out = []
        for r in self.rows(f, var):
            if len(r) < 3:
                continue
            name = self.string(f, r[0])
            if not name:
                continue
            flags = [
                t.text.removeprefix("METH_").lower() for t in r[2] if t.kind == "id" and t.text.startswith("METH_")
            ]
            doc = self.string(f, r[3]) if len(r) > 3 else None
            out.append(
                PyMethod(name=name, c_function=last_ident(r[1]), flags=flags, doc=doc or "", src=f.src(r[0][0].pos))
            )
        return out

    def getset_rows(self, f: CFile, var: VarDef) -> list[PyGetSet]:
        out = []
        for r in self.rows(f, var):
            name = self.string(f, r[0]) if r else None
            if not name:
                continue
            get = last_ident(r[1]) if len(r) > 1 else ""
            set_ = last_ident(r[2]) if len(r) > 2 else ""
            doc = (self.string(f, r[3]) if len(r) > 3 else None) or ""
            out.append(
                PyGetSet(
                    name=name,
                    getter=get if get not in NULLS else "",
                    setter=set_ if set_ not in NULLS else "",
                    doc=doc,
                    type=attr_type(doc),
                    src=f.src(r[0][0].pos),
                )
            )
        return out

    def member_rows(self, f: CFile, var: VarDef) -> list[PyMember]:
        out = []
        for r in self.rows(f, var):
            name = self.string(f, r[0]) if r else None
            if not name:
                continue
            code = last_ident(r[1]) if len(r) > 1 else ""
            flags = {t.text for t in r[3]} if len(r) > 3 else set()
            doc = (self.string(f, r[4]) if len(r) > 4 else None) or ""
            out.append(
                PyMember(
                    name=name,
                    type_code=code,
                    readonly=bool(flags & {"READONLY", "Py_READONLY"}),
                    doc=doc,
                    src=f.src(r[0][0].pos),
                )
            )
        return out

    def module_def(self, f: CFile, name: str, var: VarDef) -> None:
        flds = self.fields(f, var.init, MODULE_FIELDS, var.pos)
        mname = self.string(f, flds.get("m_name", [])) or ""
        mod = PyModule(name=mname, c_name=name, doc=self.string(f, flds.get("m_doc", [])) or "", src=f.src(var.pos))
        key = f"{f.rel}:{name}"
        self.module_fields[key] = {"m_methods": last_ident(flds.get("m_methods", [])), "file": f.rel}
        self.modules[key] = mod
        self.module_names.setdefault(name, []).append(key)

    def mkey(self, f: CFile, name: str) -> str:
        """The module key of the PyModuleDef variable ``name`` seen from ``f`` ("" when none)."""
        if f"{f.rel}:{name}" in self.modules:
            return f"{f.rel}:{name}"
        keys = self.module_names.get(name, [])
        return keys[0] if len(keys) == 1 else ""

    def type_def(self, f: CFile, name: str, var: VarDef) -> None:
        flds = self.fields(f, var.init, TP_FIELDS, var.pos)
        t = PyType(c_name=name, src=f.src(var.pos))
        self.types[name] = t
        self.type_file[name] = f
        self.apply_type_fields(f, t, {k: v for k, v in flds.items()})

    def apply_type_fields(self, f: CFile, t: PyType, flds: dict[str, list[Tok]]) -> None:
        for k, v in flds.items():
            if not v or (len(v) == 1 and v[0].text in NULLS):
                continue
            if k == "tp_name":
                t.name = self.string(f, v) or t.name
            elif k == "tp_doc":
                t.doc = self.string(f, v) or t.doc
            elif k == "tp_flags":
                t.flags = sorted(
                    {x.text.removeprefix("Py_TPFLAGS_") for x in v if x.text.startswith("Py_TPFLAGS_")} | set(t.flags)
                )
            elif k == "tp_base":
                t.base = last_ident(v)
            elif k in {"tp_methods", "tp_getset", "tp_members"}:
                t.slots["__" + k] = last_ident(v)
            elif k in {"tp_as_number", "tp_as_sequence", "tp_as_mapping", "tp_as_buffer", "tp_as_async"}:
                t.slots[k] = last_ident(v)
            elif k in {
                "tp_basicsize",
                "tp_itemsize",
                "tp_weaklistoffset",
                "tp_dictoffset",
                "tp_vectorcall_offset",
                "tp_version_tag",
            }:
                continue
            else:
                t.slots[k] = last_ident(v) or " ".join(x.text for x in v)

    def runtime_assignments(self) -> None:
        """``T.tp_base = &U;`` / ``T.tp_new = ...`` made in init functions; also struct sequence init."""
        for f in self.files:
            for defs in f.functions.values():
                for fd in defs:
                    body = fd.body
                    n = len(body)
                    alias: dict[str, str] = {}  # ``PyTypeObject *i_ty = &BPy_IDGroup_IterItems_Type;``
                    for k in range(n - 3):
                        t = body[k]
                        if t.kind != "id":
                            continue
                        if body[k + 1].text == "=" and body[k + 2].text == "&" and body[k + 3].text in self.types:
                            alias[t.text] = body[k + 3].text
                        target = alias.get(t.text, t.text)
                        if (
                            body[k + 1].text in {".", "->"}
                            and body[k + 2].text.startswith("tp_")
                            and body[k + 3].text == "="
                            and target in self.types
                        ):
                            end = k + 4
                            while end < n and body[end].text != ";":
                                end += 1
                            self.apply_type_fields(f, self.types[target], {body[k + 2].text: body[k + 4 : end]})
                        elif (
                            t.text in {"PyStructSequence_InitType", "PyStructSequence_InitType2"}
                            and body[k + 1].text == "("
                        ):
                            close = match_close(body, k + 1)
                            args = split_commas(body[k + 2 : close])
                            if len(args) == 2:
                                tvar, dvar = last_ident(args[0]), last_ident(args[1])
                                self.structseq_type(f, tvar, dvar)

    def structseq_type(self, f: CFile, tvar: str, dvar: str) -> None:
        desc = self.structseq_desc.get(dvar)
        if desc is None:
            self.warnings.append(f"{f.rel}: struct sequence {tvar}: descriptor {dvar} not found")
            return
        name, docvar, fieldsvar, df = desc
        t = self.types.get(tvar) or PyType(c_name=tvar, src=df.src(0))
        self.types[tvar] = t
        self.type_file[tvar] = df
        t.name = name
        t.doc = self.doc(df, docvar) or t.doc
        t.flags = sorted(set(t.flags) | {"STRUCTSEQ"})
        for fname, fdoc in self.structseq_fields.get((df.rel, fieldsvar), []):
            t.getsets.append(PyGetSet(name=fname, getter="structseq", doc=fdoc, type=attr_type(fdoc)))
        t.slots.setdefault("sq_length", "structseq")
        t.slots.setdefault("sq_item", "structseq")
        t.slots.setdefault("tp_iter", "structseq")

    # -- argument parsers

    def index_functions(self) -> None:
        for f in self.files:
            for name, defs in f.functions.items():
                self.functions.setdefault(name, []).extend(defs)

    def function(self, name: str, f: CFile | None) -> Any:
        defs = self.functions.get(name) or []
        for fd in defs:
            if f is not None and fd.file is f:
                return fd
        return defs[0] if defs else None

    def arg_signature(self, c_function: str, f: CFile | None) -> list[PyParam] | None:
        """Parameters from ``_keywords[]`` and the ``_PyArg_Parser`` / ``PyArg_ParseTupleAndKeywords`` format."""
        fd = self.function(c_function, f)
        if fd is None:
            return None
        body = fd.body
        keywords: list[str] | None = None
        fmt: str | None = None
        n = len(body)
        for k in range(n):
            t = body[k]
            if (
                t.text in {"_keywords", "kwlist", "keywords"}
                and k + 3 < n
                and body[k + 1].text == "["
                and body[k + 2].text == "]"
                and body[k + 3].text == "="
            ):
                if k + 4 < n and body[k + 4].text == "{":
                    close = match_close(body, k + 4)
                    keywords = []
                    for part in split_commas(body[k + 5 : close]):
                        if part and part[0].kind == "str":
                            keywords.append(string_value(part[0].text))
            elif t.text == "_PyArg_Parser" and k + 2 < n:
                j = k + 1
                while j < n and body[j].text not in {"{", ";"}:
                    j += 1
                if j < n and body[j].text == "{":
                    close = match_close(body, j)
                    toks = self.expand(fd.file, body[j + 1 : close], body[j].pos)
                    parts = split_commas(toks)
                    if parts:
                        fmt = "".join(string_value(x.text) for x in parts[0] if x.kind == "str")
            elif (
                t.text in {"PyArg_ParseTupleAndKeywords", "PyArg_ParseTuple"}
                and fmt is None
                and k + 1 < n
                and body[k + 1].text == "("
            ):
                close = match_close(body, k + 1)
                args = split_commas(body[k + 2 : close])
                idx = 2 if t.text == "PyArg_ParseTupleAndKeywords" else 1
                if len(args) > idx:
                    strs = [
                        x
                        for x in self.expand(fd.file, args[idx], args[idx][0].pos if args[idx] else 0)
                        if x.kind == "str"
                    ]
                    if strs:
                        fmt = "".join(string_value(x.text) for x in strs)
                if t.text == "PyArg_ParseTuple" and fmt is not None:
                    keywords = None
        if fmt is None:
            return None
        fmt = fmt.split(":")[0].split(";")[0]
        params: list[PyParam] = []
        optional = False  # ``$`` (keyword-only) is applied below, once the names are known
        depth = 0
        for unit in FMT_UNIT.findall(fmt):
            if unit == "|":
                optional = True
                continue
            if unit == "$":
                continue
            if unit == "(":
                depth += 1
                if depth == 1:
                    params.append(PyParam(name=f"arg{len(params)}"))
                continue
            if unit == ")":
                depth -= 1
                continue
            if depth:
                continue
            params.append(PyParam(name=f"arg{len(params)}"))
            p = params[-1]
            p.default = "..." if optional else None
        for i, p in enumerate(params):
            name = keywords[i] if keywords is not None and i < len(keywords) else ""
            if name:
                p.name = name
                p.kind = "normal"
            else:
                p.kind = "positional_only"
        # keyword-only marks: recompute the position of ``$``
        pos = 0
        for unit in FMT_UNIT.findall(fmt):
            if unit == "$":
                for p in params[pos:]:
                    if p.kind == "normal":
                        p.kind = "keyword_only"
                break
            if unit in {"|", "(", ")"}:
                continue
            pos += 1
        self.arg_kinds += 1
        return params

    def method_signature(self, m: PyMethod, f: CFile | None, owner: str) -> None:
        _kind, _name, sig, _ = parse_directive(m.doc) if m.doc else ("", "", None, "")
        params = self.arg_signature(m.c_function, f) if m.c_function else None
        if sig is None and params is not None:
            sig = PySignature(params=params)
        elif sig is not None and params is not None:
            merge_kinds(sig, params)
        if sig is None and "noargs" in m.flags:
            sig = PySignature()
        m.signature = sig

    # -- module contents

    def module_adds(self) -> None:
        init_of: dict[str, str] = {}  # PyInit-like function -> module def it creates
        for f in self.files:
            for fname, defs in f.functions.items():
                for fd in defs:
                    body = fd.body
                    for k, t in enumerate(body):
                        if (
                            t.text in {"PyModule_Create", "PyModule_Create2", "PyModuleDef_Init"}
                            and k + 1 < len(body)
                            and body[k + 1].text == "("
                        ):
                            close = match_close(body, k + 1)
                            args = split_commas(body[k + 2 : close])
                            key = self.mkey(f, last_ident(args[0])) if args else ""
                            if key:
                                init_of.setdefault(fname, key)
        self.extra["py_module_init_functions"] = len(init_of)
        returns_type: dict[str, str] = {}  # function returning ``(PyObject *)&T`` / a struct sequence instance
        for f in self.files:
            for fname, defs in f.functions.items():
                for fd in defs:
                    body = fd.body
                    for k, t in enumerate(body):
                        if t.text == "return" and k + 1 < len(body):
                            end = k + 1
                            while end < len(body) and body[end].text != ";":
                                end += 1
                            seg = body[k + 1 : end]
                            tv = last_ident(seg)
                            if tv in self.types and any(x.text == "&" for x in seg):
                                self.returns_type_object.setdefault(fname, tv)
                        if t.text == "PyStructSequence_New" and k + 2 < len(body):
                            close = match_close(body, k + 1)
                            tv = last_ident(body[k + 2 : close])
                            if tv in self.types:
                                returns_type.setdefault(fname, tv)
        for f in self.files:
            for fname, defs in f.functions.items():
                for fd in defs:
                    self.module_function(f, fd, init_of, returns_type)

    def module_function(self, f: CFile, fd: Any, init_of: dict[str, str], returns_type: dict[str, str]) -> None:
        body = fd.body
        n = len(body)
        bound: dict[str, str] = {}  # local variable -> module def
        values: dict[str, list[Tok]] = {}  # local variable -> its last assigned expression
        own = init_of.get(fd.name)
        for k in range(n):
            t = body[k]
            if (
                t.kind == "id"
                and k + 1 < n
                and body[k + 1].text == "="
                and (k == 0 or body[k - 1].text not in {".", "->"})
            ):
                end = k + 2
                depth = 0
                while end < n:
                    if body[end].text in {"(", "[", "{"}:
                        depth += 1
                    elif body[end].text in {")", "]", "}"}:
                        if depth == 0:
                            break
                        depth -= 1
                    elif body[end].text in {";", ","} and depth == 0:
                        break
                    end += 1
                rhs = body[k + 2 : end]
                values[t.text] = rhs
                callee = next((x.text for x in rhs if x.kind == "id" and x.text not in {"PyObject"}), "")
                if any(x.text in {"PyModule_Create", "PyModule_Create2"} for x in rhs):
                    d = next((self.mkey(f, x.text) for x in rhs if x.kind == "id" and self.mkey(f, x.text)), "")
                    if d:
                        bound[t.text] = d
                elif callee in init_of:
                    bound[t.text] = init_of[callee]
                elif callee == "PyModule_GetDict" and len(rhs) > 2:
                    src_var = last_ident(rhs[1:])
                    if src_var in bound:
                        bound[t.text] = bound[src_var]
            if t.kind != "id" or k + 1 >= n or body[k + 1].text != "(":
                continue
            name = t.text
            if not (name.startswith("PyModule_Add") or name in {"PyDict_SetItemString", "PyModule_AddFunctions"}):
                continue
            close = match_close(body, k + 1)
            args = split_commas(body[k + 2 : close])
            if not args or not args[0]:
                continue
            target = last_ident(args[0])
            mdef = bound.get(target) or (own if own and target in {"mod", "m", "module", "submodule"} else None)
            if mdef is None:
                continue
            mod = self.modules[mdef]
            if name == "PyModule_AddType" and len(args) >= 2:
                tv = last_ident(args[1])
                if tv in self.types:
                    attr = (self.types[tv].name or tv).rpartition(".")[2]
                    mod.types[attr] = tv
                continue
            if len(args) < 2:
                continue
            attr = self.string(f, args[1]) if name != "PyModule_AddIntMacro" else last_ident(args[1])
            if not attr:
                continue
            if name in CONST_TYPES:
                mod.constants[attr] = CONST_TYPES[name]
                continue
            value = args[2] if len(args) > 2 else []
            if len(value) == 1 and value[0].kind == "id" and value[0].text in values:
                value = values[value[0].text]
            self.module_value(f, mod, attr, value, init_of, returns_type)

    def module_value(
        self,
        f: CFile,
        mod: PyModule,
        attr: str,
        value: list[Tok],
        init_of: dict[str, str],
        returns_type: dict[str, str],
    ) -> None:
        ids = [x.text for x in value if x.kind == "id"]
        tv = next((i for i in ids if i in self.types), "")
        if tv and "&" in [x.text for x in value]:
            mod.types[attr] = tv
            return
        rt = next((i for i in ids if i in self.returns_type_object), "")
        if rt:
            mod.types[attr] = self.returns_type_object[rt]
            return
        init = next((i for i in ids if i in init_of), "")
        if init:
            mod.submodules[attr] = self.modules[init_of[init]].name
            return
        if "PyModule_Create" in ids:
            key = next((self.mkey(f, i) for i in ids if self.mkey(f, i)), "")
            if key:
                mod.submodules[attr] = self.modules[key].name
                return
        callee = next((i for i in ids if i not in {"PyObject", "Py_NewRef", "Py_INCREF", "submodule"}), "")
        if callee in returns_type:
            mod.constants[attr] = "Any"
            self.extra.setdefault("py_struct_sequence_instances", {})[f"{mod.name}.{attr}"] = self.types[
                returns_type[callee]
            ].name
            return
        for prefix, typ in VALUE_TYPES:
            if callee.startswith(prefix):
                mod.constants[attr] = typ
                return
        if tv:
            mod.constants[attr] = "Any"
            return
        mod.constants[attr] = "Any"
        self.unresolved_values.append(f"{mod.name}.{attr}: {' '.join(x.text for x in value)[:80]}")

    # -- assemble

    def assemble(self) -> None:
        for cname, t in self.types.items():
            f = self.type_file[cname]
            for key, store, rows in (
                ("__tp_methods", "methods", self.methods),
                ("__tp_getset", "getsets", self.getsets),
                ("__tp_members", "members", self.members),
            ):
                var = t.slots.pop(key, "")
                if not var:
                    continue
                found = rows.get((f.rel, var))
                if found is None:
                    found = next((v for (r, n), v in rows.items() if n == var), None)
                if found is None:
                    self.warnings.append(f"{t.src}: {cname}.{key[2:]} = {var}: table not found")
                    continue
                getattr(t, store).extend(found)
            for slot in [s for s in t.slots if s.startswith("tp_as_")]:
                var = t.slots[slot]
                found = self.sub_slots.get((f.rel, var)) or next(
                    (v for (r, n), v in self.sub_slots.items() if n == var), None
                )
                if found is None:
                    if slot != "tp_as_buffer":
                        self.warnings.append(f"{t.src}: {cname}.{slot} = {var}: table not found")
                    continue
                for k, v in found.items():
                    t.slots[k] = v
                if slot != "tp_as_buffer":
                    del t.slots[slot]
            kind, _, sig, _ = parse_directive(t.doc) if t.doc else ("", "", None, "")
            if kind == "class" and sig is not None:
                t.constructor = sig
            elif "tp_new" in t.slots or "tp_init" in t.slots:
                fn = t.slots.get("tp_init") or t.slots.get("tp_new")
                params = self.arg_signature(fn, f)
                if params is not None:
                    t.constructor = PySignature(params=params)
            elif sig is not None and t.constructor is None and kind == "class":
                t.constructor = sig
            if t.constructor is not None and "tp_new" in t.slots:
                params = self.arg_signature(t.slots.get("tp_new", ""), f)
                if params is not None:
                    merge_kinds(t.constructor, params)
            for m in t.methods:
                self.method_signature(m, f, cname)
            for g in t.getsets:
                if not g.type and g.doc:
                    g.type = attr_type(g.doc)
        for dname, mod in self.modules.items():
            info = self.module_fields[dname]
            var = info.get("m_methods")
            if var:
                rows = self.methods.get((info["file"], var)) or next(
                    (v for (r, n), v in self.methods.items() if n == var), None
                )
                if rows is None:
                    self.warnings.append(f"{mod.src}: module {mod.name} methods {var}: table not found")
                else:
                    mod.methods.extend(rows)
                    f = next((x for x in self.files if x.rel == info["file"]), None)
                    for m in mod.methods:
                        self.method_signature(m, f, mod.name)

    def run(self) -> None:
        self.read_docs()
        self.index_functions()
        self.read_tables()
        self.runtime_assignments()
        self.unresolved_values = []
        self.module_adds()
        self.assemble()
        self.model.py_types.extend(self.types.values())
        self.model.py_modules.extend(m for m in self.modules.values() if m.name)
        self.extra["py_argument_parsers_read"] = self.arg_kinds
        self.extra["py_unresolved_module_values"] = self.unresolved_values[:60]
        self.extra["py_positional_only_params"] = sum(
            1
            for t in self.types.values()
            for m in t.methods
            if m.signature
            for p in m.signature.params
            if p.kind == "positional_only"
        ) + sum(
            1
            for mod in self.modules.values()
            for m in mod.methods
            if m.signature
            for p in m.signature.params
            if p.kind == "positional_only"
        )


def merge_kinds(sig: PySignature, params: list[PyParam]) -> None:
    """Give the documented parameters the kinds the argument parser enforces (matched by name, then by position)."""
    by_name = {p.name: p for p in params if p.kind != "positional_only"}
    for i, p in enumerate(sig.params):
        if p.kind in {"var_positional", "var_keyword"}:
            continue
        q = by_name.get(p.name)
        if q is None and i < len(params) and params[i].kind == "positional_only":
            q = params[i]
        if q is None:
            continue
        if q.kind == "positional_only" and p.kind == "normal":
            p.kind = "positional_only"
        elif q.kind == "keyword_only" and p.kind == "normal":
            p.kind = "keyword_only"


_TYPE_FIELD = re.compile(r"^\s*:type:\s*(.+?)\s*$", re.MULTILINE)


def attr_type(doc: str) -> str:
    if not doc:
        return ""
    _kind, _, _, typ = parse_directive(doc)
    if typ:
        return typ
    m = _TYPE_FIELD.search(doc)
    return rst_type_to_python(m.group(1)) if m else ""


def extract_pyapi(tree: Tree, model: SourceModel, extra: dict[str, Any]) -> list[str]:
    r = PyReader(tree, model, extra)
    r.run()
    return r.warnings
