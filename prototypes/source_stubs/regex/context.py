"""Area 4: context members (``bpy.context.<member>``) from the editors' context callbacks.

Members come from three shapes:

- ``if (CTX_data_equals(member, "active_object")) { ... }`` (with ``||`` alternatives) in ``*_context`` functions;
- ``map.add("scene", screen_ctx_scene)`` registries (the callback's body is the member's region);
- ``*_context_dir[] = {"scene", ...}`` tables (the member exists; its type comes from a region when there is one).

In a member's region, the setter calls give kind and type: ``CTX_data_id_pointer_set(result, &ob->id)`` /
``CTX_data_id_list_add(result, &base.object->id)`` type the member by the C type of the variable (declarations in the
function, range-for variables, DNA member chains), mapped to the RNA struct whose DNA is that type;
``CTX_data_pointer_set(result, id, &RNA_Foo, data)`` / ``CTX_data_list_add(.., &RNA_Foo, ..)`` name the struct;
``*_ptr`` variants and helpers take the ``&RNA_Foo`` named in the region. ``CTX_data_type_set(result,
ContextDataType::Collection)`` makes a collection, ``CTX_data_prop_set`` a property, and so on. Types are merged
across editors.
"""

from __future__ import annotations

from typing import Any

from common.model import ContextMember, SourceModel
from ctok import CFile, Tok, Tree, match_close, split_commas, string_value
from dna import Dna

POINTER_SETTERS = {"CTX_data_id_pointer_set", "CTX_data_pointer_set", "CTX_data_pointer_set_ptr"}
LIST_SETTERS = {"CTX_data_id_list_add", "CTX_data_list_add", "CTX_data_list_add_ptr"}
KIND_OF_TYPE = {"Pointer": "pointer", "Collection": "collection", "Property": "property", "String": "string",
                "Int64": "int"}
SKIP_IDS = {"id", "ID", "reinterpret_cast", "static_cast", "const_cast", "nullptr", "result", "C"}


def context_files(tree: Tree) -> list[str]:
    out = []
    for path in sorted((tree.root / "source/blender").rglob("*.cc")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "CTX_data_equals" in text or "_context_dir[]" in text or "bContextDataResult" in text:
            rel = path.relative_to(tree.root).as_posix()
            if rel.endswith("blenkernel/intern/context.cc") or "/python/" in rel:
                continue
            out.append(rel)
    return out


class ContextReader:
    def __init__(self, tree: Tree, model: SourceModel, state: dict[str, Any], extra: dict[str, Any]) -> None:
        self.tree = tree
        self.model = model
        self.extra = extra
        builder = state.get("builder")
        self.dna: Dna = builder.dna if builder is not None else Dna(tree)
        self.dna_to_rna: dict[str, str] = {}
        if builder is not None:
            for st in builder.struct_list:
                if not st.identifier:
                    continue
                dna = getattr(st, "_sdna_from", "") or st.dna
                if dna and (dna not in self.dna_to_rna or st.identifier == dna):
                    self.dna_to_rna[dna] = st.identifier
        self.rna_known = {st.identifier for st in builder.struct_list} if builder is not None else set()
        self.members: dict[str, ContextMember] = {}
        self.macro_lookup: Any = None
        self.id_codes = self.read_id_codes()
        self.unknown_types: list[str] = []

    def read_id_codes(self) -> dict[str, str]:
        """``ID_WO`` -> ``World``, from ``ID_code_to_RNA_type`` in rna_ID.cc."""
        out: dict[str, str] = {}
        try:
            f = self.tree.file("source/blender/makesrna/intern/rna_ID.cc", rna_runtime=True)
        except OSError:
            return out
        for fd in f.functions.get("ID_code_to_RNA_type", []):
            body = fd.body
            for k in range(len(body) - 4):
                if body[k].text == "case" and body[k + 2].text == ":" and body[k + 3].text == "return":
                    rna = [x.text for x in body[k + 4 : k + 7] if x.text.startswith("RNA_")]
                    if rna:
                        out[body[k + 1].text] = rna[0][4:]
        return out

    def member(self, name: str, f: CFile, pos: int) -> ContextMember:
        m = self.members.get(name)
        if m is None:
            m = ContextMember(name=name, types=[], kind="", src=f.src(pos))
            self.members[name] = m
        editor = f.rel.split("/")[-2] if "/" in f.rel else f.rel
        if editor not in m.editors:
            m.editors.append(editor)
        return m

    # -- type of a C expression

    def var_type(self, body: list[Tok], name: str, before: int) -> str:
        """The declared type of local ``name`` (``Object *ob``, ``Base &base``, ``Object *ob = ...``)."""
        found = ""
        for k in range(min(before, len(body)) - 1, 0, -1):
            t = body[k]
            if t.text != name or t.kind != "id":
                continue
            j = k - 1
            while j >= 0 and body[j].text in {"*", "&", "const"}:
                j -= 1
            if j < k - 1 or (j >= 0 and body[j].kind == "id" and body[j].text not in {"return", "else", "case"} and body[j + 1 :k] == []):
                if j >= 0 and body[j].kind == "id" and body[j].text not in {"return", "else", "case", "const", "auto"}:
                    nxt = body[k + 1].text if k + 1 < len(body) else ""
                    if nxt in {"=", ";", ",", ")", ":", "{"}:
                        found = body[j].text
                        break
        if not found:
            found = self.macro_var_type(body, name, before)
        return found

    def macro_var_type(self, body: list[Tok], name: str, before: int) -> str:
        """A variable declared by a macro: ``FOREACH_OBJECT_IN_MODE_BEGIN (..., ob_iter)`` -> ``Object``."""
        for k in range(min(before, len(body)) - 1, 0, -1):
            t = body[k]
            if t.kind == "id" and t.text.isupper() and k + 1 < len(body) and body[k + 1].text == "(":
                close = match_close(body, k + 1)
                if close > before or not any(x.text == name for x in body[k + 2 : close]):
                    continue
                f = body[k].file if hasattr(body[k], "file") else None
                lookup = self.macro_lookup
                if lookup is None:
                    return ""
                from macro import expand

                exp = expand(body[k : close + 1], lookup, set(), t.pos)
                for j in range(len(exp) - 2):
                    if exp[j + 2].text == name and exp[j + 1].text == "*" and exp[j].kind == "id":
                        return exp[j].text
        return ""

    def chain_type(self, body: list[Tok], chain: list[str], at: int) -> str:
        if not chain:
            return ""
        typ = self.var_type(body, chain[0], at)
        for part in chain[1:]:
            mem = self.dna.member(typ, part) if typ else None
            if mem is None:
                return ""
            typ = mem.type
        return typ

    def rna_of(self, ctype: str) -> str:
        if not ctype:
            return ""
        if ctype in self.dna_to_rna:
            return self.dna_to_rna[ctype]
        if ctype in self.rna_known:
            return ctype
        return ""

    def id_arg_type(self, body: list[Tok], arg: list[Tok], at: int) -> str:
        """``&ob->id`` / ``&base.object->id`` / ``(ID *)ob`` / ``reinterpret_cast<ID *>(ob)`` / ``ob ? &ob->id : nullptr``
        / ``snode->id``: the C type of the ID; "" when a call or an unknown variable is involved."""
        toks = list(arg)
        texts = [t.text for t in toks]
        if "?" in texts:
            q = texts.index("?")
            toks = toks[q + 1 :]
            texts = [t.text for t in toks]
            if ":" in texts:
                toks = toks[: texts.index(":")]
        # casts
        if toks and toks[0].text in {"reinterpret_cast", "static_cast"}:
            gt = next((j for j, t in enumerate(toks) if t.text == ">"), None)
            toks = toks[gt + 1 :] if gt is not None else toks
        while toks and toks[0].text == "(":
            close = match_close(toks, 0)
            inner = [t.text for t in toks[1:close]]
            if close == len(toks) - 1:
                toks = toks[1:close]
            elif inner and inner[-1] == "*":  # ``(ID *)ob``
                toks = toks[close + 1 :]
            else:
                break
        addr = bool(toks) and toks[0].text == "&"
        if addr:
            toks = toks[1:]
            # ``&ob->id``: the ID embedded first in every ID struct
            if len(toks) >= 2 and toks[-1].text == "id" and toks[-2].text in {".", "->"}:
                toks = toks[:-2]
        if not toks or any(t.text == "(" for t in toks):
            return ""
        if not all(t.kind == "id" or t.text in {".", "->"} for t in toks):
            return ""
        chain = [t.text for t in toks if t.kind == "id"]
        return self.chain_type(body, chain, at) if len(chain) > 1 else self.var_type(body, chain[0], at)

    # -- regions

    def region(self, f: CFile, name: str, body: list[Tok], start: int, end: int, dir_names: set[str], depth: int = 0) -> None:
        m = self.member(name, f, body[start].pos if start < len(body) else 0)
        n = end
        kind = ""
        types: list[tuple[str, bool]] = []
        rna_named: list[str] = []  # RNA_X passed to a call that also takes ``result`` (setters and helpers)
        rna_created: list[str] = []  # RNA_X of the pointers the region creates
        for j in range(start, n - 1):
            if body[j].kind == "id" and body[j + 1].text == "(":
                close = match_close(body, j + 1)
                args = split_commas(body[j + 2 : close])
                rnas = [x.text[4:] for x in body[j + 2 : close] if x.kind == "id" and x.text.startswith("RNA_") and x.text[4:] in self.rna_known]
                if not rnas:
                    continue
                if any(len(a) == 1 and a[0].text == "result" for a in args):
                    rna_named += rnas
                elif body[j].text.startswith(("RNA_pointer_create", "RNA_id_pointer_create")):
                    rna_created += rnas
        rna_named = rna_named or rna_created
        k = start
        while k < n:
            t = body[k]
            if t.kind == "id" and k + 1 < n and body[k + 1].text == "(":
                fname = t.text
                if fname not in POINTER_SETTERS and fname not in LIST_SETTERS and not fname.startswith("CTX_") and depth < 3:
                    # helpers that receive ``result``: ``screen_ctx_sel_actions_impl(C, result, true, false)``
                    close = match_close(body, k + 1)
                    args = split_commas(body[k + 2 : close])
                    if any(len(a) == 1 and a[0].text == "result" for a in args):
                        for fd in f.functions.get(fname, []):
                            self.region(f, name, fd.body, 0, len(fd.body), dir_names, depth + 1)
                if fname in POINTER_SETTERS or fname in LIST_SETTERS:
                    close = match_close(body, k + 1)
                    args = split_commas(body[k + 2 : close])
                    coll = fname in LIST_SETTERS
                    typ = ""
                    if fname in {"CTX_data_id_pointer_set", "CTX_data_id_list_add"} and len(args) >= 2:
                        ctype = self.id_arg_type(body, args[1], k)
                        typ = self.rna_of(ctype)
                        if not typ:
                            typ = "ID" if ctype in {"", "ID"} else ""
                        if typ == "ID":
                            # ``if (GS(snode->id->name) == ID_WO)`` narrows the ID
                            codes = [self.id_codes[x.text] for x in body[start:n] if x.text in self.id_codes]
                            if codes:
                                for c in dict.fromkeys(codes[:-1]):
                                    types.append((c, coll))
                                typ = codes[-1]
                            if ctype not in {"", "ID"}:
                                self.unknown_types.append(f"{name}: C type {ctype}")
                    elif fname in {"CTX_data_pointer_set", "CTX_data_list_add"} and len(args) >= 3:
                        ids = [x.text for x in args[2] if x.kind == "id"]
                        if ids and ids[-1].startswith("RNA_"):
                            typ = ids[-1][4:]
                        elif ids:
                            v = self.var_type(body, ids[-1], k)
                            typ = ""
                    else:
                        typ = ""
                    if not typ and rna_named:
                        for r in dict.fromkeys(rna_named):
                            types.append((r, coll))
                    elif typ:
                        types.append((typ, coll))
                    kind = kind or ("collection" if coll else "pointer")
                    k = close
                elif fname == "CTX_data_type_set":
                    close = match_close(body, k + 1)
                    ids = [x.text for x in body[k + 2 : close] if x.kind == "id"]
                    if ids and ids[-1] in KIND_OF_TYPE:
                        kind = KIND_OF_TYPE[ids[-1]]
                    k = close
                elif fname == "CTX_data_prop_set":
                    kind = "property"
                elif fname in {"CTX_data_str_set", "CTX_data_string_set"}:
                    kind = "string"
                elif fname == "CTX_data_int64_set":
                    kind = "int"
            k += 1
        if not types and rna_named and kind in {"", "pointer", "collection"}:
            # helpers (``set_pointer_type(path, result, &RNA_Brush)``) name the type
            for r in dict.fromkeys(rna_named):
                types.append((r, kind == "collection"))
        if kind == "collection":
            types = [(t, True) for t, _ in types]
        for t in types:
            if t not in m.types:
                m.types.append(t)
        if kind and (not m.kind or m.kind == "pointer"):
            m.kind = kind

    def read_file(self, f: CFile) -> None:
        self.macro_lookup = lambda n: self.tree.macro(f, n)
        dir_names: set[str] = set()
        for name, var in f.variables.items():
            if name.endswith("_context_dir") and var.braced:
                for part in split_commas(var.init):
                    if part and part[0].kind == "str":
                        s = string_value(part[0].text)
                        dir_names.add(s)
                        self.member(s, f, var.pos)
        callbacks: dict[str, str] = {}
        for defs in f.functions.values():
            for fd in defs:
                body = fd.body
                n = len(body)
                for k in range(n - 3):
                    t = body[k]
                    # map.add("scene", screen_ctx_scene)
                    if t.text in {"add", "add_new"} and body[k - 1].text in {".", "->"} and body[k + 1].text == "(" and body[k + 2].kind == "str":
                        close = match_close(body, k + 1)
                        args = split_commas(body[k + 2 : close])
                        if len(args) == 2 and len(args[1]) == 1 and args[1][0].kind == "id":
                            callbacks[args[1][0].text] = string_value(args[0][0].text)
                    if t.text == "CTX_data_equals" and body[k + 1].text == "(":
                        names = []
                        j = k
                        # gather ``CTX_data_equals(member, "a") || CTX_data_equals(member, "b")``
                        while j < n and body[j].text == "CTX_data_equals":
                            close = match_close(body, j + 1)
                            args = split_commas(body[j + 2 : close])
                            if len(args) == 2 and args[1] and args[1][0].kind == "str":
                                names.append(string_value(args[1][0].text))
                            j = close + 1
                            if j < n and body[j].text == "||":
                                j += 1
                            else:
                                break
                        if k > 0 and body[k - 1].text == "||":
                            continue  # handled with the first alternative
                        # the condition's ``)`` then the block
                        while j < n and body[j].text == ")":
                            j += 1
                        if j < n and body[j].text == "{":
                            end = match_close(body, j)
                        else:
                            end = j
                            while end < n and body[end].text != ";":
                                end += 1
                        for name in names:
                            self.region(f, name, body, j, end, dir_names)
        for cb, name in callbacks.items():
            for fd in f.functions.get(cb, []):
                self.region(f, name, fd.body, 0, len(fd.body), dir_names)

    def run(self, files: list[str]) -> None:
        for rel in files:
            self.read_file(self.tree.file(rel))
        for m in self.members.values():
            if not m.kind:
                m.kind = "pointer" if m.types else ""
            m.nullable = m.kind == "pointer"
            m.types = list(dict.fromkeys(m.types))
            if len({t for t, _ in m.types}) > 1:
                # an untyped ``ID *`` next to concrete types: keep the concrete ones
                m.types = [t for t in m.types if t[0] != "ID"]
        self.model.context.extend(sorted(self.members.values(), key=lambda m: m.name))
        self.extra["context_untyped_members"] = sorted(m.name for m in self.members.values() if not m.types and m.kind in {"", "pointer", "collection"})
        self.extra["context_unmapped_c_types"] = sorted(set(self.unknown_types))[:40]


def extract_context(tree: Tree, model: SourceModel, state: dict[str, Any], extra: dict[str, Any]) -> None:
    ContextReader(tree, model, state, extra).run(context_files(tree))
