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

Conditions are remembered along the path as facts (``supported(ob)`` held, ``ob->type == OB_MESH`` did not), so a
test the path already decided takes only its feasible side. A local stands for its initializer in a fact until it is
assigned. Facts that name only a callee's arguments follow the call into the callee (``if (!supported(ob)) return
...; return add(ob);`` where ``add`` tests ``supported(ob)`` again), and what holds on every path where a callee
returns true (false) holds after ``if (check(ob))`` in the caller. Struct fields are not invalidated by calls, so a
callee that changes ``ob->type`` between two tests would fool it; RNA functions do not.

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


def _path(e) -> str | None:
    """``x`` or ``x->f`` (``x.f``): the locals and fields of locals the walk tracks."""
    if isinstance(e, list) and e[:1] == ["v"]:
        return e[1]
    if isinstance(e, list) and e[:1] == ["m"] and isinstance(e[1], list) and e[1][:1] == ["v"]:
        return f"{e[1][1]}->{e[2]}"
    return None


def _pointee(t: str) -> str | None:
    """``const Foo *`` -> ``Foo`` (None for a non-pointer or ``void *``)."""
    if not t.rstrip().endswith("*"):
        return None
    base = re.sub(r"\b(const|struct|volatile)\b", "", t.rstrip()[:-1]).replace(" ", "").split("::")[-1]
    return None if base in ("void", "") else base


def _is_null_literal(e) -> bool:
    return isinstance(e, list) and bool(e) and (e[0] == "null" or (e[0] == "i" and e[1] == 0))


# A fact is a canonical condition (nested tuples, types and lines dropped) and whether it held.
Key = tuple
Facts = dict[Key, bool]


def canon(e, defs: dict[str, Key]) -> Key | None:
    """The canonical form of a side-effect-free expression, or None. Locals in ``defs`` stand for their initializer."""
    if not isinstance(e, list) or not e:
        return None
    tag = e[0]
    if tag == "v":
        return defs.get(e[1], ("v", e[1]))
    if tag in ("i", "k"):
        return ("i", e[-1] if tag == "k" else e[1])
    if tag == "null":
        return ("i", 0)
    if tag == "g":
        return ("g", e[2])
    if tag == "s":
        return ("s", e[1])
    if tag == "m":
        base = canon(e[1], defs)
        return None if base is None else ("m", base, e[2])
    if tag == "u" and e[1] in ("!", "-", "~", "*", "&"):
        inner = canon(e[2], defs)
        return None if inner is None else ("u", e[1], inner)
    if tag == "b" and e[1] not in (",",):
        l, r = canon(e[2], defs), canon(e[3], defs)
        return None if l is None or r is None else ("b", e[1], l, r)
    if tag == "idx":
        a, i = canon(e[1], defs), canon(e[2], defs)
        return None if a is None or i is None else ("idx", a, i)
    if tag == "c" and e[2]:
        args = tuple(canon(a, defs) for a in e[3])
        return None if None in args else ("c", e[2], args)
    if tag == "mc":
        base = canon(e[2], defs)
        args = tuple(canon(a, defs) for a in e[3])
        return None if base is None or None in args else ("mc", e[1], base, args)
    return None


def _mentions(key, leaves: set) -> bool:
    if key in leaves:
        return True
    return isinstance(key, tuple) and any(_mentions(k, leaves) for k in key[1:])


def _substitute(key, mapping: dict):
    if key in mapping:
        return mapping[key]
    if isinstance(key, tuple) and key and isinstance(key[0], str):
        return (key[0], *(_substitute(k, mapping) for k in key[1:]))
    if isinstance(key, tuple):
        return tuple(_substitute(k, mapping) for k in key)
    return key


def _variables(key) -> set[str]:
    if isinstance(key, tuple) and key[:1] == ("v",):
        return {key[1]}
    if isinstance(key, tuple):
        return set().union(*(_variables(k) for k in key)) if key else set()
    return set()


def _parameters(key) -> bool:
    """Whether ``key`` still names a callee parameter (``("p", i)``)."""
    if isinstance(key, tuple) and key[:1] == ("p",):
        return True
    return isinstance(key, tuple) and any(_parameters(k) for k in key)


def _translate(facts, mapping: dict) -> Facts:
    """``facts`` with ``mapping`` substituted, keeping only those whose variables were all mapped."""
    out: Facts = {}
    for k, held in facts.items() if isinstance(facts, dict) else facts:
        new = _substitute(k, mapping)
        if not _variables(new):
            out[new] = held
    return out


def _condition(cond) -> tuple[list, bool]:
    """``a != b`` is the negation of ``a == b``: the condition to key facts by, and whether it is negated."""
    if isinstance(cond, list) and cond[:2] == ["b", "!="]:
        return ["b", "==", cond[2], cond[3]], True
    return cond, False


def _assigned(stmts) -> set[str]:
    """The locals assigned, incremented or address-taken anywhere in ``stmts``."""
    out: set[str] = set()

    def visit(x) -> None:
        if not isinstance(x, list) or not x:
            return
        if x[0] == "a" and isinstance(x[2], list) and x[2][:1] == ["v"]:
            out.add(x[2][1])
        if (
            x[0] == "u"
            and x[1] in ("++", "--", "&", "post++", "post--")
            and isinstance(x[2], list)
            and x[2][:1] == ["v"]
        ):
            out.add(x[2][1])
        if x[0] == "decl" and isinstance(x[1], str):
            out.add(x[1])
        for sub in x[1:]:
            visit(sub)

    visit(stmts)
    return out


@dataclass
class State:
    env: dict[str, Value]
    reported: bool = False
    facts: Facts = field(default_factory=dict)
    defs: dict[str, Key] = field(default_factory=dict)

    def copy(self) -> State:
        return State(dict(self.env), self.reported, dict(self.facts), dict(self.defs))

    def forget(self, names: set[str]) -> None:
        """``names`` were assigned: drop the facts and definitions that read them."""
        if not names:
            return
        leaves = {("v", n) for n in names}
        for n in names:
            self.defs.pop(n, None)
        self.defs = {k: d for k, d in self.defs.items() if not _mentions(d, leaves)}
        self.facts = {k: h for k, h in self.facts.items() if not _mentions(k, leaves)}


def _merge(states: list[State | None]) -> State | None:
    live = [s for s in states if s is not None]
    if not live:
        return None
    env: dict[str, Value] = {}
    for s in live:
        for k, val in s.env.items():
            env[k] = env.get(k, frozenset()) | val
    facts = {k: h for k, h in live[0].facts.items() if all(s.facts.get(k) is h for s in live[1:])}
    defs = {k: d for k, d in live[0].defs.items() if all(s.defs.get(k) == d for s in live[1:])}
    return State(env, all(s.reported for s in live), facts, defs)


class Returns:
    """Return summaries of the functions in ``program``, memoized per argument nullness."""

    def __init__(self, program: Program) -> None:
        self.program = program
        self.memo: dict[tuple, Value] = {}
        # Per memo key: the facts (over parameters ``("p", i)``) on every true return, and on every false return.
        self.ret_facts: dict[tuple, tuple[Facts, Facts]] = {}
        self.active: set[tuple] = set()
        self.unresolved: set[tuple[str, str]] = set()  # (record or "", name) of callees without a body
        self.methods: dict[str, list[Function]] = {}
        for f in program.functions.values():
            if "@S@" in f.usr or "@ST>" in f.usr or "::" in f.qual:
                self.methods.setdefault(f.name, []).append(f)

    # ------------------------------------------------------------------------------------------------------------
    # Entry points

    def verdict(self, fn: Function, args: tuple[str, ...]) -> Verdict:
        outcomes = sorted(self.summary(fn, args, 0), key=lambda o: (-RANK[o.kind], o.where))
        if not outcomes:
            return Verdict(UNKNOWN, [Outcome(UNKNOWN, f"{fn.file}:{fn.line}", "no return statement")])
        kind = max((o.kind for o in outcomes), key=RANK.__getitem__)
        return Verdict(kind, outcomes)

    def summary(self, fn: Function, args: tuple[str, ...], depth: int, facts: Facts | None = None) -> Value:
        """What ``fn`` can return, given each argument's nullness and the facts over its arguments (``("p", i)``)."""
        facts = facts or {}
        key = (fn.usr, args, tuple(sorted(facts.items(), key=repr)))
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
        outs_saved, rets_saved = getattr(self, "outs", None), getattr(self, "rets", None)
        self.outs, self.rets = [], []
        params = {("p", i): ("v", p[0]) for i, p in enumerate(fn.params)}
        self.walk(fn.body, State(env, facts={_substitute(k, params): h for k, h in facts.items()}), None)
        result = frozenset(self.outs)
        self.ret_facts[key] = (
            _common([f for held, f in self.rets if held]),
            _common([f for held, f in self.rets if not held]),
        )
        self.outs, self.rets = outs_saved, rets_saved  # type: ignore[assignment]
        self.fn, self.depth = saved, saved_depth  # type: ignore[assignment]
        self.active.discard(key)
        self.memo[key] = result
        return result

    def where(self, line) -> str:
        return f"{self.fn.file}:{line}"

    def to_params(self, st: State) -> Facts:
        """The facts of ``st`` over the current function's parameters, as ``("p", i)``."""
        return _translate(st.facts, {("v", p[0]): ("p", i) for i, p in enumerate(self.fn.params)})

    def to_callee(self, args: list, st: State) -> Facts:
        """The facts of ``st`` restated over a callee's parameters, given the call's arguments."""
        mapping = {}
        for i, a in enumerate(args):
            k = canon(a, st.defs)
            if k is not None and k not in mapping:
                mapping[k] = ("p", i)
        return _translate(st.facts, mapping) if mapping else {}

    def from_callee(self, facts: Facts, args: list, st: State) -> Facts:
        mapping = {}
        for i, a in enumerate(args):
            k = canon(a, st.defs)
            if k is not None:
                mapping[("p", i)] = k
        return {new: held for k, held in facts.items() if not _parameters(new := _substitute(k, mapping))}

    # ------------------------------------------------------------------------------------------------------------
    # Statements

    def walk(self, stmts: list, st: State | None, breaks: list | None) -> State | None:
        for s in stmts:
            if st is None:
                return None
            tag = s[0]
            if tag == "decl":
                if s[3] is not None:
                    self.effect(s[3], st, s[4])
                st.forget({s[1]})
                if s[3] is not None and (k := canon(s[3], st.defs)) is not None and s[1] not in _variables(k):
                    st.defs[s[1]] = k
                st.env[s[1]] = (
                    self.eval(s[3], st, s[4]) if s[3] is not None else _one(UNKNOWN, self.where(s[4]), "uninitialized")
                )
                init, declared = s[3], _pointee(s[2])
                if isinstance(init, list) and init[:1] == ["v"] and declared:
                    given = _pointee(init[2])
                    if given and given != declared:  # a call the lowering lost (a dependent template call)
                        st.env[s[1]] = _one(UNKNOWN, self.where(s[4]), f"{s[1]} initialized from a {init[2]}")
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
        st.forget(_assigned(s[1:]))
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
            [
                self.walk(then, a, breaks) if a is not None else None,
                self.walk(other, b, breaks) if b is not None else None,
            ]
        )

    def ret(self, e, st: State, line) -> None:
        if e is None:
            return
        facts = self.to_params(st)
        if isinstance(e, list) and e[:1] in (["i"], ["null"]):
            self.rets.append((e[0] == "i" and e[1] != 0, facts))
        elif _pointee(self.fn.ret) is None and (k := canon(e, st.defs)) is not None:
            for held in (True, False):
                self.rets.append(
                    (
                        held,
                        {
                            **facts,
                            **_translate({k: held}, {("v", p[0]): ("p", i) for i, p in enumerate(self.fn.params)}),
                        },
                    )
                )
        else:
            self.rets.append((True, facts))
            self.rets.append((False, facts))
        declared = _pointee(self.fn.ret)
        if isinstance(e, list) and e[:1] == ["v"] and declared and _pointee(e[2]) not in (None, declared):
            self.outs.append(Outcome(UNKNOWN, self.where(line), f"returns a {e[2]} (a call the lowering lost)"))
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
        if tag == "a" and isinstance(e[2], list) and e[2][:1] == ["v"]:
            self.effect(e[3], st, line)
            value = self.eval(e[3], st, line)
            st.forget({e[2][1]})
            if e[1] == "=":
                st.env[e[2][1]] = value
        elif (
            tag == "u"
            and e[1] in ("++", "--", "&", "post++", "post--")
            and isinstance(e[2], list)
            and e[2][:1] == ["v"]
        ):
            st.forget({e[2][1]})
        elif tag == "c":
            if e[2] in REPORT_FUNCTIONS and len(e[3]) > 1:
                level = e[3][1]
                if isinstance(level, list) and level[:1] == ["k"] and level[2] >= RPT_ERROR:
                    st.reported = True
            for a in e[3]:
                self.effect(a, st, line)
        elif tag in ("b", "u", "m", "mc", "idx"):
            # A dereferenced local is non-null after the dereference: a NULL would have crashed there.
            target = e[2] if tag == "u" and e[1] == "*" else e[1] if tag == "m" else None
            if isinstance(target, list) and target[:1] == ["v"] and target[2].rstrip().endswith("*"):
                st.env[target[1]] = _one(NEVER, self.where(line), f"{target[1]} dereferenced")
            if tag == "b" and e[1] in ("&&", "||"):
                self.effect(e[2], st, line)  # the right side runs only sometimes
                return
            for sub in e[1:]:
                if isinstance(sub, list):
                    if sub and isinstance(sub[0], list):
                        for a in sub:
                            self.effect(a, st, line)
                    else:
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
        if tag not in ("v",) and not (tag == "m" and _path(cond) is not None):
            return self.decide(cond, st, line)
        name = _path(cond)
        if name is not None and (name in st.env or tag == "m"):
            val = st.env.get(name, frozenset())
            yes, no = st.copy(), st.copy()
            yes.env[name] = _one(NEVER, self.where(line), f"{name} checked non-null")
            no.env[name] = _one(NULL, self.where(line), f"{name} checked NULL")
            if any(o.kind == RAISES for o in val) and not any(o.kind == NULL for o in val):
                no.reported = True  # the callee that gave it NULL reported an error first
            return (None if _null_only(val) else yes), (None if _never_only(val) else no)
        return st.copy(), st.copy()

    def decide(self, cond, st: State, line) -> tuple[State | None, State | None]:
        """A condition that is not a null check: decided by the path's facts, or remembered as a fact."""
        keyed, negated = _condition(cond)
        key = canon(keyed, st.defs)
        if key is not None and key in st.facts:
            held = st.facts[key] != negated
            return (st.copy(), None) if held else (None, st.copy())
        yes, no = st.copy(), st.copy()
        if cond[0] == "c" and cond[1] is not None:
            fn = self.program.resolve(cond[1], cond[2], len(cond[3]), self.fn.file)
            if fn is not None:
                args = self.args_of(cond[3], st, line)
                inward = self.to_callee(cond[3], st)
                outs = self.summary(fn, args, self.depth + 1, inward)
                if any(o.kind == RAISES for o in outs) and not any(o.kind == NULL for o in outs):
                    no.reported = True  # the callee reports an error on every path that returns false
                true_facts, false_facts = self.ret_facts.get(
                    (fn.usr, args, tuple(sorted(inward.items(), key=repr))), ({}, {})
                )
                yes.facts.update(self.from_callee(true_facts, cond[3], st))
                no.facts.update(self.from_callee(false_facts, cond[3], st))
        if key is not None:
            yes.facts[key] = not negated
            no.facts[key] = negated
        return yes, no

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
                st.forget({e[2][1]})
                st.env[e[2][1]] = value
            return value
        if tag == "init" and isinstance(e[2], dict) and "data" in e[2]:
            return self.eval(e[2]["data"], st, line)
        if tag == "init" and e[1] == "PointerRNA" and not e[2]:
            return _one(NULL, where, "an empty PointerRNA")
        if tag == "c":
            return self.call(e, st, line)
        if tag == "mc":
            return self.method(e, st, line)
        if tag == "m":
            name = _path(e)
            if name is not None and name in st.env:
                return st.env[name]
            return _one(UNKNOWN, where, f"field {e[2]}")
        if tag == "ctor":
            # A copy or move (``return ptr;`` of a PointerRNA by value) is its argument; ``PointerRNA()`` is empty.
            if len(e[2]) == 1:
                return self.eval(e[2][0], st, line)
            if not e[2] and e[1] == "PointerRNA":
                return _one(NULL, where, "an empty PointerRNA")
        return _one(UNKNOWN, where, f"{tag} expression")

    def args_of(self, args: list, st: State, line) -> tuple[str, ...]:
        return tuple(NEVER if _never_only(self.eval(a, st, line)) else "maybe" for a in args)

    def follow(self, fn: Function, args: tuple[str, ...], where: str, facts: Facts | None = None) -> Value:
        out = set()
        for o in self.summary(fn, args, self.depth + 1, facts):
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
        if usr is None and not (name or "").isidentifier():
            return _one(UNKNOWN, where, f"call through a pointer ({name})")
        # usr None: a call clang could not resolve (lower.recovered_call) or a dependent call in a template.
        fn = self.program.resolve(usr or "", name, len(args), self.fn.file)
        if fn is None:
            self.unresolved.add(("", name))
            return _one(UNKNOWN, where, f"no body for {name}")
        return self.follow(fn, self.args_of(args, st, line), where, self.to_callee(args, st))

    def method(self, e: list, st: State, line) -> Value:
        where = self.where(line)
        name, base, args = e[1], e[2], e[3]
        record = base[-1] if isinstance(base, list) and base and isinstance(base[-1], str) else ""
        record = record.split("::")[-1]
        # ``@S@Channelbag@`` for a class, ``@ST>1#T@Box@`` for a class template.
        cands = [f for f in self.methods.get(name, []) if record and f"@{record}@" in f.usr]
        cands = [f for f in cands if len(f.params) >= len(args)]
        if not cands:
            self.unresolved.add((record, name))
            return _one(UNKNOWN, where, f"no body for {record}::{name}")
        return self.follow(cands[0], self.args_of(args, st, line), where)


# --------------------------------------------------------------------------------------------------------------------
# Driving it over the RNA functions


def _common(facts: list[Facts]) -> Facts:
    if not facts:
        return {}
    return {k: h for k, h in facts[0].items() if all(f.get(k) is h for f in facts[1:])}


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


DEFINITION = re.compile(r"^(?![#/\s{}])(?!return\b)[^;=\n(]*?\b(?:(\w+)::)?(\w+)\s*\(", re.MULTILINE)
CLASS = re.compile(r"^\s*(?:template\s*<[^;{]*>\s*)?(?:class|struct)\s+(?:\w+\s+)?(\w+)\b[^;{()]*\{", re.MULTILINE)


def definition_index(source: Path) -> dict[str, set[tuple[str, str]]]:
    """Function name -> {(class or "", file)} for every top-level definition under ``source/blender`` (sources and
    headers: inline functions and templates), and ``class <Name>`` -> {("", file)} for every class definition (its
    methods may be defined in the class body)."""
    index: dict[str, set[tuple[str, str]]] = {}
    for path in (source / "source" / "blender").rglob("*"):
        if path.suffix not in (".cc", ".hh", ".h") or not path.is_file():
            continue
        rel = str(path.relative_to(source))
        if "/tests/" in rel or rel.endswith(("_test.cc", "_tests.cc")):
            continue
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        for m in DEFINITION.finditer(text):
            # A definition: its body opens before any ``;`` (a declaration ends first).
            semi, brace = text.find(";", m.end()), text.find("{", m.end())
            if brace != -1 and (semi == -1 or brace < semi):
                index.setdefault(m.group(2), set()).add((m.group(1) or "", rel))
        if path.suffix != ".cc":
            for m in CLASS.finditer(text):
                index.setdefault(f"class {m.group(1)}", set()).add(("", rel))
    return index


def callee_files(unresolved: set[tuple[str, str]], index: dict[str, set[tuple[str, str]]], limit: int = 3) -> set[str]:
    """The files that define the unresolved callees; names defined in more than ``limit`` files are skipped."""
    files: set[str] = set()
    for record, name in unresolved:
        hits = index.get(name, set())
        if record:
            hits = {h for h in hits if h[0] == record} or index.get(f"class {record}", set())
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
    stub = {
        NEVER: "`X`",
        RAISES: "`X` (NULL only with an error, which raises)",
        NULL: "`X | None`",
        UNKNOWN: "`X | None`",
    }
    for kind in (NEVER, RAISES, NULL, UNKNOWN):
        lines.append(f"| {kind} | {counts.get(kind, 0)} | {stub[kind]} |")
    reasons = Counter(re.sub(r"\(.*", "", r[3].split(": ", 1)[-1]).strip() for r in rows if r[0] == UNKNOWN)
    lines += ["", "Why unknown (most common):", ""]
    lines += [f"- {why}: {n}" for why, n in reasons.most_common(15)]
    for kind in (NULL, RAISES, NEVER, UNKNOWN):
        lines += ["", f"## {kind}", "", "| Function | C function | Evidence |", "|---|---|---|"]
        lines += [f"| `{name}` | `{c}` | {why} |" for k, name, c, why in sorted(rows) if k == kind]
    return "\n".join(lines) + "\n"
