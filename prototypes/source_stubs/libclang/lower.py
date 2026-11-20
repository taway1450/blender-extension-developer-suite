"""Parse one translation unit with libclang and lower its function bodies and globals to plain JSON.

The interpreter (``interp.py``) never touches libclang: it runs over this lowered form, which is cached per
translation unit. Lowering keeps what libclang knows and regex cannot: macros are expanded, every call is resolved
to its declaration (a USR, so static helpers of the same name in two files stay apart), constant expressions are
evaluated by clang (``sizeof``, ``ARRAY_SIZE``, ``#define`` arithmetic), positional initializers are mapped to the
struct's field names from its declaration, and expressions carry their C type (``Object *``).

Statement forms (lists, first item the tag, last item the line):
  ["e", expr, line]  ["decl", name, type, init|None, line]  ["if", cond, [then], [else], line]
  ["loop", kind, [body], line]  ["switch", cond, [body], line]  ["ret", expr|None, line]
Expression forms:
  ["i", int] ["f", float] ["s", str] ["null"] ["k", name, value]   (enum constant)
  ["v", name, type]  (local / parameter)   ["g", usr, name, type]  (global variable)   ["fn", usr, name]
  ["m", base, field, base_record]   ["c", usr|None, name, [args], line]   ["mc", name, base, [args], line, display]
  ["u", op, e]  ["b", op, l, r]  ["a", op, lhs, rhs]  ["?", c, x, y]  ["idx", a, i]
  ["init", record|None, {field: expr} | [expr, ...]]  ["lambda", [params], [body]]  ["x", kind, text]  (unknown)
"""

from __future__ import annotations

import ctypes
import os
from pathlib import Path

import clang.cindex as ci
from clang.cindex import CursorKind as K

LOWER_VERSION = 10

_lib = ci.conf.lib
_lib.clang_Cursor_Evaluate.argtypes = [ci.Cursor]
_lib.clang_Cursor_Evaluate.restype = ctypes.c_void_p
_lib.clang_EvalResult_getKind.argtypes = [ctypes.c_void_p]
_lib.clang_EvalResult_getKind.restype = ctypes.c_int
_lib.clang_EvalResult_getAsLongLong.argtypes = [ctypes.c_void_p]
_lib.clang_EvalResult_getAsLongLong.restype = ctypes.c_longlong
_lib.clang_EvalResult_isUnsignedInt.argtypes = [ctypes.c_void_p]
_lib.clang_EvalResult_isUnsignedInt.restype = ctypes.c_uint
_lib.clang_EvalResult_getAsUnsigned.argtypes = [ctypes.c_void_p]
_lib.clang_EvalResult_getAsUnsigned.restype = ctypes.c_ulonglong
_lib.clang_EvalResult_getAsDouble.argtypes = [ctypes.c_void_p]
_lib.clang_EvalResult_getAsDouble.restype = ctypes.c_double
_lib.clang_EvalResult_getAsStr.argtypes = [ctypes.c_void_p]
_lib.clang_EvalResult_getAsStr.restype = ctypes.c_char_p
_lib.clang_EvalResult_dispose.argtypes = [ctypes.c_void_p]
_lib.clang_getCursorBinaryOperatorKind.argtypes = [ci.Cursor]
_lib.clang_getCursorBinaryOperatorKind.restype = ctypes.c_int
_lib.clang_getCursorUnaryOperatorKind.argtypes = [ci.Cursor]
_lib.clang_getCursorUnaryOperatorKind.restype = ctypes.c_int

BINOPS = {3: "*", 4: "/", 5: "%", 6: "+", 7: "-", 8: "<<", 9: ">>", 11: "<", 12: ">", 13: "<=", 14: ">=", 15: "==",
          16: "!=", 17: "&", 18: "^", 19: "|", 20: "&&", 21: "||", 22: "=", 23: "*=", 24: "/=", 25: "%=", 26: "+=",
          27: "-=", 28: "<<=", 29: ">>=", 30: "&=", 31: "^=", 32: "|=", 33: ","}
UNOPS = {1: "post++", 2: "post--", 3: "++", 4: "--", 5: "&", 6: "*", 7: "+", 8: "-", 9: "~", 10: "!"}

PASS_THROUGH = {
    K.UNEXPOSED_EXPR, K.PAREN_EXPR, K.CSTYLE_CAST_EXPR, K.CXX_STATIC_CAST_EXPR, K.CXX_REINTERPRET_CAST_EXPR,
    K.CXX_CONST_CAST_EXPR, K.CXX_FUNCTIONAL_CAST_EXPR, K.CXX_DYNAMIC_CAST_EXPR,
}
LOOPS = {K.FOR_STMT: "for", K.WHILE_STMT: "while", K.DO_STMT: "do", K.CXX_FOR_RANGE_STMT: "range"}


def evaluate(c: ci.Cursor):
    """clang's constant evaluation of an expression: int, float, str or None."""
    res = _lib.clang_Cursor_Evaluate(c)
    if not res:
        return None
    try:
        kind = _lib.clang_EvalResult_getKind(res)
        if kind == 1:
            if _lib.clang_EvalResult_isUnsignedInt(res):
                return int(_lib.clang_EvalResult_getAsUnsigned(res))
            return int(_lib.clang_EvalResult_getAsLongLong(res))
        if kind == 2:
            return float(_lib.clang_EvalResult_getAsDouble(res))
        if kind == 4:
            raw = _lib.clang_EvalResult_getAsStr(res)
            return raw.decode("utf-8", "replace") if raw is not None else None
        return None
    finally:
        _lib.clang_EvalResult_dispose(res)


def record_name(t: ci.Type) -> str:
    """The record a (pointer to a) type names, without qualifiers/namespaces: ``Object *`` -> ``Object``."""
    try:
        t = t.get_canonical()
        while t.kind in (ci.TypeKind.POINTER, ci.TypeKind.LVALUEREFERENCE, ci.TypeKind.RVALUEREFERENCE):
            t = t.get_pointee().get_canonical()
        if t.kind == ci.TypeKind.CONSTANTARRAY or t.kind == ci.TypeKind.INCOMPLETEARRAY:
            t = t.element_type.get_canonical()
        name = t.spelling
    except Exception:
        return ""
    for q in ("const ", "volatile ", "struct ", "enum "):
        name = name.replace(q, "")
    return name.split("::")[-1].split("<")[0].strip()


class Lowerer:
    def __init__(self, tu: ci.TranslationUnit, files: set[str], root: str) -> None:
        self.tu = tu
        self.files = files  # absolute paths whose definitions we lower
        self.root = root
        self.fields_cache: dict[str, list[str] | None] = {}
        self.functions: list[dict] = []
        self.globals: list[dict] = []
        self.dna: dict[str, dict] = {}

    def rel(self, path: str) -> str:
        return os.path.relpath(path, self.root) if path.startswith(self.root) else path

    # ----------------------------------------------------------------------------------------------------------------
    def run(self) -> None:
        self.visit_scope(self.tu.cursor, "")
        if any("/makesrna/intern/rna_" in f for f in self.files):
            self.collect_dna(self.tu.cursor)

    def collect_dna(self, scope: ci.Cursor) -> None:
        """The DNA structs an RNA file includes: field -> [type, record, array dims, pointer level].

        makesrna reads the same facts from SDNA: a float property mapped onto ``float loc[3]`` is an array of 3
        without any ``RNA_def_property_array`` call, a pointer onto ``Object *parent`` points to ``Object``.
        """
        for c in scope.get_children():
            k = c.kind
            if k == K.NAMESPACE or k == K.LINKAGE_SPEC:
                self.collect_dna(c)
                continue
            if k != K.STRUCT_DECL or not c.is_definition() or not c.spelling:
                continue
            f = c.location.file
            if f is None or not os.path.basename(f.name).startswith("DNA_") or c.spelling in self.dna:
                continue
            fields = {}
            for m in c.get_children():
                if m.kind != K.FIELD_DECL:
                    continue
                t = m.type.get_canonical()
                dims = []
                while t.kind == ci.TypeKind.CONSTANTARRAY:
                    dims.append(t.element_count)
                    t = t.element_type.get_canonical()
                level = 0
                while t.kind == ci.TypeKind.POINTER:
                    level += 1
                    t = t.get_pointee().get_canonical()
                fields[m.spelling] = [m.type.spelling, record_name(t), dims, level]
            self.dna[c.spelling] = fields

    def in_files(self, c: ci.Cursor) -> str | None:
        f = c.location.file
        if f is None:
            return None
        name = f.name
        return name if name in self.files else None

    def visit_scope(self, scope: ci.Cursor, ns: str) -> None:
        for c in scope.get_children():
            k = c.kind
            if k == K.NAMESPACE or k == K.LINKAGE_SPEC or k == K.UNEXPOSED_DECL:
                self.visit_scope(c, f"{ns}{c.spelling}::" if k == K.NAMESPACE and c.spelling else ns)
                continue
            path = self.in_files(c)
            if path is None:
                continue
            if k in (K.FUNCTION_DECL, K.CXX_METHOD) and c.is_definition():
                self.lower_function(c, ns, path)
            elif k == K.VAR_DECL:
                self.lower_global(c, ns, path)
            elif k in (K.STRUCT_DECL, K.CLASS_DECL) and c.is_definition():
                for m in c.get_children():
                    if m.kind == K.CXX_METHOD and m.is_definition():
                        self.lower_function(m, f"{ns}{c.spelling}::", path)

    def lower_function(self, c: ci.Cursor, ns: str, path: str) -> None:
        params = []
        body = None
        for ch in c.get_children():
            if ch.kind == K.PARM_DECL:
                params.append([ch.spelling, ch.type.spelling, record_name(ch.type)])
            elif ch.kind == K.COMPOUND_STMT:
                body = ch
        if body is None:
            return
        self.functions.append({
            "usr": c.canonical.get_usr() or c.get_usr(),
            "name": c.spelling,
            "qual": ns + c.spelling,
            "params": params,
            "ret": c.result_type.spelling,
            "static": c.storage_class == ci.StorageClass.STATIC,
            "file": self.rel(path),
            "line": c.location.line,
            "body": self.stmts(body),
        })

    def lower_global(self, c: ci.Cursor, ns: str, path: str) -> None:
        init = None
        for ch in c.get_children():
            if ch.kind not in (K.TYPE_REF, K.NAMESPACE_REF, K.TEMPLATE_REF) and ch.kind.is_expression():
                init = ch
        self.globals.append({
            "usr": c.get_usr(),
            "name": c.spelling,
            "qual": ns + c.spelling,
            "type": c.type.spelling,
            "record": record_name(c.type),
            "file": self.rel(path),
            "line": c.location.line,
            "init": self.expr(init) if init is not None else None,
        })

    # ----------------------------------------------------------------------------------------------------------------
    # Statements

    def stmts(self, c: ci.Cursor) -> list:
        out: list = []
        if c.kind == K.COMPOUND_STMT:
            for ch in c.get_children():
                out.extend(self.stmt(ch))
        else:
            out.extend(self.stmt(c))
        return out

    def stmt(self, c: ci.Cursor) -> list:
        k = c.kind
        line = c.location.line
        if k == K.COMPOUND_STMT:
            return self.stmts(c)
        if k == K.DECL_STMT:
            out = []
            for d in c.get_children():
                if d.kind == K.VAR_DECL:
                    init = None
                    for ch in d.get_children():
                        if ch.kind.is_expression():
                            init = ch
                    out.append(["decl", d.spelling, d.type.spelling, self.expr(init) if init is not None else None,
                                d.location.line, record_name(d.type)])
            return out
        if k == K.IF_STMT:
            ch = list(c.get_children())
            # [init-stmt] [condition-variable decl] cond then [else]
            pre: list = []
            while len(ch) > 2 and ch[0].kind in (K.DECL_STMT, K.VAR_DECL) or (len(ch) > 3 and not ch[0].kind.is_expression()):
                first = ch.pop(0)
                if first.kind == K.VAR_DECL:
                    init = [x for x in first.get_children() if x.kind.is_expression()]
                    pre.append(["decl", first.spelling, first.type.spelling, self.expr(init[-1]) if init else None,
                                first.location.line, record_name(first.type)])
                else:
                    pre.extend(self.stmt(first))
            cond = self.expr(ch[0]) if ch else ["x", "?", ""]
            then = self.stmts(ch[1]) if len(ch) > 1 else []
            other = self.stmts(ch[2]) if len(ch) > 2 else []
            return [*pre, ["if", cond, then, other, line]]
        if k in LOOPS:
            # ["loop", kind, body, line, cond, inc, range_var, range_expr]: the interpreter iterates concretely
            # when the condition (or the range) evaluates, and runs the body once otherwise.
            ch = list(c.get_children())
            body = ch[-1] if ch else None
            pre: list = []
            cond = inc = None
            range_var = range_expr = None
            if k == K.FOR_STMT:
                head = ch[:-1]
                init = None
                if len(head) == 3:
                    init, cond, inc = head
                elif len(head) == 2:
                    if head[0].kind == K.DECL_STMT or (head[0].kind == K.BINARY_OPERATOR and _lib.clang_getCursorBinaryOperatorKind(head[0]) == 22):
                        init, cond = head
                    else:
                        cond, inc = head
                elif len(head) == 1:
                    cond = head[0]
                if init is not None:
                    pre = self.stmt(init)
            elif k in (K.WHILE_STMT,):
                cond = ch[0] if len(ch) > 1 else None
            elif k == K.DO_STMT:
                cond = ch[1] if len(ch) > 1 else None
                body = ch[0] if ch else None
            elif k == K.CXX_FOR_RANGE_STMT:
                for x in ch[:-1]:
                    if x.kind == K.VAR_DECL and range_var is None:
                        range_var = x.spelling
                        pre.append(["decl", x.spelling, x.type.spelling, None, x.location.line, record_name(x.type)])
                    elif x.kind.is_expression():
                        range_expr = self.expr(x)
            return [*pre, ["loop", LOOPS[k], self.stmts(body) if body is not None else [], line,
                           self.expr(cond) if cond is not None and cond.kind.is_expression() else None,
                           self.expr(inc) if inc is not None and inc.kind.is_expression() else None,
                           range_var, range_expr]]
        if k == K.SWITCH_STMT:
            ch = list(c.get_children())
            return [["switch", self.expr(ch[0]) if ch else None, self.stmts(ch[-1]) if ch else [], line]]
        if k in (K.CASE_STMT, K.DEFAULT_STMT, K.LABEL_STMT):
            ch = list(c.get_children())
            return self.stmt(ch[-1]) if ch else []
        if k == K.RETURN_STMT:
            ch = list(c.get_children())
            return [["ret", self.expr(ch[0]) if ch else None, line]]
        if k == K.BREAK_STMT:
            return [["break", line]]
        if k in (K.CONTINUE_STMT, K.NULL_STMT, K.GOTO_STMT):
            return []
        if k.is_expression():
            return [["e", self.expr(c), line]]
        return []

    # ----------------------------------------------------------------------------------------------------------------
    # Expressions

    def fields_of(self, t: ci.Type) -> list[str] | None:
        canon = t.get_canonical()
        key = canon.spelling
        if key in self.fields_cache:
            return self.fields_cache[key]
        decl = canon.get_declaration()
        fields = None
        if decl is not None and decl.kind in (K.STRUCT_DECL, K.CLASS_DECL, K.UNION_DECL):
            fields = []
            for f in decl.get_children():
                if f.kind == K.FIELD_DECL:
                    fields.append(f.spelling)
                elif f.kind == K.CXX_BASE_SPECIFIER:
                    fields.append("<base>")
        self.fields_cache[key] = fields
        return fields

    def text(self, c: ci.Cursor) -> str:
        ext = c.extent
        if ext.start.file is None or ext.end.file is None or ext.start.file.name != ext.end.file.name:
            return ""
        if ext.end.offset - ext.start.offset > 400 or ext.end.offset < ext.start.offset:
            return ""
        return " ".join(t.spelling for t in c.get_tokens())

    def expr(self, c: ci.Cursor | None):
        if c is None:
            return None
        k = c.kind
        if k in PASS_THROUGH:
            ch = [x for x in c.get_children() if x.kind.is_expression()]
            if k == K.UNEXPOSED_EXPR and len(ch) == 2 and ch[0].kind == K.MEMBER_REF:
                pass  # designated initializer: handled by the init list
            if len(ch) == 1:
                return self.expr(ch[0])
            if k == K.UNEXPOSED_EXPR and not ch:
                # user-defined literal ("Name"_ustr) has a string literal child; a recovery expression has tokens.
                sub = list(c.get_children())
                if sub:
                    return self.expr(sub[0])
                return ["x", "unexposed", self.text(c)]
            if k == K.CXX_FUNCTIONAL_CAST_EXPR and ch:
                return self.expr(ch[-1])
            if ch:
                return self.expr(ch[-1])
            return ["x", k.name, self.text(c)]
        if k == K.STRING_LITERAL:
            v = evaluate(c)
            if v is None:
                v = c.spelling.strip('"')
            return ["s", v]
        if k in (K.INTEGER_LITERAL, K.FLOATING_LITERAL, K.CHARACTER_LITERAL, K.CXX_BOOL_LITERAL_EXPR, K.CXX_UNARY_EXPR):
            v = evaluate(c)
            if isinstance(v, bool):
                v = int(v)
            if isinstance(v, int):
                return ["i", v]
            if isinstance(v, float):
                return ["f", v]
            if k == K.CXX_BOOL_LITERAL_EXPR:
                return ["i", 1 if c.spelling == "true" or self.text(c) == "true" else 0]
            return ["x", k.name, self.text(c)]
        if k in (K.CXX_NULL_PTR_LITERAL_EXPR, K.GNU_NULL_EXPR):
            return ["null"]
        if k == K.DECL_REF_EXPR:
            ref = c.referenced
            if ref is None:
                return ["x", "unresolved", c.spelling]
            rk = ref.kind
            if rk == K.ENUM_CONSTANT_DECL:
                return ["k", ref.spelling, ref.enum_value]
            if rk in (K.FUNCTION_DECL, K.CXX_METHOD, K.FUNCTION_TEMPLATE):
                return ["fn", ref.canonical.get_usr(), ref.spelling]
            if rk == K.VAR_DECL and (ref.semantic_parent is None or ref.semantic_parent.kind in (
                    K.TRANSLATION_UNIT, K.NAMESPACE, K.LINKAGE_SPEC, K.UNEXPOSED_DECL)) or (
                    rk == K.VAR_DECL and ref.storage_class == ci.StorageClass.STATIC
                    and ref.semantic_parent is not None and ref.semantic_parent.kind not in (K.FUNCTION_DECL, K.CXX_METHOD)):
                return ["g", ref.get_usr(), ref.spelling, c.type.spelling]
            return ["v", ref.spelling, c.type.spelling, record_name(c.type)]
        if k == K.MEMBER_REF_EXPR:
            ch = [x for x in c.get_children() if x.kind.is_expression()]
            base = ch[0] if ch else None
            rec = record_name(base.type) if base is not None else ""
            return ["m", self.expr(base) if base is not None else None, c.spelling, rec, c.type.spelling,
                    record_name(c.type)]
        if k == K.CALL_EXPR:
            return self.call(c)
        if k == K.UNARY_OPERATOR:
            op = UNOPS.get(_lib.clang_getCursorUnaryOperatorKind(c), "?")
            ch = [x for x in c.get_children() if x.kind.is_expression()]
            inner = self.expr(ch[0]) if ch else None
            if op == "-" and inner and inner[0] in ("i", "f"):
                return [inner[0], -inner[1]]
            if op in ("&", "*"):
                return ["u", op, inner, c.type.spelling, record_name(c.type)]
            return ["u", op, inner]
        if k in (K.BINARY_OPERATOR, K.COMPOUND_ASSIGNMENT_OPERATOR):
            op = BINOPS.get(_lib.clang_getCursorBinaryOperatorKind(c), "?")
            ch = [x for x in c.get_children() if x.kind.is_expression()]
            if len(ch) != 2:
                return ["x", "binop", self.text(c)]
            if op in ("=", "*=", "/=", "%=", "+=", "-=", "<<=", ">>=", "&=", "^=", "|="):
                return ["a", op, self.expr(ch[0]), self.expr(ch[1])]
            if op in ("*", "/", "+", "-", "%", "<<", ">>") and c.type.kind != ci.TypeKind.POINTER:
                v = evaluate(c)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    return ["i", v] if isinstance(v, int) else ["f", v]
            return ["b", op, self.expr(ch[0]), self.expr(ch[1])]
        if k == K.CONDITIONAL_OPERATOR:
            ch = [x for x in c.get_children() if x.kind.is_expression()]
            if len(ch) == 3:
                return ["?", self.expr(ch[0]), self.expr(ch[1]), self.expr(ch[2])]
            return ["x", "cond", self.text(c)]
        if k == K.ARRAY_SUBSCRIPT_EXPR:
            ch = [x for x in c.get_children() if x.kind.is_expression()]
            if len(ch) == 2:
                return ["idx", self.expr(ch[0]), self.expr(ch[1]), c.type.spelling, record_name(c.type)]
        if k == K.INIT_LIST_EXPR:
            return self.init_list(c)
        if k == K.LAMBDA_EXPR:
            params, body = [], []
            for ch in c.get_children():
                if ch.kind == K.PARM_DECL:
                    params.append([ch.spelling, ch.type.spelling, record_name(ch.type)])
                elif ch.kind == K.COMPOUND_STMT:
                    body = self.stmts(ch)
            return ["lambda", params, body]
        if k in (K.CXX_THIS_EXPR,):
            return ["v", "this", c.type.spelling, record_name(c.type)]
        if k in (K.CXX_NEW_EXPR, K.CXX_DELETE_EXPR, K.CXX_THROW_EXPR):
            return ["x", k.name, ""]
        if k == K.CXX_TYPEID_EXPR:
            return ["x", k.name, ""]
        ch = [x for x in c.get_children() if x.kind.is_expression()]
        if len(ch) == 1 and k in (K.CXX_BOOL_LITERAL_EXPR,):
            return self.expr(ch[0])
        return ["x", k.name, self.text(c)]

    def call(self, c: ci.Cursor):
        ref = c.referenced
        children = list(c.get_children())
        args = [self.expr(a) for a in c.get_arguments()] if ref is not None else []
        line = c.location.line
        if ref is None:
            # A call through a function pointer or with an unresolved callee (dependent / error).
            if children:
                callee = children[0]
                args = [self.expr(a) for a in children[1:] if a.kind.is_expression()]
                return ["c", None, callee.spelling or self.text(callee), args, line]
            return ["x", "call", self.text(c)]
        name = ref.spelling
        if name.startswith('operator""'):
            # A user-defined literal ("GeometryNodeMeshCone"_ustr): the literal is a child, not an argument.
            for ch in c.walk_preorder():
                if ch.kind == K.STRING_LITERAL:
                    return self.expr(ch)
            return ["x", "udl", self.text(c)]
        if ref.kind == K.CONSTRUCTOR:
            # T(x) / T{...}: a constructor; keep the single argument (StringRef("x"), float3(...)).
            return ["ctor", record_name(c.type), args, line]
        if ref.kind == K.CXX_METHOD or ref.kind == K.CONVERSION_FUNCTION:
            base = None
            if children and children[0].kind == K.MEMBER_REF_EXPR:
                sub = [x for x in children[0].get_children() if x.kind.is_expression()]
                if sub:
                    base = self.expr(sub[0])
            elif name.startswith("operator"):
                # Overloaded operator call (``a[i]``, ``a = b``, ``f(x)`` on a functor): the object is the first argument.
                return ["op", name, args, line]
            if ref.kind == K.CONVERSION_FUNCTION:
                return base if base is not None else ["x", "conv", ""]
            if base is None and ref.storage_class == ci.StorageClass.STATIC:
                return ["c", ref.get_usr(), name, args, line]
            return ["mc", name, base, args, line, ref.displayname, record_name(c.type)]
        return ["c", ref.canonical.get_usr(), name, args, line]

    def init_list(self, c: ci.Cursor):
        items = [x for x in c.get_children() if x.kind.is_expression()]
        t = c.type
        canon = t.get_canonical()
        if canon.kind in (ci.TypeKind.CONSTANTARRAY, ci.TypeKind.INCOMPLETEARRAY, ci.TypeKind.VARIABLEARRAY):
            return ["init", None, [self.expr(x) for x in items]]
        fields = self.fields_of(t)
        rec = record_name(t)
        if fields is None:
            return ["init", rec or None, [self.expr(x) for x in items]]
        out: dict = {}
        pos = 0
        for x in items:
            sub = list(x.get_children())
            if x.kind == K.UNEXPOSED_EXPR and len(sub) >= 2 and sub[0].kind == K.MEMBER_REF:
                # Designated: ``.tp_name = "x"`` (nested ``.a.b = ...`` keeps the first member only).
                name = sub[0].spelling
                out[name] = self.expr(sub[-1])
                if name in fields:
                    pos = fields.index(name) + 1
                continue
            if pos < len(fields):
                out[fields[pos]] = self.expr(x)
            pos += 1
        return ["init", rec, out]


def lower_tu(path: str, args: list[str], files: list[str], root: str) -> dict:
    index = ci.Index.create()
    tu = index.parse(path, args, options=0)
    diags = [d for d in tu.diagnostics if d.severity >= 3]
    low = Lowerer(tu, set(files), root)
    low.run()
    return {
        "version": LOWER_VERSION,
        "tu": os.path.relpath(path, root) if path.startswith(root) else path,
        "files": [os.path.relpath(f, root) for f in files],
        "errors": len(diags),
        "first_errors": [f"{d.location.file.name if d.location.file else '?'}:{d.location.line}: {d.spelling}"
                         for d in diags[:5]],
        "functions": low.functions,
        "globals": low.globals,
        "dna": low.dna,
    }


if __name__ == "__main__":
    import json
    import sys

    data = lower_tu(sys.argv[1], sys.argv[3:], [sys.argv[1]], sys.argv[2])
    print(json.dumps(data, indent=1)[:20000])
