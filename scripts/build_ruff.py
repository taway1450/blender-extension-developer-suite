"""Build ruff (linter and formatter) from the ``ty-blender`` submodule.

It shares the cargo workspace and ``target/`` directory with ty (see build_ty.py).

Usage:
  uv run scripts/build_ruff.py           # release build
  uv run scripts/build_ruff.py --debug   # debug build (faster to compile, slower to run)
"""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import main_wrapper
from build_ty import build_binary


def build_ruff(debug: bool = False) -> Path:
    return build_binary("ruff", debug)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--debug", action="store_true", help="Build a debug binary instead of a release binary")
    args = parser.parse_args()
    build_ruff(args.debug)
    return 0


if __name__ == "__main__":
    main_wrapper(main)
