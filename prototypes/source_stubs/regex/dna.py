"""DNA structs from ``makesdna/DNA_*.h``: member types, pointer levels, array sizes and default initializers.

makesrna reads the same headers (through makesdna) to size arrays (``float loc[3]`` -> a 3-array), bound strings
(``char name[64]`` -> max length 63) and type pointers it was not told (``struct Object *parent`` -> ``Object``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ctok import CFile, Tok, Tree, eval_number, match_close, split_commas, tokens_text

QUALIFIERS = {"const", "struct", "unsigned", "signed", "volatile", "mutable", "static", "constexpr", "inline"}


@dataclass
class Member:
    name: str
    type: str
    pointer: int = 0
    dims: list[int] = field(default_factory=list)
    default: list[Tok] | None = None

    @property
    def length(self) -> int:
        total = 1
        for d in self.dims:
            total *= d
        return total if self.dims else 0


class Dna:
    def __init__(self, tree: Tree) -> None:
        self.tree = tree
        self.structs: dict[str, dict[str, Member]] = {}
        self.consts: dict[str, int | float] = {}
        self.warnings: list[str] = []
        for rel in tree.glob("source/blender/makesdna/DNA_*.h"):
            try:
                f = tree.file(rel)
            except OSError:
                continue
            self.consts.update(tree._own_constants(f))
            self._scan(f)

    def _scan(self, f: CFile) -> None:
        toks = f.tokens
        n = len(toks)
        i = 0
        while i < n - 2:
            t = toks[i]
            if t.text == "struct" and toks[i + 1].kind == "id":
                j = i + 2
                # ``struct X : Base {`` / ``struct X final {``
                while j < n and toks[j].text not in {"{", ";", "(", ")", ",", "*", "&", "="}:
                    j += 1
                if j < n and toks[j].text == "{":
                    name = toks[i + 1].text
                    close = match_close(toks, j)
                    if name not in self.structs:
                        self.structs[name] = self._members(f, toks[j + 1 : close])
                    i = close + 1
                    continue
            i += 1

    def _members(self, f: CFile, body: list[Tok]) -> dict[str, Member]:
        out: dict[str, Member] = {}
        decls: list[list[Tok]] = [[]]
        depth = 0
        for t in body:
            s = t.text
            if s in "([{":
                depth += 1
            elif s in ")]}":
                depth -= 1
                if depth == 0 and s == "}":
                    # A nested struct/union body or an inline method body ends a declaration.
                    decls[-1].append(t)
                    if not any(x.text == "=" for x in decls[-1]):
                        decls.append([])
                    continue
            if s == ";" and depth == 0:
                decls.append([])
                continue
            decls[-1].append(t)
        for d in decls:
            # Drop leading macro calls (``DNA_DEFINE_CXX_METHODS(Object)``) and access specifiers.
            while d and d[0].kind == "id" and d[0].text.isupper() and len(d) > 1 and d[1].text == "(":
                d = d[match_close(d, 1) + 1 :]
            while len(d) >= 2 and d[0].text in {"public", "private", "protected"} and d[1].text == ":":
                d = d[2:]
            if (
                not d
                or d[0].text in {"static", "using", "typedef", "friend", "template", "enum", "union", "struct"}
                and "{" in [x.text for x in d]
            ):
                continue
            if any(x.text in {"static", "using", "typedef", "friend", "template", "operator"} for x in d[:3]):
                continue
            if any(x.text == "(" for x in d):
                continue  # methods, function pointers
            self._decl(f, d, out)
        return out

    def _decl(self, f: CFile, d: list[Tok], out: dict[str, Member]) -> None:
        parts = split_commas(d)
        if not parts:
            return
        first = parts[0]
        # Base type: everything up to the declarator of the first part.
        k = _declarator_start(first)
        if k is None:
            return
        base = [t.text for t in first[:k] if t.kind == "id" and t.text not in QUALIFIERS]
        if not base:
            return
        typ = base[-1]
        if typ.isupper() and len(base) > 1:  # ``float DNA_DEPRECATED x`` style attributes
            typ = base[0]
        for idx, part in enumerate(parts):
            decl = part[k:] if idx == 0 else part
            default = None
            for j, t in enumerate(decl):
                if t.text == "=":
                    default = decl[j + 1 :]
                    decl = decl[:j]
                    break
            if decl and decl[0].text == "{":
                continue
            ptr = sum(1 for t in decl if t.text == "*")
            names = [t for t in decl if t.kind == "id" and not t.text.isupper()]
            if not names:
                names = [t for t in decl if t.kind == "id"]
            if not names:
                continue
            name = names[0].text
            dims = []
            j = 0
            while j < len(decl):
                if decl[j].text == "[":
                    close = match_close(decl, j)
                    v = eval_number(tokens_text(decl[j + 1 : close]), self.consts)
                    if v is None:
                        v = eval_number(tokens_text(decl[j + 1 : close]), self.tree.constants(f))
                    if v is None:
                        self.warnings.append(f"{f.rel}: array size of {name} not evaluated")
                        v = 0
                    dims.append(int(v))
                    j = close + 1
                    continue
                j += 1
            out[name] = Member(name, typ, ptr, dims, default)

    def member(self, struct: str, path: str) -> Member | None:
        """``struct``'s member at ``path`` (``"pd.f_strength"``, ``"r.ffcodecdata.audio_codec"``)."""
        parts = path.replace("->", ".").split(".")
        cur = struct
        m = None
        for k, part in enumerate(parts):
            members = self.structs.get(cur)
            if members is None:
                return None
            part = part.split("[")[0]
            m = members.get(part)
            if m is None:
                return None
            cur = m.type
        return m


def _declarator_start(toks: list[Tok]) -> int | None:
    """Index where the first declarator starts (the member name, or the ``*`` before it)."""
    # The name is the last identifier before ``[`` / ``=`` / ``:`` (bitfield) / end, at depth 0.
    end = len(toks)
    depth = 0
    for j, t in enumerate(toks):
        if t.text in "([{<":
            if t.text in "[" and depth == 0:
                end = j
                break
            depth += 1
        elif t.text in ")]}>":
            depth -= 1
        elif t.text in {"=", ":"} and depth == 0:
            end = j
            break
    j = end - 1
    # Skip trailing attribute macros (``DNA_DEPRECATED``).
    while j >= 0 and toks[j].kind == "id" and toks[j].text.isupper() and j > 1:
        j -= 1
    if j < 0 or toks[j].kind != "id":
        return None
    while j - 1 >= 0 and toks[j - 1].text in {"*", "&"}:
        j -= 1
    return j if j > 0 else None
