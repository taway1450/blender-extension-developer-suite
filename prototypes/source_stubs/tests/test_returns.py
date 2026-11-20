"""The libclang classifier of RNA function returns: can the C function hand Python a NULL pointer?"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libclang.interp import Program
from libclang.returns import Returns

REPORT = [
    "c",
    "c:@F@BKE_report",
    "BKE_report",
    [["v", "reports", "ReportList *", ""], ["k", "RPT_ERROR", 32], ["s", "x"]],
    1,
]
WARN = [
    "c",
    "c:@F@BKE_report",
    "BKE_report",
    [["v", "reports", "ReportList *", ""], ["k", "RPT_WARNING", 4], ["s", "x"]],
    1,
]


def fn(name: str, body: list, params: list | None = None, usr: str | None = None, ret: str = "FCurve *") -> dict:
    return {
        "usr": usr or f"c:@F@{name}",
        "name": name,
        "qual": name,
        "params": params or [],
        "ret": ret,
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
    f = fn(
        "rna_new",
        [["if", v("bad"), [["e", REPORT, 1], ["ret", ["null"], 2]], [], 1], ["ret", ["x", "CXX_NEW_EXPR", ""], 3]],
    )
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
    f = fn(
        "rna_add", [["if", v("c"), [["ret", call("MEM_callocN", ["i", 8]), 1]], [], 1], ["ret", ["u", "&", v("x")], 2]]
    )
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


def test_copies_of_a_pointer_rna_follow_their_argument() -> None:
    """``return ptr;`` / ``return PointerRNA_NULL;`` by value lower to a copy constructor; ``PointerRNA()`` is empty."""
    null = ["g", "c:@PointerRNA_NULL", "PointerRNA_NULL", "const PointerRNA"]
    f = fn(
        "rna_ptr",
        [
            ["decl", "ptr", "PointerRNA", call("RNA_pointer_create_discrete", v("id"), v("t"), ["u", "&", v("d")]), 1],
            ["if", v("c"), [["ret", ["ctor", "PointerRNA", [v("ptr")], 2], 2]], [], 2],
            ["ret", ["ctor", "PointerRNA", [null], 3], 3],
        ],
    )
    assert kinds(f, entry="rna_ptr") == "null"
    empty = fn("rna_empty", [["ret", ["ctor", "PointerRNA", [], 1], 1]])
    assert kinds(empty, entry="rna_empty") == "null"
    copy = fn("rna_copy", [["ret", ["ctor", "PointerRNA", [call("RNA_id_pointer_create", ["u", "&", v("x")])], 1], 1]])
    assert kinds(copy, entry="rna_copy") == "never"


def test_checked_fields_are_non_null() -> None:
    """``if (ntype && ntype->inputs) { stemp = ntype->inputs; return stemp; } return nullptr;``"""
    field_ = ["m", v("ntype"), "inputs", "bNodeType", "Template *", "Template"]
    f = fn(
        "rna_tmpl",
        [
            [
                "if",
                ["b", "&&", v("ntype"), field_],
                [["decl", "s", "Template *", field_, 2], ["ret", v("s"), 3]],
                [],
                1,
            ],
            ["ret", ["x", "CXX_NEW_EXPR", ""], 4],
        ],
    )
    assert kinds(f, entry="rna_tmpl") == "never"


def test_a_dereferenced_pointer_is_non_null_after() -> None:
    """``id = alloc(); ensure(*id); if (id) {...} return id;``: a NULL ``id`` would have crashed at ``*id``."""
    alloc = fn("alloc", [["if", v("ok"), [["ret", call("MEM_new_zeroed", ["i", 8]), 1]], [], 1], ["ret", ["null"], 2]])
    f = fn(
        "rna_new",
        [
            ["decl", "id", "ID *", call("alloc"), 1],
            ["e", call("ensure", ["u", "*", ["v", "id", "ID *", "ID"], "ID &", "ID"]), 2],
            ["ret", ["v", "id", "ID *", "ID"], 3],
        ],
        ret="ID *",
    )
    assert kinds(f, alloc, fn("ensure", []), entry="rna_new") == "never"


def test_a_failed_check_that_reports_raises() -> None:
    """``if (!check(ob, reports)) return nullptr;`` where ``check`` reports an error whenever it returns false."""
    ob = [["ob", "Object *", "Object"]]
    check = fn("check", [["if", v("bad"), [["e", REPORT, 1], ["ret", ["i", 0], 1]], [], 1], ["ret", ["i", 1], 2]], ob)
    quiet = fn("quiet", [["if", v("bad"), [["ret", ["i", 0], 1]], [], 1], ["ret", ["i", 1], 2]], ob)

    def caller(name: str, callee: str) -> dict:
        return fn(
            name,
            [["if", ["u", "!", call(callee, v("ob"))], [["ret", ["null"], 1]], [], 1], ["ret", ["u", "&", v("x")], 2]],
        )

    assert kinds(caller("rna_a", "check"), check, entry="rna_a") == "raises"
    assert kinds(caller("rna_b", "quiet"), quiet, entry="rna_b") == "null"


def test_a_value_of_another_pointer_type_is_unknown() -> None:
    """A dependent template call can lower to its last argument (``add_item<A>(node, name)`` as ``name``)."""
    f = fn(
        "rna_new",
        [
            ["decl", "item", "NodeEnumItem *", ["v", "name", "const char *", "char"], 1, "NodeEnumItem"],
            ["ret", ["v", "item", "NodeEnumItem *", "NodeEnumItem"], 2],
        ],
        params=[["name", "const char *", "char"]],
    )
    assert kinds(f, entry="rna_new", args=("never",)) == "unknown"


def test_a_null_the_callee_reported_raises_in_the_caller() -> None:
    """``layer = attribute_new(..., reports); if (!layer) return PointerRNA_NULL;`` where the callee reports first."""
    make = fn(
        "attribute_new",
        [["if", v("bad"), [["e", REPORT, 1], ["ret", ["null"], 1]], [], 1], ["ret", ["x", "CXX_NEW_EXPR", ""], 2]],
    )
    null = ["g", "c:@PointerRNA_NULL", "PointerRNA_NULL", "const PointerRNA"]
    f = fn(
        "rna_new",
        [
            ["decl", "layer", "FCurve *", call("attribute_new"), 1],
            ["if", ["u", "!", v("layer")], [["ret", ["ctor", "PointerRNA", [null], 2], 2]], [], 2],
            ["ret", call("RNA_pointer_create_discrete", v("id"), v("t"), v("layer")), 3],
        ],
    )
    assert kinds(f, make, entry="rna_new") == "raises"


def test_the_definition_index_reads_headers_and_skips_declarations(tmp_path: Path) -> None:
    from libclang.returns import callee_files, definition_index

    blender = tmp_path / "source/blender/deg"
    blender.mkdir(parents=True)
    (blender / "query.cc").write_text("ID *DEG_get_evaluated_id(const Depsgraph *g, ID *id)\n{\n  return id;\n}\n")
    (blender / "DEG_query.hh").write_text(
        "ID *DEG_get_evaluated_id(const Depsgraph *g, ID *id);\n"
        "template<typename T> T *DEG_get_evaluated(const Depsgraph *g, T *id)\n{\n  return id;\n}\n"
        "class Layer : public Base {\n public:\n  Frame *frame_at(int f) const;\n};\n"
    )
    index = definition_index(tmp_path)
    assert callee_files({("", "DEG_get_evaluated_id")}, index) == {"source/blender/deg/query.cc"}
    assert callee_files({("", "DEG_get_evaluated")}, index) == {"source/blender/deg/DEG_query.hh"}
    # A method of a class without an out-of-class definition: the header that defines the class.
    assert callee_files({("Layer", "frame_at")}, index) == {"source/blender/deg/DEG_query.hh"}


def test_unresolved_calls_and_class_template_methods_resolve_by_name() -> None:
    get = fn("get", [["ret", ["null"], 1]], params=[["x", "T *", ""]], usr="c:@FT@>1#Tget#*t0.0#S0_#")
    first = fn("first", [["ret", ["null"], 1]], usr="c:@ST>1#T@Box@F@first#1")
    caller = fn("rna_get", [["ret", ["c", None, "get", [v("x")], 1], 1]])
    base = ["v", "box", "Box<Item> &", "Box"]
    member = fn("rna_first", [["ret", ["mc", "first", base, [], 1, "first()", "Item"], 1]])
    assert kinds(caller, get, entry="rna_get") == "null"
    assert kinds(member, first, entry="rna_first") == "null"
