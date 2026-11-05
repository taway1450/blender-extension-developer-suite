"""Build ruff (linter and formatter) from the ``ty-blender`` submodule.

The lint and format tasks do not need this: ruff-blender changes no ruff crate, so they run stock ruff at the same
version (see build_ty.py). Build it only to test a change to ruff itself, then pass it with ``--ruff <path>``.
It shares the cargo workspace, ``target/`` directory and profiles with ty.

Usage:
  uv run scripts/build_ruff.py
  uv run scripts/build_ruff.py --profile profiling
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
    args = parser.parse_args()
    build_ruff(args.profile)
    return 0


if __name__ == "__main__":
    main_wrapper(main)
