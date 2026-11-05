"""Build ruff (linter and formatter) from the ``ty-blender`` submodule.

It shares the cargo workspace and ``target/`` directory with ty, and the same profiles (see build_ty.py).

Usage:
  uv run scripts/build_ruff.py
  uv run scripts/build_ruff.py --profile profiling
  uv run scripts/build_ruff.py --debug
"""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import main_wrapper
from build_ty import DEFAULT_PROFILE, PROFILES, build_binary


def build_ruff(profile: str = DEFAULT_PROFILE) -> Path:
    return build_binary("ruff", profile)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile", choices=PROFILES, default=DEFAULT_PROFILE, help="Cargo profile")
    parser.add_argument(
        "--debug", dest="profile", action="store_const", const="dev", help="Shorthand for --profile dev"
    )
    args = parser.parse_args()
    build_ruff(args.profile)
    return 0


if __name__ == "__main__":
    main_wrapper(main)
