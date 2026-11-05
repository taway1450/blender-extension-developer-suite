"""Build ty from the ``ty-blender`` submodule.

Cargo profiles (``--profile``):
  release     what ty ships: fat LTO, so every change pays a long link (the default)
  profiling   release optimisations without LTO: fast binary, much faster rebuilds; the one for working on ty
  dev         unoptimised debug build (``--debug``): fastest to compile, slow on the full feature tests

Usage:
  uv run scripts/build_ty.py
  uv run scripts/build_ty.py --profile profiling
  uv run scripts/build_ty.py --debug
"""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import TY_SUBMODULE, StepError, exe, git_output, log, main_wrapper, run

RUFF_DIR = TY_SUBMODULE / "ruff-blender"

# Cargo profile -> its directory in target/.
PROFILES = {"release": "release", "profiling": "profiling", "dev": "debug"}
DEFAULT_PROFILE = "release"


def binary_path(name: str, profile: str = DEFAULT_PROFILE) -> Path:
    return RUFF_DIR / "target" / PROFILES[profile] / exe(name)


def ensure_checkout() -> None:
    """Check out ``ty-blender/ruff-blender`` if it is not checked out yet, and otherwise leave it alone.

    ``git submodule update`` on a checkout would move it back to the commit ty-blender records, discarding the
    branch someone is working on in it; the build has to test whatever is checked out.
    """
    if (RUFF_DIR / ".git").exists():
        recorded = git_output(TY_SUBMODULE, "rev-parse", "HEAD:ruff-blender")
        current = git_output(RUFF_DIR, "rev-parse", "HEAD")
        if current != recorded:
            log(f"ruff-blender is at {current[:10]}, not at the commit ty-blender records ({recorded[:10]})")
        return
    run(["git", "-C", TY_SUBMODULE, "submodule", "update", "--init", "ruff-blender"])


def build_binary(name: str, profile: str = DEFAULT_PROFILE) -> Path:
    """Build the ``name`` binary (``ty`` or ``ruff``) of the ruff workspace in ``ty-blender/ruff-blender``."""
    log(f"Building {name} ({profile} profile)")
    ensure_checkout()
    run(["cargo", "build", "--profile", profile, "--bin", name], cwd=RUFF_DIR)
    binary = binary_path(name, profile)
    if not binary.is_file():
        raise StepError(f"{name} binary not found at {binary} after building")
    log(f"{name} binary: {binary}")
    return binary


def add_binary_arguments(parser: argparse.ArgumentParser, name: str) -> None:
    """``--profile``/``--debug``, and ``--<name> <path>`` to use a binary that is already built."""
    group = parser.add_argument_group(f"{name} binary")
    group.add_argument(
        "--profile",
        choices=PROFILES,
        default=DEFAULT_PROFILE,
        help=f"Cargo profile to build {name} with (default: {DEFAULT_PROFILE}; profiling skips the slow LTO link)",
    )
    group.add_argument("--debug", dest="profile", action="store_const", const="dev", help="Shorthand for --profile dev")
    group.add_argument(f"--{name}", dest="binary", type=Path, help=f"Use this {name} binary instead of building one")


def binary_from_args(args: argparse.Namespace, name: str) -> Path:
    """The binary ``add_binary_arguments`` asked for: the one given with ``--<name>``, or a fresh build."""
    if args.binary is None:
        return build_binary(name, args.profile)
    binary = args.binary.resolve()
    if not binary.is_file():
        raise StepError(f"--{name} {args.binary}: no such file")
    log(f"Using {name} binary {binary} (not building)")
    return binary


def build_ty(profile: str = DEFAULT_PROFILE) -> Path:
    return build_binary("ty", profile)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile", choices=PROFILES, default=DEFAULT_PROFILE, help="Cargo profile")
    parser.add_argument(
        "--debug", dest="profile", action="store_const", const="dev", help="Shorthand for --profile dev"
    )
    args = parser.parse_args()
    build_ty(args.profile)
    return 0


if __name__ == "__main__":
    main_wrapper(main)
