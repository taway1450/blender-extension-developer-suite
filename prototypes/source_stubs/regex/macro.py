"""Macro expansion over token lists (object-like and function-like, ``#`` stringizing, ``##`` pasting).

Enough for the item macros of enum arrays (``RNA_ENUM_ITEM_SEPR``, ``INSTANCE_ITEMS_SHARED``), docstring pieces
(``PYDOC_...``) and argument macros; not a conforming preprocessor (no ``__VA_OPT__``, approximate rescanning).
"""

from __future__ import annotations

from collections.abc import Callable

from ctok import Macro, Tok, match_close, split_commas, tokenize


def _retag(toks: list[Tok], pos: int) -> list[Tok]:
    return [Tok(t.kind, t.text, pos) for t in toks]


def expand(toks: list[Tok], lookup: Callable[[str], Macro | None], hide: set[str], pos: int, depth: int = 0) -> list[Tok]:
    if depth > 24:
        return toks
    out: list[Tok] = []
    i = 0
    n = len(toks)
    while i < n:
        t = toks[i]
        if t.kind != "id" or t.text in hide:
            out.append(t)
            i += 1
            continue
        m = lookup(t.text)
        if m is None:
            out.append(t)
            i += 1
            continue
        if m.params is None:
            body = _retag(m.tokens, t.pos)
            out += expand(body, lookup, hide | {t.text}, pos, depth + 1)
            i += 1
            continue
        if i + 1 >= n or toks[i + 1].text != "(":
            out.append(t)
            i += 1
            continue
        close = match_close(toks, i + 1)
        args = split_commas(toks[i + 2 : close])
        if not args and m.params:
            args = [[]]
        params = list(m.params)
        bound: dict[str, list[Tok]] = {}
        for k, p in enumerate(params):
            if p == "..." or p.endswith("..."):
                rest = args[k:]
                joined: list[Tok] = []
                for j, a in enumerate(rest):
                    if j:
                        joined.append(Tok("op", ",", t.pos))
                    joined += a
                bound["__VA_ARGS__" if p == "..." else p[:-3]] = joined
                break
            bound[p] = args[k] if k < len(args) else []
        body = _retag(m.tokens, t.pos)
        result: list[Tok] = []
        j = 0
        while j < len(body):
            b = body[j]
            if b.text == "#" and j + 1 < len(body) and body[j + 1].text in bound:
                text = " ".join(x.text for x in bound[body[j + 1].text])
                result.append(Tok("str", '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"', t.pos))
                j += 2
                continue
            if b.text == "##" and result and j + 1 < len(body):
                nxt = body[j + 1]
                right = bound.get(nxt.text, [nxt]) if nxt.kind == "id" else [nxt]
                left = result.pop()
                pasted = left.text + (right[0].text if right else "")
                retok = tokenize(pasted)
                result.append(Tok(retok[0].kind if retok else "id", pasted, t.pos))
                result += right[1:]
                j += 2
                continue
            if b.kind == "id" and b.text in bound:
                nxt_is_paste = j + 1 < len(body) and body[j + 1].text == "##"
                arg = bound[b.text]
                result += arg if nxt_is_paste else expand(arg, lookup, hide, pos, depth + 1)
                j += 1
                continue
            result.append(b)
            j += 1
        out += expand(result, lookup, hide | {t.text}, pos, depth + 1)
        i = close + 1
    return out
