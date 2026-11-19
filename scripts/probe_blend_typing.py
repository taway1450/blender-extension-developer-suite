# /// script
# requires-python = ">=3.12"
# ///
"""Run the four .blend typing prototypes (``prototypes/blend_typing/``) on its example add-ons and compare them.

For each add-on under ``prototypes/blend_typing/examples/`` and each ``.blend`` its manifest binds
(``[tool.blender] blend-files``):

- **B** reads the file without Blender (``extract_manifest.py``) into ``B/<add-on>/<file>-manifest.toml``;
- **G** opens it in background Blender (``blender_extract.py``) into ``G/<add-on>/<file>-manifest.toml``;
- **C** turns B's manifest into the add-on's overlay ``_blend/<stem>.pyi`` (committed, so ``check:addons`` reads
  it), and G's into ``C/<add-on>/<stem>.pyi`` for comparison, against the builtin stubs of the version (a built-in
  node's sockets are already in them);
- **A** reads the files itself and types the add-on's ``reveal_type`` calls (``reader_check.py``) into
  ``A/<add-on>.txt``.

``summary.md`` lists, per file, where B (the file as stored) and G (the file as Blender loads it) disagree. With
``--make``, the example files that are generated (``asset_pack/assets.blend``, ``scene_template/startup.blend``) are
first rebuilt in Blender (``make_examples.py``). Everything goes to ``.cache/blend-typing/<version>/``.

Usage:
  uv run scripts/probe_blend_typing.py main [--make]
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

from _common import REPO_ROOT, StepError, log, main_wrapper
from _probe import probe_dir, probe_parser, run_blender
from generate_stubs import BUILTIN, STUBS_DIRS, find_blender

PROTOTYPES = REPO_ROOT / "prototypes" / "blend_typing"
EXAMPLES = PROTOTYPES / "examples"
# Keys a manifest records about the run, not the file.
RUN_KEYS = {"parse_seconds", "loaded_by"}


def bound_files(addon: Path) -> list[Path]:
    """The ``.blend`` files the add-on's manifest binds."""
    with (addon / "blender_manifest.toml").open("rb") as f:
        names = tomllib.load(f).get("tool", {}).get("blender", {}).get("blend-files", [])
    return [addon / name for name in names]


def run_python(script: str, *args: str | Path) -> str:
    """The output of the prototype ``script`` run with this Python, isolated; fails when it fails."""
    command = [sys.executable, "-I", str(PROTOTYPES / script), *map(str, args)]
    proc = subprocess.run(command, capture_output=True, text=True)
    if proc.returncode:
        raise StepError(f"{script} failed:\n{proc.stderr[-3000:]}")
    return proc.stdout


def flatten(table: dict, prefix: str = "") -> dict[str, object]:
    """The manifest as ``dotted.key -> value``, without the keys about the run."""
    flat: dict[str, object] = {}
    for key, value in table.items():
        if key in RUN_KEYS:
            continue
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(flatten(value, path + "."))
        else:
            flat[path] = value
    return flat


def show(item: object) -> str:
    """A manifest list item for the summary: ``Name (Class)`` for a pair, the name otherwise."""
    if isinstance(item, list) and len(item) == 2:
        return f"`{item[0]}` ({item[1]})"
    return f"`{item}`"


def differences(stored: Path, loaded: Path) -> list[str]:
    """Where B's manifest (the file as stored) and G's (as Blender loads it) disagree, one line each."""
    b = flatten(tomllib.loads(stored.read_text(encoding="utf-8")))
    d = flatten(tomllib.loads(loaded.read_text(encoding="utf-8")))
    lines = []
    for key in sorted(b.keys() | d.keys()):
        stored_value, loaded_value = b.get(key), d.get(key)
        if stored_value == loaded_value:
            continue
        if isinstance(stored_value, list) and isinstance(loaded_value, list):
            # A list of [name, class] pairs (sockets, modifiers) or of names (IDs): what each side has alone.
            stored_items = [show(item) for item in stored_value]
            loaded_items = [show(item) for item in loaded_value]
            only_b = [item for item in stored_items if item not in loaded_items]
            only_g = [item for item in loaded_items if item not in stored_items]
            if not only_b and not only_g:
                lines.append(f"- `{key}`: the same items in another order")
                continue
            only = f"only B has {', '.join(only_b) or 'nothing'}; only G has {', '.join(only_g) or 'nothing'}"
            lines.append(f"- `{key}`: {only}")
        else:
            lines.append(f"- `{key}`: B `{stored_value}`, G `{loaded_value}`")
    return lines


def main() -> int:
    parser = probe_parser(__doc__)
    parser.add_argument("--make", action="store_true", help="Rebuild the generated example .blend files first")
    args = parser.parse_args()
    blender = find_blender(args.version, args.blender)
    out = probe_dir("blend-typing", args.version)
    types_stub = STUBS_DIRS[BUILTIN] / args.version / "bpy" / "types" / "__init__.pyi"
    if not types_stub.exists():
        raise StepError(f"no builtin stubs for {args.version}: run `mise run stubs:generate {args.version}` first")
    if args.make:
        code, output = run_blender(blender, PROTOTYPES / "make_examples.py", EXAMPLES, log_path=out / "make.log")
        if code:
            raise StepError(f"make_examples.py failed (see {out / 'make.log'}):\n{output[-3000:]}")

    summary = [f"# .blend typing prototypes on the example add-ons (Blender {args.version})", ""]
    for addon in sorted(p for p in EXAMPLES.iterdir() if (p / "blender_manifest.toml").exists()):
        files = bound_files(addon)
        missing = [f.name for f in files if not f.exists()]
        if missing:
            raise StepError(f"{addon.name}: missing {', '.join(missing)} (run with --make)")
        b_dir, g_dir, c_dir = (out / kind / addon.name for kind in ("B", "G", "C"))
        for directory in (b_dir, g_dir, c_dir):
            directory.mkdir(parents=True, exist_ok=True)
        code, output = run_blender(
            blender, PROTOTYPES / "blender_extract.py", g_dir, *files, log_path=g_dir / "blender.log"
        )
        if code:
            raise StepError(f"blender_extract.py failed on {addon.name} (see {g_dir / 'blender.log'}):\n{output[-3000:]}")
        summary += [f"## {addon.name}", ""]
        for blend in files:
            manifest = f"{blend.name}-manifest.toml"
            (b_dir / manifest).write_text(run_python("extract_manifest.py", blend), encoding="utf-8")
            (addon / "_blend" / f"{blend.stem}.pyi").write_text(
                run_python("gen_stubs.py", b_dir / manifest, types_stub), encoding="utf-8"
            )
            (c_dir / f"{blend.stem}.pyi").write_text(run_python("gen_stubs.py", g_dir / manifest, types_stub), encoding="utf-8")
            diff = differences(b_dir / manifest, g_dir / manifest)
            summary += [f"`{blend.name}`: B and G " + (f"disagree on {len(diff)} fact(s):" if diff else "agree."), ""]
            summary += diff + ([""] if diff else [])
        typed = run_python("reader_check.py", addon)
        (out / "A").mkdir(exist_ok=True)
        (out / "A" / f"{addon.name}.txt").write_text(typed, encoding="utf-8")
        summary += ["Approach A:", "", "```", typed.rstrip(), "```", ""]
    (out / "summary.md").write_text("\n".join(summary), encoding="utf-8")
    log(f"wrote {out / 'summary.md'}")
    return 0


if __name__ == "__main__":
    main_wrapper(main)
