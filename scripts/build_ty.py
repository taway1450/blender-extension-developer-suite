"""Build ty from the ``ty-blender`` submodule.

Usage:
  uv run scripts/build_ty.py           # release build
  uv run scripts/build_ty.py --debug   # debug build (faster to compile, slower to run)
"""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import TY_SUBMODULE, StepError, exe, log, main_wrapper, run

RUFF_DIR = TY_SUBMODULE / "ruff"


def binary_path(name: str, debug: bool) -> Path:
    return RUFF_DIR / "target" / ("debug" if debug else "release") / exe(name)


def ty_path(debug: bool) -> Path:
    return binary_path("ty", debug)


def build_binary(name: str, debug: bool = False) -> Path:
    """Build the ``name`` binary (``ty`` or ``ruff``) of the ruff workspace in ``ty-blender/ruff``."""
    log(f"Building {name} ({'debug' if debug else 'release'})")
    run(["git", "-C", TY_SUBMODULE, "submodule", "update", "--init", "ruff"])
    run(["cargo", "build", *([] if debug else ["--release"]), "--bin", name], cwd=RUFF_DIR)
    binary = binary_path(name, debug)
    if not binary.is_file():
        raise StepError(f"{name} binary not found at {binary} after building")
    log(f"{name} binary: {binary}")
    return binary


def build_ty(debug: bool = False) -> Path:
    return build_binary("ty", debug)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--debug", action="store_true", help="Build a debug binary instead of a release binary")
    args = parser.parse_args()
    build_ty(args.debug)
    return 0


if __name__ == "__main__":
    main_wrapper(main)
