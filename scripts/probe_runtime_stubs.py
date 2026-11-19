# /// script
# requires-python = ">=3.12"
# ///
"""Run the runtime stub generator prototype (``prototypes/runtime_stubs/``) and compare its stubs with the other two
generators'.

- **General mode**: background Blender at factory startup writes ``general/stubs/`` (rendered ``.pyi`` plus the
  Python source of the script folders) and ``general/facts.json``. ``summary.md`` compares the stubs with the
  builtin and fake-bpy-module stubs of the same version: modules, classes and members each has alone, and the
  members of a class both have whose annotation differs.
- **Add-on mode**, for each example add-on: Blender enables the add-on, writes the delta it made to RNA and
  ``bpy.ops`` (``addons/<name>/delta.json``), a merged package with the add-on's registrations, and a manifest per
  ``.blend`` under the add-on (``addons/<name>/blend/``).

Everything goes to ``.cache/runtime-stubs/<version>/``; nothing in the repo is written. The builtin and
fake-bpy-module stubs must have been generated (``mise run stubs:generate <version>``).

Usage:
  uv run scripts/probe_runtime_stubs.py main [--addon PATH ...]
"""

from __future__ import annotations

import ast
import json
import shutil
from collections import Counter
from pathlib import Path

from _common import REPO_ROOT, StepError, log, main_wrapper
from _probe import probe_dir, probe_parser, run_blender
from generate_stubs import BUILTIN, FAKE_BPY, STUBS_DIRS, ensure_worktree, find_blender

PROTOTYPE = REPO_ROOT / "prototypes" / "runtime_stubs" / "runtime_stub_gen.py"
EXAMPLE_ADDONS = (
    REPO_ROOT / "prototypes" / "blend_typing" / "examples" / "asset_pack",
    REPO_ROOT / "prototypes" / "blend_typing" / "examples" / "scene_template",
    REPO_ROOT / "tests" / "typecheck" / "features" / "operator_calls" / "opcall_basic",
    REPO_ROOT / "tests" / "typecheck" / "features" / "properties" / "props_registered",
)
# Blender options: no auto-run of scripts in the .blend files the add-on mode opens.
OPTIONS = ("-Y",)
SAMPLES = 12


def module_name(root: Path, path: Path) -> str:
    """``bpy/types/__init__.pyi`` -> ``bpy.types``, also for fake-bpy-module's ``bpy-stubs/types``."""
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    if parts:
        parts[0] = parts[0].removesuffix("-stubs")
    return ".".join(parts)


def annotation(node: ast.AST) -> str:
    """A member's type as written: an annotation, a property getter's return, a method's signature."""
    if isinstance(node, ast.AnnAssign):
        return ast.unparse(node.annotation)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        decorators = {ast.unparse(d) for d in node.decorator_list}
        if decorators & {"property", "builtins.property"}:
            return ast.unparse(node.returns) if node.returns else "?"
        return f"({ast.unparse(node.args)}) -> {ast.unparse(node.returns) if node.returns else '?'}"
    return "?"


def read_stubs(root: Path) -> dict[str, dict[str, dict[str, str]]]:
    """``module -> class -> member -> type`` of the ``.pyi`` and ``.py`` files under ``root`` (module-level members
    under the class name ``""``, an unannotated one as ``?``)."""
    modules: dict[str, dict[str, dict[str, str]]] = {}
    for path in sorted(root.rglob("*.py*")):
        if path.suffix not in {".pyi", ".py"} or "__pycache__" in path.parts:
            continue
        name = module_name(root, path)
        classes: dict[str, dict[str, str]] = {"": {}}
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                members = classes.setdefault(node.name, {})
                for item in node.body:
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        members.setdefault(item.target.id, annotation(item))
                    elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        members.setdefault(item.name, annotation(item))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                classes[""].setdefault(node.target.id, annotation(node))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                classes[""].setdefault(node.name, annotation(node))
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.asname and alias.asname == alias.name and node.module and not alias.name.startswith("_"):
                        classes[""].setdefault(alias.name, f"from {node.module}")
        modules[name] = classes
    return modules


def normalized(type_text: str) -> str:
    """A member's type without what only spells it differently: ``builtins.type`` and a lone ``self, /``."""
    return type_text.replace("builtins.", "").replace("(self, /)", "(self)")


def compare(runtime: dict, other: dict, other_name: str) -> list[str]:
    """The summary section comparing the runtime stubs with ``other``."""
    lines = [f"## Runtime vs {other_name}", ""]
    only_runtime = sorted(set(runtime) - set(other))
    only_other = sorted(set(other) - set(runtime))
    lines += [
        f"- Modules: {len(runtime)} runtime, {len(other)} {other_name}; {len(only_runtime)} only in runtime, "
        f"{len(only_other)} only in {other_name}.",
        f"  - Only in {other_name}: {', '.join(only_other[:40]) or 'none'}{' ...' if len(only_other) > 40 else ''}",
    ]
    class_only = Counter()
    member_only = Counter()
    differs: list[str] = []
    untyped = 0
    same = 0
    reexported = 0
    samples: dict[str, list[str]] = {"class-runtime": [], "class-other": [], "member-runtime": [], "member-other": []}
    for module in sorted(set(runtime) & set(other)):
        ours, theirs = runtime[module], other[module]
        for cls in sorted(set(ours) | set(theirs)):
            if cls not in ours and ours.get("", {}).get(cls, "").startswith("from "):
                reexported += 1
                continue
            if cls not in theirs:
                class_only["runtime"] += 1
                samples["class-runtime"].append(f"{module}.{cls}")
                continue
            if cls not in ours:
                class_only[other_name] += 1
                samples["class-other"].append(f"{module}.{cls}")
                continue
            for member in sorted(set(ours[cls]) | set(theirs[cls])):
                where = f"{module}.{cls + '.' if cls else ''}{member}"
                if member not in theirs[cls]:
                    if ours[cls][member].startswith("from ") and member in theirs:
                        continue  # the re-export of a class the other declares, counted above
                    member_only["runtime"] += 1
                    samples["member-runtime"].append(where)
                elif member not in ours[cls]:
                    member_only[other_name] += 1
                    samples["member-other"].append(where)
                elif "?" in ours[cls][member] and "?" not in theirs[cls][member]:
                    untyped += 1
                elif normalized(ours[cls][member]) != normalized(theirs[cls][member]):
                    differs.append(f"`{where}`: runtime `{ours[cls][member]}`, {other_name} `{theirs[cls][member]}`")
                else:
                    same += 1
    lines += [
        f"- Classes in shared modules: {class_only['runtime']} only in runtime, {class_only[other_name]} only in "
        f"{other_name}, {reexported} declared by {other_name} and re-exported from their module by runtime.",
        f"- Members of shared classes: {same} the same, {len(differs)} typed differently, {untyped} untyped in "
        f"runtime (copied source without annotations) but typed by {other_name}, {member_only['runtime']} only in "
        f"runtime, {member_only[other_name]} only in {other_name}.",
        "",
    ]
    for key, title in (
        ("class-other", f"Classes only in {other_name}"),
        ("class-runtime", "Classes only in runtime"),
        ("member-other", f"Members only in {other_name}"),
        ("member-runtime", "Members only in runtime"),
    ):
        if samples[key]:
            lines += [f"{title} (first {SAMPLES} of {len(samples[key])}):", ""]
            lines += [f"- `{s}`" for s in samples[key][:SAMPLES]] + [""]
    if differs:
        lines += [f"Typed differently (first {SAMPLES * 3} of {len(differs)}):", ""]
        lines += [f"- {d}" for d in differs[: SAMPLES * 3]] + [""]
    return lines


def run_generator(blender: Path, source: Path, out: Path, addon: Path | None = None) -> dict:
    if out.exists():
        shutil.rmtree(out)  # no facts, deltas or manifests left from an earlier run
    out.mkdir(parents=True)
    args: list[str | Path] = ["--source", source, "--output", out]
    if addon is not None:
        args += ["--addon", addon]
    code, output = run_blender(blender, PROTOTYPE, *args, log_path=out / "blender.log", options=OPTIONS)
    if code or not (out / "facts.json").exists():
        raise StepError(f"runtime_stub_gen.py failed (see {out / 'blender.log'}):\n{output[-3000:]}")
    return json.loads((out / "facts.json").read_text(encoding="utf-8"))


def addon_section(name: str, out: Path, facts: dict) -> list[str]:
    delta = json.loads((out / "delta.json").read_text(encoding="utf-8"))
    lines = [f"### {name}", ""]
    lines.append(
        f"- Delta: {len(delta['structs'])} new structs, {sum(len(v) for v in delta['properties'].values())} new "
        f"members on {len(delta['properties'])} existing structs, {len(delta['operators'])} operators, "
        f"{len(delta['modules'])} modules."
    )
    for struct, info in sorted(delta["structs"].items())[:SAMPLES]:
        lines.append(f"  - struct `{struct}` ({info['base']}, {info['module']})")
    for struct, members in sorted(delta["properties"].items())[:SAMPLES]:
        lines.append(f"  - `{struct}` gains {', '.join(f'`{m}`' for m in members)}")
    for op in delta["operators"][:SAMPLES]:
        lines.append(f"  - operator `{op}`")
    for blend in sorted((out / "blend").glob("*.json")):
        manifest = json.loads(blend.read_text(encoding="utf-8"))
        counts = ", ".join(f"{len(entry['items'])} {kind}" for kind, entry in sorted(manifest["data"].items()))
        overlay = out / "stubs" / delta["package"] / "_blend" / f"{Path(manifest['file']).stem}.pyi"
        tree = ast.parse(overlay.read_text(encoding="utf-8"))
        classes = sum(isinstance(node, ast.ClassDef) for node in tree.body)
        lines.append(
            f"- `{manifest['file']}` ({manifest['seconds']} s): {counts}; overlay "
            f"`{overlay.relative_to(out).as_posix()}` with {classes} classes"
        )
    lines.append(f"- Render errors: {len(facts['render_errors'])}; total {facts['seconds_total']} s.")
    return lines + [""]


def main() -> int:
    parser = probe_parser(__doc__)
    parser.add_argument("--addon", type=Path, action="append", help="An add-on folder (default: the examples)")
    args = parser.parse_args()
    out = probe_dir("runtime-stubs", args.version)
    blender = find_blender(args.version, args.blender)
    source = ensure_worktree(args.version)

    log("Runtime stubs, general mode (factory startup)")
    facts = run_generator(blender, source, out / "general")
    runtime = read_stubs(out / "general" / "stubs")
    summary = [f"# Runtime stub generator prototype, Blender {facts['blender']} ({facts['build_hash'][:10]})", ""]
    summary += [
        "## General mode",
        "",
        f"- {facts['seconds_total']} s in Blender ({facts['seconds_rna']} s for RNA: `BuildRNAInfo` and the Type-tag probe), "
        f"{len(facts['modules'])} rendered modules, {facts['copied_python_files']} Python files copied, "
        f"{facts['startup_reexports']} startup classes re-exported from their modules.",
        f"- Default add-ons enabled at factory startup: {', '.join(facts['default_addons_enabled']) or 'none'}.",
        f"- Default add-on classes left out: {len(facts['default_addon_classes'])}; their properties on built-in "
        f"structs left out: {', '.join(f'`{p}`' for p in facts['default_addon_properties']) or 'none'}.",
        f"- Render errors: {len(facts['render_errors'])}",
        *[f"  - {e}" for e in facts["render_errors"][:SAMPLES]],
        f"- Modules that failed to import: {', '.join(facts['import_failed']) or 'none'}",
        "",
    ]
    for generator in (BUILTIN, FAKE_BPY):
        stubs = STUBS_DIRS[generator] / args.version
        if not stubs.is_dir():
            summary += [f"## Runtime vs {generator}", "", f"No stubs at {stubs}: run `mise run stubs:generate`.", ""]
            continue
        summary += compare(runtime, read_stubs(stubs), generator)

    summary += ["## Add-on mode", ""]
    for addon in args.addon or EXAMPLE_ADDONS:
        log(f"Runtime stubs, add-on mode: {addon.name}")
        addon_out = out / "addons" / addon.name
        addon_facts = run_generator(blender, source, addon_out, addon.resolve())
        summary += addon_section(addon.name, addon_out, addon_facts)

    (out / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    log(f"Summary: {out / 'summary.md'}")
    return 0


if __name__ == "__main__":
    main_wrapper(main)
