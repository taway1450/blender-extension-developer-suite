"""RNA definitions: the ``RNA_def_*`` primitives as intrinsics of the interpreter.

Only the primitives that write a struct/property/function are intrinsics (``RNA_def_struct*``,
``RNA_def_property*``, ``RNA_def_function*``, ``RNA_def_parameter*``, ``RNA_def_enum_funcs``); the convenience
helpers (``RNA_def_float_vector``, ``RNA_def_enum``, ``RNA_def_pointer_runtime``, ``RNA_def_node_enum``...) are run
from their own bodies in ``rna_define.cc`` / ``node_rna_define.cc``, so their argument order, the subtype they pick
and the defaults they apply come from the source, not from a table.

makesrna also reads SDNA: ``RNA_def_property_float_sdna(prop, nullptr, "loc")`` makes ``location`` an array of 3
because ``Object::loc`` is ``float[3]``; the lowering records the DNA structs' fields from clang's AST so the same
inference runs here (array length, string max length, pointer struct type).
"""

from __future__ import annotations

import math

from common.model import EnumItem, Operator, RnaFunction, RnaProperty, RnaStruct

from .interp import UNKNOWN, Flag, FuncRef, GlobalRef, Interp, Obj

UNITS = {
    1: "length",
    2: "area",
    3: "volume",
    4: "mass",
    5: "rotation",
    6: "time",
    7: "time_absolute",
    8: "velocity",
    9: "acceleration",
    10: "camera",
    11: "power",
    12: "temperature",
    13: "wavelength",
    14: "color_temperature",
    15: "frequency",
}
TYPES = {
    "PROP_BOOLEAN": "boolean",
    "PROP_INT": "int",
    "PROP_FLOAT": "float",
    "PROP_STRING": "string",
    "PROP_ENUM": "enum",
    "PROP_POINTER": "pointer",
    "PROP_COLLECTION": "collection",
}
TYPE_VALUES = {0: "boolean", 1: "int", 2: "float", 3: "string", 4: "enum", 5: "pointer", 6: "collection"}


def _names(value, prefix: str) -> list[str]:
    names = getattr(value, "names", None)
    if not names:
        return []
    return sorted(n[len(prefix) :].lower() for n in names if n.startswith(prefix))


def _str(value) -> str:
    return value if isinstance(value, str) else ""


def _num(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)) and not (isinstance(value, float) and (math.isinf(value) or math.isnan(value))):
        return float(value) if isinstance(value, float) else int(value)
    if isinstance(value, float):
        return value
    return None


def func_name(value) -> str:
    if isinstance(value, FuncRef):
        return value.name
    if isinstance(value, str):
        return value
    return ""


def struct_identifier(value) -> str:
    """``&RNA_Object`` / a struct handle / ``"Object"`` -> ``Object``."""
    if isinstance(value, Obj) and value.kind == "struct":
        data = value.data
        return data.identifier if isinstance(data, RnaStruct) else ""
    if isinstance(value, GlobalRef) and value.name.startswith("RNA_"):
        return value.name[4:]
    if isinstance(value, str):
        return value
    return ""


class Rna:
    def __init__(self, interp: Interp, model) -> None:
        self.i = interp
        self.model = model
        self.structs: dict[str, RnaStruct] = {}
        self.handles: dict[str, Obj] = {}
        self.dna_of: dict[str, str] = {}  # struct identifier -> DNA struct name
        self.prop_extra: dict[int, dict] = {}  # id(prop) -> raw default / dna facts resolved at the end
        self.animate = True
        self.operators: dict[str, Operator] = {}
        self.op_handles: dict[str, Obj] = {}
        self.dynamic_props = 0
        self.register()

    # ----------------------------------------------------------------------------------------------------------------
    def struct_handle(self, identifier: str, base: str = "", src: str = "") -> Obj:
        if identifier in self.handles:
            h = self.handles[identifier]
            if base and not h.data.base:
                h.data.base = base
            return h
        s = RnaStruct(identifier=identifier, base=base, src=src)
        self.structs[identifier] = s
        self.model.structs.append(s)
        h = Obj("struct", s)
        self.handles[identifier] = h
        if identifier in self.i.p.dna:
            self.dna_of[identifier] = identifier
            s.dna = identifier
        return h

    def operator_handle(self, idname: str, src: str) -> Obj:
        if idname in self.op_handles:
            return self.op_handles[idname]
        op = Operator(idname=idname, src=src)
        self.operators[idname] = op
        self.model.operators.append(op)
        srna = Obj("struct", op)
        h = Obj("optype", op, {"srna": srna, "idname": idname})
        self.op_handles[idname] = h
        return h

    def register(self) -> None:
        I = self.i.intrinsics
        for name in dir(self):
            if name.startswith("RNA_"):
                I[name] = getattr(self, name)
        self.i.methods["member:global"] = self.global_member

    def global_member(self, interp, base: GlobalRef, name: str, e):
        # ``RNA_Object.flag & STRUCT_ID``: whether a struct is an ID follows from its base chain.
        if name == "flag" and base.name.startswith("RNA_"):
            ident = base.name[4:]
            chain = set()
            while ident and ident not in chain:
                chain.add(ident)
                s = self.structs.get(ident)
                ident = s.base if s else ""
            return Flag(1 if "ID" in chain else 0, {"STRUCT_ID"} if "ID" in chain else set())
        return UNKNOWN

    # ----------------------------------------------------------------------------------------------------------------
    # Structs

    def RNA_def_struct(self, i, a, e, call):
        ident = _str(a[1]) if len(a) > 1 else ""
        if not ident:
            return UNKNOWN
        base = _str(a[2]) if len(a) > 2 else ""
        return self.struct_handle(ident, base, i.src(call[4]))

    def RNA_def_struct_ptr(self, i, a, e, call):
        ident = _str(a[1]) if len(a) > 1 else ""
        if not ident:
            return UNKNOWN
        return self.struct_handle(ident, struct_identifier(a[2]) if len(a) > 2 else "", i.src(call[4]))

    @staticmethod
    def _s(a) -> RnaStruct | None:
        if a and isinstance(a[0], Obj) and a[0].kind == "struct" and isinstance(a[0].data, RnaStruct):
            return a[0].data
        return None

    def RNA_def_struct_sdna(self, i, a, e, call):
        s = self._s(a)
        if s and isinstance(a[1], str):
            s.dna = a[1]
            self.dna_of[s.identifier] = a[1]

    def RNA_def_struct_sdna_from(self, i, a, e, call):
        s = self._s(a)
        if s and isinstance(a[1], str):
            s.dna = a[1]
            self.dna_of[s.identifier] = a[1]

    def RNA_def_struct_ui_text(self, i, a, e, call):
        s = self._s(a)
        if s:
            s.name = _str(a[1])
            s.description = _str(a[2]) if len(a) > 2 else ""

    def RNA_def_struct_name_property(self, i, a, e, call):
        s = self._s(a)
        if s and len(a) > 1 and isinstance(a[1], Obj) and a[1].kind == "prop":
            s.name_property = a[1].data.identifier

    def RNA_def_struct_nested(self, i, a, e, call):
        if len(a) > 2 and isinstance(a[1], Obj) and isinstance(a[1].data, RnaStruct):
            a[1].data.nested = _str(a[2])

    def RNA_def_struct_flag(self, i, a, e, call):
        s = self._s(a)
        if s:
            for n in _names(a[1], "STRUCT_"):
                if n not in s.flags:
                    s.flags.append(n)

    def RNA_def_struct_clear_flag(self, i, a, e, call):
        s = self._s(a)
        if s:
            for n in _names(a[1], "STRUCT_"):
                if n in s.flags:
                    s.flags.remove(n)

    def RNA_def_struct_refine_func(self, i, a, e, call):
        s = self._s(a)
        if s:
            s.refine = func_name(a[1])

    def RNA_def_struct_idprops_func(self, i, a, e, call):
        s = self._s(a)
        if s:
            s.idprops = True

    RNA_def_struct_system_idprops_func = RNA_def_struct_idprops_func

    def RNA_def_struct_register_funcs(self, i, a, e, call):
        s = self._s(a)
        if s:
            s.register = func_name(a[1])

    def RNA_def_struct_path_func(self, i, a, e, call):
        s = self._s(a)
        if s:
            s.path_func = func_name(a[1])

    RNA_def_struct_path_func_runtime = RNA_def_struct_path_func

    def RNA_def_struct_identifier(self, i, a, e, call):
        s = self._s(a)
        new = _str(a[-1])
        if s and new and new != s.identifier:
            old = s.identifier
            h = self.handles.pop(old, None)
            self.structs.pop(old, None)
            s.identifier = new
            if h is not None:
                self.handles[new] = h
            self.structs[new] = s

    def RNA_def_struct_ui_icon(self, i, a, e, call):
        pass

    # ----------------------------------------------------------------------------------------------------------------
    # Properties

    def _container(self, cont):
        if isinstance(cont, Obj):
            if cont.kind == "struct":
                return cont.data, cont.data.properties
            if cont.kind == "func":
                return cont.data, cont.data.parameters
            if cont.kind == "optype":
                return cont.data, cont.data.properties
        return None, None

    def RNA_def_property(self, i, a, e, call):
        ident = _str(a[1]) if len(a) > 1 else ""
        if not ident:
            self.dynamic_props += 1
            return UNKNOWN
        owner, plist = self._container(a[0])
        if plist is not None:
            for p in plist:
                if p.identifier == ident:
                    return Obj("prop", p, {"owner": owner})
        t = a[2] if len(a) > 2 else UNKNOWN
        names = getattr(t, "names", ())
        ptype = next((TYPES[n] for n in names if n in TYPES), None) or TYPE_VALUES.get(
            t if isinstance(t, int) else -1, "int"
        )
        sub = a[3] if len(a) > 3 else 0
        subnames = [n for n in getattr(sub, "names", ()) if n.startswith("PROP_")]
        subtype = subnames[0][5:].lower() if subnames else "none"
        unit = UNITS.get((int(sub) & 0x00FF0000) >> 16, "none") if isinstance(sub, int) else "none"
        p = RnaProperty(identifier=ident, type=ptype, subtype=subtype, unit=unit, src=i.src(call[4]))
        if subtype == "none" and any(n.startswith("PROP_UNIT_") for n in subnames):
            p.subtype = "none"
        if ptype not in ("pointer", "collection"):
            p.flags.append("editable")
            if ptype != "string" and self.animate:
                p.flags.append("animatable")
        if ptype == "string":
            p.flags.append("never_null")
            p.default = ""
        if ptype == "pointer":
            p.flags.append("thick_wrap")
        if i.speculative and getattr(owner, "idname", None) is None and not isinstance(owner, RnaFunction):
            pass
        if plist is not None:
            plist.append(p)
        else:
            self.dynamic_props += 1
        h = Obj("prop", p, {"owner": owner})
        if (
            isinstance(owner, RnaStruct)
            and i.where.startswith("source/blender/makesrna/intern/")
            and ptype != "collection"
        ):
            # makesrna's RNA_def_property looks the identifier up in the struct's DNA (silently).
            self._sdna(i, [h, None, None, 0], call, "enum" if ptype == "enum" else ptype)
        return h

    @staticmethod
    def _p(a) -> RnaProperty | None:
        if a and isinstance(a[0], Obj) and a[0].kind == "prop":
            return a[0].data
        return None

    def _extra(self, p: RnaProperty) -> dict:
        return self.prop_extra.setdefault(id(p), {"prop": p})

    def _sdna(self, i, a, call, kind: str):
        p = self._p(a)
        if p is None:
            return
        owner = a[0].fields.get("owner")
        structname = _str(a[1]) if len(a) > 1 else ""
        propname = _str(a[2]) if len(a) > 2 else ""
        if not structname and isinstance(owner, RnaStruct):
            structname = self.dna_of.get(owner.identifier, owner.dna or owner.identifier)
        propname = propname or p.identifier
        field = self.dna_field(structname, propname)
        if field is None:
            return
        _type, record, dims, level = field
        total = 1
        for d in dims:
            total *= d
        bit = a[3] if len(a) > 3 else 0
        # ``rna_def_property_sdna``: the DNA array length replaces the property's (none for a scalar member).
        if kind in ("int", "float") or (kind == "boolean" and not bit):
            p.array = [total] if total > 1 else []
        if kind == "string" and dims and p.max_length is None:
            p.max_length = total
        if (
            kind in ("pointer", "collection")
            and not p.struct_type
            and level >= 1
            and record not in ("ListBase", "void", "")
        ):
            self._extra(p)["dna_struct"] = record

    def dna_field(self, struct: str, path: str):
        fields = self.i.p.dna.get(struct)
        if fields is None:
            return None
        parts = path.replace("->", ".").split(".")
        cur = fields
        field = None
        for n, part in enumerate(parts):
            part = part.split("[")[0]
            field = cur.get(part)
            if field is None:
                return None
            if n < len(parts) - 1:
                cur = self.i.p.dna.get(field[1], {})
        if field is not None and "[" in path:
            return [field[0], field[1], [], field[3]]
        return field

    def RNA_def_property_boolean_sdna(self, i, a, e, call):
        self._sdna(i, a, call, "boolean")

    RNA_def_property_boolean_negative_sdna = RNA_def_property_boolean_sdna

    def RNA_def_property_boolean_bitset_array_sdna(self, i, a, e, call):
        p = self._p(a)
        if p is not None and len(a) > 4 and isinstance(a[4], int) and not p.array:
            p.array = [int(a[4])]

    def RNA_def_property_int_sdna(self, i, a, e, call):
        self._sdna(i, a, call, "int")

    def RNA_def_property_float_sdna(self, i, a, e, call):
        self._sdna(i, a, call, "float")

    def RNA_def_property_string_sdna(self, i, a, e, call):
        self._sdna(i, a, call, "string")

    def RNA_def_property_enum_sdna(self, i, a, e, call):
        self._sdna(i, a, call, "enum")

    def RNA_def_property_enum_bitflag_sdna(self, i, a, e, call):
        self._sdna(i, a, call, "enum_bitflag")

    def RNA_def_property_pointer_sdna(self, i, a, e, call):
        self._sdna(i, a, call, "pointer")

    def RNA_def_property_collection_sdna(self, i, a, e, call):
        self._sdna(i, a, call, "collection")

    def RNA_def_property_flag(self, i, a, e, call):
        p = self._p(a)
        if p is None:
            return
        for n in _names(a[1], "PROP_"):
            if n not in p.flags:
                p.flags.append(n)
            if n == "enum_flag":
                p.enum_flag = True
            if n == "never_null":
                p.never_null = True

    def RNA_def_property_clear_flag(self, i, a, e, call):
        p = self._p(a)
        if p is None:
            return
        for n in _names(a[1], "PROP_"):
            if n in p.flags:
                p.flags.remove(n)
            if n == "never_null":
                p.never_null = False
            if n == "enum_flag":
                p.enum_flag = False

    def RNA_def_parameter_flags(self, i, a, e, call):
        p = self._p(a)
        if p is None:
            return
        self.RNA_def_property_flag(i, a[:2], e, call)
        for n in _names(a[2] if len(a) > 2 else 0, "PARM_"):
            if n not in p.parameter_flags:
                p.parameter_flags.append(n)

    def RNA_def_parameter_clear_flags(self, i, a, e, call):
        p = self._p(a)
        if p is None:
            return
        self.RNA_def_property_clear_flag(i, a[:2], e, call)
        for n in _names(a[2] if len(a) > 2 else 0, "PARM_"):
            if n in p.parameter_flags:
                p.parameter_flags.remove(n)

    def RNA_def_property_subtype(self, i, a, e, call):
        p = self._p(a)
        if p is not None:
            names = [n for n in getattr(a[1], "names", ()) if n.startswith("PROP_")]
            if names:
                p.subtype = names[0][5:].lower()
            if isinstance(a[1], int):
                p.unit = UNITS.get((int(a[1]) & 0x00FF0000) >> 16, p.unit)

    def RNA_def_property_array(self, i, a, e, call):
        p = self._p(a)
        if p is None:
            return
        if isinstance(a[1], int) and not isinstance(a[1], bool):
            p.array = [int(a[1])] if a[1] else []
        else:
            p.dynamic_array = True

    def RNA_def_property_multi_array(self, i, a, e, call):
        p = self._p(a)
        if p is None:
            return
        dim = a[1] if isinstance(a[1], int) else 0
        dims = a[2] if len(a) > 2 else None
        if isinstance(dims, list) and dim:
            p.array = [int(x) for x in dims[:dim] if isinstance(x, int)]
        elif dims is None and p.array:
            pass
        else:
            p.dynamic_array = p.dynamic_array or not p.array

    def RNA_def_property_dynamic_array_funcs(self, i, a, e, call):
        p = self._p(a)
        if p is not None:
            p.dynamic_array = True

    def RNA_def_property_range(self, i, a, e, call):
        p = self._p(a)
        if p is not None:
            p.hard_min, p.hard_max = _num(a[1]), _num(a[2])

    def RNA_def_property_ui_range(self, i, a, e, call):
        p = self._p(a)
        if p is not None:
            p.soft_min, p.soft_max = _num(a[1]), _num(a[2])

    def RNA_def_property_enum_items(self, i, a, e, call):
        p = self._p(a)
        if p is None:
            return
        items = a[1]
        if isinstance(items, list):
            p.items = enum_items(items)
            name = i.global_names.get(id(items))
            if name:
                p.items_name = name
                self.model.enum_items.setdefault(name, p.items)
        elif items is None:
            p.items = []

    def RNA_def_property_string_maxlength(self, i, a, e, call):
        p = self._p(a)
        if p is not None and isinstance(a[1], int):
            p.max_length = int(a[1])

    def RNA_def_property_struct_type(self, i, a, e, call):
        p = self._p(a)
        if p is not None and isinstance(a[1], str):
            p.struct_type = a[1]

    def RNA_def_property_struct_runtime(self, i, a, e, call):
        # (cont, prop, type)
        if len(a) > 2 and isinstance(a[1], Obj) and a[1].kind == "prop":
            ident = struct_identifier(a[2])
            if ident:
                a[1].data.struct_type = ident

    def _default(self, i, a, e, call):
        p = self._p(a)
        if p is not None and len(a) > 1:
            v = a[1]
            if isinstance(v, (int, float, str, list)) and not isinstance(v, Flag) or isinstance(v, Flag):
                self._extra(p)["default"] = v

    RNA_def_property_boolean_default = _default
    RNA_def_property_int_default = _default
    RNA_def_property_float_default = _default
    RNA_def_property_enum_default = _default
    RNA_def_property_string_default = _default
    RNA_def_property_boolean_array_default = _default
    RNA_def_property_int_array_default = _default
    RNA_def_property_float_array_default = _default

    def RNA_def_property_ui_text(self, i, a, e, call):
        p = self._p(a)
        if p is not None:
            p.name = _str(a[1])
            p.description = _str(a[2]) if len(a) > 2 else ""

    def RNA_def_property_deprecated(self, i, a, e, call):
        p = self._p(a)
        if p is not None:
            p.deprecated = True

    def RNA_def_property_editable_func(self, i, a, e, call):
        p = self._p(a)
        if p is not None:
            p.editable_func = func_name(a[1])

    def RNA_def_property_pointer_funcs(self, i, a, e, call):
        p = self._p(a)
        if p is not None:
            p.getter = func_name(a[1])
            p.setter = func_name(a[2]) if len(a) > 2 else ""
            p.typef = func_name(a[3]) if len(a) > 3 else ""
            p.poll = func_name(a[4]) if len(a) > 4 else ""

    RNA_def_property_pointer_funcs_runtime = RNA_def_property_pointer_funcs

    def RNA_def_property_enum_funcs(self, i, a, e, call):
        p = self._p(a)
        if p is not None:
            p.getter = func_name(a[1])
            p.setter = func_name(a[2]) if len(a) > 2 else ""
            itemf = func_name(a[3]) if len(a) > 3 else ""
            if itemf:
                p.itemf = itemf

    def RNA_def_property_enum_funcs_runtime(self, i, a, e, call):
        self.RNA_def_property_enum_funcs(i, a, e, call)

    def RNA_def_enum_funcs(self, i, a, e, call):
        p = self._p(a)
        if p is not None and len(a) > 1 and func_name(a[1]):
            p.itemf = func_name(a[1])

    def _getset(self, i, a, e, call):
        p = self._p(a)
        if p is not None:
            p.getter = func_name(a[1]) if len(a) > 1 else ""
            p.setter = func_name(a[2]) if len(a) > 2 else ""

    RNA_def_property_boolean_funcs = _getset
    RNA_def_property_int_funcs = _getset
    RNA_def_property_float_funcs = _getset
    RNA_def_property_string_funcs = _getset
    RNA_def_property_boolean_funcs_runtime = _getset
    RNA_def_property_boolean_array_funcs_runtime = _getset
    RNA_def_property_int_funcs_runtime = _getset
    RNA_def_property_int_array_funcs_runtime = _getset
    RNA_def_property_float_funcs_runtime = _getset
    RNA_def_property_float_array_funcs_runtime = _getset
    RNA_def_property_string_funcs_runtime = _getset

    def RNA_def_property_collection_funcs(self, i, a, e, call):
        p = self._p(a)
        if p is not None:
            p.getter = func_name(a[1]) if len(a) > 1 else ""

    def RNA_def_property_srna(self, i, a, e, call):
        p = self._p(a)
        if p is not None and isinstance(a[1], str):
            p.collection_srna = a[1]

    def RNA_define_animate_sdna(self, i, a, e, call):
        if a and isinstance(a[0], int):
            self.animate = bool(a[0])

    # ----------------------------------------------------------------------------------------------------------------
    # Functions

    def RNA_def_function(self, i, a, e, call):
        s = self._s(a)
        ident = _str(a[1]) if len(a) > 1 else ""
        if not ident:
            return UNKNOWN
        if s is None:
            return Obj("func", RnaFunction(identifier=ident))
        for f in s.functions:
            if f.identifier == ident:
                return Obj("func", f)
        f = RnaFunction(identifier=ident, c_function=func_name(a[2]) if len(a) > 2 else "", src=i.src(call[4]))
        s.functions.append(f)
        return Obj("func", f)

    RNA_def_function_runtime = RNA_def_function

    @staticmethod
    def _f(a) -> RnaFunction | None:
        if a and isinstance(a[0], Obj) and a[0].kind == "func":
            return a[0].data
        return None

    def RNA_def_function_return(self, i, a, e, call):
        f = self._f(a)
        if f is not None and len(a) > 1 and isinstance(a[1], Obj) and a[1].kind == "prop":
            f.returns = a[1].data.identifier
            if "output" not in a[1].data.parameter_flags:
                a[1].data.parameter_flags.append("output")

    def RNA_def_function_output(self, i, a, e, call):
        if len(a) > 1 and isinstance(a[1], Obj) and a[1].kind == "prop" and "output" not in a[1].data.parameter_flags:
            a[1].data.parameter_flags.append("output")

    def RNA_def_function_flag(self, i, a, e, call):
        f = self._f(a)
        if f is not None:
            for n in _names(a[1], "FUNC_"):
                if n not in f.flags:
                    f.flags.append(n)

    def RNA_def_function_ui_description(self, i, a, e, call):
        f = self._f(a)
        if f is not None:
            f.description = _str(a[1])

    # ----------------------------------------------------------------------------------------------------------------
    def finish(self) -> None:
        """Resolve what needs all definitions: defaults (enum identifiers), DNA pointer types, readonly."""
        for extra in self.prop_extra.values():
            p = extra["prop"]
            if "dna_struct" in extra and not p.struct_type:
                dna = extra["dna_struct"]
                # makesrna looks the DNA type name up as an RNA struct identifier.
                p.struct_type = (
                    dna if dna in self.structs else next((s for s, d in self.dna_of.items() if d == dna), dna)
                )
            if "default" in extra:
                p.default = resolve_default(p, extra["default"], self.model.enum_items)
        for s in self.model.structs:
            for p in s.properties:
                finalize(p)
            for f in s.functions:
                for p in f.parameters:
                    finalize(p)
        for op in self.model.operators:
            for p in op.properties:
                finalize(p)
                implicit_default(p, self.model.enum_items)
        for s in self.model.structs:
            for f in s.functions:
                for p in f.parameters:
                    implicit_default(p, self.model.enum_items)


def finalize(p: RnaProperty) -> None:
    p.readonly = "editable" not in p.flags and not p.editable_func
    p.never_null = "never_null" in p.flags
    p.enum_flag = p.enum_flag or "enum_flag" in p.flags


def implicit_default(p: RnaProperty, shared) -> None:
    """Runtime RNA (operator properties, function parameters) has no DNA defaults: an unset default is zero."""
    if p.default is not None:
        return
    n = 1
    for d in p.array:
        n *= d
    if p.type in ("boolean", "int", "float") and not p.dynamic_array:
        zero = {"boolean": False, "int": 0, "float": 0.0}[p.type]
        p.default = [zero] * n if p.array else zero
    elif p.type == "enum" and not p.itemf:
        items = p.items or shared.get(p.items_name, [])
        if p.enum_flag:
            p.default = []
        elif items:
            p.default = next((i.identifier for i in items if i.value == 0), items[0].identifier)


def enum_items(values: list) -> list[EnumItem]:
    out = []
    for v in values:
        if not isinstance(v, dict):
            continue
        ident = v.get("identifier")
        if ident is None or ident is UNKNOWN:
            break  # the {0, nullptr, 0, nullptr, nullptr} terminator
        if ident == "" or not isinstance(ident, str):
            continue  # RNA_ENUM_ITEM_SEPR / HEADING
        icon = v.get("icon")
        icon_name = ""
        if isinstance(icon, Flag) and icon.names:
            icon_name = next(iter(icon.names)).removeprefix("ICON_")
        value = v.get("value")
        out.append(
            EnumItem(
                identifier=ident,
                name=_str(v.get("name")),
                description=_str(v.get("description")),
                value=int(value) if isinstance(value, int) else None,
                icon=icon_name,
            )
        )
    return out


def resolve_default(p: RnaProperty, raw, shared):
    if p.type == "enum":
        items = p.items or shared.get(p.items_name, [])
        if not isinstance(raw, int):
            return None
        if p.enum_flag:
            return sorted(i.identifier for i in items if i.value and (int(raw) & i.value) == i.value) if items else None
        for item in items:
            if item.value == int(raw):
                return item.identifier
        return None
    if p.type == "boolean":
        if isinstance(raw, list):
            return [bool(x) for x in raw if isinstance(x, (int, float))]
        return bool(raw) if isinstance(raw, (int, float)) else None
    if p.type in ("int", "float"):
        if isinstance(raw, list):
            vals = [(float(x) if p.type == "float" else int(x)) for x in raw if isinstance(x, (int, float))]
            return vals or None
        if isinstance(raw, (int, float)):
            value = float(raw) if p.type == "float" else int(raw)
            if p.array and not p.dynamic_array:  # ``static float4 color_default(1)``: the constructor broadcasts
                n = 1
                for d in p.array:
                    n *= d
                return [value] * n
            return value
        return None
    if p.type == "string":
        return raw if isinstance(raw, str) else None
    return None
