"""A C/C++ reader without a compiler: comments, a preprocessor-lite, tokens, top-level declarations.

What it does, in order, for one file:

1. strip comments (keeping line numbers);
2. run a preprocessor-lite: track ``#if``/``#ifdef``/``#else``/``#endif`` nesting and blank the inactive lines
   (conditions are evaluated against ``Assume``: ``RNA_RUNTIME`` per area, every ``WITH_*`` feature on, platform
   macros for Linux, the file's own ``#define``s), record ``#define``s (object-like and function-like) with their
   position, and record ``#include "..."``;
3. tokenize what is left (identifiers, numbers, string/char literals, operators);
4. split the top level (namespaces and ``extern "C"`` are transparent) into function definitions, variables with
   initializers, enums (whose constants feed a small constant evaluator) and other statements.

It never parses types or templates: callers read token runs. What it cannot follow it leaves alone.
"""

from __future__ import annotations

import bisect
import warnings
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

warnings.filterwarnings("ignore", category=SyntaxWarning)

# --------------------------------------------------------------------------------------------------------------------
# Comments

_STRIP_RE = re.compile(
    r"//[^\n]*"
    r"|/\*[\s\S]*?\*/"
    r'|(?:u8|[LuU])?R"([^(\s"]*)\([\s\S]*?\)\1"'
    r'|(?:u8|[LuU])?"(?:[^"\\\n]|\\.)*"'
    r"|'(?:[^'\\\n]|\\.)*'"
)


def strip_comments(text: str) -> str:
    """``text`` with every comment replaced by blanks (newlines kept so lines stay put)."""

    def repl(m: re.Match[str]) -> str:
        s = m.group(0)
        if s.startswith("//"):
            return " "
        if s.startswith("/*"):
            return " " + "\n" * s.count("\n")
        return s

    return _STRIP_RE.sub(repl, text)


# --------------------------------------------------------------------------------------------------------------------
# Tokens

_TOKEN_RE = re.compile(
    r'(?P<str>(?:u8|[LuU])?R"(?P<delim>[^(\s"]*)\([\s\S]*?\)(?P=delim)"|(?:u8|[LuU])?"(?:[^"\\\n]|\\.)*")(?:_[A-Za-z]\w*)?'
    r"|(?P<chr>(?:u8|[LuU])?'(?:[^'\\\n]|\\.)*')"
    r"|(?P<num>\.?\d(?:[eEpP][+-]|[\w.])*)"
    r"|(?P<id>[A-Za-z_]\w*)"
    r"|(?P<op>->\*?|::|<<=|>>=|\.\.\.|[-+*/%&|^!=<>]=|&&|\|\||\+\+|--|<<|>>|##|\S)"
)


class Tok:
    __slots__ = ("kind", "text", "pos")

    def __init__(self, kind: str, text: str, pos: int) -> None:
        self.kind = kind  # id, num, str, chr, op
        self.text = text
        self.pos = pos

    def __repr__(self) -> str:
        return f"Tok({self.text!r})"


def tokenize(code: str, base: int = 0) -> list[Tok]:
    out = []
    append = out.append
    for m in _TOKEN_RE.finditer(code):
        kind = m.lastgroup
        if kind == "delim":
            kind = "str"
        append(Tok(kind, m.group(0), m.start() + base))
    return out


def tokens_text(toks: list[Tok]) -> str:
    return " ".join(t.text for t in toks)


_STR_BODY = re.compile(r'^(?:u8|[LuU])?"((?:[^"\\\n]|\\.)*)"', re.S)
_RAW_BODY = re.compile(r'^(?:u8|[LuU])?R"([^(\s"]*)\(([\s\S]*?)\)\1"')


def string_value(tok_text: str) -> str:
    """The decoded value of one string-literal token."""
    from common.rstdoc import decode_c_string

    m = _RAW_BODY.match(tok_text)
    if m:
        return m.group(2)
    m = _STR_BODY.match(tok_text)
    return decode_c_string(m.group(1)) if m else ""


# --------------------------------------------------------------------------------------------------------------------
# Splitting


OPEN = {"(": ")", "[": "]", "{": "}"}
CLOSE = {")", "]", "}"}


def match_close(toks: list[Tok], i: int) -> int:
    """Index of the token closing the bracket at ``toks[i]`` (len(toks) - 1 when unbalanced)."""
    depth = 0
    n = len(toks)
    while i < n:
        t = toks[i].text
        if t in OPEN:
            depth += 1
        elif t in CLOSE:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return n - 1


def split_commas(toks: list[Tok]) -> list[list[Tok]]:
    """Split a token run at the commas of its top level (brackets nest; ``<>`` does not)."""
    parts: list[list[Tok]] = [[]]
    depth = 0
    for t in toks:
        s = t.text
        if s in OPEN:
            depth += 1
        elif s in CLOSE:
            depth -= 1
        elif s == "," and depth == 0:
            parts.append([])
            continue
        parts[-1].append(t)
    if parts == [[]]:
        return []
    return parts


def call_args(toks: list[Tok], open_index: int) -> tuple[list[list[Tok]], int]:
    """The arguments of the call whose ``(`` is ``toks[open_index]``, and the index of its ``)``."""
    close = match_close(toks, open_index)
    return split_commas(toks[open_index + 1 : close]), close


# --------------------------------------------------------------------------------------------------------------------
# Preprocessor-lite


@dataclass
class Macro:
    name: str
    params: list[str] | None  # None: object-like
    body: str
    pos: int
    file: str = ""
    _toks: list[Tok] | None = None

    @property
    def tokens(self) -> list[Tok]:
        if self._toks is None:
            self._toks = tokenize(self.body)
        return self._toks


class Assume:
    """What the preprocessor-lite takes as defined.

    ``RNA_RUNTIME`` is given per area (undefined for makesrna's definition half), every ``WITH_*`` build option is
    on, the platform is Linux with GCC, ``NDEBUG`` is defined (a release build) and the Python version is 3.13.
    Everything else is undefined, unless the file (or a header it includes) defines it.
    """

    def __init__(self, rna_runtime: bool = False) -> None:
        self.values: dict[str, int | None] = {
            "__cplusplus": 201703,
            "__linux__": 1,
            "__GNUC__": 13,
            "NDEBUG": 1,
            "PY_VERSION_HEX": 0x030D00F0,
            "PY_MAJOR_VERSION": 3,
            "PY_MINOR_VERSION": 13,
            "true": 1,
            "false": 0,
        }
        if rna_runtime:
            self.values["RNA_RUNTIME"] = 1
        self.undefined = {"_WIN32", "WIN32", "__APPLE__", "_MSC_VER", "__clang__", "DEBUG", "MATH_STANDALONE",
                          "__BIG_ENDIAN__", "WITH_HEADLESS", "WITH_GHOST_SDL", "WITH_CYCLES_DEBUG",
                          "BUILD_DATE", "WITH_ASSERT_ABORT", "RNA_RUNTIME" if not rna_runtime else ""}

    def lookup(self, name: str, local: dict[str, str]) -> tuple[bool, int | None]:
        """(defined, value) of ``name``."""
        if name in local:
            body = local[name].strip()
            try:
                return True, int(body.rstrip("uUlL"), 0)
            except ValueError:
                return True, 1 if body == "" else None
        if name in self.values:
            return True, self.values[name]
        if name in self.undefined:
            return False, 0
        if name.startswith("WITH_"):
            return True, 1
        return False, 0


_DEFINED_RE = re.compile(r"\bdefined\s*(?:\(\s*(\w+)\s*\)|(\w+))")
_IDENT_RE = re.compile(r"\b[A-Za-z_]\w*\b")


def eval_condition(expr: str, assume: Assume, local: dict[str, str]) -> bool | None:
    """The truth of an ``#if`` expression; None when it cannot be evaluated."""
    expr = _DEFINED_RE.sub(lambda m: "1" if assume.lookup(m.group(1) or m.group(2), local)[0] else "0", expr)

    def ident(m: re.Match[str]) -> str:
        name = m.group(0)
        if name in {"and", "or", "not"}:
            return name
        defined, value = assume.lookup(name, local)
        if value is None:
            raise ValueError(name)
        return str(value)

    try:
        expr = _IDENT_RE.sub(ident, expr)
    except ValueError:
        return None
    expr = re.sub(r"(\d)[uUlL]+\b", r"\1", expr)
    expr = expr.replace("&&", " and ").replace("||", " or ")
    expr = re.sub(r"!(?!=)", " not ", expr)
    try:
        return bool(eval(expr, {"__builtins__": {}}, {}))  # noqa: S307 - arithmetic on digits only
    except Exception:
        return None


_DIRECTIVE_RE = re.compile(r"^\s*#\s*(\w+)\s*(.*)$", re.S)
_DEFINE_RE = re.compile(r"^(\w+)(\(([^)]*)\))?\s?(.*)$", re.S)


@dataclass
class Preprocessed:
    code: str
    macros: list[Macro]  # in source order; a None-bodied entry (params == ["#undef"]) undefines
    includes: list[str]
    warnings: list[str]


def preprocess(text: str, assume: Assume, rel: str = "") -> Preprocessed:
    """Blank inactive conditional regions and directives of comment-free ``text``; collect macros and includes."""
    lines = text.split("\n")
    out: list[str] = []
    macros: list[Macro] = []
    includes: list[str] = []
    warnings: list[str] = []
    local: dict[str, str] = {}
    # Stack entries: [parent_active, this_active, taken]
    stack: list[list[bool]] = []
    active = True
    pos = 0
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        start_pos = pos
        if line.lstrip().startswith("#"):
            # Join continuation lines.
            full = line
            consumed = 1
            while full.endswith("\\") and i + consumed < n:
                full = full[:-1] + " " + lines[i + consumed]
                consumed += 1
            for k in range(consumed):
                pos += 1
                out.append("")
            i += consumed
            m = _DIRECTIVE_RE.match(full)
            if not m:
                continue
            d, rest = m.group(1), m.group(2).strip()
            if d in {"if", "ifdef", "ifndef"}:
                if not active:
                    stack.append([False, False, True])
                    continue
                if d == "ifdef":
                    cond: bool | None = assume.lookup(rest.split()[0] if rest else "", local)[0]
                elif d == "ifndef":
                    cond = not assume.lookup(rest.split()[0] if rest else "", local)[0]
                else:
                    cond = eval_condition(rest, assume, local)
                    if cond is None:
                        warnings.append(f"{rel}: '#if {rest}' not evaluated, taken as true")
                        cond = True
                stack.append([active, cond, cond])
                active = cond
            elif d == "elif":
                if not stack:
                    continue
                parent, _, taken = stack[-1]
                if not parent or taken:
                    stack[-1][1] = False
                    active = False
                else:
                    cond = eval_condition(rest, assume, local)
                    if cond is None:
                        cond = False
                    stack[-1][1] = cond
                    stack[-1][2] = cond
                    active = cond
            elif d == "else":
                if not stack:
                    continue
                parent, _, taken = stack[-1]
                stack[-1][1] = parent and not taken
                stack[-1][2] = True
                active = stack[-1][1]
            elif d == "endif":
                if stack:
                    parent = stack.pop()[0]
                    active = parent
            elif not active:
                continue
            elif d == "define":
                dm = _DEFINE_RE.match(rest)
                if dm:
                    name, has_params, params, body = dm.group(1), dm.group(2), dm.group(3), dm.group(4)
                    plist = [p.strip() for p in params.split(",") if p.strip()] if has_params else None
                    macros.append(Macro(name, plist, body.strip(), start_pos, rel))
                    local[name] = body.strip() if plist is None else "1"
            elif d == "undef":
                name = rest.split()[0] if rest else ""
                macros.append(Macro(name, ["#undef"], "", start_pos, rel))
                local.pop(name, None)
            elif d == "include":
                im = re.match(r'"([^"]+)"', rest)
                if im:
                    includes.append(im.group(1))
            continue
        out.append(line if active else "")
        pos += (len(line) if active else 0) + 1
        i += 1
    return Preprocessed("\n".join(out), macros, includes, warnings)


# --------------------------------------------------------------------------------------------------------------------
# Top-level declarations


@dataclass
class Param:
    name: str
    type: str
    default: list[Tok] | None = None


@dataclass
class FuncDef:
    name: str
    qualname: str
    params: list[Param]
    file: CFile
    body_start: int  # index of the first token after "{"
    body_end: int  # index of the closing "}"
    pos: int
    is_static: bool = False

    @property
    def body(self) -> list[Tok]:
        return self.file.tokens[self.body_start : self.body_end]

    def text(self) -> str:
        return self.file.code[self.file.tokens[self.body_start - 1].pos : self.file.tokens[self.body_end].pos + 1]


@dataclass
class VarDef:
    name: str
    type_toks: list[Tok]
    init: list[Tok]  # inside the braces for a brace initializer, else the expression
    braced: bool
    pos: int
    is_array: bool = False
    is_static: bool = False

    @property
    def type_text(self) -> str:
        return tokens_text(self.type_toks)


@dataclass
class EnumDef:
    name: str
    constants: list[tuple[str, list[Tok]]]  # (name, value tokens or [])
    pos: int


KEYWORDS_NOT_FUNC = {"if", "for", "while", "switch", "return", "sizeof", "decltype", "alignas", "alignof",
                     "__attribute__", "static_assert", "noexcept", "operator", "throw", "catch", "new", "delete"}


def parse_params(toks: list[Tok]) -> list[Param]:
    params = []
    for part in split_commas(toks):
        if not part:
            continue
        default = None
        depth = 0
        for k, t in enumerate(part):
            if t.text in OPEN:
                depth += 1
            elif t.text in CLOSE:
                depth -= 1
            elif t.text == "=" and depth == 0:
                default = part[k + 1 :]
                part = part[:k]
                break
        if len(part) == 1 and part[0].text in {"void", "..."}:
            continue
        name = ""
        # Function pointer: ``void (*func)(...)``
        for k in range(len(part) - 2):
            if part[k].text == "(" and part[k + 1].text in {"*", "&"} and part[k + 2].kind == "id":
                name = part[k + 2].text
                break
        if not name:
            depth = 0
            for t in part:
                if t.text in OPEN:
                    depth += 1
                elif t.text in CLOSE:
                    depth -= 1
                elif depth == 0 and t.kind == "id":
                    name = t.text
            # ``int`` alone, ``const bContext *`` (unnamed): the last identifier is the type.
            ids = [t for t in part if t.kind == "id" and t.text not in {"const", "struct", "unsigned", "signed"}]
            if len(ids) <= 1 or part[-1].text in {"*", "&", "&&"}:
                name = ""
        params.append(Param(name, tokens_text(part), default))
    return params


class CFile:
    """One source file, preprocessed and tokenized, with its top-level declarations."""

    def __init__(self, path: Path, rel: str, assume: Assume, *, toplevel: bool = True) -> None:
        self.path = path
        self.rel = rel
        raw = path.read_text(encoding="utf-8", errors="replace")
        pre = preprocess(strip_comments(raw), assume, rel)
        self.code = pre.code
        self.macro_list = pre.macros
        self.includes = pre.includes
        self.warnings = pre.warnings
        self._line_starts = [0] + [m.end() for m in re.finditer("\n", self.code)]
        self.tokens = tokenize(self.code)
        self.macros: dict[str, list[Macro]] = {}
        for m in self.macro_list:
            self.macros.setdefault(m.name, []).append(m)
        self.functions: dict[str, list[FuncDef]] = {}
        self.variables: dict[str, VarDef] = {}
        self.enums: list[EnumDef] = []
        self.statements: list[tuple[int, int]] = []  # top-level ``...;`` token ranges
        self.struct_defs: dict[str, tuple[int, int]] = {}  # struct name -> body token range
        if toplevel:
            self._scan_toplevel()

    # -- positions

    def line(self, pos: int) -> int:
        return bisect.bisect_right(self._line_starts, pos)

    def src(self, pos: int) -> str:
        return f"{self.rel}:{self.line(pos)}"

    # -- macros

    def macro(self, name: str, pos: int | None = None) -> Macro | None:
        defs = self.macros.get(name)
        if not defs:
            return None
        found = None
        for m in defs:
            if pos is not None and m.pos > pos:
                break
            found = m
        if found is None or found.params == ["#undef"]:
            return None
        return found

    # -- top level

    def _scan_toplevel(self) -> None:
        toks = self.tokens
        n = len(toks)
        i = 0
        start = 0  # first token of the current declaration
        while i < n:
            t = toks[i]
            s = t.text
            if s == ";":
                if i > start:
                    self._statement(start, i)
                i += 1
                start = i
                continue
            if s == "}":  # closing a transparent namespace
                i += 1
                start = i
                continue
            if s in {"(", "["}:
                i = match_close(toks, i) + 1
                continue
            if s != "{":
                i += 1
                continue
            decl = toks[start:i]
            words = [d.text for d in decl]
            # namespace / extern "C" blocks are transparent.
            if (words and words[0] == "namespace") or (len(words) >= 2 and words[0] == "extern" and decl[1].kind == "str"):
                i += 1
                start = i
                continue
            close = match_close(toks, i)
            eq = _top_index(decl, "=")
            if eq is not None:
                # ``type name[] = { ... };``
                self._variable(decl[:eq], toks[i + 1 : close], True, decl[0].pos if decl else t.pos)
                j = close + 1
                while j < n and toks[j].text != ";":
                    j += 1
                i = j + 1
                start = i
                continue
            kind = next((w for w in words if w in {"struct", "class", "union", "enum"}), None)
            paren = _first_call_paren(decl)
            if kind == "enum" and (paren is None):
                self._enum(decl, toks[i + 1 : close], t.pos)
                j = close + 1
                while j < n and toks[j].text != ";":
                    j += 1
                i = j + 1
                start = i
                continue
            if paren is not None and kind not in {"struct", "class", "union"}:
                name_tok = decl[paren - 1]
                qual = [name_tok.text]
                k = paren - 2
                while k >= 1 and decl[k].text == "::" and decl[k - 1].kind == "id":
                    qual.insert(0, decl[k - 1].text)
                    k -= 2
                pclose = match_close(decl, paren)
                params = parse_params(decl[paren + 1 : pclose])
                fd = FuncDef(name_tok.text, "::".join(qual), params, self, i + 1, close,
                             decl[0].pos if decl else t.pos, is_static="static" in words[:paren])
                self.functions.setdefault(fd.name, []).append(fd)
                i = close + 1
                start = i
                continue
            # struct/class bodies and anything else: skipped (``struct X {...} name = {...};`` is rare).
            if kind in {"struct", "class"}:
                k_ = words.index(kind)
                if k_ + 1 < len(decl) and decl[k_ + 1].kind == "id":
                    self.struct_defs.setdefault(decl[k_ + 1].text, (i + 1, close))
            j = close + 1
            if kind in {"struct", "class", "union"}:
                while j < n and toks[j].text != ";":
                    if toks[j].text == "{":
                        break
                    j += 1
                if j < n and toks[j].text == ";":
                    j += 1
            i = j
            start = i

    def _statement(self, start: int, end: int) -> None:
        decl = self.tokens[start:end]
        self.statements.append((start, end))
        eq = _top_index(decl, "=")
        if eq is not None and eq > 0:
            self._variable(decl[:eq], decl[eq + 1 :], False, decl[0].pos)

    def _variable(self, head: list[Tok], init: list[Tok], braced: bool, pos: int) -> None:
        if not head:
            return
        is_array = False
        k = len(head) - 1
        while k >= 0 and head[k].text == "]":
            k = _match_open(head, k) - 1
            is_array = True
        if k < 0 or head[k].kind != "id":
            return
        name = head[k].text
        words = {h.text for h in head[:k]}
        self.variables[name] = VarDef(name, head[:k], init, braced, pos, is_array, "static" in words)

    def _enum(self, decl: list[Tok], body: list[Tok], pos: int) -> None:
        ids = [d.text for d in decl if d.kind == "id" and d.text not in {"enum", "class", "struct", "typedef"}]
        # ``enum class X : int8_t``: the name precedes ``:``
        name = ""
        colon = _top_index(decl, ":")
        named = decl[:colon] if colon is not None else decl
        named_ids = [d.text for d in named if d.kind == "id" and d.text not in {"enum", "class", "struct", "typedef"}]
        if named_ids:
            name = named_ids[-1]
        elif ids:
            name = ""
        consts = []
        for part in split_commas(body):
            if not part or part[0].kind != "id":
                continue
            value = part[2:] if len(part) > 2 and part[1].text == "=" else []
            consts.append((part[0].text, value))
        self.enums.append(EnumDef(name, consts, pos))


def _top_index(toks: list[Tok], text: str) -> int | None:
    depth = 0
    for k, t in enumerate(toks):
        s = t.text
        if s in OPEN:
            depth += 1
        elif s in CLOSE:
            depth -= 1
        elif s == text and depth == 0:
            return k
    return None


def _first_call_paren(decl: list[Tok]) -> int | None:
    depth = 0
    for k, t in enumerate(decl):
        s = t.text
        if s == "(" and depth == 0 and k > 0 and decl[k - 1].kind == "id" and decl[k - 1].text not in KEYWORDS_NOT_FUNC:
            # ``__attribute__((...))`` / attribute macros taking args are rare before the name.
            return k
        if s in OPEN:
            depth += 1
        elif s in CLOSE:
            depth -= 1
    return None


def _match_open(toks: list[Tok], close: int) -> int:
    depth = 0
    k = close
    while k >= 0:
        s = toks[k].text
        if s in CLOSE:
            depth += 1
        elif s in OPEN:
            depth -= 1
            if depth == 0:
                return k
        k -= 1
    return 0


# --------------------------------------------------------------------------------------------------------------------
# The source tree: files, headers, includes, macros and constants across files


class Tree:
    """Cached access to the files of a Blender source tree."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.files: dict[tuple[str, bool], CFile] = {}
        self._header_index: dict[str, list[Path]] | None = None
        self.warnings: list[str] = []
        self._reach: dict[str, list[str]] = {}
        self._const_cache: dict[str, dict[str, int | float]] = {}
        self._macro_cache: dict[str, dict[str, Macro]] = {}
        # Constants of every DNA header and of the RNA/WM type headers, for files that include them only in
        # regions the preprocessor-lite dropped (``#ifdef RNA_RUNTIME``).
        self.global_consts: dict[str, int | float] = {}

    def load_global_constants(self) -> None:
        for pattern in ("source/blender/makesdna/DNA_*.h", "source/blender/makesrna/RNA_types.hh",
                        "source/blender/windowmanager/WM_types.hh", "source/blender/editors/include/*.hh",
                        "source/blender/blenkernel/BKE_*.hh"):
            for rel in self.glob(pattern):
                try:
                    for k, v in self._own_constants(self.header(rel)).items():
                        self.global_consts.setdefault(k, v)
                except OSError:
                    continue

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def file(self, rel: str, *, rna_runtime: bool = False) -> CFile:
        key = (rel, rna_runtime)
        f = self.files.get(key)
        if f is None:
            f = CFile(self.root / rel, rel, Assume(rna_runtime))
            self.warnings.extend(f.warnings)
            self.files[key] = f
        return f

    def glob(self, *patterns: str) -> list[str]:
        out = []
        for pattern in patterns:
            out += [self.rel(p) for p in sorted(self.root.glob(pattern)) if p.is_file()]
        return out

    # -- headers

    def header_index(self) -> dict[str, list[Path]]:
        if self._header_index is None:
            index: dict[str, list[Path]] = {}
            for top in ("source", "intern"):
                for dirpath, dirnames, filenames in os.walk(self.root / top):
                    dirnames[:] = [d for d in dirnames if d not in {"tests", "testing"}]
                    for fn in filenames:
                        if fn.endswith((".h", ".hh", ".hpp", ".inl")):
                            index.setdefault(fn, []).append(Path(dirpath) / fn)
            self._header_index = index
        return self._header_index

    def resolve_include(self, name: str, from_rel: str) -> str | None:
        here = (self.root / from_rel).parent / name
        if here.is_file():
            return self.rel(here)
        base = name.rsplit("/", 1)[-1]
        cands = self.header_index().get(base, [])
        if not cands:
            return None
        if "/" in name:
            cands = [c for c in cands if c.as_posix().endswith(name)] or cands
        # Prefer the header closest to the including file.
        from_parts = Path(from_rel).parts
        def score(p: Path) -> tuple[int, int]:
            parts = Path(self.rel(p)).parts
            common = 0
            for a, b in zip(parts, from_parts):
                if a != b:
                    break
                common += 1
            return (-common, len(parts))
        return self.rel(min(cands, key=score))

    def header(self, rel: str) -> CFile:
        key = (rel, False)
        f = self.files.get(key)
        if f is None:
            f = CFile(self.root / rel, rel, Assume(False), toplevel=True)
            self.files[key] = f
        return f

    def reachable(self, f: CFile, limit: int = 400) -> list[str]:
        """Headers transitively included by ``f`` (closest first)."""
        if f.rel in self._reach:
            return self._reach[f.rel]
        seen: dict[str, None] = {}
        queue = [(inc, f.rel) for inc in f.includes]
        while queue and len(seen) < limit:
            inc, frm = queue.pop(0)
            r = self.resolve_include(inc, frm)
            if r is None or r in seen or r == f.rel:
                continue
            seen[r] = None
            try:
                h = self.header(r)
            except OSError:
                continue
            queue += [(i2, r) for i2 in h.includes]
        out = list(seen)
        self._reach[f.rel] = out
        return out

    def struct_fields(self, f: CFile, name: str) -> list[str]:
        """Field names of struct ``name`` as visible from ``f`` (its own definitions, then its headers')."""
        for cand in [f] + [self.header(r) for r in self.reachable(f)]:
            rng = cand.struct_defs.get(name)
            if rng is not None:
                return field_names(cand.tokens[rng[0] : rng[1]])
        return []

    def macro(self, f: CFile, name: str, pos: int | None = None) -> Macro | None:
        m = f.macro(name, pos)
        if m is not None:
            return m
        table = self._macro_cache.get(f.rel)
        if table is None:
            table = {}
            for r in reversed(self.reachable(f)):
                h = self.header(r)
                for mm in h.macro_list:
                    if mm.params == ["#undef"]:
                        table.pop(mm.name, None)
                    else:
                        table[mm.name] = mm
            self._macro_cache[f.rel] = table
        return table.get(name)

    # -- constants

    def constants(self, f: CFile) -> dict[str, int | float]:
        """Enum constants and numeric macros visible in ``f`` (its own and its headers')."""
        table = self._const_cache.get(f.rel)
        if table is not None:
            return table
        table = {}
        for r in reversed(self.reachable(f)):
            h = self.header(r)
            table.update(self._own_constants(h))
        table.update(self._own_constants(f))
        from collections import ChainMap

        table = ChainMap(table, self.global_consts)  # type: ignore[assignment]
        self._const_cache[f.rel] = table
        return table

    def _own_constants(self, f: CFile) -> dict[str, int | float]:
        key = "own:" + f.rel
        cached = self._const_cache.get(key)
        if cached is not None:
            return cached
        table: dict[str, int | float] = {}
        for m in f.macro_list:
            if m.params is None and m.body:
                v = eval_number(m.body, table)
                if v is not None:
                    table[m.name] = v
        for e in f.enums:
            value: int | float = -1
            for cname, vtoks in e.constants:
                if vtoks:
                    v = eval_number(tokens_text(vtoks), table)
                    value = int(v) if v is not None else value + 1
                else:
                    value += 1
                table[cname] = value
                if e.name:
                    table[f"{e.name}::{cname}"] = value
        self._const_cache[key] = table
        return table


def field_names(body: list[Tok]) -> list[str]:
    """Data member names of a struct body, in order (methods and static members skipped)."""
    names: list[str] = []
    decl: list[Tok] = []
    depth = 0
    for t in body:
        s = t.text
        if s in OPEN:
            depth += 1
        elif s in CLOSE:
            depth -= 1
            if depth == 0 and s == "}":
                decl = []  # inline method body
                continue
        if depth == 0 and s == ";":
            d = decl
            decl = []
            if not d or d[0].text in {"static", "using", "typedef", "friend", "template"}:
                continue
            fp = next((d[k + 2].text for k in range(len(d) - 2) if d[k].text == "(" and d[k + 1].text == "*" and d[k + 2].kind == "id"), None)
            if fp:
                names.append(fp)
                continue
            if any(x.text == "(" for x in d):
                continue
            for part in split_commas(d):
                cut = len(part)
                for k, x in enumerate(part):
                    if x.text in {"[", "=", "{", ":"}:
                        cut = k
                        break
                ids = [x for x in part[:cut] if x.kind == "id"]
                if ids:
                    names.append(ids[-1].text)
            continue
        if depth == 0 or (depth > 0 and decl):
            decl.append(t)
    return names


# --------------------------------------------------------------------------------------------------------------------
# Numbers

KNOWN_NUMBERS: dict[str, float | int] = {
    "FLT_MAX": 3.4028234663852886e38,
    "FLT_MIN": 1.1754943508222875e-38,
    "FLT_EPSILON": 1.1920928955078125e-07,
    "DBL_MAX": 1.7976931348623157e308,
    "INT_MAX": 2147483647,
    "INT_MIN": -2147483648,
    "UINT_MAX": 4294967295,
    "SHRT_MAX": 32767,
    "SHRT_MIN": -32768,
    "USHRT_MAX": 65535,
    "CHAR_MAX": 127,
    "UCHAR_MAX": 255,
    "INT16_MAX": 32767,
    "INT32_MAX": 2147483647,
    "INT32_MIN": -2147483648,
    "M_PI": 3.141592653589793,
    "M_PI_2": 1.5707963267948966,
    "M_PI_4": 0.7853981633974483,
    "M_SQRT2": 1.4142135623730951,
    "M_SQRT1_2": 0.7071067811865476,
    "M_E": 2.718281828459045,
    "true": 1,
    "false": 0,
    "nullptr": 0,
    "NULL": 0,
}
_CAST_RE = re.compile(
    r"\b(?:static_cast|reinterpret_cast|const_cast)\s*<[^<>]*>"
    r"|\((?:const\s+)?(?:unsigned\s+|signed\s+)?(?:int|short|char|float|double|long|uint|uint8_t|int8_t|uint16_t|"
    r"int16_t|uint32_t|int32_t|uint64_t|int64_t|size_t|bool)\s*\)"
)
_FUNC_CAST_RE = re.compile(
    r"\b(?:unsigned|int|short|char|float|double|uint|uint8_t|int8_t|uint16_t|int16_t|uint32_t|int32_t|uint64_t|"
    r"int64_t|size_t|bool|eWM_GizmoFlagTweak|PropertyFlag|ParameterFlag|[A-Z]\w*Flag\w*|e[A-Z]\w*)\s*(?=\()"
)
_NUM_TOKEN_RE = re.compile(r"(?<![\w.])(\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?[fFuUlL]*\b|0[xX][0-9a-fA-F]+[uUlL]*")
_DEG_RE = re.compile(r"\b(DEG2RADF?|RAD2DEGF?)\s*\(")


def eval_number(expr: str, consts: dict[str, int | float] | None = None) -> int | float | None:
    """The value of a C constant expression made of numbers, known constants and arithmetic; None otherwise."""
    expr = expr.strip()
    if not expr:
        return None
    consts = consts or {}
    expr = _CAST_RE.sub("", expr)
    expr = _FUNC_CAST_RE.sub("", expr)
    expr = _DEG_RE.sub(lambda m: "(3.141592653589793/180.0)*(" if m.group(1).startswith("DEG") else "(180.0/3.141592653589793)*(", expr)
    expr = re.sub(r"\s*::\s*", "::", expr)

    def num(m: re.Match[str]) -> str:
        s = m.group(0)
        if s[:2].lower() == "0x":
            return str(int(s.rstrip("uUlL"), 16))
        s = s.rstrip("fFuUlL")
        if re.fullmatch(r"0\d+", s):
            return str(int(s, 8))
        return s

    expr = _NUM_TOKEN_RE.sub(num, expr)

    def ident(m: re.Match[str]) -> str:
        name = m.group(0)
        if name in consts:
            return repr(consts[name])
        tail = name.rsplit("::", 1)[-1]
        if name in KNOWN_NUMBERS:
            return repr(KNOWN_NUMBERS[name])
        if tail in consts:
            return repr(consts[tail])
        if tail in KNOWN_NUMBERS:
            return repr(KNOWN_NUMBERS[tail])
        if re.fullmatch(r"e\d+", name):  # exponent part of a float already handled
            return name
        raise ValueError(name)

    try:
        expr = re.sub(r"(?<![\d.])[A-Za-z_][\w]*(?:::[A-Za-z_]\w*)*", ident, expr)
    except ValueError:
        return None
    if re.search(r"[^\d\s.+\-*/%()<>&|^~eE]", expr):
        if not re.fullmatch(r"[\d\s.+\-*/%()<>&|^~eE!=?:]*", expr):
            return None
    expr = expr.replace("&&", " and ").replace("||", " or ")
    if "?" in expr or "!" in expr:
        return None
    try:
        v = eval(expr, {"__builtins__": {}}, {})  # noqa: S307 - digits and operators only
    except Exception:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return v
    return None
