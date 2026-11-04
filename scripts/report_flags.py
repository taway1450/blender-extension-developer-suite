# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""Create tables comparing Blender's RNA flags with runtime behaviour, the API docs and the bpy stubs.

Steps:
  1. Make sure the bpy stubs exist (see generate_stubs.py).
  2. Run Blender with ``scripts/blender/dump_rna_flags.py``: it dumps the flags of every class,
     property, function, parameter, return value and operator argument of the documented API, what
     the API docs say about them (computed with the same ``rna_info`` calls as ``sphinx_doc_gen.py``)
     and the runtime behaviour probed in Blender. A probe step that crashes Blender is recorded and
     skipped on the next run.
  3. Parse the stubs of each stub generator (``--generator``) and compare, for every row and flag:
     does the probed behaviour match the flag, do the docs match the behaviour, do the stubs match
     the behaviour?

Output in ``.cache/flag-report/<version>/`` (the report against Blender's own stubs goes to its
``builtin/`` subdirectory):
  summary.md  per-flag counts of correct and wrong docs/stubs, unnecessary or wrong flag combinations
  rows.md     one row per class, property, function, parameter, return value and operator argument
  rows.csv    the same rows as CSV
  rna.json    the raw dump from Blender

Usage:
  uv run scripts/report_flags.py 5.2
  uv run scripts/report_flags.py 5.2 --blender "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
"""

from __future__ import annotations

import argparse
import ast
import collections
import csv
import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path

from _common import CACHE_DIR, REPO_ROOT, StepError, log, main_wrapper
from generate_stubs import (
    BUILTIN,
    FAKE_BPY,
    add_stubs_arguments,
    ensure_worktree,
    find_blender,
    generate_stubs,
    resolve_generators,
)

STUB_NAMES = {FAKE_BPY: "fake-bpy-module stubs", BUILTIN: "stubs of Blender's own stub generator"}
DUMP_SCRIPT = REPO_ROOT / "scripts" / "blender" / "dump_rna_flags.py"
MAX_CRASH_RETRIES = 100

OK, WRONG, NA = "ok", "wrong", "n/a"
CONFIRMED, CONTRADICTED, NOT_PROBED = "confirmed", "contradicted", "not probed"

# Python-visible RNA flag -> C flag(s) it reflects.
FLAG_NAMES = {
    "is_required": "PARM_REQUIRED",
    "keyword-only": "PARM_REQUIRED order",
    "is_output": "PARM_OUTPUT",
    "is_never_none": "PROP_NEVER_NULL",
    "is_argument_optional": "PARM_PYFUNC_REGISTER_OPTIONAL",
    "is_readonly": "not PROP_EDITABLE",
    "is_enum_flag": "PROP_ENUM_FLAG",
    "array_length": "PROP_DYNAMIC",
    "is_registered": "PROP_REGISTER / FUNC_REGISTER",
    "is_registered_optional": "PROP_REGISTER_OPTIONAL / FUNC_REGISTER_OPTIONAL",
    "use_self / use_self_type": "FUNC_NO_SELF / FUNC_USE_SELF_TYPE",
    "is_path_supports_blend_relative": "PROP_PATH_SUPPORTS_BLEND_RELATIVE",
    "is_path_supports_templates": "PROP_PATH_SUPPORTS_TEMPLATES",
    "is_deprecated": "RNA_def_property_deprecated",
    "base": "StructRNA base",
    "in stub": "-",
}


# -----------------------------------------------------------------------------
# Running Blender


def dump_rna(blender: Path, source: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "rna.json"
    progress = Path(f"{output}.progress")
    crashed_file = out_dir / "crashed.txt"
    # Steps that crashed in an earlier run of the same version are skipped right away.
    crashed = crashed_file.read_text(encoding="utf-8").split() if crashed_file.exists() else []
    crashed_file.write_text("".join(f"{step}\n" for step in crashed), encoding="utf-8")
    sphinx_doc_gen = (source / "doc" / "python_api" / "sphinx_doc_gen.py").read_text(encoding="utf-8")
    # Newer docs mark the arguments after the first optional one as keyword-only.
    docs_kw_only = "args_kw_only_index" in sphinx_doc_gen

    for _ in range(MAX_CRASH_RETRIES):
        output.unlink(missing_ok=True)
        cmd = [
            str(blender),
            "--background",
            "--factory-startup",
            "-noaudio",
            "--python-exit-code",
            "1",
            "--python",
            str(DUMP_SCRIPT),
            "--",
            str(output),
            "--crashed",
            str(crashed_file),
        ]
        if docs_kw_only:
            cmd.append("--docs-kw-only")
        print(f"    $ {' '.join(cmd)}", flush=True)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        if output.exists() and not progress.exists():
            if result.returncode != 0:
                # The dump script removes the progress file once rna.json is written.
                log(f"Warning: Blender exited with code {result.returncode} after writing the complete dump")
            break
        step = progress.read_text(encoding="utf-8").strip() if progress.exists() else ""
        if ":" not in step or step in crashed:
            print(result.stdout[-3000:], result.stderr[-3000:])
            raise StepError(f"Blender failed with exit code {result.returncode} (last step: {step or 'none'})")
        log(f"Blender crashed in probe step {step}, skipping it and running again")
        crashed.append(step)
        if step.endswith(":read") and not step.startswith("pool "):
            # Reading crashed: the instance's data is gone, skip all probes on it.
            path = step.removesuffix(":read")
            crashed.append(path[: path.index("(") + 1] + "*" if "(" in path else path[: path.rindex(".") + 1] + "*")
        crashed_file.write_text("\n".join(crashed) + "\n", encoding="utf-8")
    else:
        raise StepError(f"Blender crashed more than {MAX_CRASH_RETRIES} times")
    return json.loads(output.read_text(encoding="utf-8"))


# -----------------------------------------------------------------------------
# Stubs


def split_union(annotation: str | None) -> list[str]:
    """Split a type annotation at its top-level ``|``."""
    if not annotation:
        return []
    parts, depth, current = [], 0, ""
    for char in annotation:
        if char in "[(":
            depth += 1
        elif char in "])":
            depth -= 1
        if char == "|" and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += char
    parts.append(current.strip())
    return parts


def has_none(annotation: str | None) -> bool:
    return "None" in split_union(annotation)


@dataclasses.dataclass
class StubArg:
    annotation: str | None
    kw_only: bool
    has_default: bool
    default: str | None


@dataclasses.dataclass
class StubFunction:
    decorators: set[str]
    args: dict[str, StubArg]
    returns: str | None
    doc: str


@dataclasses.dataclass
class StubAttribute:
    annotation: str | None
    readonly: bool
    doc: str


@dataclasses.dataclass
class StubClass:
    bases: list[str]
    attributes: dict[str, StubAttribute]
    methods: dict[str, StubFunction]


def parse_function(node: ast.FunctionDef, skip_first: bool) -> StubFunction:
    args = node.args
    positional = args.posonlyargs + args.args
    if skip_first:
        positional = positional[1:]
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    stub_args = {}
    for arg, default in zip(positional, defaults):
        stub_args[arg.arg] = StubArg(
            ast.unparse(arg.annotation) if arg.annotation else None,
            False,
            default is not None,
            ast.unparse(default) if default else None,
        )
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        stub_args[arg.arg] = StubArg(
            ast.unparse(arg.annotation) if arg.annotation else None,
            True,
            default is not None,
            ast.unparse(default) if default else None,
        )
    return StubFunction(
        {ast.unparse(d) for d in node.decorator_list},
        stub_args,
        ast.unparse(node.returns) if node.returns else None,
        ast.get_docstring(node) or "",
    )


def parse_class(node: ast.ClassDef) -> StubClass:
    cls = StubClass([ast.unparse(b) for b in node.bases], {}, {})
    body = node.body
    for i, item in enumerate(body):
        following = body[i + 1] if i + 1 < len(body) else None
        doc = (
            following.value.value
            if isinstance(following, ast.Expr)
            and isinstance(getattr(following, "value", None), ast.Constant)
            and isinstance(following.value.value, str)
            else ""
        )
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            cls.attributes[item.target.id] = StubAttribute(ast.unparse(item.annotation), False, doc)
        elif isinstance(item, ast.FunctionDef):
            decorators = {ast.unparse(d) for d in item.decorator_list}
            if "property" in decorators:
                cls.attributes[item.name] = StubAttribute(
                    ast.unparse(item.returns) if item.returns else None, True, ast.get_docstring(item) or ""
                )
            elif any(d.endswith(".setter") for d in decorators):
                if item.name in cls.attributes:
                    cls.attributes[item.name].readonly = False
            elif item.name not in cls.methods:  # The first of several overloads.
                cls.methods[item.name] = parse_function(item, skip_first="staticmethod" not in decorators)
    return cls


def parse_stubs(stubs: Path, generator: str) -> tuple[dict[str, StubClass], dict[str, StubFunction]]:
    package = stubs / ("bpy-stubs" if generator == FAKE_BPY else "bpy")
    tree = ast.parse((package / "types" / "__init__.pyi").read_text(encoding="utf-8"))
    classes = {node.name: parse_class(node) for node in tree.body if isinstance(node, ast.ClassDef)}
    ops = {}
    for module in sorted((package / "ops").glob("*/__init__.pyi")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in tree.body:
            # Blender's own stubs declare operators as functions, fake-bpy-module's as classes.
            if isinstance(node, ast.FunctionDef):
                ops[f"bpy.ops.{module.parent.name}.{node.name}"] = parse_function(node, skip_first=False)
            elif isinstance(node, ast.ClassDef):
                new = next((n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "__new__"), None)
                if new is not None:
                    ops[f"bpy.ops.{module.parent.name}.{node.name}"] = parse_function(new, skip_first=True)
    return classes, ops


# -----------------------------------------------------------------------------
# Comparison


@dataclasses.dataclass
class Check:
    flag: str  # Key of FLAG_NAMES.
    value: str  # Flag value (plus context) the row has.
    behaviour: str  # What happens at runtime.
    runtime: str  # Does the probed behaviour match the flag?
    docs: str
    stub: str
    docs_note: str = ""
    stub_note: str = ""


@dataclasses.dataclass
class Row:
    kind: str
    path: str
    flags: str
    checks: list[Check] = dataclasses.field(default_factory=list)
    issues: list[str] = dataclasses.field(default_factory=list)
    crashed: list[str] = dataclasses.field(default_factory=list)
    notes: list[str] = dataclasses.field(default_factory=list)


def ok(condition: bool) -> str:
    return OK if condition else WRONG


def runtime_status(probed, expected) -> str:
    if probed is None:
        return NOT_PROBED
    return CONFIRMED if probed == expected else CONTRADICTED


def type_group(flags: dict) -> str:
    return flags["type"].lower()


def flag_summary(flags: dict) -> str:
    names = [flags["type"].lower() + (f" {flags['fixed_type']}" if flags.get("fixed_type") else "")]
    for key in (
        "is_required",
        "is_output",
        "is_never_none",
        "is_argument_optional",
        "is_readonly",
        "is_enum_flag",
        "is_registered",
        "is_registered_optional",
        "is_path_supports_blend_relative",
        "is_path_supports_templates",
        "is_deprecated",
    ):
        if flags.get(key):
            names.append(key.removeprefix("is_"))
    if flags.get("is_array"):
        dims = flags.get("array_dimensions") or []
        names.append(f"array[{'*'.join(map(str, dims)) if len(dims) > 1 else flags.get('array_length') or 'dynamic'}]")
    return ", ".join(names)


def nullable(flags: dict) -> bool:
    """Whether None can be passed for an argument with these flags (``pyrna_py_to_prop``)."""
    return flags["type"] in {"POINTER", "STRING"} and not flags["is_never_none"]


def common_checks(
    row: Row, flags: dict, docs: dict, stub_type: str | None, stub_doc: str | None, in_stub: bool
) -> None:
    """Checks shared by all property-like rows: enum flag, path flags, deprecation."""
    stub_missing = NA if in_stub else WRONG
    if flags["type"] == "ENUM":
        is_flag = flags["is_enum_flag"]
        docs_set = docs["set"]
        stub_set = stub_type is not None and "set[" in stub_type
        row.checks.append(
            Check(
                "is_enum_flag",
                str(is_flag),
                "takes a set" if is_flag else "takes a str",
                NOT_PROBED,
                ok(docs_set == is_flag),
                ok(stub_set == is_flag) if in_stub else stub_missing,
            )
        )
    for key, text in (
        ("is_path_supports_blend_relative", "blend relative"),
        ("is_path_supports_templates", "template expressions"),
    ):
        if flags.get(key):
            in_docs = any(text in info for info in docs["info"])
            row.checks.append(
                Check(
                    key,
                    "True",
                    "path prefix supported",
                    NOT_PROBED,
                    ok(in_docs),
                    ok(text in (stub_doc or "")) if in_stub else stub_missing,
                    stub_note="not mentioned in stub docstring",
                )
            )
    if flags.get("is_deprecated"):
        # The stubs keep the deprecation note in the docstring ("... removal planned in version X")
        # but don't mark it with @deprecated, so type checkers don't warn.
        doc = (stub_doc or "").lower()
        mentioned = "deprecat" in doc or "removal planned" in doc
        row.checks.append(
            Check(
                "is_deprecated",
                "True",
                "deprecated",
                NOT_PROBED,
                OK,
                ok(mentioned) if in_stub else stub_missing,
                stub_note="deprecation not mentioned in stub",
            )
        )


def compare_property(item: dict, stub_class: StubClass | None) -> Row:
    flags, docs, runtime = item["flags"], item["docs"], item["runtime"]
    name = item["path"].split(".", 1)[1]
    stub = stub_class.attributes.get(name) if stub_class else None
    row = Row("property", item["path"], flag_summary(flags), crashed=runtime.get("crashed", []))
    in_stub = stub is not None
    if not in_stub:
        row.checks.append(Check("in stub", "property", "exists", NA, OK, WRONG, stub_note="missing from stub"))

    if flags["is_registered"]:
        optional = flags["is_registered_optional"]
        row.checks.append(
            Check(
                "is_registered",
                "optional" if optional else "required",
                "optional class attribute for registration"
                if optional
                else "required class attribute for registration",
                NOT_PROBED,
                OK if optional else WRONG,
                OK if optional else WRONG,
                docs_note="not documented as required for registration",
                stub_note="not marked as required for registration",
            )
        )
    else:
        # Read-only.
        readonly = flags["is_readonly"]
        probed_writable = runtime.get("writable")
        behaviour_readonly = readonly if probed_writable is None else not probed_writable
        docs_readonly = docs["readonly"]
        if probed_writable is not None and probed_writable == readonly:
            row.notes.append(
                "assignable without error through the collection wrapper: pyrna_prop_collection_setattro skips the read-only check"
                if runtime.get("collection_wrapper")
                else "read-only on the probed instance only (an editable() callback)"
                if readonly is False
                else "writable despite the read-only flag"
            )
        row.checks.append(
            Check(
                "is_readonly",
                f"{readonly} ({type_group(flags)})",
                "read-only" if behaviour_readonly else "writable",
                runtime_status(None if probed_writable is None else not probed_writable, readonly),
                ok(docs_readonly == behaviour_readonly),
                ok(stub.readonly == behaviour_readonly) if in_stub else NA,
                stub_note="stub is " + ("read-only (@property)" if in_stub and stub.readonly else "assignable"),
            )
        )

    # None when read.
    may_be_none = flags["type"] == "POINTER" and not flags["is_never_none"]
    observed_none = runtime.get("observed_none")
    accepts_none = runtime.get("accepts_none")
    status = NOT_PROBED
    if flags["type"] == "POINTER":
        if flags["is_never_none"] and observed_none:
            status = CONTRADICTED
            row.notes.append("flagged never None, but is None on the probed instance")
        elif accepts_none is not None:
            status = runtime_status(accepts_none, not flags["is_never_none"])
        elif observed_none and not flags["is_never_none"]:
            status = CONFIRMED
    elif flags["type"] == "STRING" and accepts_none is not None:
        status = runtime_status(accepts_none, not flags["is_never_none"])
    elif accepts_none is not None:
        status = runtime_status(accepts_none, False)
    docs_none, stub_none = docs["none"], in_stub and has_none(stub.annotation)
    row.checks.append(
        Check(
            "is_never_none",
            f"{flags['is_never_none']} ({type_group(flags)})",
            "may be None" if may_be_none else "never None",
            status,
            ok(docs_none == may_be_none),
            ok(stub_none == may_be_none) if in_stub else NA,
            docs_note="docs type " + ("has" if docs_none else "lacks") + " | None",
            stub_note="stub type " + ("has" if stub_none else "lacks") + " | None",
        )
    )
    common_checks(row, flags, docs, stub.annotation if stub else None, stub.doc if stub else None, in_stub)

    if flags["is_never_none"] and flags["type"] not in {"POINTER", "STRING"}:
        row.issues.append(f"PROP_NEVER_NULL on a {type_group(flags)} property: no effect")
    if flags["is_registered_optional"] and not flags["is_registered"]:
        row.issues.append("PROP_REGISTER_OPTIONAL without PROP_REGISTER")
    if flags["is_required"]:
        row.issues.append("PARM_REQUIRED on a property: no effect outside functions")
    if (flags["is_path_supports_blend_relative"] or flags["is_path_supports_templates"]) and flags["type"] != "STRING":
        row.issues.append(f"path flag on a {type_group(flags)} property")
    return row


def compare_parameter(item: dict, stub_func: StubFunction | None, inputs: list[dict]) -> Row:
    flags, docs, runtime = item["flags"], item["docs"], item["runtime"]
    name = item["path"].rsplit("(", 1)[1][:-1]
    index = item["index"]
    callback = item["callback"]
    stub = stub_func.args.get(name) if stub_func else None
    in_stub = stub is not None
    row = Row(
        "callback parameter" if callback else "parameter",
        item["path"],
        flag_summary(flags),
        crashed=runtime.get("crashed", []),
    )
    if runtime.get("skipped"):
        row.crashed.append(f"not probed: {runtime['skipped']}")
    if not in_stub:
        row.checks.append(Check("in stub", "parameter", "exists", NA, OK, WRONG, stub_note="missing from stub"))
    docs_optional = "=" in docs["signature"]
    docs_none = docs["none"]
    stub_none = in_stub and has_none(stub.annotation)

    if callback:
        # Blender passes every parameter to a Python callback; the override may leave out the
        # parameters from the first PARM_PYFUNC_REGISTER_OPTIONAL one on (bpy_class_validate).
        row.checks.append(
            Check(
                "is_required",
                f"{flags['is_required']} (callback)",
                "always passed by Blender",
                NOT_PROBED,
                ok(not docs_optional and "optional" not in docs["info"]),
                ok(not stub.has_default) if in_stub else NA,
                docs_note="docs say optional",
                stub_note="stub has a default",
            )
        )
        first_optional = next((i for i, p in enumerate(inputs) if p["flags"]["is_argument_optional"]), None)
        if first_optional is not None:
            optional_in_override = index >= first_optional
            documented = flags["is_argument_optional"]
            value = "True" if documented else ("False (after a flagged parameter)" if optional_in_override else "False")
            row.checks.append(
                Check(
                    "is_argument_optional",
                    value,
                    "may be left out of the override" if optional_in_override else "must be in the override",
                    NOT_PROBED,
                    ok(documented == optional_in_override),
                    ok(not optional_in_override) if in_stub else NA,
                    docs_note="docs don't say it may be left out",
                    stub_note="stub can't express a parameter the override may leave out",
                )
            )
            if optional_in_override and not documented:
                row.issues.append(
                    "implicitly optional for registration: after a PARM_PYFUNC_REGISTER_OPTIONAL parameter"
                )
        may_be_none = nullable(flags)
        row.checks.append(
            Check(
                "is_never_none",
                f"{flags['is_never_none']} ({type_group(flags)}, callback)",
                "Blender may pass None" if may_be_none else "Blender never passes None",
                NOT_PROBED,
                ok(docs_none == may_be_none),
                ok(stub_none == may_be_none) if in_stub else NA,
                docs_note="docs type " + ("has" if docs_none else "lacks") + " | None",
                stub_note="stub type " + ("has" if stub_none else "lacks") + " | None",
            )
        )
        if not flags["is_required"]:
            row.issues.append("callback parameter without PARM_REQUIRED: Blender always passes it, docs say optional")
    else:
        # Required.
        required = flags["is_required"]
        probed = runtime.get("required")
        behaviour = required if probed is None else probed
        row.checks.append(
            Check(
                "is_required",
                str(required),
                "required" if behaviour else "optional",
                runtime_status(probed, required),
                ok(docs_optional == (not behaviour)),
                ok(stub.has_default == (not behaviour)) if in_stub else NA,
                docs_note="docs " + ("show a default" if docs_optional else "show no default"),
                stub_note="stub "
                + (f"has default {stub.default}" if in_stub and stub.has_default else "has no default"),
            )
        )
        # Keyword-only: pyrna_func_vectorcall only takes required parameters by position, so everything
        # from the first optional parameter on is keyword-only.
        expected_positional = all(p["flags"]["is_required"] for p in inputs[: index + 1])
        probed = runtime.get("positional")
        behaviour = expected_positional if probed is None else probed
        docs_positional = not docs["kw_only"]
        row.checks.append(
            Check(
                "keyword-only",
                "positional" if expected_positional else "keyword-only",
                "positional or keyword" if behaviour else "keyword-only",
                runtime_status(probed, expected_positional),
                ok(docs_positional == behaviour),
                ok((not stub.kw_only) == behaviour) if in_stub else NA,
                docs_note="docs " + ("allow it by position" if docs_positional else "make it keyword-only"),
                stub_note="stub " + ("makes it keyword-only" if in_stub and stub.kw_only else "allows it by position"),
            )
        )
        # None.
        expected = nullable(flags)
        probed = runtime.get("accepts_none")
        behaviour = expected if probed is None else probed
        row.checks.append(
            Check(
                "is_never_none",
                f"{flags['is_never_none']} ({type_group(flags)})",
                "accepts None" if behaviour else "rejects None",
                runtime_status(probed, expected),
                ok(docs_none == behaviour),
                ok(stub_none == behaviour) if in_stub else NA,
                docs_note="docs type " + ("has" if docs_none else "lacks") + " | None",
                stub_note="stub type " + ("has" if stub_none else "lacks") + " | None",
            )
        )
        # Dynamic arrays (PROP_DYNAMIC isn't visible from Python; only the probe can tell).
        if flags["is_array"] and flags["array_length"] and "accepts_other_length" in runtime:
            dynamic = runtime["accepts_other_length"]
            docs_dynamic = docs["dynamic"]
            row.checks.append(
                Check(
                    "array_length",
                    "dynamic" if dynamic else f"fixed {flags['array_length']}",
                    "any length" if dynamic else f"exactly {flags['array_length']} items",
                    CONFIRMED,
                    ok(docs_dynamic == dynamic),
                    NA,
                    docs_note="docs give a fixed length" if dynamic else "docs say dynamic",
                )
            )
        if flags["is_argument_optional"]:
            row.issues.append("PARM_PYFUNC_REGISTER_OPTIONAL on a parameter of a non-callback function: no effect")
        if required and any(not p["flags"]["is_required"] for p in inputs[:index]):
            row.issues.append("required parameter after an optional one: must be passed as a keyword")
        if not required and flags["is_never_none"] and flags["type"] == "POINTER":
            row.issues.append("optional parameter that rejects None, but its default is shown as None")
    common_checks(row, flags, docs, stub.annotation if stub else None, stub_func.doc if stub_func else None, in_stub)
    if "enum_flag_accepts_set" in runtime:
        takes_set = runtime["enum_flag_accepts_set"] and not runtime["enum_flag_accepts_str"]
        for check in row.checks:
            if check.flag == "is_enum_flag":
                check.runtime = CONFIRMED if takes_set else CONTRADICTED

    if flags["is_never_none"] and flags["type"] not in {"POINTER", "STRING"}:
        row.issues.append(f"PROP_NEVER_NULL on a {type_group(flags)} parameter: no effect")
    if flags["is_readonly"]:
        row.issues.append("PROP_EDITABLE cleared on a parameter: no effect")
    return row


def tuple_elements(annotation: str | None) -> list[str] | None:
    if not annotation:
        return None
    try:
        node = ast.parse(annotation, mode="eval").body
    except SyntaxError:
        return None
    if isinstance(node, ast.Subscript) and ast.unparse(node.value) == "tuple":
        elements = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        return [ast.unparse(e) for e in elements]
    return None


def compare_return(item: dict, stub_func: StubFunction | None) -> Row:
    flags, docs = item["flags"], item["docs"]
    row = Row("return", item["path"], flag_summary(flags))
    in_stub = stub_func is not None
    stub_type = stub_func.returns if in_stub else None
    if item["n_outputs"] > 1:
        elements = tuple_elements(stub_type)
        row.checks.append(
            Check(
                "is_output",
                "multiple outputs",
                "returned as a tuple",
                NOT_PROBED,
                OK,
                ok(elements is not None and len(elements) == item["n_outputs"]) if in_stub else NA,
                stub_note="stub doesn't return a tuple of that length",
            )
        )
        stub_type = elements[item["index"]] if elements and len(elements) == item["n_outputs"] else None
    may_be_none = flags["type"] == "POINTER" and not flags["is_never_none"]
    docs_none, stub_none = docs["none"], has_none(stub_type)
    row.checks.append(
        Check(
            "is_never_none",
            f"{flags['is_never_none']} ({type_group(flags)}, return)",
            "may be None (by flag)" if may_be_none else "never None",
            NOT_PROBED,
            ok(docs_none == may_be_none),
            ok(stub_none == may_be_none) if stub_type is not None else NA,
            docs_note="docs type " + ("has" if docs_none else "lacks") + " | None",
            stub_note="stub type " + ("has" if stub_none else "lacks") + " | None",
        )
    )
    common_checks(row, flags, docs, stub_type, stub_func.doc if stub_func else None, in_stub)
    if flags["is_required"]:
        row.issues.append("PARM_REQUIRED on a return value: no effect")
    if flags["is_never_none"] and flags["type"] not in {"POINTER", "STRING"}:
        row.issues.append(f"PROP_NEVER_NULL on a {type_group(flags)} return value: no effect")
    return row


def compare_function(item: dict, stub_func: StubFunction | None) -> Row:
    flags = item["flags"]
    row = Row("function", item["path"], ", ".join(k for k, v in flags.items() if v) or "-")
    if stub_func is None:
        row.checks.append(Check("in stub", "function", "exists", NA, OK, WRONG, stub_note="missing from stub"))
    if flags["use_self"]:
        kind = "method"
    elif flags["use_self_type"]:
        kind = "classmethod"
    else:
        kind = "staticmethod"
    stub_kind = None
    if stub_func is not None:
        stub_kind = (
            "classmethod"
            if "classmethod" in stub_func.decorators
            else "staticmethod"
            if "staticmethod" in stub_func.decorators
            else "method"
        )
    row.checks.append(
        Check(
            "use_self / use_self_type",
            f"use_self={flags['use_self']}, use_self_type={flags['use_self_type']}",
            kind,
            NOT_PROBED,
            ok(item["docs"]["kind"] == kind),
            ok(stub_kind == kind) if stub_func else NA,
            docs_note=f"docs say {item['docs']['kind']}",
            stub_note=f"stub says {stub_kind}",
        )
    )
    if flags["is_registered"]:
        optional = flags["is_registered_optional"]
        row.checks.append(
            Check(
                "is_registered",
                "optional" if optional else "required",
                "optional callback" if optional else "required callback: registration fails without it",
                NOT_PROBED,
                OK if optional else WRONG,
                OK if optional else WRONG,
                docs_note="not documented as required",
                stub_note="not marked as required",
            )
        )
    if flags["is_registered_optional"] and not flags["is_registered"]:
        row.issues.append("FUNC_REGISTER_OPTIONAL without FUNC_REGISTER")
    if flags["use_self"] and flags["use_self_type"]:
        row.issues.append("FUNC_USE_SELF_TYPE on a method with self: also receives the type")
    return row


def compare_operator_argument(item: dict, stub_func: StubFunction | None) -> Row:
    flags, docs, runtime = item["flags"], item["docs"], item["runtime"]
    name = item["path"].rsplit("(", 1)[1][:-1]
    stub = stub_func.args.get(name) if stub_func else None
    in_stub = stub is not None
    row = Row("operator argument", item["path"], flag_summary(flags), crashed=runtime.get("crashed", []))
    if not in_stub:
        row.checks.append(Check("in stub", "operator argument", "exists", NA, OK, WRONG, stub_note="missing from stub"))
    expected = nullable(flags)
    probed = runtime.get("accepts_none")
    behaviour = expected if probed is None else probed
    docs_none, stub_none = docs["none"], in_stub and has_none(stub.annotation)
    row.checks.append(
        Check(
            "is_never_none",
            f"{flags['is_never_none']} ({type_group(flags)}, operator)",
            "accepts None" if behaviour else "rejects None",
            runtime_status(probed, expected),
            ok(docs_none == behaviour),
            ok(stub_none == behaviour) if in_stub else NA,
            docs_note="docs type " + ("has" if docs_none else "lacks") + " | None",
            stub_note="stub type " + ("has" if stub_none else "lacks") + " | None",
        )
    )
    row.checks.append(
        Check(
            "keyword-only",
            "keyword-only (operator)",
            "keyword-only",
            NOT_PROBED,
            OK,
            ok(stub.kw_only and stub.has_default) if in_stub else NA,
            stub_note="stub allows it by position",
        )
    )
    common_checks(row, flags, docs, stub.annotation if stub else None, stub_func.doc if stub_func else None, in_stub)
    if flags["is_required"]:
        row.issues.append("PARM_REQUIRED on an operator property: no effect")
    if flags["is_never_none"] and flags["type"] not in {"POINTER", "STRING"}:
        row.issues.append(f"PROP_NEVER_NULL on a {type_group(flags)} operator property: no effect")
    return row


def compare(dump: dict, stub_classes: dict[str, StubClass], stub_ops: dict[str, StubFunction]) -> list[Row]:
    rows: list[Row] = []
    items = dump["rows"]
    inputs_by_function = collections.defaultdict(list)
    for item in items:
        if item["kind"] == "parameter":
            inputs_by_function[item["function"]].append(item)
    for item in items:
        kind = item["kind"]
        if kind == "class":
            stub_class = stub_classes.get(item["path"])
            row = Row(
                "class", item["path"], f"base {item['base']}" + (", registerable" if item["registerable"] else "")
            )
            if stub_class is None:
                row.checks.append(Check("in stub", "class", "exists", NA, OK, WRONG, stub_note="missing from stub"))
            else:
                base = item["base"] or "bpy_struct"
                row.checks.append(
                    Check(
                        "base",
                        "has base" if item["base"] else "no base",
                        f"subclass of {base}",
                        NA,
                        OK,
                        ok(any(b.split(".")[-1] == base or b.startswith(base + "[") for b in stub_class.bases)),
                        stub_note=f"stub bases: {', '.join(stub_class.bases)}",
                    )
                )
            rows.append(row)
        elif kind == "property":
            rows.append(compare_property(item, stub_classes.get(item["path"].split(".", 1)[0])))
        elif kind in {"function", "parameter", "return"}:
            function = item["path"] if kind == "function" else item["function"]
            struct_id, func_name = function.split(".", 1)
            stub_class = stub_classes.get(struct_id)
            stub_func = stub_class.methods.get(func_name) if stub_class else None
            if kind == "function":
                rows.append(compare_function(item, stub_func))
            elif kind == "parameter":
                rows.append(compare_parameter(item, stub_func, inputs_by_function[function]))
            else:
                rows.append(compare_return(item, stub_func))
        elif kind == "operator":
            row = Row("operator", item["path"], "-")
            if item["path"] not in stub_ops:
                row.checks.append(Check("in stub", "operator", "exists", NA, OK, WRONG, stub_note="missing from stub"))
            rows.append(row)
        elif kind == "operator argument":
            rows.append(compare_operator_argument(item, stub_ops.get(item["function"])))
    return rows


# -----------------------------------------------------------------------------
# Output


def md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def row_cells(row: Row) -> dict[str, str]:
    def column(attr: str, note_attr: str | None, bad: str) -> str:
        notes = [
            f"{c.flag}: {getattr(c, note_attr)}" if note_attr and getattr(c, note_attr) else c.flag
            for c in row.checks
            if getattr(c, attr) == bad
        ]
        if notes:
            return "✗ " + "; ".join(notes)
        return "✓" if any(getattr(c, attr) not in (NA, NOT_PROBED) for c in row.checks) else "–"

    behaviour = ", ".join(c.behaviour for c in row.checks if c.flag != "in stub")
    runtime = column("runtime", None, CONTRADICTED)
    extra = [f"crashed Blender: {s}" if ":" not in s else s for s in row.crashed] + row.notes
    if extra:
        runtime += " (" + "; ".join(extra) + ")"
    return {
        "Kind": row.kind,
        "Path": row.path,
        "Flags": row.flags,
        "Behaviour": behaviour,
        "Runtime matches flags": runtime,
        "Docs match behaviour": column("docs", "docs_note", WRONG),
        "Stub matches behaviour": column("stub", "stub_note", WRONG),
        "Flag issues": "; ".join(row.issues),
    }


def write_rows(rows: list[Row], out_dir: Path) -> None:
    cells = [row_cells(row) for row in rows]
    headers = list(cells[0])
    with open(out_dir / "rows.csv", "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, headers)
        writer.writeheader()
        writer.writerows(cells)
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(md_escape(c[h]) for h in headers) + " |" for c in cells]
    (out_dir / "rows.md").write_text("# RNA flags per row\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def summarize(rows: list[Row], dump: dict, crashed: list[str], generator: str) -> str:
    counts: dict[tuple[str, str, str], collections.Counter] = collections.defaultdict(collections.Counter)
    examples: dict[tuple[str, str, str], dict[str, list[str]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    for row in rows:
        for check in row.checks:
            key = (check.flag, check.value, row.kind)
            counter = counts[key]
            counter["rows"] += 1
            for column, value in (("runtime", check.runtime), ("docs", check.docs), ("stub", check.stub)):
                counter[f"{column} {value}"] += 1
                if value in (WRONG, CONTRADICTED) and len(examples[key][column]) < 2:
                    examples[key][column].append(row.path)

    def cell(counter, column, good, bad):
        g, b = counter[f"{column} {good}"], counter[f"{column} {bad}"]
        return f"{g} / {b}" if g or b else "–"

    flag_order = list(FLAG_NAMES)
    lines = [
        f"# RNA flag report for Blender {dump['blender_version']}",
        "",
        "One check per row and flag. **Runtime** compares the behaviour probed in Blender with what the flag",
        "says (`confirmed / contradicted`; rows without a probe count in neither). **Docs** and **Stub** compare",
        f"the Blender API docs and the {STUB_NAMES[generator]} with the behaviour (`correct / wrong`). Where no",
        "probe ran, the behaviour is the one the flag implies in `bpy_rna.cc`.",
        "",
        "| Flag | C flag | Value | Row kind | Rows | Runtime ✓ / ✗ | Docs ✓ / ✗ | Stub ✓ / ✗ | Examples of wrong |",
        "|---|---|---|---|---:|---:|---:|---:|---|",
    ]
    for key in sorted(counts, key=lambda k: (flag_order.index(k[0]), k[2], k[1])):
        flag, value, kind = key
        c = counts[key]
        ex = "; ".join(f"{col}: {', '.join(paths)}" for col, paths in examples[key].items())
        lines.append(
            f"| {flag} | {FLAG_NAMES[flag]} | {md_escape(value)} | {kind} | {c['rows']} | "
            f"{cell(c, 'runtime', CONFIRMED, CONTRADICTED)} | {cell(c, 'docs', OK, WRONG)} | "
            f"{cell(c, 'stub', OK, WRONG)} | {md_escape(ex)} |"
        )

    totals = collections.Counter()
    for c in counts.values():
        totals.update(c)
    lines += [
        (
            f"| **Total** | | | | {totals['rows']} | {totals['runtime ' + CONFIRMED]} / {totals['runtime ' + CONTRADICTED]} | "
            f"{totals['docs ' + OK]} / {totals['docs ' + WRONG]} | {totals['stub ' + OK]} / {totals['stub ' + WRONG]} | |"
        ),
        "",
        "## Unnecessary or wrong flag combinations",
        "",
        "| Combination | Count | Examples |",
        "|---|---:|---|",
    ]
    issues = collections.Counter()
    issue_examples = collections.defaultdict(list)
    for row in rows:
        for issue in row.issues:
            issues[issue] += 1
            if len(issue_examples[issue]) < 3:
                issue_examples[issue].append(row.path)
    for issue, count in issues.most_common():
        lines.append(f"| {md_escape(issue)} | {count} | {md_escape(', '.join(issue_examples[issue]))} |")

    kinds = collections.Counter(row.kind for row in rows)
    lines += ["", "## Rows", "", "| Row kind | Count |", "|---|---:|"]
    lines += [f"| {kind} | {count} |" for kind, count in kinds.most_common()]
    notes = collections.Counter(note for row in rows for note in row.notes)
    lines += ["", "## Runtime contradictions explained", "", "| Explanation | Count |", "|---|---:|"]
    lines += [f"| {md_escape(note)} | {count} |" for note, count in notes.most_common()]
    lines += [
        "",
        "## Notes",
        "",
        f"- Probe instances were found for {dump['pool_types']} struct types; rows without an instance aren't probed.",
        "- Function probes never run the function: an extra unknown keyword makes `pyrna_func_vectorcall` stop",
        "  after converting the arguments. Property probes assign a value no type accepts (read-only check)",
        "  and `None` (restoring the old value).",
        "- Return values can't be probed without running the function, so their behaviour is the flag's: a",
        "  pointer return without `PROP_NEVER_NULL` may be `None`. Many functions never return `None` in",
        "  practice, so the flag itself is unreliable for return values.",
        "- `PROP_DYNAMIC` isn't visible from Python; arrays are tested by passing a longer array.",
        '- Blender < 4.4 documents types as prose ("Object, (optional, never None)"); there a pointer counts',
        '  as documented to allow None unless it says "never None".',
        "- A crash can be caused by an earlier probe that changed data (a stale Python reference), so",
        "  reproduce a crash on its own before reporting it as a Blender bug.",
        "",
    ]
    lines += ["## Probe steps that crashed Blender", ""]
    lines += [f"- `{step}`" for step in crashed] or ["None."]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_stubs_arguments(parser)
    parser.add_argument(
        "--reuse-dump", action="store_true", help="Compare the existing rna.json again instead of running Blender"
    )
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    generators = resolve_generators(args.version, args.ref, args.generator)
    all_stubs = {
        g: generate_stubs(args.version, generator=g, ref=args.ref, blender=args.blender, force=args.force)
        for g in generators
    }
    source = ensure_worktree(args.version, args.ref)
    blender = find_blender(args.version, args.blender)
    out_dir = CACHE_DIR / "flag-report" / args.version

    if args.reuse_dump and (out_dir / "rna.json").exists():
        dump = json.loads((out_dir / "rna.json").read_text(encoding="utf-8"))
    else:
        if args.force:
            (out_dir / "crashed.txt").unlink(missing_ok=True)
        log(f"Dumping RNA flags, docs and runtime behaviour with Blender {args.version}")
        dump = dump_rna(blender, source, out_dir)
    crashed = (out_dir / "crashed.txt").read_text(encoding="utf-8").split()

    for generator, stubs in all_stubs.items():
        log(f"Comparing {len(dump['rows'])} rows with the {generator} stubs in {stubs}")
        stub_classes, stub_ops = parse_stubs(stubs, generator)
        rows = compare(dump, stub_classes, stub_ops)
        # The report against fake-bpy-module's stubs keeps its place next to rna.json.
        report_dir = out_dir if generator == FAKE_BPY else out_dir / generator
        report_dir.mkdir(parents=True, exist_ok=True)
        write_rows(rows, report_dir)
        summary = summarize(rows, dump, crashed, generator)
        (report_dir / "summary.md").write_text(summary, encoding="utf-8")
        print(summary)
        log(f"Report: {report_dir / 'summary.md'} (all rows: {report_dir / 'rows.md'}, {report_dir / 'rows.csv'})")
    return 0


if __name__ == "__main__":
    main_wrapper(main)
