"""Area 1: RNA from ``makesrna/intern/rna_*.cc`` (definition half), run in makesrna's own order."""

from __future__ import annotations

from typing import Any

from common.model import SourceModel
from ctok import CFile, FuncDef, Tok, Tree, VarDef, eval_number, split_commas, tokens_text
from enums import EnumRegistry, is_enum_item_var, parse_items, EnumArray
from interp import MISSING, Interp
from rnadef import BRNA, RnaBuilder, make_handlers

RNA_DIR = "source/blender/makesrna/intern"
SKIP = {"rna_access.cc", "rna_access_compare_override.cc", "rna_define.cc", "rna_path.cc", "makesrna.cc",
        "makesrna_utils.cc", "makesrna_test.cc"}


def make_global_lookup(tree: Tree, enums: EnumRegistry, ip: Interp):
    cache: dict[tuple[str, str], Any] = {}

    def lookup(name: str, f: CFile) -> Any:
        key = (f.rel, name)
        if key in cache:
            return cache[key]
        var = f.variables.get(name)
        value: Any = MISSING
        if var is not None:
            if is_enum_item_var(var):
                value = enums.parse(f, var)
            elif var.braced and var.is_array:
                if _numeric_type(var):
                    value = _number_list(tree, f, var)
                else:
                    value = ip.array_init(var.type_toks, var.init, f)
            elif not var.braced and len(var.init) >= 1 and all(t.kind == "str" for t in var.init):
                value = ip.concat(var.init) if ip.frames else MISSING
        if value is MISSING and name in enums.shared:
            value = enums.shared[name]
        if value is MISSING and name in enums.global_vars:
            gf, gvar = enums.global_vars[name]
            if gvar.is_array:
                value = _number_list(tree, gf, gvar) if _numeric_type(gvar) else ip.array_init(gvar.type_toks, gvar.init, gf)
        cache[key] = value
        return value

    return lookup


NUMERIC = {"float", "int", "short", "char", "double", "bool", "uint", "uchar", "int8_t", "uint8_t", "int16_t",
           "uint16_t", "int32_t", "uint32_t", "int64_t", "uint64_t", "size_t", "ushort"}


def _numeric_type(var: VarDef) -> bool:
    return any(t.text in NUMERIC for t in var.type_toks) and not any(t.text == "*" for t in var.type_toks)


def _number_list(tree: Tree, f: CFile, var: VarDef) -> Any:
    consts = tree.constants(f)
    out: list[Any] = []
    for part in split_commas(var.init):
        if part and part[0].text == "{":
            inner = part[1:-1]
            row = [eval_number(tokens_text(p), consts) for p in split_commas(inner)]
            out.append(row)
        else:
            out.append(eval_number(tokens_text(part), consts))
    return out


def make_initializer_hook(tree: Tree, enums: EnumRegistry):
    def hook(ip: Interp, type_toks: list[Tok], name: str, inner: list[Tok], is_array: bool) -> Any:
        if is_array and any(t.text == "EnumPropertyItem" for t in type_toks):
            items, raws, skipped = parse_items(tree, ip.file, inner, inner[0].pos if inner else 0)
            if skipped:
                ip.warn("local enum rows not read", ip.file.src(inner[0].pos))
            return EnumArray(name, items, raws, False, ip.file.src(inner[0].pos) if inner else "")
        if is_array:
            return ip.array_init(type_toks, inner)
        return MISSING

    return hook


def rna_files(tree: Tree) -> list[str]:
    files = [r for r in tree.glob(f"{RNA_DIR}/rna_*.cc") if r.rsplit("/", 1)[-1] not in SKIP]
    files += tree.glob(f"{RNA_DIR}/*.hh")
    return files


def build_rna(tree: Tree, model: SourceModel) -> tuple[RnaBuilder, Interp, EnumRegistry]:
    enums = EnumRegistry(tree)
    builder = RnaBuilder(tree, model.structs, enums)
    handlers = make_handlers(builder)
    names = set(handlers)

    def relevant(fd: FuncDef) -> bool:
        for t in fd.body:
            if t.kind == "id" and t.text in names and t.text.startswith("RNA_def"):
                return True
        return False

    ip = Interp(tree, handlers, relevant)
    ip.global_lookup = make_global_lookup(tree, enums, ip)
    handlers["__initializer__"] = make_initializer_hook(tree, enums)
    files = [tree.file(r) for r in rna_files(tree)]
    for f in files:
        enums.scan(f)
        ip.add_file(f)
    enums.scan(tree.file(f"{RNA_DIR}/rna_define.cc"))  # rna_matrix_dimsize_4x4 and friends
    ip.compute_relevance()
    return builder, ip, enums


def process_items(tree: Tree) -> list[str]:
    """The ``RNA_def_*`` entry points in makesrna's order (``PROCESS_ITEMS`` in ``makesrna.cc``)."""
    f = tree.file(f"{RNA_DIR}/makesrna.cc")
    var = f.variables.get("PROCESS_ITEMS")
    out = []
    if var is None:
        return out
    for part in split_commas(var.init):
        if part and part[0].text == "{":
            fields = split_commas(part[1:-1])
            if len(fields) >= 3 and fields[2]:
                out.append(fields[2][-1].text)
    return out


def extract_rna(tree: Tree, model: SourceModel) -> tuple[RnaBuilder, Interp, EnumRegistry]:
    builder, ip, enums = build_rna(tree, model)
    brna = BRNA()
    for entry in process_items(tree):
        fd = ip.lookup_function(entry, None)
        if fd is None:
            ip.warn("makesrna entry point not found", entry)
            continue
        ip.run(fd, [brna])
    return builder, ip, enums
