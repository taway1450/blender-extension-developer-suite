# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""Type-check the generated bpy stubs themselves with ty.

Builds ty (see build_ty.py), makes sure the bpy stubs for the Blender version exist (see
generate_stubs.py) and runs ty on all ``.pyi`` files of each stub generator's stubs
(``--generator``). The full output goes to ``.cache/ty-results/stubs-<version>.txt`` (fake-bpy-module
stubs) and ``stubs-<version>-builtin.txt`` (Blender's own stubs).

Usage:
  uv run scripts/check_stubs.py 5.2
  uv run scripts/check_stubs.py 5.2 --debug
"""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import CACHE_DIR, COMPLETE_MARKER, log, main_wrapper, run
from build_ty import build_ty
from check_blender import run_ty_with_summary
from generate_stubs import (
    add_stubs_arguments,
    blender_python_version,
    ensure_worktree,
    generate_stubs,
    resolve_generators,
    results_name,
)


def stubs_venv(python_version: str) -> Path:
    """A virtual environment with the stubs' runtime dependencies (the fake-bpy-module package requires numpy)."""
    venv = CACHE_DIR / "stubs-venv" / python_version
    if not (venv / COMPLETE_MARKER).exists():
        log(f"Creating a Python {python_version} environment with numpy at {venv}")
        run(["uv", "venv", "--quiet", "--clear", "--python", python_version, venv])
        run(["uv", "pip", "install", "--quiet", "--python", venv, "numpy>=1.21"])
        (venv / COMPLETE_MARKER).touch()
    return venv


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_stubs_arguments(parser)
    parser.add_argument("--debug", action="store_true", help="Use a debug build of ty")
    args = parser.parse_args()

    generators = resolve_generators(args.version, args.ref, args.generator)
    all_stubs = {g: generate_stubs(args.version, generator=g, ref=args.ref, blender=args.blender, force=args.force)
                 for g in generators}
    python_version = blender_python_version(ensure_worktree(args.version, args.ref))
    ty = build_ty(args.debug)

    for generator, stubs in all_stubs.items():
        cmd: list[str | Path] = [ty, "check", "--project", stubs, "--python-version", python_version,
                                 "--python", stubs_venv(python_version),
                                 "--output-format", "concise", "--no-progress", "--color", "never",
                                 "--extra-search-path", stubs, stubs]
        log(f"Running ty (Python {python_version}) on the {generator} bpy stubs {stubs}")
        run_ty_with_summary(cmd, stubs, CACHE_DIR / "ty-results" / results_name(f"stubs-{args.version}", generator))
    return 0


if __name__ == "__main__":
    main_wrapper(main)
