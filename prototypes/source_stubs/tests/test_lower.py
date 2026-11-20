"""The libclang lowering (``libclang/lower.py``) on small C++ sources."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("clang.cindex")

from libclang.lower import lower_tu

HEADER = """#pragma once
template<typename T> T *get(T *x) { if (!x) { return nullptr; } return x; }
template<typename T> struct Box { T *ptr; T *first() const { return ptr; } };
inline int twice(int x) { return x * 2; }
"""

SOURCE = """#include "h.hh"
struct Item {};
namespace ns {
template<typename A> typename A::ItemT *add_item(Missing &node, const char *name);
}
struct Accessor { using ItemT = Item; };
Item *f(int *node, const char *name)
{
  Item *it = ns::add_item<Accessor>(*node, name);
  Item *it2 = undeclared_fn(node, name);
  return it;
}
Item *g(Item *x) { return get(x); }
"""


def lowered(tmp_path: Path, files: list[str]) -> dict[str, dict]:
    (tmp_path / "h.hh").write_text(HEADER)
    (tmp_path / "t.cc").write_text(SOURCE)
    args = ["-x", "c++", "-std=c++20", f"-I{tmp_path}"]
    data = lower_tu(str(tmp_path / "t.cc"), args, [str(tmp_path / f) for f in files], str(tmp_path))
    return {f["name"]: f for f in data["functions"]}


def test_calls_clang_could_not_resolve_stay_calls(tmp_path: Path) -> None:
    """A call clang recovers from (no matching overload, an undeclared callee) keeps its callee and arguments
    instead of collapsing to its last argument."""
    body = lowered(tmp_path, ["t.cc"])["f"]["body"]
    it, it2 = body[0][3], body[1][3]
    assert it[:3] == ["c", None, "add_item"] and len(it[3]) == 2
    assert it2[:3] == ["c", None, "undeclared_fn"] and len(it2[3]) == 2


def test_header_templates_and_inline_functions_are_lowered(tmp_path: Path) -> None:
    functions = lowered(tmp_path, ["h.hh"])
    assert {"get", "first", "twice"} <= set(functions)
    assert functions["get"]["body"][-1][0] == "ret"


def test_files_included_by_another_spelling_are_lowered(tmp_path: Path) -> None:
    """``rna_object_gen.cc`` includes ``rna_object.cc`` through an include path: the definitions still count."""
    (tmp_path / "h.hh").write_text(HEADER)
    (tmp_path / "t.cc").write_text(SOURCE)
    (tmp_path / "sub").mkdir()
    (tmp_path / "gen.cc").write_text('#include "sub/../t.cc"\n')
    args = ["-x", "c++", "-std=c++20", f"-I{tmp_path}"]
    data = lower_tu(str(tmp_path / "gen.cc"), args, [str(tmp_path / "t.cc")], str(tmp_path))
    assert {"f", "g"} <= {f["name"] for f in data["functions"]}
