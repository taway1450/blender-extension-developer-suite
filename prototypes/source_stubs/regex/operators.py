"""Area 2: operators defined in C (``void X_OT_y(wmOperatorType *ot)``) and macro operators.

Each ``*_OT_*`` function is executed with ``ot`` bound to a fresh operator: ``ot->name/idname/description/flag``
and the callbacks set are recorded; properties come from the same ``RNA_def_*`` handlers as RNA, on ``ot->srna``,
including those the shared helpers add (``WM_operator_properties_filesel(ot, ...)`` is followed with its flag
arguments, so only the properties its constants select are kept).
"""

from __future__ import annotations

import re
from typing import Any

from common.model import Operator, RnaProperty, SourceModel
from ctok import FuncDef, Tree
from enums import EnumRegistry
from interp import MISSING, Interp, Raw, flags_of
from rna_area import make_global_lookup, make_initializer_hook
from rnadef import OpH, OpSrna, RnaBuilder, make_handlers

OT_RE = re.compile(r"^[A-Z][A-Z0-9_]*_OT_\w+$")


def operator_files(tree: Tree) -> list[str]:
    out = []
    root = tree.root
    for top in ("source/blender", "intern/cycles/blender"):
        base = root / top
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.cc")):
            rel = path.relative_to(root).as_posix()
            if "/makesrna/" in rel or "/tests/" in rel or rel.endswith("_test.cc"):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "wmOperatorType" in text:
                out.append(rel)
    return out


def extract_operators(tree: Tree, model: SourceModel, state: dict[str, Any]) -> Interp:
    enums: EnumRegistry = state.get("enums") or EnumRegistry(tree)
    builder: RnaBuilder = state.get("builder") or RnaBuilder(tree, [], enums)
    state.setdefault("enums", enums)
    state.setdefault("builder", builder)
    handlers = make_handlers(builder)
    names = {n for n in handlers if n.startswith("RNA_def")}

    def relevant(fd: FuncDef) -> bool:
        if any("wmOperatorType" in p.type for p in fd.params):
            return True
        for t in fd.body:
            if t.kind == "id" and t.text in names:
                return True
        return False

    ip = Interp(tree, handlers, relevant)
    ip.global_lookup = make_global_lookup(tree, enums, ip)
    handlers["__initializer__"] = make_initializer_hook(tree, enums)

    def compound(ip_: Interp, target: Any, member: str, op: str, value: Any, toks: Any) -> None:
        if isinstance(target, OpH):
            target.compound(member, op, value if not isinstance(value, (int, float)) else Raw(toks, ip_.file))

    handlers["__compound__"] = compound
    ops: dict[str, Operator] = {}
    order: list[str] = []

    def new_op(idname: str, src: str) -> Operator:
        op = Operator(idname=idname, src=src)
        return op

    # Macro operators: ``ot = WM_operatortype_append_macro("MESH_OT_x", "Name", "Desc", OPTYPE_...)``
    def append_macro(ip_: Interp, vals: list[Any], toks: Any, pos: int) -> Any:
        idname = vals[0] if vals and isinstance(vals[0], str) else ""
        op = new_op(idname, ip_.src(pos))
        if len(vals) > 1 and isinstance(vals[1], str):
            op.name = vals[1]
        if len(vals) > 2 and isinstance(vals[2], str):
            op.description = vals[2]
        if len(vals) > 3:
            op.flags = [f[len("OPTYPE_"):].lower() for f in flags_of(vals[3], "OPTYPE_")] + ["macro"]
        if idname and idname not in ops:
            ops[idname] = op
            order.append(idname)
        return OpH(op, builder)

    def macro_define(ip_: Interp, vals: list[Any], toks: Any, pos: int) -> Any:
        oth, sub = (vals + [None, None])[:2]
        if isinstance(oth, OpH) and isinstance(sub, str):
            if not any(p.identifier == sub for p in oth.op.properties):
                p = RnaProperty(identifier=sub, type="pointer", struct_type=sub, src=ip_.src(pos))
                p.flags = []
                p._final = True  # type: ignore[attr-defined]
                p.readonly = True
                oth.op.properties.append(p)
        return Raw([], ip_.file)

    handlers["WM_operatortype_append_macro"] = append_macro
    handlers["WM_operatortype_macro_define"] = macro_define

    files = [tree.file(r) for r in operator_files(tree)]
    for f in files:
        enums.scan(f)
        ip.add_file(f)
    ip.compute_relevance()

    for f in files:
        for name, defs in f.functions.items():
            for fd in defs:
                if OT_RE.match(name) and fd.params and "wmOperatorType" in fd.params[0].type:
                    op = new_op(name, f.src(fd.pos))
                    ip.run(fd, [OpH(op, builder)])
                    idname = op.idname or name
                    op.idname = idname
                    if "_OT_" not in idname:
                        ip.warn("operator idname without _OT_", idname)
                    if idname in ops:
                        continue
                    ops[idname] = op
                    order.append(idname)
                elif any(t.text == "WM_operatortype_append_macro" for t in fd.body):
                    ip.run(fd, [])
    model.operators.extend(ops[i] for i in order)
    state["op_interp"] = ip
    return ip
