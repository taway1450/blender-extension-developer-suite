"""``EnumPropertyItem`` arrays: ``{VALUE, "ID", ICON, "Name", "Description"}`` rows, item macros, terminators."""

from __future__ import annotations

from dataclasses import dataclass

from ctok import CFile, Tok, Tree, VarDef, eval_number, match_close, split_commas, string_value, tokens_text
from macro import expand

from common.model import EnumItem


@dataclass
class EnumArray:
    name: str
    items: list[EnumItem]
    raw_values: list[str]  # the value expression of each item, as written
    shared: bool  # a non-static array other files can use (``rna_enum_*``)
    src: str = ""
    dynamic_rows: int = 0  # rows the reader could not read


def _field_string(toks: list[Tok]) -> str | None:
    """A name/description/identifier field: string literals, ``N_("x")``, ``CTX_N_(ctx, "x")``; None for null."""
    if not toks:
        return ""
    if len(toks) == 1 and toks[0].text in {"nullptr", "NULL", "0"}:
        return None
    if toks[0].text in {"CTX_N_", "CTX_IFACE_", "CTX_TIP_"}:
        close = match_close(toks, 1)
        parts = split_commas(toks[2:close])
        toks = parts[-1] if parts else []
    return "".join(string_value(t.text) for t in toks if t.kind == "str")


def is_enum_item_var(var: VarDef) -> bool:
    return var.is_array and var.braced and "EnumPropertyItem" in var.type_text


def parse_items(tree: Tree, f: CFile, init: list[Tok], pos: int) -> tuple[list[EnumItem], list[str], int]:
    """The items of an item array's initializer tokens (macros expanded)."""
    toks = expand(init, lambda n: tree.macro(f, n, pos), set(), pos)
    consts = tree.constants(f)
    items: list[EnumItem] = []
    raws: list[str] = []
    skipped = 0
    for part in split_commas(toks):
        if not part:
            continue
        if part[0].text != "{":
            skipped += 1
            continue
        close = match_close(part, 0)
        fields = split_commas(part[1:close])
        if len(fields) < 2:
            if fields and tokens_text(fields[0]) in {"0", ""}:
                break
            skipped += 1
            continue
        while len(fields) < 5:
            fields.append([])
        ident = _field_string(fields[1])
        if ident is None:
            break  # terminator
        raw = tokens_text(fields[0])
        value = eval_number(raw, consts)
        icon = tokens_text(fields[2])
        items.append(
            EnumItem(
                identifier=ident,
                name=_field_string(fields[3]) or "",
                description=_field_string(fields[4]) or "",
                value=int(value) if isinstance(value, (int, float)) else None,
                icon=icon if icon not in {"0", "ICON_NONE"} else "",
            )
        )
        raws.append(raw)
    return items, raws, skipped


class EnumRegistry:
    """Item arrays by name: shared ones (any file) and each file's own."""

    def __init__(self, tree: Tree) -> None:
        self.tree = tree
        self.shared: dict[str, EnumArray] = {}
        self._local: dict[tuple[str, str], EnumArray | None] = {}
        self.warnings: list[str] = []
        self.global_vars: dict[str, tuple[CFile, VarDef]] = {}

    def scan(self, f: CFile) -> None:
        """Register the shared arrays of ``f``."""
        for name, var in f.variables.items():
            if var.braced and not var.is_static and not is_enum_item_var(var):
                self.global_vars.setdefault(name, (f, var))
            if is_enum_item_var(var) and not var.is_static and name not in self.shared:
                arr = self.parse(f, var)
                if arr is not None:
                    self.shared[name] = arr

    def parse(self, f: CFile, var: VarDef) -> EnumArray | None:
        key = (f.rel, var.name)
        if key in self._local:
            return self._local[key]
        items, raws, skipped = parse_items(self.tree, f, var.init, var.pos)
        arr = EnumArray(var.name, items, raws, not var.is_static, f.src(var.pos), skipped)
        if skipped:
            self.warnings.append(f"{f.src(var.pos)}: {var.name}: {skipped} rows not read")
        self._local[key] = arr
        return arr

    def lookup(self, name: str, f: CFile) -> EnumArray | None:
        var = f.variables.get(name)
        if var is not None and is_enum_item_var(var):
            return self.parse(f, var)
        return self.shared.get(name)
