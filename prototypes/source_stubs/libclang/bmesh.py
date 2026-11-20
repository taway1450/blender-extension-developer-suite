"""bmesh operators: the ``BMOpDefine`` globals of ``bmesh_opdefines.cc``.

The initializers arrive mapped to ``BMOpDefine`` / ``BMOSlotType`` field names; slot types and element subtypes are
enum constants (``BMO_OP_SLOT_ELEMENT_BUF``, ``BM_VERT | BM_EDGE`` through the file's casting macros) whose names
the lowering keeps. Comments are not part of clang's AST, so the docs (the comment block before each define and the
comment before each slot) are read from the source text at the positions the AST gives.
"""

from __future__ import annotations

import re
from pathlib import Path

from common.model import BmeshOp, BmeshSlot

from .interp import Interp

_SLOT_DOC = re.compile(r'/\*((?:[^*]|\*(?!/))*)\*/\s*\{\s*"(\w+)"')


def _clean_comment(text: str) -> str:
    lines = [ln.strip().lstrip("*").strip() for ln in text.strip().splitlines()]
    return "\n".join(ln for ln in lines).strip()


def _names(v) -> list[str]:
    return sorted(getattr(v, "names", ()) or ())


def _slot_type(v) -> str:
    for n in _names(v):
        if n.startswith("BMO_OP_SLOT_"):
            return {"ELEMENT_BUF": "elem_buf"}.get(n[12:], n[12:].lower())
    return ""


def _subtype(v) -> str:
    if isinstance(v, dict):
        vals = [x for k, x in v.items() if k != "__record__"]
        v = vals[0] if vals else None
    names = _names(v)
    elems = [n[3:].lower() for n in names if n in ("BM_VERT", "BM_EDGE", "BM_FACE")]
    if elems:
        return "|".join(e for e in ("vert", "edge", "face") if e in elems)
    for n in names:
        if n.startswith("BMO_OP_SLOT_SUBTYPE_"):
            return n.split("_")[-1].lower()
    return ""


def _items(interp: Interp, v) -> list[str]:
    """Identifiers of a slot's ``BMO_FlagSet`` array (``{value, "IDENTIFIER"}`` rows ending in ``{0, nullptr}``)."""
    from .interp import GlobalRef

    if isinstance(v, GlobalRef):
        v = interp.global_value(v.usr, v.name)
    if not isinstance(v, list):
        return []
    out = []
    for row in v:
        ident = row.get("identifier") if isinstance(row, dict) else None
        if not isinstance(ident, str):
            break
        out.append(ident)
    return out


def read_bmesh(interp: Interp, source: Path, model) -> None:
    text_cache: dict[str, list[str]] = {}
    for usr, g in interp.p.globals.items():
        if g["record"] != "BMOpDefine" or g["type"].endswith("*"):
            continue
        value = interp.global_value(usr, g["name"])
        if not isinstance(value, dict) or not isinstance(value.get("opname"), str):
            continue
        lines = text_cache.setdefault(g["file"], (source / g["file"]).read_text(errors="replace").splitlines())
        start = g["line"] - 1
        # The doc comment ends right above the define.
        doc = ""
        j = start - 1
        if j >= 0 and lines[j].strip().endswith("*/"):
            k = j
            while k >= 0 and "/*" not in lines[k]:
                k -= 1
            doc = _clean_comment("\n".join(lines[k : j + 1]).replace("/*", "").replace("*/", ""))
        end = start
        while end < len(lines) and not lines[end].startswith("};"):
            end += 1
        body = "\n".join(lines[start : end + 1])
        slot_docs = {m.group(2): _clean_comment(m.group(1)) for m in _SLOT_DOC.finditer(body)}
        op = BmeshOp(name=value["opname"], doc=doc, src=f"{g['file']}:{g['line']}")
        for key, out in (("slot_types_in", op.inputs), ("slot_types_out", op.outputs)):
            slots = value.get(key)
            if not isinstance(slots, list):
                continue
            for s in slots:
                if not isinstance(s, dict) or not isinstance(s.get("name"), str) or not s["name"]:
                    break
                out.append(BmeshSlot(name=s["name"], type=_slot_type(s.get("type")),
                                     subtype=_subtype(s.get("subtype")), doc=slot_docs.get(s["name"], ""),
                                     items=_items(interp, s.get("enum_flags"))))
        model.bmesh_ops.append(op)
