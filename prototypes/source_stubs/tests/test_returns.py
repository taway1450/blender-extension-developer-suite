"""The libclang classifier of RNA function returns: can the C function hand Python a NULL pointer?"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libclang.interp import Program
from libclang.returns import Returns

REPORT = ["c", "c:@F@BKE_report", "BKE_report", [["v", "reports", "ReportList *", ""], ["k", "RPT_ERROR", 32], ["s", "x"]], 1]
WARN = ["c", "c:@F@BKE_report", "BKE_report", [["v", "reports", "ReportList *", ""], ["k", "RPT_WARNING", 4], ["s", "x"]], 1]


def fn(name: str, body: list, params: list | None = None, usr: str | None = None) -> dict:
    return {
        "usr": usr or f"c:@F@{name}",
        "name": name,
        "qual": name,
        "params": params or [],
        "ret": "FCurve *",
        "static": False,
        "file": "f.cc",
        "line": 1,
        "body": body,
    }


def call(name: str, *args) -> list:
    return ["c", f"c:@F@{name}", name, list(args), 1]


def v(name: str) -> list:
    return ["v", name, "FCurve *", "FCurve"]


def kinds(*functions: dict, entry: str, args: tuple[str, ...] = ()) -> str:
    program = Program([{"tu": "t", "functions": list(functions)}])
    return Returns(program).verdict(program.by_name[entry][0], args).kind


# A lookup: a loop over a list that returns the match, else NULL.
FIND = fn(
    "find",
    [
        ["decl", "it", "FCurve *", ["m", v("list"), "first", "ListBase", "void *", ""], 2],
        ["loop", "for", [["if", call("match", v("it")), [["ret", v("it"), 3]], [], 3]], 3, v("it"), None, None, None],
        ["ret", ["null"], 4],
    ],
    params=[["list", "ListBase *", "ListBase"]],
)
MATCH = fn("match", [["ret", ["i", 1], 1]])


def test_null_after_an_error_report_raises() -> None:
    f = fn("rna_new", [["if", v("bad"), [["e", REPORT, 1], ["ret", ["null"], 2]], [], 1], ["ret", ["x", "CXX_NEW_EXPR", ""], 3]])
    assert kinds(f, entry="rna_new") == "raises"


def test_a_warning_does_not_raise() -> None:
    f = fn("rna_get", [["if", v("bad"), [["e", WARN, 1], ["ret", ["null"], 2]], [], 1], ["ret", ["u", "&", v("x")], 3]])
    assert kinds(f, entry="rna_get") == "null"


def test_lookup_through_a_callee_is_null() -> None:
    f = fn("rna_find", [["ret", call("find", v("list")), 1]])
    assert kinds(f, FIND, MATCH, entry="rna_find") == "null"


def test_checked_lookup_is_never_null() -> None:
    """``x = find(); if (!x) { report; return nullptr; } return x;``: the check makes ``x`` non-null after it."""
    f = fn(
        "rna_ensure",
        [
            ["decl", "x", "FCurve *", call("find", v("list")), 1],
            ["if", ["u", "!", v("x")], [["e", REPORT, 2], ["ret", ["null"], 2]], [], 2],
            ["ret", v("x"), 3],
        ],
    )
    assert kinds(f, FIND, MATCH, entry="rna_ensure") == "raises"


def test_allocations_and_addresses_are_never_null() -> None:
    f = fn("rna_add", [["if", v("c"), [["ret", call("MEM_callocN", ["i", 8]), 1]], [], 1], ["ret", ["u", "&", v("x")], 2]])
    assert kinds(f, entry="rna_add") == "never"


def test_a_parameter_check_follows_the_argument() -> None:
    """``get(ob) { if (ob == nullptr) return nullptr; return &ob->pose; }``: NULL only when the caller passes it."""
    get = fn(
        "get",
        [["if", ["b", "==", v("ob"), ["null"]], [["ret", ["null"], 1]], [], 1], ["ret", ["u", "&", v("ob")], 2]],
        params=[["ob", "Object *", "Object"]],
    )
    caller = fn("rna_get", [["ret", call("get", v("self")), 1]], params=[["self", "Object *", "Object"]])
    assert kinds(caller, get, entry="rna_get", args=("never",)) == "never"
    assert kinds(caller, get, entry="rna_get", args=("maybe",)) == "null"


def test_unparsed_callee_is_unknown() -> None:
    f = fn("rna_x", [["ret", call("elsewhere"), 1]])
    program = Program([{"tu": "t", "functions": [f]}])
    returns = Returns(program)
    assert returns.verdict(program.by_name["rna_x"][0], ()).kind == "unknown"
    assert returns.unresolved == {("", "elsewhere")}


def test_methods_resolve_by_their_record() -> None:
    method = fn(
        "fcurve_find",
        [["ret", ["null"], 1]],
        usr="c:@N@blender@N@animrig@S@Channelbag@F@fcurve_find#",
    )
    other = fn("fcurve_find", [["ret", ["u", "&", v("x")], 1]], usr="c:@S@Other@F@fcurve_find#")
    base = ["v", "self", "animrig::Channelbag &", "Channelbag"]
    f = fn("rna_find", [["ret", ["mc", "fcurve_find", base, [], 1, "fcurve_find()", "FCurve"], 1]])
    assert kinds(f, method, other, entry="rna_find") == "null"


def test_pointer_rna_follows_its_data() -> None:
    f = fn(
        "rna_ptr",
        [
            ["if", v("c"), [["ret", ["g", "c:@PointerRNA_NULL", "PointerRNA_NULL", "const PointerRNA"], 1]], [], 1],
            ["ret", call("RNA_pointer_create_discrete", v("id"), ["u", "&", v("t")], ["u", "&", v("d")]), 2],
        ],
    )
    assert kinds(f, entry="rna_ptr") == "null"
