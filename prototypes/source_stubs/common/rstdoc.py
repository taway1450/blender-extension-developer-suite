"""Signatures and types from the rst inside C docstrings (``PyDoc_STRVAR``), and C string literals.

Blender's C functions have no ``__text_signature__``: their signatures exist only as rst in the docstring
(``.. method:: to_track_quat(track='Z', up='Y')`` followed by ``:arg track: ...``, ``:type track: str``,
``:rtype: :class:`Quaternion```). A source reader reads the same strings from the source that the doc generator
reads from ``__doc__`` at runtime. Shared by the regex and libclang prototypes (the tools differ in how they find the
literal, not in what it says).
"""

from __future__ import annotations

import ast
import re

from .model import PyParam, PySignature

_ESCAPES = {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'", "0": "\0", "r": "\r"}


def decode_c_string(body: str) -> str:
    """The value of a C string literal's body (between the quotes), with escapes decoded."""
    out = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt in _ESCAPES:
                out.append(_ESCAPES[nxt])
                i += 2
                continue
            if nxt == "\n":
                i += 2
                continue
            out.append(nxt)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


_LITERAL = re.compile(r'(?:u8|L|u|U)?"((?:[^"\\\n]|\\.)*)"', re.S)


def concat_literals(text: str, macros: dict[str, str] | None = None) -> str:
    """The value of adjacent C string literals (``"a" "b" PY_ARG_X "c"``); known macro names expand to ``macros``."""
    macros = macros or {}
    out = []
    pos = 0
    token = re.compile(r'\s+|//[^\n]*|/\*.*?\*/|(?:u8|L|u|U)?"(?:[^"\\\n]|\\.)*"|[A-Za-z_]\w*|.', re.S)
    while pos < len(text):
        m = token.match(text, pos)
        if not m:
            break
        tok = m.group(0)
        pos = m.end()
        if tok.endswith('"'):
            out.append(decode_c_string(_LITERAL.match(tok).group(1)))
        elif tok in macros:
            out.append(macros[tok])
    return "".join(out)


# --------------------------------------------------------------------------------------------------------------------
# rst -> Python types

_ROLE = re.compile(r":(?:class|func|mod|data|attr|obj|meth|ref):`~?([^`<]+?)(?:\s*<[^>]+>)?`")
_WORD_TYPES = {
    "boolean": "bool",
    "bool": "bool",
    "int": "int",
    "integer": "int",
    "float": "float",
    "string": "str",
    "str": "str",
    "bytes": "bytes",
    "tuple": "tuple[Any, ...]",
    "list": "list[Any]",
    "dict": "dict[Any, Any]",
    "set": "set[Any]",
    "frozenset": "frozenset[Any]",
    "callable": "Callable[..., Any]",
    "function": "Callable[..., Any]",
    "None": "None",
    "object": "object",
    "Any": "Any",
}


def rst_type_to_python(text: str) -> str:
    """``:class:`mathutils.Vector` | None`` -> ``mathutils.Vector | None``; "" when the text is prose."""
    t = text.strip().rstrip(".")
    if not t:
        return ""
    t = _ROLE.sub(lambda m: m.group(1).strip(), t)
    t = t.replace("\\ ", "").replace("``", "")
    t = re.sub(r"\s+or\s+", " | ", t)
    t = re.sub(r",\s*optional$", "", t)
    if t in _WORD_TYPES:
        return _WORD_TYPES[t]
    candidate = t
    for word, py in (("boolean", "bool"), ("string", "str"), ("integer", "int")):
        candidate = re.sub(rf"\b{word}\b", py, candidate)
    try:
        expr = ast.parse(candidate, mode="eval")
    except SyntaxError:
        return ""
    # Only accept what looks like a type expression: names, attributes, subscripts, ``|`` unions, literals.
    for node in ast.walk(expr):
        if not isinstance(
            node,
            (
                ast.Expression,
                ast.Name,
                ast.Attribute,
                ast.Subscript,
                ast.Tuple,
                ast.BinOp,
                ast.BitOr,
                ast.Load,
                ast.Constant,
                ast.List,
                ast.Slice,
            ),
        ):
            return ""
        if isinstance(node, ast.BinOp) and not isinstance(node.op, ast.BitOr):
            return ""
    return ast.unparse(expr)


# --------------------------------------------------------------------------------------------------------------------
# Directives

_DIRECTIVE = re.compile(
    r"^\s*\.\.\s+(function|method|classmethod|staticmethod|class|attribute|data|property)::\s*(\w+)\s*(\((.*)\))?\s*$",
    re.M,
)
_FIELD = re.compile(r"^\s*:(arg|param|type|rtype|return|returns|raises|kwarg|keyword)\b\s*([\w*]*)\s*:(.*)$")


def parse_directive(doc: str) -> tuple[str, str, PySignature | None, str]:
    """The first directive of ``doc``: (kind, name, signature, attribute type); ("", "", None, "") without one.

    A signature records the parameters as written (defaults kept as source text when they parse), typed by the
    ``:type name:`` fields, and the return type from ``:rtype:``. An attribute's type is its ``:type:`` field.
    """
    m = _DIRECTIVE.search(doc)
    if not m:
        return "", "", None, ""
    kind, name, has_args, args = m.group(1), m.group(2), m.group(3), m.group(4)
    types: dict[str, str] = {}
    rtype = ""
    attr_type = ""
    lines = doc[m.end() :].splitlines()
    i = 0
    while i < len(lines):
        fm = _FIELD.match(lines[i])
        if fm:
            field_kind, field_name, rest = fm.groups()
            # A field continues on more-indented lines.
            j = i + 1
            while j < len(lines) and lines[j].startswith(" " * 6) and not _FIELD.match(lines[j]):
                rest += " " + lines[j].strip()
                j += 1
            if field_kind == "type":
                if field_name:
                    types[field_name] = rst_type_to_python(rest)
                else:
                    attr_type = rst_type_to_python(rest)
            elif field_kind == "rtype":
                rtype = rst_type_to_python(rest)
            i = j
            continue
        if _DIRECTIVE.match(lines[i]):
            break
        i += 1
    signature = None
    if has_args is not None:
        signature = PySignature(params=parse_params(args or "", types), returns=rtype)
    elif kind in {"function", "method", "classmethod", "staticmethod"}:
        signature = PySignature(params=[], returns=rtype)
    return kind, name, signature, attr_type


def _split_top(text: str) -> list[str]:
    parts, depth, cur, quote = [], 0, [], ""
    for ch in text:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "'\"":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
            continue
        cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur).strip())
    return parts


def parse_params(text: str, types: dict[str, str]) -> list[PyParam]:
    """``a, b=1, *, c=None`` (rst signature text, optionally with ``[``optional``]`` brackets) -> parameters."""
    text = text.replace("[", "").replace("]", "") if "=" not in text and "[" in text else text
    params: list[PyParam] = []
    kind = "normal"
    for part in _split_top(text):
        if part == "/":
            for p in params:
                if p.kind == "normal":
                    p.kind = "positional_only"
            continue
        if part == "*":
            kind = "keyword_only"
            continue
        if part.startswith("**"):
            name = part[2:].split(":")[0].strip()
            params.append(PyParam(name=name, type=types.get(name, ""), kind="var_keyword"))
            continue
        if part.startswith("*"):
            name = part[1:].split(":")[0].strip()
            params.append(PyParam(name=name, type=types.get(name, ""), kind="var_positional"))
            kind = "keyword_only"
            continue
        name, _, default = part.partition("=")
        name = name.split(":")[0].strip()
        if not name.isidentifier():
            continue
        default = default.strip() or None
        if default is not None:
            try:
                ast.parse(default, mode="eval")
            except SyntaxError:
                default = "..."
        params.append(PyParam(name=name, type=types.get(name, ""), default=default, kind=kind))
    return params
