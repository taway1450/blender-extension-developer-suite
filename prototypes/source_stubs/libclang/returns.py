"""Classify the pointer returns of RNA functions: can the C function hand Python a NULL pointer?

RNA has no flag for it (``PROP_NEVER_NULL`` is checked only for arguments), so the answer is in the C bodies. They
are behind ``#ifdef RNA_RUNTIME``, so each ``rna_*.cc`` is parsed a second time with ``-DRNA_RUNTIME``, and calls are
followed into the files that define the callees (blenkernel, animrig, editors), a few rounds deep.

A small path-sensitive walk over the lowered AST (``lower.py``) collects what every ``return`` can give:

- ``never``: an address (``&x``), ``new``, a string, an allocation (``MEM_*``), ``this``, or a local the walk knows
  is non-null: assigned from such a value, or checked (``if (!x) return ...;``, a loop's ``for (x = first; x; ...)``).
- ``null``: ``nullptr``, ``0`` or ``PointerRNA_NULL``, or a callee that can return NULL.
- ``raises``: NULL after an error report on the same path. ``pyrna_func_call`` (``bpy_rna.cc``) turns any report of
  level ``RPT_ERROR`` or above into a ``RuntimeError`` (``BPy_reports_to_error``), so that NULL never reaches Python.
- ``unknown``: a callee without a parsed body, a struct field, an array element, a call through a pointer.

Calls are followed with each argument's nullness bound to the callee's parameter, so ``get(ob) { if (!ob) return
nullptr; ... }`` called with the never-null ``self`` gives ``never``. A ``PointerRNA`` return is NULL when its
``data`` is (``pyrna_struct_CreatePyObject`` gives ``None`` for it), so ``RNA_pointer_create_discrete(owner, type,
data)`` follows ``data``.

The verdict of a function is ``null`` if any return can be NULL, else ``unknown`` if any return is unknown, else
``raises`` if any return is NULL after a report, else ``never``.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from libclang.interp import Function, Program

NEVER, NULL, RAISES, UNKNOWN = "never", "null", "raises", "unknown"
RANK = {NULL: 3, UNKNOWN: 2, RAISES: 1, NEVER: 0}
RPT_ERROR = 1 << 5  # BKE_report.hh: the error levels are RPT_ERROR and up
REPORT_FUNCTIONS = {"BKE_report", "BKE_reportf"}
# Allocation: guarded allocators abort or return memory; ``new`` throws.
ALLOCATORS = re.compile(r"MEM_(new|cnew|calloc|malloc|dupalloc|new_array|calloc_array|malloc_array)\w*$")
POINTER_RNA_DATA = {"RNA_pointer_create_discrete": 2, "RNA_pointer_create_with_parent": 2, "RNA_id_pointer_create": 0}
POINTER_RNA_NULL = {"PointerRNA_NULL"}
MAX_DEPTH = 8


@dataclass(frozen=True)
class Outcome:
    kind: str
    where: str  # file:line of the return (or the call that gave it)
    why: str


@dataclass
class Verdict:
    kind: str
    outcomes: list[Outcome] = field(default_factory=list)

    @property
    def evidence(self) -> Outcome | None:
        best = [o for o in self.outcomes if o.kind == self.kind]
        return best[0] if best else None


Value = frozenset[Outcome]


def _one(kind: str, where: str, why: str) -> Value:
    return frozenset({Outcome(kind, where, why)})


def _never_only(value: Value) -> bool:
    return bool(value) and all(o.kind == NEVER for o in value)


def _null_only(value: Value) -> bool:
    return bool(value) and all(o.kind in (NULL, RAISES) for o in value)


def _is_null_literal(e) -> bool:
    return isinstance(e, list) and bool(e) and (e[0] == "null" or (e[0] == "i" and e[1] == 0))


@dataclass
class State:
    env: dict[str, Value]
    reported: bool = False

    def copy(self) -> State:
        return State(dict(self.env), self.reported)


def _merge(states: list[State | None]) -> State | None:
    live = [s for s in states if s is not None]
    if not live:
        return None
    env: dict[str, Value] = {}
    for s in live:
        for k, val in s.env.items():
            env[k] = env.get(k, frozenset()) | val
    return State(env, all(s.reported for s in live))


class Returns:
    """Return summaries of the functions in ``program``, memoized per argument nullness."""

    def __init__(self, program: Program) -> None:
        self.program = program
        self.memo: dict[tuple[str, tuple[str, ...]], Value] = {}
        self.active: set[tuple[str, tuple[str, ...]]] = set()
        self.unresolved: set[tuple[str, str]] = set()  # (record or "", name) of callees without a body
        self.methods: dict[str, list[Function]] = {}
        for f in program.functions.values():
            if "@S@" in f.usr or "::" in f.qual:
                self.methods.setdefault(f.name, []).append(f)

    # ------------------------------------------------------------------------------------------------------------
    # Entry points

    def verdict(self, fn: Function, args: tuple[str, ...]) -> Verdict:
        outcomes = sorted(self.summary(fn, args, 0), key=lambda o: (-RANK[o.kind], o.where))
        if not outcomes:
            return Verdict(UNKNOWN, [Outcome(UNKNOWN, f"{fn.file}:{fn.line}", "no return statement")])
        kind = max((o.kind for o in outcomes), key=RANK.__getitem__)
        return Verdict(kind, outcomes)

    def summary(self, fn: Function, args: tuple[str, ...], depth: int) -> Value:
        key = (fn.usr, args)
        if key in self.memo:
            return self.memo[key]
        where = f"{fn.file}:{fn.line}"
        if key in self.active or depth > MAX_DEPTH:
            return _one(UNKNOWN, where, f"recursion or depth limit in {fn.name}")
        self.active.add(key)
        self.fn, saved = fn, getattr(self, "fn", None)
        self.depth, saved_depth = depth, getattr(self, "depth", 0)
        env: dict[str, Value] = {}
        for i, (name, ptype, _rec) in enumerate(fn.params):
            if i < len(args) and args[i] == NEVER or ptype.endswith("&"):
                env[name] = _one(NEVER, where, f"parameter {name}")
            else:
                env[name] = _one(UNKNOWN, where, f"parameter {name} may be NULL")
        self.outs: list[Outcome]
        outs_saved = getattr(self, "outs", None)
        self.outs = []
        self.walk(fn.body, State(env), None)
        result = frozenset(self.outs)
        self.outs = outs_saved  # type: ignore[assignment]
        self.fn, self.depth = saved, saved_depth  # type: ignore[assignment]
        self.active.discard(key)
        self.memo[key] = result
        return result

    def where(self, line) -> str:
        return f"{self.fn.file}:{line}"

    # ------------------------------------------------------------------------------------------------------------
    # Statements

    def walk(self, stmts: list, st: State | None, breaks: list | None) -> State | None:
        for s in stmts:
            if st is None:
                return None
            tag = s[0]
            if tag == "decl":
                st.env[s[1]] = self.eval(s[3], st, s[4]) if s[3] is not None else _one(UNKNOWN, self.where(s[4]), "uninitialized")
            elif tag == "e":
                self.effect(s[1], st, s[2])
            elif tag == "if":
                st = self.branch(s[1], s[2], s[3], st, s[4], breaks)
            elif tag == "loop":
                st = self.loop(s, st)
            elif tag == "switch":
                inner: list[State | None] = []
                after = self.walk_cases(s[2], st, inner)
                st = _merge([st, after, *inner])
            elif tag == "ret":
                self.ret(s[1], st, s[2])
                return None
            elif tag == "break":
                if breaks is not None:
                    breaks.append(st)
                return None
        return st

    def walk_cases(self, stmts: list, st: State, breaks: list) -> State | None:
        """A switch body: after a ``return`` or ``break`` the next statement is reached through another case."""
        cur: State | None = st.copy()
        for s in stmts:
            if cur is None:
                cur = st.copy()
            cur = self.walk([s], cur, breaks)
        return cur

    def loop(self, s: list, st: State) -> State:
        body, cond = s[2], s[4] if len(s) > 4 else None
        inside = st.copy()
        if cond is not None:
            self.effect(cond, inside, s[3])
            inside, _ = self.refine(cond, inside, s[3])
        if s[1] == "range" and len(s) > 6 and s[6]:
            inside.env[s[6]] = _one(UNKNOWN, self.where(s[3]), f"element {s[6]} of a range")
        breaks: list[State | None] = []
        after = self.walk(body, inside, breaks) if inside is not None else None
        merged = _merge([st, after, *breaks])
        return merged if merged is not None else st

    def branch(self, cond, then: list, other: list, st: State, line, breaks) -> State | None:
        self.effect(cond, st, line)
        if isinstance(cond, list) and cond and cond[0] == "i":
            return self.walk(then if cond[1] else other, st, breaks)
        a, b = self.refine(cond, st, line)
        return _merge(
            [self.walk(then, a, breaks) if a is not None else None, self.walk(other, b, breaks) if b is not None else None]
        )

    def ret(self, e, st: State, line) -> None:
        if e is None:
            return
        for o in self.eval(e, st, line):
            if o.kind == NULL and st.reported:
                self.outs.append(Outcome(RAISES, o.where, f"{o.why}, after an error report"))
            else:
                self.outs.append(o)

    def effect(self, e, st: State, line) -> None:
        """Side effects the walk tracks: assignments to locals and error reports."""
        if not isinstance(e, list) or not e:
            return
        tag = e[0]
        if tag == "a" and e[1] == "=" and isinstance(e[2], list) and e[2][:1] == ["v"]:
            st.env[e[2][1]] = self.eval(e[3], st, line)
        elif tag == "c":
            if e[2] in REPORT_FUNCTIONS and len(e[3]) > 1:
                level = e[3][1]
                if isinstance(level, list) and level[:1] == ["k"] and level[2] >= RPT_ERROR:
                    st.reported = True
            for a in e[3]:
                self.effect(a, st, line)
        elif tag in ("b", "u"):
            for sub in e[2:]:
                self.effect(sub, st, line)

    # ------------------------------------------------------------------------------------------------------------
    # Conditions

    def refine(self, cond, st: State, line) -> tuple[State | None, State | None]:
        """The states on the true and the false side of ``cond`` (None: that side cannot happen)."""
        if not isinstance(cond, list) or not cond:
            return st.copy(), st.copy()
        tag = cond[0]
        if tag == "a" and cond[1] == "=" and isinstance(cond[2], list) and cond[2][:1] == ["v"]:
            return self.refine(cond[2], st, line)
        if tag == "u" and cond[1] == "!":
            a, b = self.refine(cond[2], st, line)
            return b, a
        if tag == "b" and cond[1] in ("==", "!="):
            l, r = cond[2], cond[3]
            if _is_null_literal(r) or _is_null_literal(l):
                var = l if _is_null_literal(r) else r
                a, b = self.refine(var, st, line)
                return (b, a) if cond[1] == "==" else (a, b)
        if tag == "b" and cond[1] == "&&":
            a1, b1 = self.refine(cond[2], st, line)
            if a1 is None:
                return None, b1
            a2, b2 = self.refine(cond[3], a1, line)
            return a2, _merge([b1, b2])
        if tag == "b" and cond[1] == "||":
            a1, b1 = self.refine(cond[2], st, line)
            if b1 is None:
                return a1, None
            a2, b2 = self.refine(cond[3], b1, line)
            return _merge([a1, a2]), b2
        if tag == "v" and cond[1] in st.env:
            name, val = cond[1], st.env[cond[1]]
            yes, no = st.copy(), st.copy()
            yes.env[name] = _one(NEVER, self.where(line), f"{name} checked non-null")
            no.env[name] = _one(NULL, self.where(line), f"{name} checked NULL")
            return (None if _null_only(val) else yes), (None if _never_only(val) else no)
        return st.copy(), st.copy()

    # ------------------------------------------------------------------------------------------------------------
    # Expressions

    def eval(self, e, st: State, line) -> Value:
        where = self.where(line)
        if not isinstance(e, list) or not e:
            return _one(UNKNOWN, where, "no expression")
        tag = e[0]
        if _is_null_literal(e):
            return _one(NULL, where, "returns NULL")
        if tag in ("s", "lambda") or (tag == "u" and e[1] == "&"):
            return _one(NEVER, where, "an address")
        if tag == "x" and e[1] == "CXX_NEW_EXPR":
            return _one(NEVER, where, "new")
        if tag == "v":
            if e[1] == "this":
                return _one(NEVER, where, "this")
            return st.env.get(e[1], _one(UNKNOWN, where, f"{e[1]} unknown"))
        if tag == "g":
            if e[2] in POINTER_RNA_NULL:
                return _one(NULL, where, e[2])
            if "[" in e[3]:
                return _one(NEVER, where, "an array")
            return _one(UNKNOWN, where, f"global {e[2]}")
        if tag == "?":
            a, b = self.refine(e[1], st, line)
            return (self.eval(e[2], a, line) if a else frozenset()) | (self.eval(e[3], b, line) if b else frozenset())
        if tag == "a":
            value = self.eval(e[3], st, line)
            if isinstance(e[2], list) and e[2][:1] == ["v"]:
                st.env[e[2][1]] = value
            return value
        if tag == "init" and isinstance(e[2], dict) and "data" in e[2]:
            return self.eval(e[2]["data"], st, line)
        if tag == "c":
            return self.call(e, st, line)
        if tag == "mc":
            return self.method(e, st, line)
        if tag == "m":
            return _one(UNKNOWN, where, f"field {e[2]}")
        return _one(UNKNOWN, where, f"{tag} expression")

    def args_of(self, args: list, st: State, line) -> tuple[str, ...]:
        return tuple(NEVER if _never_only(self.eval(a, st, line)) else "maybe" for a in args)

    def follow(self, fn: Function, args: tuple[str, ...], where: str) -> Value:
        out = set()
        for o in self.summary(fn, args, self.depth + 1):
            why = o.why if o.why.startswith("via ") else f"via {fn.name} ({o.where}: {o.why})"
            out.add(Outcome(o.kind, where, why))
        return frozenset(out)

    def call(self, e: list, st: State, line) -> Value:
        where = self.where(line)
        usr, name, args = e[1], e[2], e[3]
        if ALLOCATORS.match(name or ""):
            return _one(NEVER, where, f"allocation ({name})")
        if name in POINTER_RNA_DATA and len(args) > POINTER_RNA_DATA[name]:
            return self.eval(args[POINTER_RNA_DATA[name]], st, line)
        if usr is None:
            return _one(UNKNOWN, where, f"call through a pointer ({name})")
        fn = self.program.resolve(usr, name, len(args), self.fn.file)
        if fn is None:
            self.unresolved.add(("", name))
            return _one(UNKNOWN, where, f"no body for {name}")
        return self.follow(fn, self.args_of(args, st, line), where)

    def method(self, e: list, st: State, line) -> Value:
        where = self.where(line)
        name, base, args = e[1], e[2], e[3]
        record = base[-1] if isinstance(base, list) and base and isinstance(base[-1], str) else ""
        record = record.split("::")[-1]
        cands = [f for f in self.methods.get(name, []) if record and f"@S@{record}@" in f.usr]
        cands = [f for f in cands if len(f.params) >= len(args)]
        if not cands:
            self.unresolved.add((record, name))
            return _one(UNKNOWN, where, f"no body for {record}::{name}")
        return self.follow(cands[0], self.args_of(args, st, line), where)


# --------------------------------------------------------------------------------------------------------------------
# Driving it over the RNA functions


def rna_arguments(f, c_params: list) -> tuple[str, ...]:
    """The nullness of each C parameter of an RNA function's C implementation, in makesrna's calling order:
    ``[self_id] [self] [Main] [bContext] [ReportList]`` then the RNA parameters (the return value excluded)."""
    lead = []
    if "use_self_id" in f.flags:
        lead.append(NEVER)
    if "no_self" not in f.flags or "use_self_type" in f.flags:
        lead.append(NEVER)
    for flag in ("use_main", "use_context", "use_reports"):
        if flag in f.flags:
            lead.append(NEVER)
    rest = [p for p in f.parameters if p.identifier != f.returns]
    kinds = [NEVER if (p.type == "pointer" and p.never_null) or p.type != "pointer" else "maybe" for p in rest]
    if len(lead) + len(kinds) == len(c_params):
        return (*lead, *kinds)
    by_name = {p.identifier: k for p, k in zip(rest, kinds, strict=True)}
    return tuple(by_name.get(name, NEVER if i < len(lead) else "maybe") for i, (name, _t, _r) in enumerate(c_params))


DEFINITION = re.compile(r"^(?![#/\s{}])(?!return\b)[^;=\n(]*?\b(?:(\w+)::)?(\w+)\s*\(", re.M)


def definition_index(source: Path) -> dict[str, set[tuple[str, str]]]:
    """Function name -> {(class or "", file)} for every top-level definition-looking line under ``source/blender``."""
    index: dict[str, set[tuple[str, str]]] = {}
    for path in (source / "source" / "blender").rglob("*.cc"):
        rel = str(path.relative_to(source))
        if "/tests/" in rel or rel.endswith(("_test.cc", "_tests.cc")):
            continue
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        for m in DEFINITION.finditer(text):
            index.setdefault(m.group(2), set()).add((m.group(1) or "", rel))
    return index


def callee_files(unresolved: set[tuple[str, str]], index: dict[str, set[tuple[str, str]]], limit: int = 3) -> set[str]:
    """The files that define the unresolved callees; names defined in more than ``limit`` files are skipped."""
    files: set[str] = set()
    for record, name in unresolved:
        hits = index.get(name, set())
        if record:
            hits = {h for h in hits if h[0] == record} or set()
        if 0 < len({f for _c, f in hits}) <= limit:
            files.update(f for _c, f in hits)
    return files


def classify(model, program: Program) -> tuple[Counter, Returns]:
    """Set ``returns_null`` / ``returns_null_why`` on every RNA function returning a pointer."""
    returns = Returns(program)
    counts: Counter = Counter()
    for s in model.structs:
        for f in s.functions:
            ret = next((p for p in f.parameters if p.identifier == f.returns), None)
            if ret is None or ret.type != "pointer":
                continue
            fn = program.function(f.c_function, "") if f.c_function else None
            if fn is None:
                f.returns_null, f.returns_null_why = UNKNOWN, f"no body for {f.c_function or '(no C function)'}"
            else:
                v = returns.verdict(fn, rna_arguments(f, fn.params))
                ev = v.evidence
                f.returns_null = v.kind
                f.returns_null_why = f"{ev.where}: {ev.why}" if ev else ""
            counts[f.returns_null] += 1
    return counts, returns


def report(model) -> str:
    """``returns.md``: the verdict of every RNA function returning a pointer, with its evidence."""
    rows = [
        (f.returns_null, f"{s.identifier}.{f.identifier}", f.c_function, f.returns_null_why)
        for s in model.structs
        for f in s.functions
        if f.returns_null
    ]
    counts = Counter(r[0] for r in rows)
    lines = [
        "# RNA pointer returns, classified from the C bodies (libclang)",
        "",
        "See `prototypes/source_stubs/libclang/returns.py` for the rules.",
        "",
        "| Verdict | Functions | Stub |",
        "|---|---|---|",
    ]
    stub = {NEVER: "`X`", RAISES: "`X` (NULL only with an error, which raises)", NULL: "`X | None`", UNKNOWN: "`X | None`"}
    for kind in (NEVER, RAISES, NULL, UNKNOWN):
        lines.append(f"| {kind} | {counts.get(kind, 0)} | {stub[kind]} |")
    reasons = Counter(re.sub(r"\(.*", "", r[3].split(": ", 1)[-1]).strip() for r in rows if r[0] == UNKNOWN)
    lines += ["", "Why unknown (most common):", ""]
    lines += [f"- {why}: {n}" for why, n in reasons.most_common(15)]
    for kind in (NULL, RAISES, NEVER, UNKNOWN):
        lines += ["", f"## {kind}", "", "| Function | C function | Evidence |", "|---|---|---|"]
        lines += [f"| `{name}` | `{c}` | {why} |" for k, name, c, why in sorted(rows) if k == kind]
    return "\n".join(lines) + "\n"
