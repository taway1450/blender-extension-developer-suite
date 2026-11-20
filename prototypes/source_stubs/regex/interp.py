"""A tiny symbolic executor of C function bodies, enough to follow ``RNA_def_*`` / ``ot->`` definition code.

Bodies are parsed into a statement tree (blocks, ``if``/``else``, loops, ``switch``, ``return``, simple
statements). Executing one binds local variables (``srna = RNA_def_struct(...)``, ``prop = ...``), evaluates calls
in source order and dispatches them:

- to an area's *handlers* (``RNA_def_property_flag`` -> set a flag on the bound property);
- to the source's own functions (static helpers, other files' ``rna_def_*_api``, ``WM_operator_properties_*``),
  binding the caller's values to the callee's parameters, so a helper that receives ``StructRNA *srna`` defines on
  the caller's struct; lambdas and function pointers (``define("ShaderNode", "X", def_principled)``) work the same;
- to nothing (any other call: its arguments are still evaluated when they contain definitions).

Conditions are evaluated when their operands are known (``if (flag & WM_FILESEL_FILEPATH)`` with ``flag`` a
constant from the caller); otherwise both branches run. Loop bodies run once. Values it cannot compute are
``Raw`` (their tokens, for flags and numbers).
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ctok import (
    CFile,
    FuncDef,
    Tok,
    Tree,
    call_args,
    eval_number,
    match_close,
    parse_params,
    split_commas,
    string_value,
)

I18N = {
    "N_": -1,
    "CTX_N_": -1,
    "IFACE_": -1,
    "TIP_": -1,
    "DATA_": -1,
    "RPT_": -1,
    "CTX_IFACE_": -1,
    "CTX_TIP_": -1,
    "CTX_DATA_": -1,
    "CTX_RPT_": -1,
    "BLT_I18N_MSGID_MULTI_CTXT": 0,
}
BINARY_OPS = {"||", "&&", "|", "^", "&", "==", "!=", "<", ">", "<=", ">=", "<<", ">>", "+", "-", "*", "/", "%", "?"}
CASTS = {"static_cast", "reinterpret_cast", "const_cast", "dynamic_cast"}


class Raw:
    """An expression the executor could not compute: its tokens (flags, numbers, unknown names)."""

    __slots__ = ("file", "toks")

    def __init__(self, toks: list[Tok], file: CFile | None) -> None:
        self.toks = toks
        self.file = file

    @property
    def text(self) -> str:
        return " ".join(t.text for t in self.toks)

    def __repr__(self) -> str:
        return f"Raw({self.text!r})"


@dataclass
class StructRef:
    """``&RNA_Object``."""

    name: str


@dataclass
class FuncRef:
    name: str
    defs: list[FuncDef]


@dataclass
class Lambda:
    params: list[Any]
    file: CFile
    start: int  # body token range in file.tokens
    end: int
    scope: Env


class StructInit:
    """A brace-initialized struct value: ``{"cameras", "Camera", ..., RNA_def_main_cameras}``."""

    def __init__(self, fields: list[str], values: list[Any], named: dict[str, Any]) -> None:
        self.fields = fields
        self.values = values
        self.named = named

    def getmember(self, name: str, ip: Any) -> Any:
        if name in self.named:
            return self.named[name]
        if name in self.fields:
            k = self.fields.index(name)
            return self.values[k] if k < len(self.values) else None
        return None

    def __repr__(self) -> str:
        return f"StructInit({self.values!r})"


class ArrayPtr:
    """A pointer walking an array: ``for (effect = def_effects; effect->name; effect++)``."""

    def __init__(self, items: list[Any], index: int = 0) -> None:
        self.items = items
        self.index = index

    @property
    def current(self) -> Any:
        return self.items[self.index] if 0 <= self.index < len(self.items) else None

    def getmember(self, name: str, ip: Any) -> Any:
        cur = self.current
        getter = getattr(cur, "getmember", None)
        return getter(name, ip) if getter is not None else None


class ItemView:
    """One row of an item array seen from code: ``items[i].identifier``."""

    def __init__(self, item: Any, raw: str) -> None:
        self.item = item
        self.raw = raw

    def getmember(self, name: str, ip: Any) -> Any:
        if self.item is None:
            return None
        if name in {"value", "flag"}:
            return self.item.value
        if name == "icon":
            return Raw([], None)
        return getattr(self.item, name, None)


class Env(dict):
    def __init__(self, parent: Env | None = None) -> None:
        super().__init__()
        self.parent = parent

    def find(self, name: str) -> tuple[bool, Any]:
        env: Env | None = self
        while env is not None:
            if name in env:
                return True, env[name]
            env = env.parent
        return False, None

    def assign(self, name: str, value: Any, declare: bool) -> None:
        if not declare:
            env: Env | None = self
            while env is not None:
                if name in env:
                    env[name] = value
                    return
                env = env.parent
        self[name] = value


_MISSING = object()


class BreakSignal(Exception):
    pass


class ReturnSignal(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


# --------------------------------------------------------------------------------------------------------------------
# Statements


def parse_statements(toks: list[Tok], i: int, end: int) -> list[tuple]:
    out = []
    while i < end:
        node, i = parse_statement(toks, i, end)
        if node is not None:
            out.append(node)
    return out


def _paren_group(toks: list[Tok], i: int, end: int) -> tuple[int, int]:
    """(open, close) of the ``(...)`` at or after ``i``."""
    while i < end and toks[i].text != "(":
        i += 1
    if i >= end:
        return end, end
    return i, min(match_close(toks, i), end)


def parse_statement(toks: list[Tok], i: int, end: int) -> tuple[tuple | None, int]:
    t = toks[i].text
    if t == "{":
        close = min(match_close(toks, i), end)
        return ("block", parse_statements(toks, i + 1, close)), close + 1
    if t == ";":
        return None, i + 1
    if t == "if":
        o, c = _paren_group(toks, i + 1, end)
        then, k = parse_statement(toks, c + 1, end) if c + 1 < end else (None, end)
        els = None
        if k < end and toks[k].text == "else":
            els, k = parse_statement(toks, k + 1, end)
        return ("if", toks[o + 1 : c], then, els, toks[i].pos), k
    if t in {"for", "while"}:
        o, c = _paren_group(toks, i + 1, end)
        body, k = parse_statement(toks, c + 1, end) if c + 1 < end else (None, end)
        return ("loop", toks[o + 1 : c], body), k
    if t == "switch":
        o, c = _paren_group(toks, i + 1, end)
        body, k = parse_statement(toks, c + 1, end) if c + 1 < end else (None, end)
        return ("switch", toks[o + 1 : c], body), k
    if t == "do":
        body, k = parse_statement(toks, i + 1, end)
        if k < end and toks[k].text == "while":
            o, c = _paren_group(toks, k + 1, end)
            k = c + 1
            if k < end and toks[k].text == ";":
                k += 1
        return ("loop", [], body), k
    if t in {"case", "default"}:
        k = i + 1
        label_start = k
        depth = 0
        while k < end:
            s = toks[k].text
            if s in "([{":
                depth += 1
            elif s in ")]}":
                depth -= 1
            elif s == ":" and depth == 0:
                break
            k += 1
        return ("case", toks[label_start:k] if t == "case" else None), k + 1
    if t == "try":
        body, k = parse_statement(toks, i + 1, end)
        while k < end and toks[k].text == "catch":
            o, c = _paren_group(toks, k + 1, end)
            _, k = parse_statement(toks, c + 1, end)
        return body, k
    # Simple statement up to ";" at depth 0.
    k = i
    depth = 0
    while k < end:
        s = toks[k].text
        if s in "([{":
            depth += 1
        elif s in ")]}":
            depth -= 1
            if depth < 0:
                break
        elif s == ";" and depth == 0:
            break
        k += 1
    if t == "return":
        return ("return", toks[i + 1 : k]), k + 1
    if t == "break":
        return ("break",), k + 1
    if t in {"continue", "goto"}:
        return None, k + 1
    return ("expr", toks[i:k]), k + 1


# --------------------------------------------------------------------------------------------------------------------
# The executor


def strip_parens(toks: list[Tok]) -> list[Tok]:
    while len(toks) >= 2 and toks[0].text == "(" and match_close(toks, 0) == len(toks) - 1:
        toks = toks[1:-1]
    return toks


def top_index(toks: list[Tok], texts: set[str]) -> int | None:
    depth = 0
    for k, t in enumerate(toks):
        s = t.text
        if s in "([{":
            depth += 1
        elif s in ")]}":
            depth -= 1
        elif depth == 0 and s in texts:
            return k
    return None


def flags_of(value: Any, prefix: str = "") -> list[str]:
    """Identifiers of a flag expression (``PROP_A | PROP_B``, ``PropertyFlag(0)``), optionally by prefix."""
    if isinstance(value, Raw):
        names = [t.text for t in value.toks if t.kind == "id"]
    elif isinstance(value, str):
        names = re.findall(r"\w+", value)
    else:
        return []
    return [n for n in names if (n.startswith(prefix) if prefix else True)]


@dataclass
class Frame:
    file: CFile
    env: Env
    func: str = ""


class Interp:
    """Executes function bodies of the files in ``index`` with ``handlers`` for the calls an area cares about."""

    def __init__(
        self, tree: Tree, handlers: dict[str, Callable[..., Any]], relevant: Callable[[FuncDef], bool]
    ) -> None:
        self.tree = tree
        self.handlers = handlers
        self.index: dict[str, list[FuncDef]] = {}
        self._relevant_direct = relevant
        self._relevant: dict[int, bool] = {}
        self.stack: list[int] = []
        self.frames: list[Frame] = []
        self.warnings: Counter[str] = Counter()
        self.global_lookup: Callable[[str, CFile], Any] | None = None
        self._parsed: dict[tuple[str, int], list[tuple]] = {}
        self.conditions_unknown = 0  # depth of enclosing unknown conditions
        self.loop_depth = 0
        self.max_depth = 40
        self.max_unroll = 600
        self.break_level = -1

    # -- index

    def add_file(self, f: CFile) -> None:
        for name, defs in f.functions.items():
            self.index.setdefault(name, []).extend(defs)

    def compute_relevance(self) -> None:
        """A function is relevant when it defines (``relevant``) or calls a relevant function."""
        calls: dict[int, set[str]] = {}
        direct: set[str] = set()
        by_id: dict[int, FuncDef] = {}
        for name, defs in self.index.items():
            for fd in defs:
                by_id[id(fd)] = fd
                body = fd.body
                called = set()
                for k in range(len(body) - 1):
                    if body[k].kind == "id" and body[k + 1].text in {"(", "<"}:
                        called.add(body[k].text)
                    elif body[k].kind == "id" and body[k].text in self.index:
                        called.add(body[k].text)  # function pointers passed along
                calls[id(fd)] = called
                if self._relevant_direct(fd):
                    self._relevant[id(fd)] = True
                    direct.add(name)
        relevant_names = set(direct)
        changed = True
        while changed:
            changed = False
            for fid, called in calls.items():
                if self._relevant.get(fid):
                    continue
                if called & relevant_names:
                    self._relevant[fid] = True
                    relevant_names.add(by_id[fid].name)
                    changed = True

    def is_relevant(self, fd: FuncDef) -> bool:
        return self._relevant.get(id(fd), False)

    def lookup_function(self, name: str, file: CFile | None) -> FuncDef | None:
        defs = self.index.get(name)
        if not defs:
            return None
        if file is not None:
            for fd in defs:
                if fd.file is file:
                    return fd
        for fd in defs:
            if not fd.is_static:
                return fd
        return defs[0]

    # -- context

    @property
    def frame(self) -> Frame:
        return self.frames[-1]

    @property
    def file(self) -> CFile:
        return self.frames[-1].file

    def warn(self, kind: str, detail: str = "") -> None:
        self.warnings[kind if not detail else f"{kind}: {detail}"] += 1

    def src(self, pos: int) -> str:
        return self.file.src(pos)

    def constants(self) -> dict[str, int | float]:
        return self.tree.constants(self.file)

    def number(self, value: Any) -> int | float | None:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, Raw):
            text = value.text
            v = eval_number(text, self.tree.constants(value.file) if value.file else {})
            return v
        return None

    def number_with_env(self, toks: list[Tok]) -> int | float | None:
        """A numeric expression over constants and the numbers bound to local names."""
        consts = self.constants()
        env = self.frame.env
        local = None
        for t in toks:
            if t.kind == "id":
                found, value = env.find(t.text)
                if found and isinstance(value, Raw):
                    value = self.number(value)
                if found and isinstance(value, (bool, int, float)):
                    if local is None:
                        local = dict(consts)
                    local[t.text] = int(value) if isinstance(value, bool) else value
        return eval_number(" ".join(t.text for t in toks), local if local is not None else consts)

    # -- running

    def run(self, fd: FuncDef, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        if id(fd) in self.stack or len(self.stack) >= self.max_depth:
            return None
        env = Env()
        self.bind_params(env, fd.params, args, fd.file)
        if kwargs:
            env.update(kwargs)
        key = (fd.file.rel, fd.body_start)
        nodes = self._parsed.get(key)
        if nodes is None:
            nodes = parse_statements(fd.file.tokens, fd.body_start, fd.body_end)
            self._parsed[key] = nodes
        self.stack.append(id(fd))
        self.frames.append(Frame(fd.file, env, fd.name))
        saved = self.conditions_unknown, self.loop_depth, self.break_level
        self.conditions_unknown = 0
        self.loop_depth = 0
        self.break_level = -1
        try:
            self.exec_nodes(nodes)
            result = env.get("__return__")
        except ReturnSignal as r:
            result = r.value
        except BreakSignal:
            result = env.get("__return__")
        finally:
            self.conditions_unknown, self.loop_depth, self.break_level = saved
            self.frames.pop()
            self.stack.pop()
        return result

    def run_lambda(self, lam: Lambda, args: list[Any]) -> Any:
        env = Env(lam.scope)
        self.bind_params(env, lam.params, args, lam.file)
        key = (lam.file.rel, lam.start)
        nodes = self._parsed.get(key)
        if nodes is None:
            nodes = parse_statements(lam.file.tokens, lam.start, lam.end)
            self._parsed[key] = nodes
        self.frames.append(Frame(lam.file, env, "<lambda>"))
        saved = self.conditions_unknown, self.break_level
        self.conditions_unknown = 0
        self.break_level = -1
        try:
            self.exec_nodes(nodes)
            result = env.get("__return__")
        except ReturnSignal as r:
            result = r.value
        except BreakSignal:
            result = env.get("__return__")
        finally:
            self.conditions_unknown, self.break_level = saved
            self.frames.pop()
        return result

    def bind_params(self, env: Env, params: list[Any], args: list[Any], file: CFile) -> None:
        for k, p in enumerate(params):
            if not p.name:
                continue
            if k < len(args):
                env[p.name] = args[k]
            elif p.default is not None:
                env[p.name] = None
            else:
                env[p.name] = None

    def exec_nodes(self, nodes: list[tuple]) -> None:
        for node in nodes:
            self.exec_node(node)

    def exec_node(self, node: tuple | None) -> None:
        if node is None:
            return
        kind = node[0]
        if kind == "expr":
            self.exec_simple(node[1])
        elif kind == "block":
            self.exec_nodes(node[1])
        elif kind == "if":
            cond = self.condition(node[1])
            if cond is True:
                self.exec_node(node[2])
            elif cond is False:
                self.exec_node(node[3])
            else:
                self.conditions_unknown += 1
                try:
                    self.exec_node(node[2])
                    self.exec_node(node[3])
                finally:
                    self.conditions_unknown -= 1
        elif kind == "loop":
            self.exec_loop(node[1], node[2])
        elif kind == "switch":
            self.exec_switch(node[1], node[2])
        elif kind == "break":
            if self.conditions_unknown == self.break_level:
                raise BreakSignal()
        elif kind == "return":
            value = self.eval(node[1]) if node[1] else None
            if self.conditions_unknown:
                if value is not None:
                    self.frame.env.setdefault("__return__", value)
            else:
                raise ReturnSignal(value)

    def _body(self, body: tuple | None, level: int) -> bool:
        """Run a loop/switch body; False when it ended with a ``break``."""
        saved = self.break_level
        self.break_level = level
        try:
            self.exec_node(body)
        except BreakSignal:
            return False
        finally:
            self.break_level = saved
        return True

    def exec_loop(self, head: list[Tok], body: tuple | None) -> None:
        env = self.frame.env
        semis = [k for k, t in enumerate(head) if t.text == ";"]
        colon = top_index(head, {":"}) if not semis else None
        # Range-for over a known list: unrolled.
        if colon is not None:
            iterable = self.eval(head[colon + 1 :])
            names = [t.text for t in head[:colon] if t.kind == "id"]
            if isinstance(iterable, list) and names and len(iterable) <= self.max_unroll:
                self.loop_depth += 0
                for item in iterable:
                    env.assign(names[-1], item, True)
                    if not self._body(body, self.conditions_unknown):
                        break
                return
        elif len(semis) == 2:
            init, cond, step = head[: semis[0]], head[semis[0] + 1 : semis[1]], head[semis[1] + 1 :]
            if init:
                self.exec_simple(init)
            eq = top_index(init, {"="}) if init else None
            var = ""
            if eq is not None:
                var = next((t.text for t in reversed(init[:eq]) if t.kind == "id"), "")
                _found, value = env.find(var)
                if isinstance(value, list):
                    env.assign(var, ArrayPtr(value), False)
            first = self.condition(cond) if cond else None
            if first is not None and var:
                count = 0
                while self.condition(cond) and count < self.max_unroll:
                    if not self._body(body, self.conditions_unknown):
                        break
                    if not self.step(var, step):
                        break
                    count += 1
                return
        # Unknown iteration: run the body once.
        self.loop_depth += 1
        self.conditions_unknown += 1
        try:
            self._body(body, self.conditions_unknown)
        finally:
            self.loop_depth -= 1
            self.conditions_unknown -= 1

    def step(self, var: str, step: list[Tok]) -> bool:
        env = self.frame.env
        found, value = env.find(var)
        if isinstance(value, ArrayPtr):
            if [t.text for t in step] in ([var, "++"], ["++", var]):
                value.index += 1
                return value.index <= len(value.items)
            return False
        value = self.number(value) if found else None
        if not isinstance(value, (int, float)):
            return False
        texts = [t.text for t in step]
        if texts in ([var, "++"], ["++", var]):
            env.assign(var, value + 1, False)
        elif texts in ([var, "--"], ["--", var]):
            env.assign(var, value - 1, False)
        elif len(texts) >= 3 and texts[0] == var and texts[1] in {"+=", "-="}:
            n = self.number(self.eval(step[2:]))
            if not isinstance(n, (int, float)):
                return False
            env.assign(var, value + n if texts[1] == "+=" else value - n, False)
        else:
            return False
        return True

    def exec_switch(self, head: list[Tok], body: tuple | None) -> None:
        value = self.number(self.eval(head))
        stmts = body[1] if body is not None and body[0] == "block" else ([body] if body is not None else [])
        if value is not None:
            start = None
            default = None
            for k, st in enumerate(stmts):
                if st[0] == "case":
                    if st[1] is None:
                        default = k
                    elif self.number(self.eval(st[1])) == value:
                        start = k
                        break
            if start is None:
                start = default
            if start is None:
                return
            self._body(("block", stmts[start:]), self.conditions_unknown)
            return
        self.conditions_unknown += 1
        try:
            self._body(("block", stmts), self.conditions_unknown + 1)
        finally:
            self.conditions_unknown -= 1

    def condition(self, toks: list[Tok]) -> bool | None:
        """The truth of a condition when the values it reads are known; None otherwise."""
        toks = strip_parens(toks)
        if not toks:
            return None
        for op in ("||", "&&"):
            k = top_index(toks, {op})
            if k is not None:
                a, b = self.condition(toks[:k]), self.condition(toks[k + 1 :])
                if op == "||":
                    if a is True or b is True:
                        return True
                    if a is False and b is False:
                        return False
                    return None
                if a is False or b is False:
                    return False
                if a is True and b is True:
                    return True
                return None
        if toks[0].text == "!" and len(toks) > 1:
            inner = self.condition(toks[1:])
            return None if inner is None else not inner
        k = top_index(toks, {"==", "!=", "<", ">", "<=", ">="})
        if k is not None:
            a, b = self.eval(toks[:k]), self.eval(toks[k + 1 :])
            op = toks[k].text
            if isinstance(a, str) and isinstance(b, str) and op in {"==", "!="}:
                return (a == b) == (op == "==")
            if op in {"==", "!="} and (a is None or b is None) and not isinstance(a, Raw) and not isinstance(b, Raw):
                same = a is b
                return same == (op == "==")
            na, nb = self.number(a), self.number(b)
            if na is None or nb is None:
                return None
            return {"==": na == nb, "!=": na != nb, "<": na < nb, ">": na > nb, "<=": na <= nb, ">=": na >= nb}[op]
        v = self.eval(toks)
        if v is None:
            return False
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        if isinstance(v, Raw):
            n = self.number(v)
            return None if n is None else bool(n)
        if isinstance(v, str):
            return True
        if isinstance(v, ArrayPtr):
            return v.current is not None
        if isinstance(v, (list, Lambda, FuncRef, StructRef, StructInit)) or hasattr(v, "__dataclass_fields__"):
            return True
        return None

    # -- simple statements

    def exec_simple(self, toks: list[Tok]) -> None:
        if not toks:
            return
        while toks and toks[0].text in {
            "static",
            "const",
            "constexpr",
            "inline",
            "else",
            "typedef",
            "using",
            "struct",
            "enum",
        }:
            if (
                toks[0].text in {"typedef", "using", "struct", "enum"}
                and "=" not in [t.text for t in toks]
                and "(" not in [t.text for t in toks]
            ):
                return
            toks = toks[1:]
        if not toks:
            return
        eq = top_index(toks, {"="})
        if eq is not None and eq > 0:
            lhs, rhs = toks[:eq], toks[eq + 1 :]
            self.assign(lhs, rhs)
            return
        for op in ("|=", "&=", "+=", "-="):
            k = top_index(toks, {op})
            if k is not None:
                self.compound(toks[:k], op, toks[k + 1 :])
                return
        # Array declared without initializer: ``static char names[N][M];`` (filled by SNPRINTF/strcpy)
        if len(toks) >= 4 and toks[-1].text == "]" and toks[0].kind == "id":
            k = next((j for j, t in enumerate(toks) if t.text == "["), None)
            if k is not None and k >= 2 and toks[k - 1].kind == "id":
                self.frame.env.assign(toks[k - 1].text, {}, True)
                return
        # Declaration without initializer: ``PropertyRNA *prop;`` / ``bNodeType ntype;``
        if (
            len(toks) >= 2
            and toks[-1].kind == "id"
            and all(t.kind == "id" or t.text in {"*", "&", "::", "<", ">", ","} for t in toks)
        ) and (toks[-2].kind == "id" or toks[-2].text in {"*", "&", ">"}):
            self.frame.env.assign(toks[-1].text, self.declared(toks[:-1], toks[-1].text), True)
            return
        # A macro standing for statements: ``SCULPT_BRUSH_CAPABILITY(has_accumulate, "Has Accumulate");``
        if toks[0].kind == "id" and toks[0].text not in self.handlers and toks[0].text not in self.index:
            m = self.tree.macro(self.file, toks[0].text, toks[0].pos)
            if m is not None and (m.params is None or (len(toks) > 1 and toks[1].text == "(")):
                from macro import expand

                expanded = expand(toks, lambda n_: self.tree.macro(self.file, n_, toks[0].pos), set(), toks[0].pos)
                if [t.text for t in expanded] != [t.text for t in toks]:
                    self.exec_nodes(parse_statements(expanded, 0, len(expanded)))
                    return
        self.eval(toks)

    def declared(self, type_toks: list[Tok], name: str) -> Any:
        """The value of a declared, uninitialized variable (hook for areas: ``bNodeType ntype``)."""
        hook = self.handlers.get("__declare__")
        if hook is not None:
            return hook(self, type_toks, name)
        return None

    def compound(self, lhs: list[Tok], op: str, rhs: list[Tok]) -> None:
        hook = self.handlers.get("__compound__")
        if hook is not None:
            target = self.eval(lhs[:-2]) if len(lhs) >= 3 and lhs[-2].text in {"->", "."} else None
            hook(self, target, lhs[-1].text if lhs else "", op, self.eval(rhs), rhs)

    def assign(self, lhs: list[Tok], rhs: list[Tok]) -> None:
        # Member assignment: ``ot->name = ...`` / ``ntype.ui_name = ...``
        if len(lhs) >= 3 and lhs[-2].text in {"->", "."} and lhs[-1].kind == "id":
            target = self.eval(lhs[:-2])
            value = self.eval(rhs)
            setter = getattr(target, "setmember", None)
            if setter is not None:
                setter(lhs[-1].text, value, self, rhs)
            return
        # Array declaration: ``static const float x[3] = {...};``
        is_array = False
        k = len(lhs) - 1
        while k >= 0 and lhs[k].text == "]":
            depth = 0
            while k >= 0:
                if lhs[k].text == "]":
                    depth += 1
                elif lhs[k].text == "[":
                    depth -= 1
                    if depth == 0:
                        break
                k -= 1
            k -= 1
            is_array = True
        if k < 0 or lhs[k].kind != "id":
            self.eval(rhs)
            return
        name = lhs[k].text
        declare = k > 0
        if rhs and rhs[0].text == "{":
            close = match_close(rhs, 0)
            value = self.initializer(lhs[:k], name, rhs[1:close], is_array)
        else:
            value = self.eval(rhs)
        self.frame.env.assign(name, value, declare)

    def initializer(self, type_toks: list[Tok], name: str, inner: list[Tok], is_array: bool) -> Any:
        hook = self.handlers.get("__initializer__")
        if hook is not None:
            value = hook(self, type_toks, name, inner, is_array)
            if value is not _MISSING:
                return value
        if is_array:
            return self.array_init(type_toks, inner)
        return None

    def array_init(self, type_toks: list[Tok], inner: list[Tok], file: CFile | None = None) -> list[Any]:
        """The elements of an array initializer; braced elements become ``StructInit`` (fields from the type)."""
        type_name = next(
            (
                t.text
                for t in reversed(type_toks)
                if t.kind == "id" and t.text not in {"const", "static", "struct", "constexpr"}
            ),
            "",
        )
        fields: list[str] | None = None
        brace = next((k for k, t in enumerate(type_toks) if t.text == "{"), None)
        if brace is not None:  # ``struct { ... } info[] = {...}``
            from ctok import field_names

            fields = field_names(type_toks[brace + 1 : match_close(type_toks, brace)])
        out: list[Any] = []
        for part in split_commas(inner):
            if part and part[0].text == "{":
                if fields is None:
                    fields = self.tree.struct_fields(file or self.file, type_name)
                close = match_close(part, 0)
                values: list[Any] = []
                named: dict[str, Any] = {}
                for elem in split_commas(part[1:close]):
                    if len(elem) >= 3 and elem[0].text == "." and elem[2].text == "=":
                        named[elem[1].text] = self.eval(elem[3:])
                    elif elem and elem[0].text == "{":
                        values.append([self.eval(x) for x in split_commas(elem[1 : match_close(elem, 0)])])
                    else:
                        values.append(self.eval(elem))
                out.append(StructInit(fields, values, named))
            else:
                out.append(self.eval(part))
        return out

    # -- expressions

    def eval(self, toks: list[Tok]) -> Any:
        toks = strip_parens(toks)
        n = len(toks)
        if n == 0:
            return None
        t0 = toks[0]
        if n == 1:
            return self.atom(t0)
        if t0.text == "[":
            return self.make_lambda(toks)
        if t0.text in {"&", "*"} and n > 1:
            if t0.text == "&" and toks[1].kind == "id" and toks[1].text.startswith("RNA_") and n == 2:
                return StructRef(toks[1].text[4:])
            return self.eval(toks[1:])
        if t0.text == "!" and n > 1:
            v = self.eval(toks[1:])
            if isinstance(v, (bool, int, float)) or v is None:
                return not v
            return Raw(toks, self.file)
        if t0.text == "(":
            close = match_close(toks, 0)
            inner = toks[1:close]
            if (
                close < n - 1
                and inner
                and all(t.kind == "id" or t.text in {"*", "&", "::"} for t in inner)
                and toks[close + 1].text not in BINARY_OPS
            ):
                return self.eval(toks[close + 1 :])  # C cast
        # Adjacent string literals and macros: ``"a" "b" MACRO``
        if any(t.kind == "str" for t in toks) and all(t.kind in {"str", "id"} for t in toks):
            return self.concat(toks)
        # Binary operators (also unary minus): numbers or Raw.
        if top_index(toks, BINARY_OPS) is not None:
            k = top_index(toks, {"?"})
            if k is not None:
                colon = top_index(toks[k + 1 :], {":"})
                if colon is not None:
                    cond = self.condition(toks[:k])
                    if cond is False:
                        return self.eval(toks[k + 2 + colon :])
                    if cond is None:
                        self.warn("ternary with an unknown condition: first branch taken")
                    return self.eval(toks[k + 1 : k + 1 + colon])
                return Raw(toks, self.file)
            # Keep names (flags: ``PROP_A | PROP_B``) unless the expression reads local values.
            env = self.frame.env
            has_ids = False
            reads_locals = False
            for t in toks:
                if t.kind == "id":
                    has_ids = True
                    if env.find(t.text)[0]:
                        reads_locals = True
                        break
            if has_ids and not reads_locals:
                return Raw(toks, self.file)
            v = self.number_with_env(toks)
            if v is not None:
                return v
            return Raw(toks, self.file)
        return self.postfix(toks)

    def atom(self, t: Tok) -> Any:
        if t.kind == "str":
            return string_value(t.text)
        if t.kind == "num":
            v = eval_number(t.text)
            return v if v is not None else Raw([t], self.file)
        if t.kind == "chr":
            v = string_value('"' + t.text.split("'", 1)[1].rsplit("'", 1)[0] + '"')
            return ord(v[0]) if v else 0
        if t.kind == "id":
            return self.lookup(t)
        return Raw([t], self.file)

    def lookup(self, t: Tok) -> Any:
        name = t.text
        found, value = self.frame.env.find(name)
        if found:
            return value
        if name in {"nullptr", "NULL"}:
            return None
        if name == "true":
            return True
        if name == "false":
            return False
        if self.global_lookup is not None:
            value = self.global_lookup(name, self.file)
            if value is not _MISSING:
                return value
        if name in self.index:
            return FuncRef(name, self.index[name])
        m = self.tree.macro(self.file, name, t.pos)
        if m is not None and m.params is None and m.body and m.body != name:
            from macro import expand

            toks = expand(m.tokens, lambda n_, p_=t.pos: self.tree.macro(self.file, n_, p_), {name}, t.pos)
            if toks:
                return self.eval(toks)
        if name.startswith("RNA_") and name[4:5].isupper():
            # ``StructRNA &RNA_Object``: 5.x passes the generated structs by reference, without ``&``.
            return StructRef(name[4:])
        return Raw([t], self.file)

    def concat(self, toks: list[Tok]) -> Any:
        from macro import expand

        out = []
        expanded = expand(toks, lambda n_: self.tree.macro(self.file, n_, toks[0].pos), set(), toks[0].pos)
        for t in expanded:
            if t.kind == "str":
                out.append(string_value(t.text))
            elif t.kind == "id":
                found, value = self.frame.env.find(t.text)
                if found and isinstance(value, str):
                    out.append(value)
                else:
                    self.warn("unresolved name in string concatenation", t.text)
            else:
                return Raw(toks, self.file)
        return "".join(out)

    def make_lambda(self, toks: list[Tok]) -> Any:
        close = match_close(toks, 0)
        k = close + 1
        params: list[Any] = []
        if k < len(toks) and toks[k].text == "(":
            pclose = match_close(toks, k)
            params = parse_params(toks[k + 1 : pclose])
            k = pclose + 1
        while k < len(toks) and toks[k].text != "{":
            k += 1
        if k >= len(toks):
            return Raw(toks, self.file)
        body_close = match_close(toks, k)
        # Find the token indexes in the file to reuse the statement cache.
        file_toks = self.file.tokens
        start = _index_of(file_toks, toks[k])
        end = _index_of(file_toks, toks[body_close])
        if start is None or end is None:
            return Raw(toks, self.file)
        return Lambda(params, self.file, start + 1, end, self.frame.env)

    def postfix(self, toks: list[Tok]) -> Any:
        n = len(toks)
        i = 0
        value: Any = _MISSING
        if toks[0].text in CASTS and n > 1 and toks[1].text == "<":
            k = 2
            depth = 1
            while k < n and depth:
                if toks[k].text == "<":
                    depth += 1
                elif toks[k].text == ">":
                    depth -= 1
                elif toks[k].text == ">>":
                    depth -= 2
                k += 1
            if k < n and toks[k].text == "(":
                close = match_close(toks, k)
                value = self.eval(toks[k + 1 : close])
                i = close + 1
        if value is _MISSING:
            if toks[0].text == "::":
                i = 1
            if i >= n or toks[i].kind != "id":
                return Raw(toks, self.file)
            # Qualified name: a::b::c
            name_tok = toks[i]
            i += 1
            while i + 1 < n and toks[i].text == "::" and toks[i + 1].kind == "id":
                name_tok = toks[i + 1]
                i += 2
            i = self._skip_template(toks, i)
            if i < n and toks[i].text == "(":
                args, close = call_args(toks, i)
                value = self.call(name_tok, args)
                i = close + 1
            elif i < n and toks[i].text == "{" and name_tok.text[:1].isupper():
                close = match_close(toks, i)  # ``Type{...}`` construction
                value = Raw(toks[: close + 1], self.file)
                i = close + 1
            else:
                value = self.lookup(name_tok)
        while i < n:
            s = toks[i].text
            if s in {".", "->"} and i + 1 < n and toks[i + 1].kind == "id":
                member = toks[i + 1].text
                i += 2
                i = self._skip_template(toks, i)
                if i < n and toks[i].text == "(":
                    args, close = call_args(toks, i)
                    method = getattr(value, "callmethod", None)
                    if method is not None:
                        value = method(member, [self.eval(a) for a in args], self, args)
                    else:
                        getter = getattr(value, "getmember", None)
                        target = getter(member, self) if getter is not None else None
                        if isinstance(target, (FuncRef, Lambda)):
                            value = self.call_value(target, args, toks[i])
                        else:
                            self._side_effects(args)
                            value = Raw(toks, self.file)
                    i = close + 1
                else:
                    getter = getattr(value, "getmember", None)
                    value = getter(member, self) if getter is not None else Raw(toks, self.file)
            elif s == "(":
                args, close = call_args(toks, i)
                value = self.call_value(value, args, toks[i])
                i = close + 1
            elif s == "[":
                close = match_close(toks, i)
                idx = self.number(self.eval(toks[i + 1 : close]))
                if isinstance(value, list) and isinstance(idx, int) and 0 <= idx < len(value):
                    value = value[idx]
                elif isinstance(value, str) and isinstance(idx, int):
                    value = ord(value[idx]) if 0 <= idx < len(value) else 0
                elif hasattr(value, "raw_values") and isinstance(idx, int):  # an EnumArray
                    value = (
                        ItemView(value.items[idx], value.raw_values[idx])
                        if 0 <= idx < len(value.items)
                        else ItemView(None, "")
                    )
                elif isinstance(value, dict) and isinstance(idx, int):
                    value = value.get(idx)
                elif isinstance(value, ArrayPtr) and isinstance(idx, int):
                    value = ArrayPtr(value.items, value.index + idx).current
                else:
                    value = Raw(toks, self.file)
                i = close + 1
            else:
                return Raw(toks, self.file)
        return value

    def _skip_template(self, toks: list[Tok], i: int) -> int:
        n = len(toks)
        if i < n and toks[i].text == "<":
            depth = 0
            k = i
            while k < n:
                s = toks[k].text
                if s == "<":
                    depth += 1
                elif s == ">":
                    depth -= 1
                elif s == ">>":
                    depth -= 2
                elif s in {";", "{", "}", "&&", "||"}:
                    return i
                if depth <= 0:
                    break
                k += 1
            if k + 1 < n and toks[k + 1].text in {"(", "{", "::"}:
                return k + 1
        return i

    def _side_effects(self, args: list[list[Tok]]) -> None:
        for a in args:
            if any(t.kind == "id" and (t.text in self.handlers or t.text in self.index) for t in a):
                self.eval(a)

    def string_store(self, name: str, args: list[list[Tok]]) -> None:
        """``SNPRINTF(buf, "x_%s", id)`` / ``STRNCPY(buf, src)``: store the string into ``buf``."""
        if name.startswith(("SNPRINTF", "BLI_snprintf")):
            fmt_k = 2 if name == "BLI_snprintf" else 1
            fmt = self.eval(args[fmt_k]) if len(args) > fmt_k else None
            vals = [self.eval(a) for a in args[fmt_k + 1 :]]
            if not isinstance(fmt, str) or any(isinstance(v, Raw) or v is None for v in vals):
                text = None
            else:
                try:
                    text = re.sub(r"%(?:[-+ #0]*\d*(?:\.\d+)?)(?:z|l|ll|h)?([sdiufgxc])", "%\\1", fmt) % tuple(vals)
                except (TypeError, ValueError):
                    text = None
        else:
            src = self.eval(args[1]) if len(args) > 1 else None
            text = src if isinstance(src, str) else None
        target = args[0]
        if len(target) == 1 and target[0].kind == "id":
            self.frame.env.assign(target[0].text, text, False)
        elif len(target) >= 4 and target[0].kind == "id" and target[1].text == "[":
            _found, arr = self.frame.env.find(target[0].text)
            idx = self.number(self.eval(target[2 : match_close(target, 1)]))
            if isinstance(arr, dict) and isinstance(idx, int):
                arr[idx] = text

    def call_value(self, value: Any, args: list[list[Tok]], at: Tok) -> Any:
        vals = [self.eval(a) for a in args]
        if isinstance(value, Lambda):
            return self.run_lambda(value, vals)
        if isinstance(value, FuncRef):
            fd = self.lookup_function(value.name, self.file)
            if fd is not None:
                return self.run(fd, vals)
        return Raw([at], self.file)

    def call(self, name_tok: Tok, args: list[list[Tok]]) -> Any:
        name = name_tok.text
        if name in {"ARRAY_SIZE", "size"} and len(args) == 1:
            v = self.eval(args[0])
            if isinstance(v, list):
                return len(v)
        if name in {"SNPRINTF", "BLI_snprintf", "SNPRINTF_UTF8", "STRNCPY", "BLI_strncpy", "STRNCPY_UTF8"} and args:
            self.string_store(name, args)
            return None
        handler = self.handlers.get(name)
        if handler is not None:
            vals = [self.eval(a) for a in args]
            return handler(self, vals, args, name_tok.pos)
        if name in I18N and args:
            return self.eval(args[I18N[name]])
        found, value = self.frame.env.find(name)
        if found and isinstance(value, (Lambda, FuncRef)):
            return self.call_value(value, args, name_tok)
        fd = self.lookup_function(name, self.file)
        if fd is not None and self.is_relevant(fd):
            vals = [self.eval(a) for a in args]
            return self.run(fd, vals)
        m = self.tree.macro(self.file, name, name_tok.pos)
        if m is not None and m.params is not None:
            from macro import expand

            call_toks = [name_tok, Tok("op", "(", name_tok.pos)]
            for k, a in enumerate(args):
                if k:
                    call_toks.append(Tok("op", ",", name_tok.pos))
                call_toks += a
            call_toks.append(Tok("op", ")", name_tok.pos))
            expanded = expand(call_toks, lambda n_: self.tree.macro(self.file, n_, name_tok.pos), set(), name_tok.pos)
            if expanded and [t.text for t in expanded] != [t.text for t in call_toks]:
                return self.eval(expanded)
        fallback = self.handlers.get("__call__")
        if fallback is not None:
            result = fallback(self, name, args, name_tok.pos)
            if result is not _MISSING:
                return result
        self._side_effects(args)
        return Raw([name_tok], self.file)


def _index_of(toks: list[Tok], tok: Tok) -> int | None:
    # Tokens are sorted by position: bisect.
    lo, hi = 0, len(toks)
    pos = tok.pos
    while lo < hi:
        mid = (lo + hi) // 2
        if toks[mid].pos < pos:
            lo = mid + 1
        else:
            hi = mid
    if lo < len(toks) and toks[lo] is tok:
        return lo
    return lo if lo < len(toks) and toks[lo].pos == pos else None


MISSING = _MISSING
