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


def ty_path(debug: bool) -> Path:
    return RUFF_DIR / "target" / ("debug" if debug else "release") / exe("ty")


def build_ty(debug: bool = False) -> Path:
    log(f"Building ty ({'debug' if debug else 'release'})")
    run(["git", "-C", TY_SUBMODULE, "submodule", "update", "--init", "ruff"])
    run(["cargo", "build", *([] if debug else ["--release"]), "--bin", "ty"], cwd=RUFF_DIR)
    ty = ty_path(debug)
    if not ty.is_file():
        raise StepError(f"ty binary not found at {ty} after building")
    log(f"ty binary: {ty}")
    return ty


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--debug", action="store_true", help="Build a debug binary instead of a release binary")
    args = parser.parse_args()
    build_ty(args.debug)
    return 0


if __name__ == "__main__":
    main_wrapper(main)
