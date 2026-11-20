"""The ``RNA_def_*`` API as handlers of the executor: what each call does to the bound struct/property/function.

The compact helpers (``RNA_def_float_vector_xyz``, ``RNA_def_enum_flag``, ...) are not hand-tabled: their parameter
names come from ``RNA_define.hh`` and their property type/subtype from their own bodies in ``rna_define.cc``
(``RNA_def_property(cont, identifier, PROP_FLOAT, PROP_XYZ)``, ``prop->subtype = PROP_XYZ_LENGTH``, or the helper
they delegate to). Units come from ``RNA_types.hh`` (``PROP_DISTANCE = 18 | PROP_UNIT_LENGTH``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from common.model import EnumItem, Operator, RnaFunction, RnaProperty, RnaStruct
from ctok import CFile, Tok, Tree, parse_params, tokenize, tokens_text
from enums import EnumArray, EnumRegistry
from interp import MISSING, FuncRef, Interp, Raw, StructRef, flags_of

PROP_TYPES = {"PROP_BOOLEAN": "boolean", "PROP_INT": "int", "PROP_FLOAT": "float", "PROP_STRING": "string",
              "PROP_ENUM": "enum", "PROP_POINTER": "pointer", "PROP_COLLECTION": "collection"}


class BRNA:
    """The ``BlenderRNA *brna`` handle."""

    def __repr__(self) -> str:
        return "BRNA"


@dataclass
class HelperSpec:
    name: str
    params: list[str]
    type: str = ""
    subtype: str = ""
    enum_flag: bool = False


class OpH:
    """A ``wmOperatorType *ot`` being defined."""

    def __init__(self, op: Operator, builder: RnaBuilder) -> None:
        self.op = op
        self.builder = builder

    def getmember(self, name: str, ip: Interp) -> Any:
        if name == "srna":
            return OpSrna(self.op)
        return getattr(self, "_" + name, None)

    def setmember(self, name: str, value: Any, ip: Interp, toks: list[Tok]) -> None:
        op = self.op
        if name == "name" and isinstance(value, str):
            op.name = value
        elif name == "idname" and isinstance(value, str):
            op.idname = value
        elif name == "description" and isinstance(value, str):
            op.description = value
        elif name == "flag":
            op.flags = [f[len("OPTYPE_"):].lower() for f in flags_of(value, "OPTYPE_")]
        elif name in {"exec", "invoke", "modal", "poll", "ui", "cancel", "check", "poll_property", "get_name",
                      "get_description", "pyop_poll"}:
            if value is not None and name not in op.callbacks:
                op.callbacks.append(name)
        setattr(self, "_" + name, value)

    def compound(self, name: str, op_: str, value: Any) -> None:
        if name == "flag":
            extra = [f[len("OPTYPE_"):].lower() for f in flags_of(value, "OPTYPE_")]
            if op_ == "|=":
                self.op.flags += [e for e in extra if e not in self.op.flags]
            elif op_ == "&=":
                self.op.flags = [f for f in self.op.flags if f not in extra]


@dataclass
class OpSrna:
    op: Operator


class RnaBuilder:
    """State of an RNA definition run: the structs, the ``DefRNA.animate`` switch, the helper specs."""

    def __init__(self, tree: Tree, model_structs: list[RnaStruct], enums: EnumRegistry) -> None:
        self.tree = tree
        self.structs: dict[str, RnaStruct] = {}
        self.struct_list = model_structs
        self.enums = enums
        self.animate = True
        self.specs: dict[str, HelperSpec] = {}
        self.decl_params: dict[str, list[str]] = {}
        self.units: dict[str, str] = {}
        self.props: list[RnaProperty] = []
        self.warnings: list[str] = []
        self.unknown_calls: dict[str, int] = {}
        from dna import Dna

        self.dna = Dna(tree)
        self._load_api()

    # ----------------------------------------------------------------------------------------------------------------
    # The API, read from RNA_define.hh / rna_define.cc / RNA_types.hh

    def _load_api(self) -> None:
        hdr = self.tree.file("source/blender/makesrna/RNA_define.hh")
        for m in re.finditer(r"\b(RNA_def_\w+|RNA_define_\w+)\s*\(([^;{}]*)\)\s*;", hdr.code):
            params = parse_params(tokenize(m.group(2)))
            self.decl_params[m.group(1)] = [p.name for p in params]
        funcs: dict[str, Any] = {}
        for runtime in (False, True):
            f = self.tree.file("source/blender/makesrna/intern/rna_define.cc", rna_runtime=runtime)
            for name, defs in f.functions.items():
                if name.startswith("RNA_def_"):
                    funcs.setdefault(name, defs[0])

        def spec_of(name: str, seen: set[str]) -> HelperSpec | None:
            if name in self.specs:
                return self.specs[name]
            fd = funcs.get(name)
            if fd is None or name in seen:
                return None
            params = [p.name for p in fd.params]
            if not params or params[0] not in {"cont_", "cont"}:
                return None
            spec = HelperSpec(name, self.decl_params.get(name, params))
            body = fd.body
            for k, t in enumerate(body):
                if t.kind != "id":
                    continue
                if t.text == "RNA_def_property" and k + 1 < len(body) and body[k + 1].text == "(":
                    # RNA_def_property(cont, identifier, PROP_X, PROP_Y)
                    j = k + 2
                    args = []
                    depth = 0
                    cur: list[str] = []
                    while j < len(body):
                        s = body[j].text
                        if s == "(":
                            depth += 1
                        elif s == ")":
                            if depth == 0:
                                break
                            depth -= 1
                        if s == "," and depth == 0:
                            args.append(" ".join(cur))
                            cur = []
                        else:
                            cur.append(s)
                        j += 1
                    args.append(" ".join(cur))
                    if len(args) >= 4 and not spec.type:
                        spec.type = PROP_TYPES.get(args[2].strip(), "")
                        spec.subtype = args[3].strip()
                elif t.text.startswith("RNA_def_") and t.text != name and k + 1 < len(body) and body[k + 1].text == "(" and not spec.type:
                    inner = spec_of(t.text, seen | {name})
                    if inner is not None and inner.type:
                        spec.type, spec.subtype, spec.enum_flag = inner.type, inner.subtype, inner.enum_flag
                elif t.text == "subtype" and k >= 1 and body[k - 1].text == "->" and k + 2 < len(body) and body[k + 1].text == "=":
                    spec.subtype = body[k + 2].text
                elif t.text == "RNA_def_property_subtype" and k + 4 < len(body):
                    spec.subtype = body[k + 4].text
                elif t.text == "PROP_ENUM_FLAG":
                    spec.enum_flag = True
            if spec.type:
                self.specs[name] = spec
                return spec
            return None

        for name in funcs:
            spec_of(name, set())
        # Units: ``PROP_DISTANCE = 18 | PROP_UNIT_LENGTH``
        types = self.tree.file("source/blender/makesrna/RNA_types.hh")
        for e in types.enums:
            if e.name == "PropertySubType":
                for cname, vtoks in e.constants:
                    unit = next((t.text for t in vtoks if t.text.startswith("PROP_UNIT_")), "")
                    self.units[cname] = unit[len("PROP_UNIT_"):].lower() if unit else "none"

    # ----------------------------------------------------------------------------------------------------------------
    # Structs and containers

    def struct(self, name: str, create: bool = True, src: str = "") -> RnaStruct | None:
        s = self.structs.get(name)
        if s is None and create:
            s = RnaStruct(identifier=name, src=src)
            self.structs[name] = s
            self.struct_list.append(s)
        return s

    def resolve_struct(self, value: Any, ip: Interp | None = None) -> RnaStruct | None:
        if isinstance(value, RnaStruct):
            return value
        if isinstance(value, StructRef):
            s = self.struct(value.name, create=False)
            if s is None and ip is not None:
                ip.warn("reference to a struct not defined (yet)", value.name)
            return s
        if isinstance(value, str):
            return self.struct(value, create=False)
        return None

    def struct_name(self, value: Any) -> str:
        if isinstance(value, RnaStruct):
            return value.identifier
        if isinstance(value, StructRef):
            return value.name
        if isinstance(value, str):
            return value
        return ""

    def container_list(self, cont: Any, ip: Interp) -> list[RnaProperty] | None:
        if isinstance(cont, RnaStruct):
            return cont.properties
        if isinstance(cont, RnaFunction):
            return cont.parameters
        if isinstance(cont, OpSrna):
            return cont.op.properties
        if isinstance(cont, OpH):
            return cont.op.properties
        if isinstance(cont, StructRef):
            s = self.resolve_struct(cont, ip)
            return s.properties if s is not None else None
        return None

    # ----------------------------------------------------------------------------------------------------------------
    # Properties

    def subtype_unit(self, value: Any) -> tuple[str, str]:
        names = flags_of(value, "PROP_") if not isinstance(value, str) else re.findall(r"PROP_\w+", value)
        subtype, unit = "none", "none"
        for n in names:
            if n.startswith("PROP_UNIT_"):
                unit = n[len("PROP_UNIT_"):].lower()
            elif n != "PROP_NONE":
                subtype = n[len("PROP_"):].lower()
                if unit == "none":
                    unit = self.units.get(n, "none")
        return subtype, unit

    def new_prop(self, ip: Interp, cont: Any, ident: Any, ptype: str, subtype: Any, pos: int) -> RnaProperty:
        st, unit = self.subtype_unit(subtype)
        p = RnaProperty(identifier=ident if isinstance(ident, str) else "", type=ptype, subtype=st, unit=unit,
                        src=ip.src(pos))
        flags = []
        if ptype not in {"pointer", "collection"}:
            flags.append("editable")
            if ptype != "string" and self.animate:
                flags.append("animatable")
        p.flags = flags
        p.name = p.identifier
        target = self.container_list(cont, ip)
        if not isinstance(ident, str):
            ip.warn("property identifier not a constant string", ip.src(pos))
            return p
        if target is None:
            ip.warn("property on a container the reader could not follow", ip.src(pos))
            return p
        if any(q.identifier == ident for q in target):
            ip.warn("property defined twice (both branches of an unknown condition)")
            return p
        if ip.loop_depth:
            ip.warn("property defined in a loop (identifier read once)")
        target.append(p)
        self.props.append(p)
        if isinstance(cont, RnaStruct):
            p._struct = cont  # type: ignore[attr-defined]
            if ptype != "collection":
                self.apply_sdna(p, None, None)
        return p

    def dna_name(self, st: RnaStruct) -> str:
        return getattr(st, "_sdna_from", "") or st.dna or st.identifier

    def apply_sdna(self, p: Any, structname: Any, propname: Any, bitset_length: int = 0) -> None:
        """``rna_def_property_sdna``: the DNA member sizes the array (or bounds the string) and types pointers."""
        if not isinstance(p, RnaProperty):
            return
        st = getattr(p, "_struct", None)
        sname = structname if isinstance(structname, str) else (self.dna_name(st) if st is not None else "")
        pname = propname if isinstance(propname, str) else p.identifier
        if not sname or not pname:
            return
        m = self.dna.member(sname, pname)
        if m is None:
            if bitset_length > 1:
                p.array = [bitset_length]
            return
        p._dnatype = m.type  # type: ignore[attr-defined]
        p._dna = m  # type: ignore[attr-defined]
        if p.type in {"pointer", "collection"}:
            return
        length = m.length if not m.pointer else 0
        indexed = pname.rstrip().endswith("]")
        if indexed and m.dims:  # ``"to_max[0]"``: one element (of the remaining dimensions)
            n_idx = pname.count("[")
            rest = m.dims[n_idx:]
            length = 1
            for d in rest:
                length *= d
            if not rest:
                length = 0
        if p.type == "string":
            if length > 1:
                p.max_length = length
            p.array = []
            return
        if p.type == "enum":
            return
        p.array = [length] if length > 1 else []
        if bitset_length > 1:
            p.array = [bitset_length]

    def set_flag(self, p: Any, names: list[str], on: bool = True) -> None:
        if not isinstance(p, RnaProperty):
            return
        for n in names:
            if not n.startswith("PROP_") or n == "PROP_NONE":
                continue
            flag = n[len("PROP_"):].lower()
            if on and flag not in p.flags:
                p.flags.append(flag)
            elif not on and flag in p.flags:
                p.flags.remove(flag)
            if flag == "enum_flag":
                p.enum_flag = on

    def set_items(self, ip: Interp, p: Any, items: Any) -> None:
        if not isinstance(p, RnaProperty):
            return
        if isinstance(items, EnumArray):
            if items.shared and items.name.startswith("rna_enum_"):
                p.items_name = items.name
                p.items = []
            else:
                p.items = list(items.items)
                p.items_name = items.name if items.shared else ""
            p._raw_values = items.raw_values  # type: ignore[attr-defined]
            p._raw_items = items.items  # type: ignore[attr-defined]
        elif items is None:
            pass
        else:
            ip.warn("enum items not a readable array", getattr(items, "text", type(items).__name__))

    def set_default(self, ip: Interp, p: Any, value: Any) -> None:
        if not isinstance(p, RnaProperty) or value is None:
            if isinstance(p, RnaProperty) and value is None and p.type == "string":
                p.default = ""
            return
        if p.type == "enum":
            p._default_raw = value  # type: ignore[attr-defined]
            return
        if isinstance(value, list):
            nums = [ip.number(v) if not isinstance(v, bool) else v for v in value]
            if all(v is not None for v in nums):
                if p.type == "boolean":
                    p.default = [bool(v) for v in nums]
                elif p.type == "int":
                    p.default = [int(v) for v in nums]
                else:
                    p.default = [float(v) for v in nums]
            return
        if p.type == "string":
            if isinstance(value, str):
                p.default = value
            return
        v = ip.number(value) if not isinstance(value, bool) else value
        if v is None:
            return
        if p.type == "boolean":
            p.default = bool(v)
        elif p.type == "int":
            p.default = int(v)
        elif p.type == "float":
            p.default = float(v)

    def array_value(self, ip: Interp, value: Any) -> Any:
        """A default array argument: a bound list, a file-level array, or null."""
        if isinstance(value, list) or value is None:
            return value
        if isinstance(value, Raw):
            return None
        return None

    # ----------------------------------------------------------------------------------------------------------------
    # Finalization

    def finalize(self) -> None:
        # makesrna's ``rna_auto_types``: an untyped pointer takes the RNA struct whose DNA is the member's type.
        by_dna: dict[str, str] = {}
        for st in self.struct_list:
            by_dna.setdefault(self.dna_name(st), st.identifier)
        for p in self.props:
            if p.type == "pointer" and not p.struct_type and not p.getter and getattr(p, "_dnatype", ""):
                dt = {"Screen": "bScreen", "Group": "Collection"}.get(p._dnatype, p._dnatype)  # type: ignore[attr-defined]
                if dt in by_dna:
                    p.struct_type = by_dna[dt]
        for p in self.props:
            finalize_prop(p, self.enums)
        for s in self.struct_list:
            for f in s.functions:
                for p in f.parameters:
                    finalize_prop(p, self.enums)


def finalize_prop(p: RnaProperty, enums: EnumRegistry) -> None:
    if getattr(p, "_final", False):
        return
    p._final = True  # type: ignore[attr-defined]
    p.readonly = "editable" not in p.flags and not p.editable_func and p.type not in {"collection"}
    if p.type == "collection":
        p.readonly = True
    p.never_null = "never_null" in p.flags and p.type in {"pointer", "collection"}
    if p.type == "enum":
        items = getattr(p, "_raw_items", None)
        raws = getattr(p, "_raw_values", None)
        if items is None and p.items_name in enums.shared:
            arr = enums.shared[p.items_name]
            items, raws = arr.items, arr.raw_values
        raw = getattr(p, "_default_raw", None)
        if raw is not None and items:
            text = raw.text if isinstance(raw, Raw) else str(raw)
            num = raw if isinstance(raw, (int, float)) and not isinstance(raw, bool) else None
            if num is None and isinstance(raw, Raw):
                from ctok import eval_number

                num = eval_number(raw.text, enums.tree.constants(raw.file) if raw.file else {})
            if p.enum_flag:
                if isinstance(num, (int, float)):
                    p.default = {i.identifier for i in items if i.value is not None and int(num) & i.value and i.identifier}
            else:
                hit = None
                for item, rv in zip(items, raws or []):
                    if rv == text and item.identifier:
                        hit = item
                        break
                if hit is None and isinstance(num, (int, float)):
                    hit = next((i for i in items if i.value == num and i.identifier), None)
                if hit is not None:
                    p.default = hit.identifier
        elif raw is None and items and not p.enum_flag and p.default is None:
            # RNA's default enum value is 0: the item valued 0, else the first item.
            hit = next((i for i in items if i.value == 0 and i.identifier), None)
            p.default = hit.identifier if hit else next((i.identifier for i in items if i.identifier), None)
        elif p.enum_flag and p.default is None and raw is None:
            p.default = set()
    elif p.default is None and p.type in {"boolean", "int", "float"}:
        zero = {"boolean": False, "int": 0, "float": 0.0}[p.type]
        if p.array and not p.dynamic_array:
            total = 1
            for n in p.array:
                total *= n
            if len(p.array) == 1:
                p.default = [zero] * total
            elif len(p.array) == 2:
                p.default = [[zero] * p.array[1] for _ in range(p.array[0])]
        elif not p.array:
            p.default = zero
    elif p.default is None and p.type == "string":
        p.default = ""


# --------------------------------------------------------------------------------------------------------------------
# Handlers


def make_handlers(b: RnaBuilder) -> dict[str, Any]:
    H: dict[str, Any] = {}

    def arg(vals: list[Any], k: int) -> Any:
        return vals[k] if k < len(vals) else None

    def s(v: Any) -> str:
        return v if isinstance(v, str) else ""

    # -- structs

    def def_struct(ip: Interp, vals: list[Any], toks: Any, pos: int) -> Any:
        name = arg(vals, 1)
        if not isinstance(name, str):
            ip.warn("struct identifier not a constant string", ip.src(pos))
            return RnaStruct(identifier="")
        st = b.struct(name, src=ip.src(pos))
        if not st.dna and name in b.dna.structs:
            st.dna = name
        if not arg(vals, 2) and "undo" not in st.flags:
            st.flags.append("undo")
        base = b.struct_name(arg(vals, 2))
        if base:
            st.base = base
        if not st.src:
            st.src = ip.src(pos)
        return st

    H["RNA_def_struct"] = def_struct
    H["RNA_def_struct_ptr"] = def_struct

    def struct_attr(attr: str, k: int = 1, conv=s):
        def h(ip: Interp, vals: list[Any], toks: Any, pos: int) -> Any:
            st = arg(vals, 0)
            st = b.resolve_struct(st, ip) if not isinstance(st, RnaStruct) else st
            if st is not None:
                v = conv(arg(vals, k))
                if v not in ("", None):
                    setattr(st, attr, v)
            return None
        return h

    H["RNA_def_struct_sdna"] = struct_attr("dna")
    H["RNA_def_struct_refine_func"] = struct_attr("refine")
    H["RNA_def_struct_path_func"] = struct_attr("path_func")
    H["RNA_def_struct_register_funcs"] = struct_attr("register")
    H["RNA_def_struct_idprops_func"] = struct_attr("idprops", conv=lambda v: True if v is not None else None)

    def struct_sdna_from(ip, vals, toks, pos):
        st = b.resolve_struct(arg(vals, 0), ip)
        if st is not None and isinstance(arg(vals, 1), str):
            st._sdna_from = arg(vals, 1)  # type: ignore[attr-defined]

    H["RNA_def_struct_sdna_from"] = struct_sdna_from

    def struct_ui_text(ip, vals, toks, pos):
        st = b.resolve_struct(arg(vals, 0), ip)
        if st is not None:
            st.name = s(arg(vals, 1)) or st.name
            if isinstance(arg(vals, 2), str):
                st.description = arg(vals, 2)

    H["RNA_def_struct_ui_text"] = struct_ui_text

    def struct_nested(ip, vals, toks, pos):
        st = b.resolve_struct(arg(vals, 1), ip)
        if st is not None:
            st.nested = s(arg(vals, 2))

    H["RNA_def_struct_nested"] = struct_nested

    def struct_flag(on: bool):
        def h(ip, vals, toks, pos):
            st = b.resolve_struct(arg(vals, 0), ip)
            if st is None:
                return
            for n in flags_of(arg(vals, 1), "STRUCT_"):
                f = n[len("STRUCT_"):].lower()
                if on and f not in st.flags:
                    st.flags.append(f)
                elif not on and f in st.flags:
                    st.flags.remove(f)
        return h

    H["RNA_def_struct_flag"] = struct_flag(True)
    H["RNA_def_struct_clear_flag"] = struct_flag(False)

    def struct_name_property(ip, vals, toks, pos):
        st = b.resolve_struct(arg(vals, 0), ip)
        p = arg(vals, 1)
        if st is not None and isinstance(p, RnaProperty):
            st.name_property = p.identifier

    H["RNA_def_struct_name_property"] = struct_name_property

    def struct_identifier(ip, vals, toks, pos):
        st = b.resolve_struct(arg(vals, 1), ip)
        new = arg(vals, 2)
        if st is not None and isinstance(new, str):
            b.structs.pop(st.identifier, None)
            st.identifier = new
            b.structs[new] = st

    H["RNA_def_struct_identifier"] = struct_identifier

    # -- property constructors

    def make_ctor(spec: HelperSpec):
        names = spec.params

        def h(ip: Interp, vals: list[Any], toks: Any, pos: int) -> Any:
            by = {names[k]: vals[k] for k in range(min(len(names), len(vals)))}
            subtype = spec.subtype
            m = re.match(r"^\(?\s*(\w+)\s*(>=|<=|==|>|<)\s*(\d+)\s*\)?\s*\?\s*(\w+)\s*:\s*(\w+)$", subtype)
            if m:  # ``(len >= 3) ? PROP_EULER : PROP_ANGLE``
                n = ip.number(by.get(m.group(1)))
                if isinstance(n, (int, float)):
                    ok = eval(f"{n} {m.group(2)} {m.group(3)}")  # noqa: S307 - digits and a comparison
                    subtype = m.group(4) if ok else m.group(5)
                else:
                    subtype = m.group(4)
            p = b.new_prop(ip, arg(vals, 0), by.get("identifier"), spec.type, subtype, pos)
            if spec.enum_flag:
                p.enum_flag = True
                if "enum_flag" not in p.flags:
                    p.flags.append("enum_flag")
            if "len" in by:
                n = ip.number(by["len"])
                if isinstance(n, (int, float)) and n > 0:
                    p.array = [int(n)]
            if "rows" in by and "columns" in by:
                r, c = ip.number(by["rows"]), ip.number(by["columns"])
                if isinstance(r, (int, float)) and isinstance(c, (int, float)):
                    p.array = [int(r), int(c)]
            if "items" in by:
                b.set_items(ip, p, by["items"])
            if "type" in by:
                p.struct_type = b.struct_name(by["type"])
            if "default_value" in by:
                dv = by["default_value"]
                if p.array and spec.type != "enum":
                    if isinstance(dv, list):
                        b.set_default(ip, p, _flatten(dv))
                else:
                    b.set_default(ip, p, dv)
            if "maxlen" in by:
                n = ip.number(by["maxlen"])
                if isinstance(n, int) and n > 0:
                    p.max_length = n
            lo, hi = ip.number(by.get("hardmin")), ip.number(by.get("hardmax"))
            if lo is not None and hi is not None and lo != hi:
                p.hard_min, p.hard_max = float(lo), float(hi)
            lo, hi = ip.number(by.get("softmin")), ip.number(by.get("softmax"))
            if lo is not None and hi is not None and lo != hi:
                p.soft_min, p.soft_max = float(lo), float(hi)
            if isinstance(by.get("ui_name"), str):
                p.name = by["ui_name"]
            if isinstance(by.get("ui_description"), str):
                p.description = by["ui_description"]
            return p

        return h

    for name, spec in b.specs.items():
        H[name] = make_ctor(spec)

    def def_property(ip, vals, toks, pos):
        t = flags_of(arg(vals, 2), "PROP_")
        ptype = PROP_TYPES.get(t[0], "") if t else ""
        if not ptype:
            ip.warn("RNA_def_property type not a constant", ip.src(pos))
        return b.new_prop(ip, arg(vals, 0), arg(vals, 1), ptype, arg(vals, 3), pos)

    H["RNA_def_property"] = def_property

    # -- property modifiers

    def prop_of(vals: list[Any]) -> RnaProperty | None:
        p = arg(vals, 0)
        return p if isinstance(p, RnaProperty) else None

    def ui_text(ip, vals, toks, pos):
        p = prop_of(vals)
        if p is not None:
            if isinstance(arg(vals, 1), str):
                p.name = arg(vals, 1)
            if isinstance(arg(vals, 2), str):
                p.description = arg(vals, 2)

    H["RNA_def_property_ui_text"] = ui_text
    H["RNA_def_property_flag"] = lambda ip, vals, toks, pos: b.set_flag(prop_of(vals), flags_of(arg(vals, 1), "PROP_"), True)
    H["RNA_def_property_clear_flag"] = lambda ip, vals, toks, pos: b.set_flag(prop_of(vals), flags_of(arg(vals, 1), "PROP_"), False)

    def subtype(ip, vals, toks, pos):
        p = prop_of(vals)
        if p is not None:
            p.subtype, unit = b.subtype_unit(arg(vals, 1))
            if unit != "none":
                p.unit = unit

    H["RNA_def_property_subtype"] = subtype

    def array(ip, vals, toks, pos):
        p = prop_of(vals)
        n = ip.number(arg(vals, 1))
        if p is not None and isinstance(n, (int, float)):
            p.array = [int(n)] if n > 0 else []
        elif p is not None:
            ip.warn("array length not a constant", ip.src(pos))

    H["RNA_def_property_array"] = array

    def multi_array(ip, vals, toks, pos):
        p = prop_of(vals)
        dims = arg(vals, 2)
        if p is None:
            return
        if dims is None:
            return
        if isinstance(dims, list):
            nums = [ip.number(d) for d in dims]
            if all(isinstance(n, (int, float)) for n in nums):
                p.array = [int(n) for n in nums]
                return
        ip.warn("multi-array dimensions not constant", ip.src(pos))

    H["RNA_def_property_multi_array"] = multi_array

    def rng(attr_lo: str, attr_hi: str):
        def h(ip, vals, toks, pos):
            p = prop_of(vals)
            lo, hi = ip.number(arg(vals, 1)), ip.number(arg(vals, 2))
            if p is not None and lo is not None and hi is not None:
                setattr(p, attr_lo, float(lo))
                setattr(p, attr_hi, float(hi))
        return h

    H["RNA_def_property_range"] = rng("hard_min", "hard_max")
    H["RNA_def_property_ui_range"] = rng("soft_min", "soft_max")

    def maxlen(ip, vals, toks, pos):
        p = prop_of(vals)
        n = ip.number(arg(vals, 1))
        if p is not None and isinstance(n, (int, float)):
            p.max_length = int(n)

    H["RNA_def_property_string_maxlength"] = maxlen
    H["RNA_def_property_enum_items"] = lambda ip, vals, toks, pos: b.set_items(ip, prop_of(vals), arg(vals, 1))

    def struct_type(ip, vals, toks, pos):
        p = prop_of(vals)
        if p is not None:
            p.struct_type = b.struct_name(arg(vals, 1)) or p.struct_type

    H["RNA_def_property_struct_type"] = struct_type

    def struct_runtime(ip, vals, toks, pos):
        p = arg(vals, 1)
        if isinstance(p, RnaProperty):
            p.struct_type = b.struct_name(arg(vals, 2)) or p.struct_type

    H["RNA_def_property_struct_runtime"] = struct_runtime

    def srna(ip, vals, toks, pos):
        p = prop_of(vals)
        if p is not None:
            p.collection_srna = b.struct_name(arg(vals, 1))

    H["RNA_def_property_srna"] = srna

    def default(ip, vals, toks, pos):
        b.set_default(ip, prop_of(vals), arg(vals, 1))

    def array_default(ip, vals, toks, pos):
        v = arg(vals, 1)
        if isinstance(v, list):
            b.set_default(ip, prop_of(vals), _flatten(v))

    for t in ("boolean", "int", "float", "enum", "string"):
        H[f"RNA_def_property_{t}_default"] = default
    for t in ("boolean", "int", "float"):
        H[f"RNA_def_property_{t}_array_default"] = array_default

    def str_attr(attr: str, k: int = 1):
        def h(ip, vals, toks, pos):
            p = prop_of(vals)
            v = arg(vals, k)
            if p is not None and v is not None:
                setattr(p, attr, v if isinstance(v, str) else _name(v))
        return h

    H["RNA_def_property_editable_func"] = str_attr("editable_func")

    def sdna(ip, vals, toks, pos):
        b.apply_sdna(prop_of(vals), arg(vals, 1), arg(vals, 2))

    for t in ("boolean", "int", "float", "string", "enum", "pointer", "collection"):
        H[f"RNA_def_property_{t}_sdna"] = sdna
    H["RNA_def_property_boolean_negative_sdna"] = sdna
    H["RNA_def_property_enum_bitflag_sdna"] = sdna

    def bitset_sdna(ip, vals, toks, pos):
        n = ip.number(arg(vals, 4))
        b.apply_sdna(prop_of(vals), arg(vals, 1), arg(vals, 2), int(n) if isinstance(n, (int, float)) else 0)

    H["RNA_def_property_boolean_bitset_array_sdna"] = bitset_sdna

    def dyn_array(ip, vals, toks, pos):
        p = prop_of(vals)
        if p is not None and arg(vals, 1) is not None:
            p.dynamic_array = True

    H["RNA_def_property_dynamic_array_funcs"] = dyn_array

    def deprecated(ip, vals, toks, pos):
        p = prop_of(vals)
        if p is not None:
            p.deprecated = True

    H["RNA_def_property_deprecated"] = deprecated

    def enum_funcs_simple(ip, vals, toks, pos):
        p = prop_of(vals)
        if p is not None and arg(vals, 1) is not None:
            p.itemf = _name(arg(vals, 1))

    H["RNA_def_enum_funcs"] = enum_funcs_simple

    # ``RNA_def_property_<type>_funcs[_runtime](prop, get, set, ...)``: parameter names from the header.
    def funcs_handler(fname: str, params: list[str]):
        runtime = fname.endswith("_runtime")

        def h(ip, vals, toks, pos):
            p = prop_of(vals)
            if p is None:
                return
            by = {params[k]: vals[k] for k in range(min(len(params), len(vals)))}
            getter = next((by[k] for k in by if k in {"get", "getfunc", "getter", "get_func", "begin"}), None)
            setter = next((by[k] for k in by if k in {"set", "setfunc", "setter", "set_func"}), None)
            if getter is not None:
                p.getter = _name(getter)
            if setter is not None:
                p.setter = _name(setter)
            for k, v in by.items():
                if v is None:
                    continue
                if "item" in k and p.type == "enum":
                    p.itemf = _name(v)
                elif k in {"type_fn", "typef", "type"} and p.type == "pointer":
                    p.typef = _name(v)
                elif k == "poll" and p.type in {"pointer", "collection"}:
                    p.poll = _name(v)
                elif k == "length" and p.type != "string" and False:
                    pass
            if runtime and getter is not None and setter is None and p.type not in {"pointer", "collection"}:
                b.set_flag(p, ["PROP_EDITABLE"], False)
            if runtime and p.type in {"boolean", "int", "float"} and "array" in fname:
                pass
        return h

    for fname, params in b.decl_params.items():
        if re.match(r"RNA_def_property_\w+_funcs(_runtime)?$", fname) or fname in {
            "RNA_def_property_pointer_funcs", "RNA_def_property_collection_funcs"}:
            H[fname] = funcs_handler(fname, params)

    # -- functions

    def def_function(ip, vals, toks, pos):
        st = b.resolve_struct(arg(vals, 0), ip)
        name = arg(vals, 1)
        func = RnaFunction(identifier=name if isinstance(name, str) else "", c_function=_name(arg(vals, 2)) if arg(vals, 2) is not None else "",
                           src=ip.src(pos))
        if st is None:
            ip.warn("function on a struct the reader could not follow", ip.src(pos))
            return func
        if not isinstance(name, str):
            ip.warn("function identifier not a constant string", ip.src(pos))
            return func
        if any(f.identifier == name for f in st.functions):
            return func
        st.functions.append(func)
        return func

    H["RNA_def_function"] = def_function
    H["RNA_def_function_runtime"] = def_function

    def func_of(vals):
        f = arg(vals, 0)
        return f if isinstance(f, RnaFunction) else None

    def func_return(ip, vals, toks, pos):
        f, p = func_of(vals), arg(vals, 1)
        if f is not None and isinstance(p, RnaProperty):
            f.returns = p.identifier

    def func_output(ip, vals, toks, pos):
        p = arg(vals, 1)
        if isinstance(p, RnaProperty) and "output" not in p.parameter_flags:
            p.parameter_flags.append("output")

    def func_flag(ip, vals, toks, pos):
        f = func_of(vals)
        if f is not None:
            for n in flags_of(arg(vals, 1), "FUNC_"):
                fl = n[len("FUNC_"):].lower()
                if fl not in f.flags:
                    f.flags.append(fl)

    def func_desc(ip, vals, toks, pos):
        f = func_of(vals)
        if f is not None and isinstance(arg(vals, 1), str):
            f.description = arg(vals, 1)

    H["RNA_def_function_return"] = func_return
    H["RNA_def_function_output"] = func_output
    H["RNA_def_function_flag"] = func_flag
    H["RNA_def_function_ui_description"] = func_desc

    def param_flags(on: bool):
        def h(ip, vals, toks, pos):
            p = prop_of(vals)
            if p is None:
                return
            b.set_flag(p, flags_of(arg(vals, 1), "PROP_"), on)
            for n in flags_of(arg(vals, 2), "PARM_"):
                fl = n[len("PARM_"):].lower()
                if on and fl not in p.parameter_flags:
                    p.parameter_flags.append(fl)
                elif not on and fl in p.parameter_flags:
                    p.parameter_flags.remove(fl)
        return h

    H["RNA_def_parameter_flags"] = param_flags(True)
    H["RNA_def_parameter_clear_flags"] = param_flags(False)

    # -- global switches

    def animate(ip, vals, toks, pos):
        v = arg(vals, 0)
        b.animate = bool(v) if isinstance(v, (bool, int)) else True

    H["RNA_define_animate_sdna"] = animate
    for k in b.decl_params:
        if k.startswith(("RNA_define_", "RNA_def_")) and k not in H:
            H[k] = _noop
    return H


def _noop(ip, vals, toks, pos):
    return None


def _name(v: Any) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, FuncRef):
        return v.name
    if isinstance(v, Raw):
        return v.text
    if v is None:
        return ""
    return type(v).__name__


def _flatten(v: list[Any]) -> list[Any]:
    out = []
    for x in v:
        if isinstance(x, list):
            out += _flatten(x)
        else:
            out.append(x)
    return out
