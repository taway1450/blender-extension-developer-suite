"""PROTOTYPE (throwaway): stubs from what a running Blender holds, with no rst in between.

Runs inside Blender (``blender -b --factory-startup -Y --python runtime_stub_gen.py -- ...``). It fills the data model
of Blender's own stub generator (``doc/python_api/sphinx_stub_gen.py``: ``ModuleInfo``, ``ClassInfo``, ...) straight
from introspection, and renders it with that generator's back end, so the stubs keep the shapes ty-blender reads.
See ``docs/research/runtime-stub-generator.md`` and this folder's README.

- RNA (``bpy.types``, ``bpy.ops``): ``_rna_info.BuildRNAInfo`` with ``get_type_description`` strings, the shared enum
  aliases from ``_bpy.rna_enum_items_static()``, the context member table of ``sphinx_doc_gen``;
- C modules (``mathutils``, ``gpu``, ``bmesh``, ...): their members, read live, typed by the rst field lists in their
  ``__doc__`` (Blender's C functions have no ``__text_signature__``);
- Python modules (``bpy.utils``, ``bpy_extras``, ``bl_ui``, ...): copied as source, as the research note recommends;
  a class that a startup module registers in ``bpy.types`` is re-exported from its module, with its members;
- the add-on (``--addon``): what enabling it adds to RNA and ``bpy.ops`` (the delta), rendered into a merged package,
  and the content of every ``.blend`` under it, from a generic RNA walk.

Arguments after ``--``: ``--source <blender source> --output <dir> [--addon <add-on folder>]``.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import inspect
import json
import re
import shutil
import sys
import time
import types
from pathlib import Path

import _bpy
import _rna_info
import addon_utils
import bpy

# Root modules walked for C members. A Python module under them is copied as source instead.
C_ROOTS = ("mathutils", "gpu", "blf", "imbuf", "bmesh", "bl_math", "aud", "idprop", "_freestyle", "bpy")
# Modules rendered from RNA or written here, never walked or copied.
RENDERED = {"bpy", "bpy.types", "bpy.ops", "bpy.context", "bpy.data"}
# The Python C-API classes of `bpy.types` (not RNA structs), walked like a C module's classes.
PYCAPI_CLASSES = (
    "bpy_struct", "bpy_prop", "bpy_prop_array", "bpy_prop_collection", "bpy_prop_collection_idprop", "bpy_func",
    "bpy_struct_meta_idprop",
)
# Script folders whose loaded modules are copied as source.
SCRIPT_DIRS = ("scripts/modules", "scripts/startup", "scripts/addons_core", "scripts/freestyle/modules")
DIRECTIVE = re.compile(r"^(\s*)\.\. (class|method|function|staticmethod|classmethod|data|attribute):: (.+)$")
FIELD = re.compile(r"^(\s*):(\w+)(?: ([\w*.]+))?:(.*)$")
OPERATOR_RETURN = "set[rna_enum_operator_return_items]"
# What a protocol slot returns, whatever the class: a C slot's docstring is CPython's generic text.
SLOT_RETURNS = {"__len__": "int", "__contains__": "bool", "__setitem__": "None", "__delitem__": "None",
                "__exit__": "None"}
# The slots a C class's stub declares: the protocols and operators scripts use (`len(v)`, `v + w`, `-q`). Their
# operand types are not introspectable, so an operator returns `Any` unless the docs type it.
PROTOCOL_SLOTS = {
    "__getitem__", "__setitem__", "__delitem__", "__len__", "__iter__", "__next__", "__contains__", "__enter__",
    "__exit__", "__call__", "__buffer__", "__neg__", "__pos__", "__invert__", "__abs__", "__add__", "__radd__",
    "__iadd__", "__sub__", "__rsub__", "__isub__", "__mul__", "__rmul__", "__imul__", "__matmul__", "__rmatmul__",
    "__imatmul__", "__truediv__", "__itruediv__", "__lt__", "__le__", "__gt__", "__ge__",
}


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--addon", type=Path)
    return parser.parse_args(argv)


def load_back_end(source: Path) -> types.ModuleType:
    """``sphinx_stub_gen`` from the source tree. Blender's Python has no docutils, which only its rst front end uses:
    a stand-in lets the module import (the research note's R0 seam would move those imports instead)."""
    shim = types.ModuleType("docutils")
    for name in ("nodes", "parsers", "parsers.rst", "utils", "frontend"):
        module = types.ModuleType("docutils." + name)
        sys.modules["docutils." + name] = module
    sys.modules["docutils"] = shim
    nodes = sys.modules["docutils.nodes"]
    nodes.Element = nodes.Node = nodes.document = nodes.paragraph = nodes.field = object
    rst = sys.modules["docutils.parsers.rst"]
    rst.Parser = rst.Directive = object
    rst.directives = types.SimpleNamespace(flag=None, unchanged=None)
    rst.roles = types.SimpleNamespace()
    sys.modules["docutils.utils"].new_document = None
    sys.modules["docutils.frontend"].get_default_settings = None
    doc_dir = source / "doc" / "python_api"
    sys.path.insert(0, str(doc_dir))
    spec = importlib.util.spec_from_file_location("sphinx_stub_gen", doc_dir / "sphinx_stub_gen.py")
    back = importlib.util.module_from_spec(spec)
    sys.modules["sphinx_stub_gen"] = back
    spec.loader.exec_module(back)
    return back


def load_doc_tables(source: Path) -> types.ModuleType:
    """``sphinx_doc_gen`` for its tables (the context member types, the enum pointer map), not its rst writer."""
    doc_dir = source / "doc" / "python_api"
    spec = importlib.util.spec_from_file_location("sphinx_doc_gen", doc_dir / "sphinx_doc_gen.py")
    doc_gen = importlib.util.module_from_spec(spec)
    sys.modules["sphinx_doc_gen"] = doc_gen
    spec.loader.exec_module(doc_gen)
    return doc_gen


# ----------------------------------------------------------------------------
# rst text in docstrings -> the type strings the back end reads


SUBSTITUTIONS: dict[str, str] = {}


def rst_type(text: str) -> str:
    """A ``:type:`` field's text as the rst front end hands it to the back end: ``:class:`` roles kept, a shared
    enum ``:ref:`` as its alias name (``Literal[...]`` around it dropped), other markup as its text."""
    text = re.sub(r"\|(\w+)\|", lambda m: SUBSTITUTIONS.get(m[1], m[0]), " ".join(text.split()))
    text = re.sub(r"Literal\[:ref:`([^`]+)`\]", r"\1", text)
    text = re.sub(r":ref:`([^`]+)`", r"\1", text)
    text = re.sub(r"``([^`]*)``", r"\1", text)
    text = text.replace("\\ ", "")
    text = re.sub(r":(?!class:)[\w:]+:`([^`]+)`", r"\1", text)
    return text.strip()


def doc_blocks(doc: str | None) -> list[tuple[str | None, str | None, dict[str, str]]]:
    """The API directives of a docstring, ``(directive, argument, fields)``; a docstring without any is one block
    with its fields (a getset's ``:type:``, a Python function's ``:param:`` / ``:type:`` / ``:rtype:``)."""
    if not isinstance(doc, str) or not doc:
        return [(None, None, {})]
    blocks: list[tuple[str | None, str | None, dict[str, str]]] = []
    current: tuple[str | None, str | None, dict[str, str]] = (None, None, {})
    field: tuple[str, int] | None = None
    for line in doc.expandtabs().splitlines():
        if match := DIRECTIVE.match(line):
            if current[0] is not None or current[2]:
                blocks.append(current)
            current, field = (match[2], match[3].strip(), {}), None
            continue
        if match := FIELD.match(line):
            key = match[2] if match[3] is None else f"{match[2]} {match[3]}"
            current[2][key] = match[4].strip()
            field = (key, len(match[1]))
            continue
        if field is not None:
            if not line.strip() or len(line) - len(line.lstrip()) <= field[1]:
                field = None
            else:
                current[2][field[0]] += " " + line.strip()
    blocks.append(current)
    return blocks


def split_name(argument: str) -> tuple[str, str]:
    match = re.match(r"([A-Za-z_][\w.]*)(.*)$", argument)
    return (match[1].rsplit(".", 1)[-1], match[2].strip()) if match else (argument, "")


def field_types(fields: dict[str, str]) -> dict[str, str]:
    return {key[5:]: rst_type(value) for key, value in fields.items() if key.startswith("type ") and value}


def callable_infos(back, name: str, obj: object, kind: str) -> list:
    """``FunctionInfo`` / ``MethodInfo`` entries (several for overloads) for a C or Python callable."""
    infos = []
    blocks = [b for b in doc_blocks(getattr(obj, "__doc__", None)) if b[0] in {None, "function", "method",
                                                                            "staticmethod", "classmethod"}]
    for directive, argument, fields in blocks:
        if argument:
            _name, params = split_name(argument)
            params, return_type, _args = back.split_signature(params)
        else:
            params, return_type = python_params(obj), None
        return_type = return_type or (rst_type(fields["rtype"]) if fields.get("rtype") else None)
        if return_type is None and not argument:
            # Neither a directive nor a field: an unannotated Python return, or a C slot nobody documented.
            return_type = python_return(obj) or SLOT_RETURNS.get(name) or ("Any" if not fields else None)
        if params is None:
            continue
        if kind == "function":
            infos.append(back.FunctionInfo(name=name, params=params, return_type=return_type,
                                           body_param_types=field_types(fields)))
        else:
            infos.append(back.MethodInfo(
                name=name, params=params, return_type=return_type,
                is_static=directive == "staticmethod" or isinstance(obj, staticmethod),
                is_classmethod=directive == "classmethod" or isinstance(obj, classmethod),
                body_param_types=field_types(fields)))
    if len(infos) > 1 and kind != "function":
        for info in infos:
            info.is_overload = True
    return infos[:1] if kind == "function" else infos


def python_params(obj: object) -> str | None:
    """The parameters of a Python callable without annotations (the docstring types them), or None."""
    func = obj.__func__ if isinstance(obj, (staticmethod, classmethod)) else obj
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return None
    params = []
    for param in signature.parameters.values():
        params.append(param.replace(annotation=inspect.Parameter.empty))
    return str(signature.replace(parameters=params, return_annotation=inspect.Signature.empty))


def python_return(obj: object) -> str | None:
    func = obj.__func__ if isinstance(obj, (staticmethod, classmethod)) else obj
    annotation = getattr(func, "__annotations__", {}).get("return")
    return annotation if isinstance(annotation, str) else getattr(annotation, "__name__", None)


# ----------------------------------------------------------------------------
# RNA -> bpy.types, bpy.ops


class Rna:
    def __init__(self, back, doc_gen) -> None:
        self.back = back
        self.doc_gen = doc_gen
        self.enum_ids = doc_gen.rna_enum_pointer_to_id_map
        for key, items in doc_gen.rna_enum_dict.items():
            back.enum_alias_map[key] = [item.identifier for item in items if item.identifier]
        # The fork's Type-tag probe, run in this process as the doc generator runs it.
        self.type_tags = doc_gen.rna_type_tags()

    def refine(self, structs: dict) -> None:
        """A pointer to a base whose tag allows one subclass gives that subclass (``ActionStrip``)."""
        for struct in structs.values():
            for prop in (*struct.properties, *(r for func in struct.functions for r in func.return_values)):
                if prop.fixed_type is not None and (refined := self.type_tags.refined.get(prop.fixed_type.identifier)):
                    prop.fixed_type = _rna_info.GetInfoStructRNA(getattr(bpy.types, refined).bl_rna)

    def type_of(self, prop, *, as_arg=False, as_ret=False, operator_arg=False) -> str:
        override = None
        if prop.type == "enum" and (pointer := prop.enum_pointer) and (alias := self.enum_ids.get(pointer)):
            override = f":ref:`{alias}`"
        descr, _info = prop.get_type_description(
            as_arg=as_arg, as_ret=as_ret, class_fmt=":class:`{:s}`", mathutils_fmt=":class:`mathutils.{:s}`",
            literal_fmt="``{!r}``", collection_id=self.doc_gen._BPY_PROP_COLLECTION_ID, enum_descr_override=override)
        if as_ret and prop.type == "string" and not prop.is_never_none:
            descr += " | None"
        if prop.fixed_type is not None and prop.fixed_type.is_operator_properties():
            descr = "dict[str, Any]"
        elif operator_arg and prop.type in {"pointer", "collection"} and prop.fixed_type is not None:
            descr = "dict[str, Any]" if prop.type == "pointer" else "Sequence[dict[str, Any]]"
        return rst_type(descr)

    def method(self, func, struct_id: str):
        back = self.back
        # A required parameter after an optional one (`Panel.draw_header`'s ...) can only be passed by keyword.
        params, optional = [], False
        for arg in func.args:
            text = arg.get_arg_default(force=False)
            if "=" not in text and optional and "*" not in params:
                params.append("*")
            optional = optional or "=" in text
            params.append(text)
        params = "({:s})".format(", ".join(params))
        returns = func.return_values
        if len(returns) == 1:
            return_type = self.type_of(returns[0], as_ret=True)
        elif returns:
            return_type = "tuple[{:s}]".format(", ".join(self.type_of(r, as_ret=True) for r in returns))
        else:
            return_type = None
        return back.MethodInfo(
            name=func.identifier, params=params, return_type=return_type, is_classmethod=func.is_classmethod,
            body_param_types={arg.identifier: self.type_of(arg, as_arg=True) for arg in func.args})

    def tag_type(self, struct_id: str, prop) -> str | None:
        """The Type-tag probe's type for a property, as ``sphinx_doc_gen``'s ``tag_type_override``: the tag value
        of a refined subclass (``SubsurfModifier.type``), or the subclasses a base without a tag is one of."""
        tags = self.type_tags
        if (values := tags.values.get(struct_id, {}).get(prop.identifier)) is not None:
            return "Literal[{:s}]".format(", ".join(repr(value) for value in values))
        if prop.fixed_type is not None and (union_ids := tags.unions.get(prop.fixed_type.identifier)):
            return self.type_of(prop).replace(f":class:`{prop.fixed_type.identifier}`", " | ".join(
                f":class:`{union_id}`" for union_id in union_ids))
        return None

    def struct(self, struct, collection_wrappers: set[str]):
        back, doc_gen = self.back, self.doc_gen
        struct_id = struct.identifier
        base = getattr(struct.base, "identifier", "") or (
            "bpy_prop_collection" if struct_id in collection_wrappers else "bpy_struct")
        cls = back.ClassInfo(name=struct_id, bases=[base], metaclass=doc_gen.rna_metaclass_id(struct))
        for prop in sorted(struct.properties, key=lambda p: p.identifier):
            cls.attributes.append(back.AttrInfo(
                name=prop.identifier, type_str=self.tag_type(struct_id, prop) or self.type_of(prop),
                readonly=prop.is_readonly))
        # A refined subclass's tag (`SubsurfModifier.type`, a node's `bl_idname`) is a base property it does not
        # redeclare in RNA: declared on the subclass with the probed value.
        own = {attr.name for attr in cls.attributes}
        for identifier, values in sorted(self.type_tags.values.get(struct_id, {}).items()):
            if identifier not in own and (prop := struct.bl_rna.properties.get(identifier)) is not None:
                cls.attributes.append(back.AttrInfo(
                    name=identifier, type_str="Literal[{:s}]".format(", ".join(repr(v) for v in values)),
                    readonly=prop.is_readonly))
        for func in struct.functions:
            cls.methods.append(self.method(func, struct_id))
        # The members `_bpy_types` defines in Python (`Object.children`, `Mesh.from_pydata`, ...).
        for identifier, attr in struct.get_py_properties():
            fields = doc_blocks(getattr(attr, "__doc__", None))[-1][2]
            cls.attributes.append(back.AttrInfo(
                name=identifier, type_str=rst_type(fields["type"]) if fields.get("type") else None,
                readonly=getattr(attr, "fset", None) is None))
        for identifier, func in struct.get_py_functions():
            cls.methods += callable_infos(back, identifier, func, "method")
        for identifier, func in struct.get_py_c_functions():
            cls.methods += callable_infos(back, identifier, func, "method")
        return cls

    def context_members(self, cls) -> None:
        """The screen context members, typed by ``sphinx_doc_gen``'s table, checked against the live list."""
        back, doc_gen = self.back, self.doc_gen
        seen = {attr.name for attr in cls.attributes}
        for _space, members in sorted(_bpy.context_members().items()):
            for member in members:
                if member in seen:
                    continue
                seen.add(member)
                member_types = doc_gen.context_type_map.get(member)
                if not member_types:
                    print(f"runtime_stub_gen: context member {member!r} has no type in context_type_map")
                    continue
                strs = [f"list[:class:`{t}`]" if is_seq else f":class:`{t}`" if t.isidentifier() else t
                        for t, is_seq in member_types]
                if all(not is_seq and hasattr(bpy.types, t) for t, is_seq in member_types):
                    strs.append("None")
                cls.attributes.append(back.AttrInfo(name=member, type_str=" | ".join(strs), readonly=True))
        for member, member_type in sorted(doc_gen.context_store_type_map.items()):
            if member not in seen:
                cls.attributes.append(back.AttrInfo(name=member, type_str=f":class:`{member_type}` | None",
                                                    readonly=True))

    def operators(self, ops) -> dict[str, list]:
        back = self.back
        modules: dict[str, list] = {}
        for op in sorted(ops.values(), key=lambda o: (o.module_name, o.func_name)):
            params = ["*"] if op.args else []
            body = {}
            for arg in op.args:
                text = arg.get_arg_default(force=True)
                if arg.type in {"pointer", "collection"} and text.endswith("=None"):
                    # Passed as a dict (a sequence of dicts), which the call leaves empty when not given.
                    text = text[:-len("None")] + ("{}" if arg.type == "pointer" else "()")
                params.append(text)
                body[arg.identifier] = self.type_of(arg, as_arg=True, operator_arg=True)
            modules.setdefault(op.module_name, []).append(back.FunctionInfo(
                name=op.func_name, params="({:s})".format(", ".join(params)), return_type=OPERATOR_RETURN,
                body_param_types=body))
        return modules


def rna_snapshot() -> tuple[dict, dict]:
    """``BuildRNAInfo``'s structs and operators, with a fresh lookup (it caches by identifier)."""
    for cls in (_rna_info.InfoStructRNA, _rna_info.InfoPropertyRNA, _rna_info.InfoFunctionRNA,
                _rna_info.InfoOperatorRNA):
        cls.global_lookup.clear()
    structs, _funcs, ops, _props = _rna_info.BuildRNAInfo(keep_ui=True)
    # The dicts are the classes' lookups, which the next snapshot clears: copies keep this one.
    return dict(structs), dict(ops)


def rna_modules(rna: Rna, structs: dict, ops: dict, provenance: dict[str, str], hidden_roots: set[str]) -> dict:
    """``bpy.types`` and ``bpy.ops.*``: every struct ``bpy.types`` holds. A Python class from a script module is
    re-exported from its module (``provenance``) instead of rendered, so it keeps its own members. A class of a
    package in ``hidden_roots`` (the default add-ons, in general mode) is left out, with every property typed by it:
    the user may disable those add-ons, so the checker reports their registrations as an Assumption."""
    back = rna.back
    types_module = back.ModuleInfo(name="bpy.types")
    collection_wrappers = {p.srna.identifier for s in structs.values() for p in s.properties
                           if p.type == "collection" and p.srna is not None}
    hidden: set[str] = set()
    for struct in structs.values():
        py_module = getattr(struct.py_class, "__module__", "") or ""
        if struct.py_class is not None and py_module.split(".")[0] in hidden_roots:
            provenance[struct.identifier] = f"default-addon:{py_module}"
            hidden.add(struct.identifier)
        elif struct.module_name != "bpy.types":
            # A registered class `bpy.types` does not hold (a PropertyGroup): imported from its module for the
            # properties it types, not re-exported.
            provenance[struct.identifier] = f"import:{struct.module_name}"
        elif struct.py_class is not None and py_module not in {"bpy.types", "_bpy_types"} and struct.base is not None:
            provenance[struct.identifier] = f"startup:{py_module}"
    for struct in sorted(structs.values(), key=lambda s: s.identifier):
        if struct.identifier in hidden or provenance.get(struct.identifier, "").startswith(("startup:", "import:")):
            continue
        dropped = [p for p in struct.properties
                   if {getattr(p.fixed_type, "identifier", None), getattr(p.srna, "identifier", None)} & hidden]
        for prop in dropped:
            provenance[f"{struct.identifier}.{prop.identifier}"] = "default-addon-property"
        struct.properties = [p for p in struct.properties if p not in dropped]
        cls = rna.struct(struct, collection_wrappers)
        if struct.identifier == "Context":
            rna.context_members(cls)
        types_module.classes.append(cls)
    for name in PYCAPI_CLASSES:
        if (obj := getattr(bpy.types, name, None)) is not None:
            types_module.classes.append(c_class(back, name, obj, "bpy.types"))
    import _bpy_types
    for name, (_description, members) in rna.doc_gen.RNA_METACLASSES.items():
        metaclass = getattr(_bpy_types, name)
        bases = [b.__name__ for b in metaclass.__bases__
                 if b.__name__ in rna.doc_gen.RNA_METACLASSES or b.__name__ == "bpy_struct_meta_idprop"] or ["type"]
        types_module.classes.append(back.ClassInfo(name=name, bases=bases, attributes=[
            back.AttrInfo(name=member, type_str=member_type, readonly=True) for member, _d, member_type in members]))
    modules = {"bpy.types": types_module}
    for category, functions in rna.operators(ops).items():
        modules[f"bpy.ops.{category}"] = back.ModuleInfo(name=f"bpy.ops.{category}", functions=functions)
    return modules


# ----------------------------------------------------------------------------
# C modules -> their members, typed by their docstrings


def c_class(back, name: str, obj: type, module_name: str):
    blocks = doc_blocks(obj.__doc__)
    init_params, bases = None, [b.__name__ for b in obj.__bases__ if b is not object]
    init_types: dict[str, str] = {}
    for directive, argument, fields in blocks:
        if directive == "class" and argument:
            _name, rest = split_name(argument)
            if rest.startswith("(") and not re.fullmatch(r"\(\s*[\w.]+(\s*,\s*[\w.]+)*\s*\)", rest):
                init_params = rest
            init_types = field_types(fields)
    cls = back.ClassInfo(name=name, init_params=init_params, bases=bases, init_param_types=init_types)
    for member, value in sorted(vars(obj).items()):
        if member.startswith("__") and member not in PROTOCOL_SLOTS:
            continue
        if inspect.isroutine(value) or isinstance(value, (staticmethod, classmethod)):
            cls.methods += callable_infos(back, member, value, "method")
        elif inspect.isgetsetdescriptor(value) or inspect.ismemberdescriptor(value) or isinstance(value, property):
            fields = doc_blocks(getattr(value, "__doc__", None))[-1][2]
            readonly = "readonly" in (value.__doc__ or "").lower() or isinstance(value, property) and value.fset is None
            cls.attributes.append(back.AttrInfo(
                name=member, type_str=rst_type(fields["type"]) if fields.get("type") else None, readonly=readonly))
        elif not member.startswith("_") and not inspect.isclass(value):
            cls.attributes.append(back.AttrInfo(name=member, type_str=type(value).__name__, readonly=True))
    return cls


def doc_line_function(back, name: str, obj: object) -> list:
    """A function from a ``name(args) -> return`` first docstring line (``bmesh.ops``): the parameter names and
    defaults, untyped (their types are only in C source, the research note's §2.5)."""
    first = (getattr(obj, "__doc__", None) or "").strip().splitlines()[:1]
    match = re.match(r"[\w.]*?(\w+)(\(.*\))", first[0]) if first else None
    if not match:
        return [back.FunctionInfo(name=name, params="(*args, **kwargs)", return_type="Any")]
    params, _return_type, args = back.split_signature(match[2])
    if args is None:
        params = "(*args, **kwargs)"
    return [back.FunctionInfo(name=name, params=params, return_type="dict[str, Any]")]


def doc_substitutions(doc: str | None) -> dict[str, str]:
    """The ``.. |NAME| replace:: text`` definitions of a module docstring (``bmesh.types`` defines the ones its
    methods' fields use)."""
    found: dict[str, str] = {}
    if not isinstance(doc, str):
        return found
    current = None
    for line in doc.splitlines():
        if match := re.match(r"\s*\.\. \|(\w+)\| replace:: ?(.*)$", line):
            current = match[1]
            found[current] = match[2].strip()
        elif current and line.startswith((" ", "\t")) and line.strip():
            found[current] += " " + line.strip()
        else:
            current = None
    return found


def is_python_module(module: types.ModuleType) -> bool:
    return (getattr(module, "__file__", "") or "").endswith(".py")


def c_modules(back, provenance: dict[str, str]) -> tuple[dict, list[types.ModuleType]]:
    """The C modules under ``C_ROOTS`` rendered from their members; the Python modules met on the way."""
    modules: dict = {}
    python: list[types.ModuleType] = []
    seen: set[str] = set()

    def walk(name: str, module: types.ModuleType | None = None) -> None:
        """A module by the name scripts import it as (``bpy.msgbus``, whose ``__name__`` is ``msgbus``)."""
        if name in seen or name in RENDERED - {"bpy"}:
            return
        seen.add(name)
        try:
            module = module or sys.modules.get(name) or importlib.import_module(name)
        except Exception as ex:
            provenance[name] = f"import-failed: {ex}"
            return
        if is_python_module(module) and name != "bpy":
            python.append(module)
            return
        SUBSTITUTIONS.update(doc_substitutions(module.__doc__))
        info = back.ModuleInfo(name=name)
        for member in sorted(dir(module)):
            value = getattr(module, member)
            if name == "bpy" and member == "app":
                walk_struct_sequence("bpy.app", value)
                continue
            if isinstance(value, types.ModuleType):
                if not is_python_module(value) or value.__name__.startswith(f"{name}."):
                    if value.__name__.split(".")[0] not in sys.stdlib_module_names:
                        walk(f"{name}.{member}", value)
                continue
            if member.startswith("__") or name == "bpy":
                continue
            if inspect.isclass(value):
                if value.__module__ in {name, module.__name__, "builtins"} or name.endswith(".types"):
                    info.classes.append(c_class(back, member, value, name))
            elif inspect.isroutine(value):
                info.functions += callable_infos(back, member, value, "function")
            elif callable(value):
                # A callable object (`bmesh.ops.bevel`): its docstring's first line is its signature.
                info.functions += doc_line_function(back, member, value)
            elif not member.startswith("_"):
                info.data.append(back.DataInfo(name=member, type_str=(
                    type(value).__name__ if type(value).__module__ == "builtins" else None)))
        if name != "bpy":
            modules[name] = info

    def walk_struct_sequence(name: str, value: object) -> None:
        """``bpy.app`` and its namespaces: a struct sequence or C object, typed by its fields' docs."""
        info = back.ModuleInfo(name=name)
        for member in sorted(dir(value)):
            if member.startswith("_") and not member.startswith("_extension"):
                continue
            item = getattr(value, member)
            if member in {"count", "index", "n_fields", "n_sequence_fields", "n_unnamed_fields"} and (
                    hasattr(value, "n_fields")):
                continue
            if isinstance(item, types.ModuleType):
                walk(f"{name}.{member}", item)
                continue
            if inspect.isroutine(item):
                info.functions += callable_infos(back, member, item, "function")
                continue
            # A namespace: a C object (`bpy.app.translations`) or a struct sequence of lists (`bpy.app.handlers`).
            is_struct_sequence = hasattr(item, "n_fields")
            if (type(item).__module__ != "builtins" and not isinstance(item, (tuple, list, str))) or (
                    is_struct_sequence and any(isinstance(field, list) for field in item)):
                walk_struct_sequence(f"{name}.{member}", item)
                continue
            descriptor = getattr(type(value), member, None)
            fields = doc_blocks(getattr(descriptor, "__doc__", None))[-1][2] if descriptor is not None else {}
            type_str = rst_type(fields["type"]) if fields.get("type") else (
                type(item).__name__ if not isinstance(item, (tuple, list)) else None)
            info.data.append(back.DataInfo(name=member, type_str=type_str))
        modules[name] = info

    for root in C_ROOTS:
        walk(root)
    return modules, python


# ----------------------------------------------------------------------------
# Python modules -> copied as source


def copy_python_modules(output: Path, package_roots: list[Path]) -> int:
    """Copy the Python source the runtime offers into ``output``, beside the rendered stubs: every ``.py`` of the
    module search folders (``scripts/modules``, ``scripts/startup``, Freestyle's) and of the packages in
    ``package_roots`` (an enabled add-on). A module the stubs render (``bpy``, ``bpy.ops``) keeps its stub. The
    number of files copied."""
    scripts = Path(bpy.utils.resource_path("LOCAL")) / "scripts"
    sources = [(f, sorted(f.rglob("*.py"))) for f in (scripts / "modules", scripts / "startup",
                                                      scripts / "freestyle" / "modules") if f.is_dir()]
    sources += [(root.parent, sorted(root.rglob("*.py"))) for root in package_roots]
    copied = 0
    for folder, files in sources:
        for path in files:
            relative = path.relative_to(folder)
            if "__pycache__" in relative.parts:
                continue
            target = output / relative
            stub = target.with_name("__init__.pyi") if target.name == "__init__.py" else target.with_suffix(".pyi")
            if stub.exists() or (target.with_suffix("") / "__init__.pyi").exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            copied += 1
    return copied


def startup_reexports(provenance: dict[str, str]) -> str:
    """``bpy.types`` re-exports of the classes the startup scripts register, from their modules."""
    lines = []
    for identifier, origin in sorted(provenance.items()):
        if origin.startswith("startup:"):
            lines.append(f"from {origin[len('startup:'):]} import {identifier} as {identifier}\n")
        elif origin.startswith("import:"):
            lines.append(f"from {origin[len('import:'):]} import {identifier}\n")
    return "".join(lines)


# ----------------------------------------------------------------------------
# Rendering


def drop_unrenderable(back, module, locations, modules: dict) -> list[str]:
    """Remove the members of ``module`` the back end fails on (an unparsable signature in a docstring), each
    tried alone; their names."""
    def renders(**parts) -> bool:
        try:
            back.render_stub(back.ModuleInfo(name=module.name, **parts), locations, modules)
            return True
        except Exception:
            return False

    dropped = []
    for func in list(module.functions):
        if not renders(functions=[func]):
            module.functions.remove(func)
            dropped.append(func.name)
    for data in list(module.data):
        if not renders(data=[data]):
            module.data.remove(data)
            dropped.append(data.name)
    for cls in module.classes:
        if renders(classes=[cls]):
            continue
        for kind in ("methods", "attributes"):
            for member in list(getattr(cls, kind)):
                rest = dataclasses.replace(cls, **{"methods": [], "attributes": [], kind: [member]})
                if not renders(classes=[rest]):
                    getattr(cls, kind).remove(member)
                    dropped.append(f"{cls.name}.{member.name}")
        if not renders(classes=[cls]):
            cls.init_params = None
            dropped.append(f"{cls.name}()")
    return dropped


def render(back, modules: dict, output: Path, extra: dict[str, str]) -> list[str]:
    """Render ``modules`` with the back end into ``output``; ``extra`` text is appended to a module's stub. The
    rendering errors the back end counted."""
    for name in sorted(modules):
        parts = name.split(".")
        for i in range(1, len(parts)):
            modules.setdefault(".".join(parts[:i]), back.ModuleInfo(name=".".join(parts[:i])))
    if "bpy" in modules:
        modules["bpy"].data += [
            back.DataInfo(name="context", type_str=":class:`bpy.types.Context`"),
            back.DataInfo(name="data", type_str=":class:`bpy.types.BlendData`"),
        ]
    back.build_collection_element_map(modules)
    locations = back.ClassLocations(modules)
    errors = []
    for name, module in sorted(modules.items()):
        try:
            content = back.render_stub(module, locations, modules)
        except Exception:
            dropped = drop_unrenderable(back, module, locations, modules)
            errors.append(f"{name}: dropped what the back end cannot render: {', '.join(dropped)}")
            try:
                content = back.render_stub(module, locations, modules)
            except Exception as ex:
                errors.append(f"{name}: render failed: {type(ex).__name__}: {ex}")
                continue
        back.write_stub(output, name, content + extra.get(name, ""))
    back.write_enum_aliases_module(output)
    back.write_handwritten_stubs(output, set(modules))
    errors += [f"type reference {e.ref} in {e.module}" for e in back.find_type_ref_errors(modules, locations)]
    return errors


def module_summary(modules: dict) -> dict:
    return {name: {"classes": len(m.classes), "functions": len(m.functions), "data": len(m.data)}
            for name, m in sorted(modules.items())}


# ----------------------------------------------------------------------------
# Add-on mode


def enable_addon(addon: Path) -> str:
    """Enable the add-on folder as a legacy add-on (its parent on ``sys.path``); its module name."""
    sys.path.insert(0, str(addon.parent))
    errors: list[str] = []
    module = addon_utils.enable(addon.name, default_set=True, handle_error=lambda ex: errors.append(repr(ex)))
    if module is None or errors:
        raise SystemExit(f"runtime_stub_gen: enabling {addon.name} failed: {errors}")
    return addon.name


def struct_facts(structs: dict) -> dict[str, dict[str, str]]:
    """Per struct, its properties and functions as ``name -> type text``: what the add-on delta compares."""
    facts = {}
    for struct in structs.values():
        members = {p.identifier: f"{p.type}:{getattr(p.fixed_type, 'identifier', '')}" for p in struct.properties}
        members.update({f"{f.identifier}()": "function" for f in struct.functions})
        facts[struct.identifier] = members
    return facts


def addon_delta(pre: tuple[dict, dict], post: tuple[dict, dict], package: str) -> dict:
    pre_facts, post_facts = struct_facts(pre[0]), struct_facts(post[0])
    new_structs = sorted(set(post_facts) - set(pre_facts))
    new_members = {s: sorted(set(post_facts[s]) - set(pre_facts[s])) for s in post_facts
                   if s in pre_facts and set(post_facts[s]) - set(pre_facts[s])}
    new_ops = sorted({op.identifier for op in post[1].values()} - {op.identifier for op in pre[1].values()})
    structs = {s.identifier: s for s in post[0].values()}
    return {
        "package": package,
        "structs": {s: {"module": structs[s].module_name, "base": getattr(structs[s].base, "identifier", None)}
                    for s in new_structs},
        "properties": new_members,
        "operators": new_ops,
        "modules": sorted(name for name in sys.modules if name == package or name.startswith(package + ".")),
    }


# ----------------------------------------------------------------------------
# .blend content: a generic RNA walk of every ID


def walk_value(value, depth: int, *, top: bool = False):
    """What a manifest records about an RNA value: a struct's class and its named collections, to ``depth``; an ID
    other than the one walked (``top``) as a reference by class and name."""
    if depth <= 0 or value is None:
        return None
    if isinstance(value, bpy.types.ID) and not top:
        return {"id": f"{type(value).bl_rna.identifier}:{value.name}"}
    if not isinstance(value, bpy.types.bpy_struct):
        return None
    out: dict = {"class": type(value).bl_rna.identifier}
    for prop in value.bl_rna.properties:
        if prop.identifier in {"rna_type", "id_data", "original", "node", "owner"} or prop.type not in {"POINTER", "COLLECTION"}:
            continue
        try:
            item = getattr(value, prop.identifier)
        except Exception:
            continue
        if prop.type == "COLLECTION":
            name_prop = getattr(prop.fixed_type, "name_property", None)
            if name_prop is None or not len(item):
                continue
            key = "identifier" if prop.fixed_type.identifier.startswith("NodeSocket") else name_prop.identifier
            out[prop.identifier] = {getattr(x, key, "") or "": walk_value(x, depth - 1) or
                                    {"class": type(x).bl_rna.identifier} for x in item}
        elif (sub := walk_value(item, depth - 1)) is not None:
            out[prop.identifier] = sub
    return out


def walk_blend(path: Path) -> dict:
    started = time.perf_counter()
    bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False)
    content: dict = {}
    for prop in bpy.data.bl_rna.properties:
        if prop.type != "COLLECTION" or prop.identifier in {"window_managers", "workspaces", "screens", "all_ids"}:
            continue
        ids = getattr(bpy.data, prop.identifier)
        local = [i for i in ids if i.library is None]
        if not local:
            continue
        content[prop.identifier] = {
            i.name: {
                **(walk_value(i, 4, top=True) or {}),
                "custom_properties": {k: type(v).__name__ for k, v in i.items()},
            } for i in local
        }
    return {"file": path.name, "seconds": round(time.perf_counter() - started, 3), "data": content}


# ----------------------------------------------------------------------------


def general(back, doc_gen, source: Path, output: Path, *, addon: Path | None = None) -> dict:
    started = time.perf_counter()
    facts: dict = {
        "blender": bpy.app.version_string,
        "build_hash": bpy.app.build_hash.decode(),
        "platform": sys.platform,
        "default_addons_enabled": sorted(m.__name__ for m in addon_utils.modules() if addon_utils.check(m.__name__)[1]),
        "has_aud": "aud" in sys.modules or importlib.util.find_spec("aud") is not None,
    }
    provenance: dict[str, str] = {}
    default_addons = set(facts["default_addons_enabled"])
    rna = Rna(back, doc_gen)
    pre = rna_snapshot()
    delta = None
    package = None
    if addon is not None:
        package = enable_addon(addon)
        post = rna_snapshot()
        delta = addon_delta(pre, post, package)
        structs, ops = post
    else:
        structs, ops = pre
    rna.refine(structs)
    facts["seconds_rna_info"] = round(time.perf_counter() - started, 2)
    modules = rna_modules(rna, structs, ops, provenance, default_addons - {package})
    c, python = c_modules(back, provenance)
    modules.update(c)
    facts["seconds_collect"] = round(time.perf_counter() - started, 2)
    stubs = output / "stubs"
    if stubs.exists():
        shutil.rmtree(stubs)
    errors = render(back, modules, stubs, {"bpy.types": startup_reexports(provenance)})
    copied = copy_python_modules(stubs, [Path(sys.modules[package].__file__).parent] if package else [])
    facts["seconds_total"] = round(time.perf_counter() - started, 2)
    facts["render_errors"] = errors
    facts["copied_python_files"] = copied
    facts["startup_reexports"] = sum(1 for v in provenance.values() if v.startswith("startup:"))
    facts["imported_from_module"] = sorted(k for k, v in provenance.items() if v.startswith("import:"))
    facts["default_addon_classes"] = sorted(k for k, v in provenance.items() if v.startswith("default-addon:"))
    facts["default_addon_properties"] = sorted(k for k, v in provenance.items() if v == "default-addon-property")
    facts["import_failed"] = {k: v for k, v in provenance.items() if v.startswith("import-failed")}
    facts["modules"] = module_summary(modules)
    if delta is not None:
        (output / "delta.json").write_text(json.dumps(delta, indent=1, sort_keys=True), encoding="utf-8")
        blends = sorted(addon.rglob("*.blend"))
        blend_out = output / "blend"
        blend_out.mkdir(exist_ok=True)
        for blend in blends:
            manifest = walk_blend(blend)
            (blend_out / f"{blend.relative_to(addon).as_posix().replace('/', '__')}.json").write_text(
                json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
        facts["blend_files"] = [b.relative_to(addon).as_posix() for b in blends]
    return facts


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    back = load_back_end(args.source)
    doc_gen = load_doc_tables(args.source)
    facts = general(back, doc_gen, args.source, args.output, addon=args.addon)
    (args.output / "facts.json").write_text(json.dumps(facts, indent=1, sort_keys=True), encoding="utf-8")
    print("runtime_stub_gen: done in {:.1f}s".format(facts["seconds_total"]))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.exit(1)
    sys.exit(0)
