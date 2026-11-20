"""A small abstract interpreter over the lowered AST (``lower.py``).

It runs definition functions the way Blender does at build/registration time, with concrete values where the
source gives them (string and number literals, enum constants, initializer lists, ``static const`` arrays) and
``UNKNOWN`` elsewhere (``bContext *C``, runtime data). Calls are resolved by USR: a call to a helper is followed
into its body with its parameters bound to the caller's values, so ``rna_def_object_api(srna)`` defines its
functions on the caller's struct, and ``RNA_def_float_vector`` is run from ``rna_define.cc`` itself (its
``RNA_def_property(cont, identifier, PROP_FLOAT, PROP_XYZ)`` then reaches an intrinsic). Intrinsics (the
``RNA_def_property*`` / ``RNA_def_struct*`` / ``RNA_def_function*`` primitives, ``CTX_data_*`` setters, node
declaration builder methods, ...) are Python functions registered by the area modules.

Conditions that evaluate to a constant pick their branch; unknown conditions run both branches ("speculative"),
and loops run their body once. Each speculative step bumps ``self.speculative`` so area code can mark facts
read there as dynamic.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


class _Unknown:
    _inst = None

    def __new__(cls):
        if cls._inst is None:
            cls._inst = super().__new__(cls)
        return cls._inst

    def __repr__(self) -> str:
        return "UNKNOWN"

    def __bool__(self) -> bool:
        raise TypeError("UNKNOWN has no truth value")


UNKNOWN = _Unknown()


class Flag(int):
    """An integer built from named enum constants: keeps the names (``PROP_EDITABLE | PROP_ANIMATABLE``)."""

    names: frozenset[str]

    def __new__(cls, value: int, names=frozenset()):
        obj = super().__new__(cls, value)
        obj.names = frozenset(names)
        return obj

    def __or__(self, other):
        if isinstance(other, int):
            return Flag(int(self) | int(other), self.names | getattr(other, "names", frozenset()))
        return NotImplemented

    __ror__ = __or__

    def __repr__(self) -> str:
        return "|".join(sorted(self.names)) or str(int(self))


@dataclass(eq=False)
class Obj:
    """A symbolic object: an RNA struct/property/function handle, an operator type, a node type, a builder..."""

    kind: str
    data: Any = None
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GlobalRef:
    """A global without a usable initializer (``RNA_Object``, ``PyFloat_Type``): known by name only."""

    name: str
    usr: str = ""


@dataclass(frozen=True)
class FuncRef:
    usr: str
    name: str


@dataclass(eq=False)
class Lambda:
    params: list
    body: list
    env: dict


@dataclass(frozen=True)
class Ptr:
    """A pointer into a table: ``for (effect = def_effects; effect->struct_name[0]; effect++)``."""

    seq: list
    index: int = 0

    def current(self) -> Any:
        return self.seq[self.index] if 0 <= self.index < len(self.seq) else UNKNOWN


@dataclass(frozen=True)
class MemberTest:
    """``CTX_data_equals(member, "x")`` (possibly or-ed): the then-branch defines these context members."""

    names: frozenset[str]


class _Break(Exception):
    pass


class Return(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


@dataclass
class Function:
    usr: str
    name: str
    qual: str
    params: list
    body: list
    file: str
    line: int
    static: bool = False
    ret: str = ""
    unit_errors: int = 0  # clang errors in the unit it was lowered from


Intrinsic = Callable[["Interp", list, list, list], Any]


class Program:
    """All lowered units, indexed: functions and globals by USR and by name."""

    def __init__(self, lowered: list[dict]) -> None:
        self.functions: dict[str, Function] = {}
        self.by_name: dict[str, list[Function]] = {}
        self.globals: dict[str, dict] = {}
        self.globals_by_name: dict[str, list[dict]] = {}
        self.dna: dict[str, dict] = {}
        self.errors: dict[str, int] = {}
        for unit in lowered:
            self.errors[unit.get("tu", "?")] = unit.get("errors", 0)
            for f in unit.get("functions", []):
                if f["usr"] in self.functions:
                    continue
                fn = Function(
                    f["usr"],
                    f["name"],
                    f["qual"],
                    f["params"],
                    f["body"],
                    f["file"],
                    f["line"],
                    f.get("static", False),
                    f.get("ret", ""),
                    max(unit.get("errors", 0), 0),
                )
                self.functions[fn.usr] = fn
                self.by_name.setdefault(fn.name, []).append(fn)
            for g in unit.get("globals", []):
                prev = self.globals.get(g["usr"])
                if prev is None or (prev.get("init") is None and g.get("init") is not None):
                    self.globals[g["usr"]] = g
            for name, fields in unit.get("dna", {}).items():
                self.dna.setdefault(name, fields)
        for g in self.globals.values():
            self.globals_by_name.setdefault(g["name"], []).append(g)

    def resolve(self, usr: str, name: str, nargs: int, file_hint: str) -> Function | None:
        """A definition whose USR differs from its declaration's (top-level ``const`` on a parameter in the
        definition only changes the USR): the same name, a compatible parameter count, the same file if static."""
        cands = [f for f in self.by_name.get(name, []) if len(f.params) >= nargs]
        if not cands:
            return None
        if usr and usr.startswith("c:") and "@F@" in usr:
            scope = usr.split("@F@")[0]
            same = [f for f in cands if f.usr.split("@F@")[0] == scope]
            cands = same or cands
        local = [f for f in cands if f.file == file_hint]
        if local:
            return local[0]
        public = [f for f in cands if not f.static]
        return public[0] if public else None

    def function(self, name: str, file_hint: str = "") -> Function | None:
        cands = self.by_name.get(name, [])
        if file_hint:
            for c in cands:
                if c.file == file_hint:
                    return c
        return cands[0] if cands else None


class Interp:
    MAX_DEPTH = 40

    def __init__(self, program: Program) -> None:
        self.p = program
        self.intrinsics: dict[str, Intrinsic] = {}
        self.methods: dict[str, Callable] = {}  # member-call handlers, keyed by method name
        self.global_values: dict[str, Any] = {}
        self.global_names: dict[int, str] = {}  # id(value) -> global name (shared item arrays)
        self.stack: list[Function] = []
        self.speculative = 0
        self.ctx_members: frozenset[str] = frozenset()
        self.on_assign: list[Callable] = []
        self.warnings: list[str] = []
        self.calls_followed = 0
        self.unresolved: dict[str, int] = {}

    # ----------------------------------------------------------------------------------------------------------------
    @property
    def where(self) -> str:
        return self.stack[-1].file if self.stack else ""

    def src(self, line: int | None) -> str:
        return f"{self.where}:{line}" if line else self.where

    def global_value(self, usr: str, name: str) -> Any:
        if usr in self.global_values:
            return self.global_values[usr]
        g = self.p.globals.get(usr)
        if g is None:
            cands = self.p.globals_by_name.get(name, [])
            g = next((c for c in cands if c.get("init") is not None), cands[0] if cands else None)
        init = g.get("init") if g is not None else None
        # ``PyTypeObject X;`` in C++ arrives as an implicit default constructor call.
        zero_init = init is None or (isinstance(init, list) and init[:2] == ["ctor", "_typeobject"] and not init[2])
        if (
            g is not None
            and zero_init
            and g.get("record")
            and not g["type"].rstrip().endswith(("*", "]"))
            and g["record"].lstrip("_")[:1].isalpha()
            and g["record"] not in ("StructRNA", "PropertyRNA", "BlenderRNA")
        ):
            # A zero-initialized struct global (``static PyTypeObject BlenderAppType;``): fields are assigned at runtime.
            value = {"__record__": g["record"]}
            self.global_names[id(value)] = name
        elif g is None or g.get("init") is None:
            value = GlobalRef(name, usr)
        else:
            self.global_values[usr] = UNKNOWN  # recursion guard
            saved = self.stack
            self.stack = [Function(g["usr"], g["name"], g["qual"], [], [], g["file"], g["line"])]
            try:
                value = self.eval(g["init"], {})
            finally:
                self.stack = saved
            if isinstance(value, (list, dict, Obj)):
                self.global_names[id(value)] = name
        self.global_values[usr] = value
        return value

    def global_src(self, usr: str) -> str:
        g = self.p.globals.get(usr)
        return f"{g['file']}:{g['line']}" if g else ""

    # ----------------------------------------------------------------------------------------------------------------
    # Running functions

    def call_function(self, fn: Function, args: list, extra_env: dict | None = None) -> Any:
        if len(self.stack) >= self.MAX_DEPTH or sum(1 for f in self.stack if f.usr == fn.usr) > 2:
            return UNKNOWN
        env: dict[str, Any] = dict(extra_env or {})
        for i, param in enumerate(fn.params):
            env[param[0]] = args[i] if i < len(args) else UNKNOWN
        self.stack.append(fn)
        self.calls_followed += 1
        try:
            self.run(fn.body, env)
        except Return as r:
            return r.value
        except _Break:
            return None
        finally:
            self.stack.pop()
        return None

    def call_lambda(self, lam: Lambda, args: list) -> Any:
        env = dict(lam.env)
        for i, param in enumerate(lam.params):
            env[param[0]] = args[i] if i < len(args) else UNKNOWN
        try:
            self.run(lam.body, env)
        except Return as r:
            return r.value
        return None

    def run(self, stmts: list, env: dict) -> None:
        for s in stmts:
            self.stmt(s, env)

    def run_speculative(self, stmts: list, env: dict) -> None:
        self.speculative += 1
        try:
            self.run(stmts, env)
        except (Return, _Break):
            pass
        finally:
            self.speculative -= 1

    def stmt(self, s: list, env: dict) -> None:
        tag = s[0]
        if tag == "e":
            self.eval(s[1], env)
        elif tag == "decl":
            if s[3] is not None:
                env[s[1]] = self.eval(s[3], env)
            elif s[5] and not s[2].rstrip().endswith(("*", "]")) and s[5][:1].isalpha():
                # A struct-typed local (``static bNodeType ntype;``): a fresh object its fields are assigned into.
                env[s[1]] = Obj("local", s[5], {})
            else:
                env[s[1]] = UNKNOWN
        elif tag == "if":
            cond = self.eval(s[1], env)
            if isinstance(cond, MemberTest):
                saved = self.ctx_members
                self.ctx_members = cond.names
                try:
                    self.run(s[2], env)
                finally:
                    self.ctx_members = saved
                self.run(s[3], env)
                return
            truth = self.truth(cond)
            if truth is True:
                self.run(s[2], env)
            elif truth is False:
                self.run(s[3], env)
            else:
                self.run_speculative(s[2], env)
                self.run_speculative(s[3], env)
        elif tag == "loop":
            self.loop(s, env)
        elif tag == "switch":
            self.eval(s[1], env) if s[1] is not None else None
            self.run_speculative(s[2], env)
        elif tag == "break":
            raise _Break()
        elif tag == "ret":
            raise Return(self.eval(s[1], env) if s[1] is not None else None)

    MAX_ITERATIONS = 512

    def loop(self, s: list, env: dict) -> None:
        """Iterate concretely while the condition is known (``for (i = 0; table[i].name; i++)``, a range-for over
        an initializer array); otherwise run the body once, speculatively."""
        cond, inc = (s[4], s[5]) if len(s) > 5 else (None, None)
        range_var, range_expr = (s[6], s[7]) if len(s) > 7 else (None, None)
        if range_var and range_expr is not None:
            seq = self.eval(range_expr, env)
            if isinstance(seq, list) and len(seq) <= self.MAX_ITERATIONS:
                for item in seq:
                    env[range_var] = item
                    try:
                        self.run(s[2], env)
                    except _Break:
                        break
                return
            self.run_speculative(s[2], env)
            return
        if cond is not None and s[1] in ("for", "while"):
            done = False
            for _ in range(self.MAX_ITERATIONS):
                t = self.truth(self.eval(cond, env))
                if t is False:
                    done = True
                    break
                if t is not True:
                    break
                try:
                    self.run(s[2], env)
                except _Break:
                    done = True
                    break
                if inc is not None:
                    self.eval(inc, env)
            else:
                done = True
            if done:
                return
        self.run_speculative(s[2], env)

    @staticmethod
    def truth(value: Any) -> bool | None:
        if isinstance(value, Ptr):
            return True if 0 <= value.index < len(value.seq) else None
        if value is UNKNOWN or isinstance(value, (Obj, GlobalRef, FuncRef, Lambda, MemberTest)):
            return (
                True
                if isinstance(value, (FuncRef, Lambda))
                else (None if value is UNKNOWN or isinstance(value, Obj) else True)
            )
        if value is None:
            return False
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, (str, list, dict)):
            return True
        return None

    # ----------------------------------------------------------------------------------------------------------------
    # Expressions

    def eval(self, e: Any, env: dict) -> Any:
        if e is None:
            return UNKNOWN
        tag = e[0]
        if tag == "i":
            return e[1]
        if tag == "f":
            return e[1]
        if tag == "s":
            return e[1]
        if tag == "null":
            return None
        if tag == "k":
            return Flag(e[2] if e[2] is not None else 0, {e[1]})
        if tag == "v":
            return env.get(e[1], UNKNOWN)
        if tag == "g":
            return self.global_value(e[1], e[2])
        if tag == "fn":
            return FuncRef(e[1], e[2])
        if tag == "m":
            base = self.eval(e[1], env)
            return self.member(base, e[2], e)
        if tag == "c":
            return self.call(e, env)
        if tag == "mc":
            if e[1] == "operator=" and len(e[3]) == 2:
                # ``ntype.ui_name = "Mix"`` on a std::string member: the call's arguments are (lhs, rhs).
                return self.assign(e[3][0], self.eval(e[3][1], env), env)
            base = self.eval(e[2], env) if e[2] is not None else UNKNOWN
            args = [self.eval(a, env) for a in e[3]]
            handler = None
            if isinstance(base, Obj):
                handler = self.methods.get(f"{base.kind}.{e[1]}") or self.methods.get(f"{base.kind}.*")
            handler = handler or self.methods.get(e[1])
            if handler is not None:
                return handler(self, base, args, e)
            if isinstance(base, Obj) and e[1] in ("ptr", "get", "data"):
                return base
            return UNKNOWN
        if tag == "op":
            args = [self.eval(a, env) for a in e[2]]
            if e[1] == "operator=" and len(e[2]) == 2:
                return self.assign(e[2][0], args[1], env)
            if e[1] == "operator()" and args and isinstance(args[0], Lambda):
                return self.call_lambda(args[0], args[1:])
            if e[1] in ("operator->", "operator*") and len(args) == 1:
                return args[0]
            if e[1][8:] in ("|", "&", "^") and len(args) == 2:
                return self.arith(e[1][8:], args[0], args[1])
            if e[1][8:] in ("|=", "&=") and len(args) == 2:
                return self.assign(e[2][0], self.arith(e[1][8], args[0], args[1]), env)
            return UNKNOWN
        if tag == "ctor":
            args = [self.eval(a, env) for a in e[2]]
            if not args and e[1]:
                return Obj("local", e[1], {})  # ``static bNodeType ntype;`` (default-constructed)
            if len(args) == 1:
                return args[0]
            if args and all(isinstance(a, (int, float)) for a in args):
                return list(args)
            return UNKNOWN
        if tag == "u":
            return self.unary(e, env)
        if tag == "b":
            return self.binary(e[1], e[2], e[3], env)
        if tag == "a":
            if e[1] == "=":
                value = self.eval(e[3], env)
            else:
                cur = self.eval(e[2], env)
                rhs = self.eval(e[3], env)
                value = self.arith(e[1][:-1], cur, rhs)
            return self.assign(e[2], value, env)
        if tag == "?":
            truth = self.truth(self.eval(e[1], env))
            if truth is True:
                return self.eval(e[2], env)
            if truth is False:
                return self.eval(e[3], env)
            a = self.eval(e[2], env)
            b = self.eval(e[3], env)
            return a if a == b else UNKNOWN
        if tag == "idx":
            base = self.eval(e[1], env)
            idx = self.eval(e[2], env)
            if isinstance(base, Ptr) and isinstance(idx, int):
                base, idx = base.seq, base.index + idx
            if isinstance(base, str) and isinstance(idx, int) and 0 <= idx < len(base):
                return ord(base[idx])  # a C ``char`` (character literals are lowered as ints)
            if isinstance(base, list) and isinstance(idx, int) and 0 <= idx < len(base):
                return base[idx]
            if isinstance(base, str) and idx == len(base):
                return 0  # the terminating NUL
            if isinstance(base, list) and idx is UNKNOWN:
                return Obj("anyof", base)  # ``table[i]`` in a loop over a table
            return UNKNOWN
        if tag == "init":
            if isinstance(e[2], dict):
                out = {k: self.eval(v, env) for k, v in e[2].items()}
                out["__record__"] = e[1]
                return out
            return [self.eval(v, env) for v in e[2]]
        if tag == "lambda":
            return Lambda(e[1], e[2], env)
        if tag == "x" and e[1] == "udl":
            # A string user-defined literal whose literal libclang does not expose: its single token.
            text = e[2]
            if text.startswith('"') and '"_' in text:
                from common.rstdoc import decode_c_string

                return decode_c_string(text[1 : text.rindex('"_')])
        return UNKNOWN

    def member(self, base: Any, name: str, e: list) -> Any:
        if isinstance(base, Ptr):
            base = base.current()
        elif isinstance(base, list) and base and isinstance(base[0], dict):
            base = base[0]  # ``table->field``: a table used as a pointer to its first row
        if isinstance(base, Obj):
            if name in base.fields:
                return base.fields[name]
            hook = self.methods.get(f"member:{base.kind}")
            if hook is not None:
                return hook(self, base, name, e)
            return UNKNOWN
        if isinstance(base, dict):
            if name in base:
                return base[name]
            hook = self.methods.get("member:dict")
            return hook(self, base, name, e) if hook is not None else UNKNOWN
        if isinstance(base, GlobalRef):
            hook = self.methods.get("member:global")
            if hook is not None:
                return hook(self, base, name, e)
        return UNKNOWN

    def assign(self, lhs: list, value: Any, env: dict) -> Any:
        tag = lhs[0]
        if tag == "v":
            env[lhs[1]] = value
        elif tag == "m":
            base = self.eval(lhs[1], env)
            if isinstance(base, Obj):
                base.fields[lhs[2]] = value
                for hook in self.on_assign:
                    hook(self, base, lhs[2], value, lhs)
            elif isinstance(base, dict):
                base[lhs[2]] = value
        elif tag == "u" and lhs[1] == "*":
            pass
        return value

    def unary(self, e: list, env: dict) -> Any:
        op = e[1]
        v = self.eval(e[2], env)
        if op in ("++", "--", "post++", "post--"):
            if isinstance(v, int) and e[2] and e[2][0] == "v":
                new = v + (1 if "+" in op else -1)
                env[e[2][1]] = new
                return v if op.startswith("post") else new
            if isinstance(v, (list, Ptr)) and e[2] and e[2][0] == "v":
                # A pointer walk over a table.
                ptr = v if isinstance(v, Ptr) else Ptr(v, 0)
                new_ptr = Ptr(ptr.seq, ptr.index + (1 if "+" in op else -1))
                env[e[2][1]] = new_ptr
                return ptr if op.startswith("post") else new_ptr
            return UNKNOWN
        if op == "*" and isinstance(v, Ptr):
            return v.current()
        if op in ("&", "*", "+"):
            return v
        if op == "!":
            t = self.truth(v)
            return UNKNOWN if t is None else (not t)
        if op == "-":
            return -v if isinstance(v, (int, float)) and not isinstance(v, bool) else UNKNOWN
        if op == "~":
            return ~int(v) if isinstance(v, int) else UNKNOWN
        return UNKNOWN

    def arith(self, op: str, a: Any, b: Any) -> Any:
        if op == "|" and isinstance(a, int) and isinstance(b, int):
            if isinstance(a, Flag):
                return a | b
            if isinstance(b, Flag):
                return b | a
            return a | b
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            return UNKNOWN
        try:
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            if op == "/":
                if isinstance(a, int) and isinstance(b, int):
                    return int(a / b) if b else UNKNOWN
                return a / b if b else UNKNOWN
            if op == "%":
                return a % b if b else UNKNOWN
            if op == "&":
                return int(a) & int(b)
            if op == "^":
                return int(a) ^ int(b)
            if op == "<<":
                return int(a) << int(b)
            if op == ">>":
                return int(a) >> int(b)
        except (TypeError, ValueError, OverflowError):
            return UNKNOWN
        return UNKNOWN

    def binary(self, op: str, le: list, re_: list, env: dict) -> Any:
        if op == "&&":
            a = self.truth(self.eval(le, env))
            if a is False:
                return False
            b = self.truth(self.eval(re_, env))
            if a is True and b is not None:
                return b
            return False if b is False else UNKNOWN
        if op == "||":
            av = self.eval(le, env)
            bv = self.eval(re_, env)
            if isinstance(av, MemberTest) or isinstance(bv, MemberTest):
                names = set()
                for v in (av, bv):
                    if isinstance(v, MemberTest):
                        names |= v.names
                return MemberTest(frozenset(names))
            a, b = self.truth(av), self.truth(bv)
            if a is True or b is True:
                return True
            if a is False and b is False:
                return False
            return UNKNOWN
        if op == ",":
            self.eval(le, env)
            return self.eval(re_, env)
        a = self.eval(le, env)
        b = self.eval(re_, env)
        if op in ("==", "!=", "<", ">", "<=", ">="):
            if a is UNKNOWN or b is UNKNOWN or isinstance(a, (Obj, GlobalRef)) or isinstance(b, (Obj, GlobalRef)):
                if (
                    op in ("==", "!=")
                    and (a is None or b is None)
                    and isinstance(a if b is None else b, (Obj, GlobalRef, FuncRef, list, str))
                ):
                    return op == "!="
                return UNKNOWN
            try:
                return {"==": a == b, "!=": a != b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]
            except TypeError:
                return UNKNOWN
        return self.arith(op, a, b)

    def call(self, e: list, env: dict) -> Any:
        usr, name, arg_exprs = e[1], e[2], e[3]
        intrinsic = self.intrinsics.get(name)
        target = env.get(name)
        if intrinsic is None and (usr is None or isinstance(target, (Lambda, FuncRef))):
            # A call through a variable: a lambda or a function pointer held in a local (its USR is the local's).
            args = [self.eval(a, env) for a in arg_exprs]
            if isinstance(target, Lambda):
                return self.call_lambda(target, args)
            if isinstance(target, FuncRef):
                fn = self.p.resolve(target.usr, target.name, len(args), self.where)
                if fn is not None:
                    return self.call_function(fn, args)
            return UNKNOWN
        args = [self.eval(a, env) for a in arg_exprs]
        if intrinsic is not None:
            return intrinsic(self, args, arg_exprs, e)
        if name.startswith("operator") and name[8:] in ("|", "&", "^", "+", "-", "*", "/") and len(args) == 2:
            return self.arith(name[8:], args[0], args[1])  # ENUM_OPERATORS: ``PROP_HIDDEN | PROP_SKIP_SAVE``
        if name.startswith("operator") and name[8:] in ("|=", "&=", "^=") and len(args) == 2:
            return self.assign(arg_exprs[0], self.arith(name[8], args[0], args[1]), env)
        if name == "operator~" and len(args) == 1:
            return ~int(args[0]) if isinstance(args[0], int) else UNKNOWN
        if name.startswith('operator""'):
            return args[0] if args else UNKNOWN  # a user-defined literal: "GeometryNodeMeshCone"_ustr
        fn = self.p.functions.get(usr)
        if fn is None:
            fn = self.p.resolve(usr, name, len(arg_exprs), self.where)
        if fn is None:
            self.unresolved[name] = self.unresolved.get(name, 0) + 1
            return UNKNOWN
        return self.call_function(fn, args)
