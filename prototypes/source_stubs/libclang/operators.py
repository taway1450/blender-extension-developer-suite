"""C operators: every ``void X_OT_y(wmOperatorType *ot)`` is run with ``ot`` bound to a fresh operator type.

Assignments to ``ot->name`` / ``idname`` / ``description`` / ``flag`` / callbacks fill the operator; RNA calls on
``ot->srna`` (or on ``ot`` passed to a helper such as ``WM_operator_properties_filesel``, followed through its body
in ``wm_operator_props.cc``) define its properties. Macro operators are read from the functions that call
``WM_operatortype_append_macro``: each ``WM_operatortype_macro_define(ot, "SUB_OT_x")`` step adds the pointer
property Blender adds for it (named after the sub-operator).
"""

from __future__ import annotations

import re

from common.model import Operator, RnaProperty

from .interp import UNKNOWN, Flag, FuncRef, Interp, Lambda, Obj
from .rna import Rna, finalize

CALLBACKS = ("exec", "invoke", "modal", "poll", "poll_property", "ui", "cancel", "check", "get_name",
             "get_description", "pyop_poll")
OT_NAME = re.compile(r"^[A-Z0-9_]+_OT_\w+$")


def _flags(value) -> list[str]:
    names = getattr(value, "names", None) or ()
    return sorted(n.removeprefix("OPTYPE_").lower() for n in names if n.startswith("OPTYPE_"))


class Operators:
    def __init__(self, interp: Interp, rna: Rna, model) -> None:
        self.i = interp
        self.rna = rna
        self.model = model
        interp.intrinsics["WM_operatortype_append_macro"] = self.append_macro
        interp.intrinsics["WM_operatortype_macro_define"] = self.macro_define
        for name in ("WM_operatortype_append", "WM_operatortype_append_ptr", "WM_operatortype_append_macro_ptr",
                     "WM_operatortype_find", "WM_operatortype_props_advanced_begin",
                     "WM_operatortype_props_advanced_end"):
            interp.intrinsics.setdefault(name, lambda i, a, e, c: UNKNOWN)

    def apply(self, op: Operator, h: Obj) -> None:
        f = h.fields
        if isinstance(f.get("idname"), str) and f["idname"] != op.idname:
            op.idname = f["idname"]
        if isinstance(f.get("name"), str):
            op.name = f["name"]
        if isinstance(f.get("description"), str):
            op.description = f["description"]
        if "flag" in f:
            op.flags = _flags(f["flag"])
        op.callbacks = [cb for cb in CALLBACKS if isinstance(f.get(cb), (FuncRef, Lambda))]

    def run(self) -> None:
        seen: set[str] = set()
        for fn in list(self.i.p.functions.values()):
            if not OT_NAME.match(fn.name) or len(fn.params) != 1 or "wmOperatorType" not in fn.params[0][1]:
                continue
            op = Operator(idname=fn.name, src=f"{fn.file}:{fn.line}")
            h = Obj("optype", op, {})
            h.fields["srna"] = Obj("struct", op)
            self.i.call_function(fn, [h])
            self.apply(op, h)
            if op.idname in seen or "_OT_" not in op.idname:
                continue
            seen.add(op.idname)
            self.model.operators.append(op)
        # Macro operators
        for fn in list(self.i.p.functions.values()):
            if self._calls(fn.body, "WM_operatortype_append_macro"):
                self.i.call_function(fn, [UNKNOWN] * len(fn.params))
        for op in self.model.operators:
            for p in op.properties:
                finalize(p)

    def _calls(self, body, name: str) -> bool:
        stack = [body]
        while stack:
            x = stack.pop()
            if isinstance(x, list):
                if len(x) > 2 and x[0] == "c" and x[2] == name:
                    return True
                stack.extend(y for y in x if isinstance(y, list))
        return False

    def append_macro(self, i, a, e, call):
        idname = a[0] if a and isinstance(a[0], str) else ""
        if not idname:
            return UNKNOWN
        for op in self.model.operators:
            if op.idname == idname:
                return Obj("optype", op, {"srna": Obj("struct", op)})
        op = Operator(idname=idname, name=a[1] if len(a) > 1 and isinstance(a[1], str) else "",
                      description=a[2] if len(a) > 2 and isinstance(a[2], str) else "",
                      flags=[*_flags(a[3] if len(a) > 3 else 0), "macro"], callbacks=["macro"], src=i.src(call[4]))
        self.model.operators.append(op)
        return Obj("optype", op, {"srna": Obj("struct", op)})

    def macro_define(self, i, a, e, call):
        if not a or not isinstance(a[0], Obj) or a[0].kind != "optype":
            return UNKNOWN
        op: Operator = a[0].data
        sub = a[1] if len(a) > 1 and isinstance(a[1], str) else ""
        if sub and not any(p.identifier == sub for p in op.properties):
            p = RnaProperty(identifier=sub, type="pointer", struct_type="OperatorProperties", src=i.src(call[4]),
                            flags=["editable"])
            op.properties.append(p)
        return Obj("macro", sub, {"ptr": UNKNOWN})
