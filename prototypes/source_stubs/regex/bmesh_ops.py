"""Area 6: bmesh operators from ``source/blender/bmesh/intern/bmesh_opdefines.cc`` (as ``rst_from_bmesh_opdefines.py``).

Each ``static BMOpDefine bmo_*_def = {"name", {in slots}, {out slots}, init, exec, flags}`` gives the operator; a slot
row is ``{"name", BMO_OP_SLOT_<TYPE>, {subtype}, enum items}``. The subtype is evaluated from the ``BM_*`` /
``BMO_OP_SLOT_SUBTYPE_*`` names (element kinds, single element, map value type, pointer type, int enum / flag).
Docs are the comments of the raw text: the block above the definition (the operator) and the one above each row.
Only the operators listed in ``bmo_opdefines[]`` are exposed to Python (``bmesh.ops``).
"""

from __future__ import annotations

import re
from typing import Any

from common.model import BmeshOp, BmeshSlot, SourceModel
from ctok import CFile, Tok, Tree, match_close, split_commas, string_value

REL = "source/blender/bmesh/intern/bmesh_opdefines.cc"
ELEM = {"BM_VERT": "vert", "BM_EDGE": "edge", "BM_FACE": "face", "BM_LOOP": "loop",
        "BMO_OP_SLOT_SUBTYPE_ELEM_VERT": "vert", "BMO_OP_SLOT_SUBTYPE_ELEM_EDGE": "edge",
        "BMO_OP_SLOT_SUBTYPE_ELEM_FACE": "face", "BMO_OP_SLOT_SUBTYPE_ELEM_IS_SINGLE": "single"}
_COMMENT = re.compile(r"/\*(.*?)\*/|//([^\n]*)", re.S)


def _clean_comment(text: str) -> str:
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("*"):
            line = line[1:]
            if line.startswith(" "):
                line = line[1:]
        lines.append(line.rstrip())
    out = "\n".join(lines).strip()
    if out.startswith('"""') and out.endswith('"""'):
        out = out[3:-3].strip()
    return out


class BmeshReader:
    def __init__(self, tree: Tree, model: SourceModel, extra: dict[str, Any]) -> None:
        self.tree = tree
        self.model = model
        self.extra = extra
        self.f: CFile = tree.file(REL)
        self.raw_lines = (tree.root / REL).read_text(encoding="utf-8", errors="replace").splitlines()
        self.enums: dict[str, list[str]] = {}
        self.enum_slots: dict[str, list[str]] = {}

    def comment_above(self, line: int, stop: int) -> str:
        """The comment ending on the lines right above 1-based ``line`` (not above ``stop``)."""
        k = line - 2
        while k >= 0 and not self.raw_lines[k].strip():
            k -= 1
        if k < 0 or k < stop - 1:
            return ""
        end_line = self.raw_lines[k].rstrip()
        if end_line.lstrip().startswith("//"):
            parts = []
            while k >= 0 and self.raw_lines[k].lstrip().startswith("//"):
                parts.insert(0, self.raw_lines[k].lstrip()[2:].strip())
                k -= 1
            return "\n".join(parts).strip()
        if not end_line.endswith("*/"):
            return ""
        j = k
        while j >= 0 and "/*" not in self.raw_lines[j]:
            j -= 1
        if j < stop - 1:
            return ""
        text = "\n".join(self.raw_lines[j : k + 1])
        m = _COMMENT.search(text)
        return _clean_comment(m.group(1)) if m and m.group(1) is not None else ""

    def read_enums(self) -> None:
        for name, var in self.f.variables.items():
            if "BMO_FlagSet" in var.type_text and var.braced:
                ids = []
                for part in split_commas(var.init):
                    if part and part[0].text == "{":
                        fields = split_commas(part[1 : match_close(part, 0)])
                        if len(fields) >= 2 and fields[1] and fields[1][0].kind == "str":
                            ids.append(string_value(fields[1][0].text))
                self.enums[name] = ids

    def slot(self, op: str, row: list[list[Tok]], stop_line: int) -> BmeshSlot | None:
        if not row or not row[0] or row[0][0].kind != "str":
            return None
        name = string_value(row[0][0].text)
        if not name:
            return None
        typ = ""
        if len(row) > 1:
            ids = [t.text for t in row[1] if t.kind == "id"]
            typ = ids[-1].removeprefix("BMO_OP_SLOT_").lower() if ids else ""
            typ = {"element_buf": "elem_buf"}.get(typ, typ)
        sub: list[str] = []
        if len(row) > 2:
            for t in row[2]:
                if t.kind != "id":
                    continue
                if t.text in ELEM:
                    sub.append(ELEM[t.text])
                elif t.text.startswith("BMO_OP_SLOT_SUBTYPE_"):
                    rest = t.text.removeprefix("BMO_OP_SLOT_SUBTYPE_")
                    for prefix in ("MAP_", "PTR_", "INT_"):
                        if rest.startswith(prefix):
                            sub.append(rest[len(prefix):].lower())
        items: list[str] = []
        if len(row) > 3:
            items_var = next((t.text for t in row[3] if t.kind == "id"), "")
            if items_var in self.enums:
                items = self.enums[items_var]
                self.enum_slots[f"{op}.{name}"] = items
        line = self.f.line(row[0][0].pos)
        return BmeshSlot(name=name, type=typ, subtype="|".join(sub), doc=self.comment_above(line, stop_line), items=items)

    def slots(self, op: str, toks: list[Tok], stop_line: int) -> list[BmeshSlot]:
        out = []
        if not toks or toks[0].text != "{":
            return out
        inner = toks[1 : match_close(toks, 0)]
        prev = stop_line
        for part in split_commas(inner):
            if not part or part[0].text != "{":
                continue
            row = split_commas(part[1 : match_close(part, 0)])
            s = self.slot(op, row, prev)
            if s is not None:
                out.append(s)
            prev = self.f.line(part[-1].pos) + 1
        return out

    def run(self) -> None:
        self.read_enums()
        exposed: list[str] = []
        var = self.f.variables.get("bmo_opdefines")
        if var is not None:
            exposed = [t.text for t in var.init if t.kind == "id"]
        defs = {name: v for name, v in self.f.variables.items() if "BMOpDefine" in v.type_text and v.braced and name != "bmo_opdefines"}
        order = exposed or list(defs)
        prev_end = 0
        for name in order:
            v = defs.get(name)
            if v is None:
                continue
            parts = split_commas(v.init)
            if not parts or not parts[0] or parts[0][0].kind != "str":
                continue
            opname = string_value(parts[0][0].text)
            line = self.f.line(v.pos)
            op = BmeshOp(name=opname, doc=self.comment_above(line, 0), src=self.f.src(v.pos))
            if len(parts) > 1:
                op.inputs = self.slots(opname, parts[1], line)
            if len(parts) > 2:
                op.outputs = self.slots(opname, parts[2], self.f.line(parts[1][-1].pos) if parts[1] else line)
            self.model.bmesh_ops.append(op)
        self.extra["bmesh_enum_slots"] = self.enum_slots
        self.extra["bmesh_ops_not_exposed"] = sorted(set(defs) - set(exposed)) if exposed else []


def extract_bmesh(tree: Tree, model: SourceModel, extra: dict[str, Any] | None = None) -> None:
    BmeshReader(tree, model, extra if extra is not None else {}).run()
