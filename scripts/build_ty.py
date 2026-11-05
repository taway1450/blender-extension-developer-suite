"""Build ty from the ``ty-blender`` submodule, and choose the ty or ruff a task runs.

Cargo profiles (``--profile``):
  dev         the default: opt-level 1, incremental, so a change in ty_python_semantic rebuilds in well under a
              minute; fast enough for the feature tests
  profiling   release optimisations without LTO, built incrementally; a fast binary for whole-Blender runs, but
              every rebuild recompiles the big crates at opt-level 3 (minutes)
  release     what ty ships: fat LTO, so every change pays a long link; only to measure the shipped binary

Only ty differs from upstream: ruff-blender changes no ruff crate, so the lint and format tasks run stock ruff
(``stock_command``) at the version ruff-blender is based on, and need no build.

Usage:
  uv run scripts/build_ty.py
  uv run scripts/build_ty.py --profile profiling
"""

from __future__ import annotations

import argparse
import os
import tomllib
from pathlib import Path

from _common import TY_SUBMODULE, StepError, exe, git_output, log, main_wrapper, run

RUFF_DIR = TY_SUBMODULE / "ruff-blender"

# Cargo profile -> its directory in target/.
PROFILES = {"dev": "debug", "profiling": "profiling", "release": "release"}
DEFAULT_PROFILE = "dev"
# Profiles that inherit from release are not incremental by default; release itself stays so, LTO undoes it anyway.
INCREMENTAL_PROFILES = ("profiling",)


def binary_path(name: str, profile: str = DEFAULT_PROFILE) -> Path:
    return RUFF_DIR / "target" / PROFILES[profile] / exe(name)


def stock_command(name: str) -> list[str]:
    """Upstream ``ty`` or ``ruff`` from PyPI (through uvx) at the version ty-blender / ruff-blender is based on."""
    if name == "ty":
        version = tomllib.loads((TY_SUBMODULE / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    else:
        cargo = tomllib.loads((RUFF_DIR / "crates" / name / "Cargo.toml").read_text(encoding="utf-8"))
        version = cargo["package"]["version"]
    return ["uvx", f"{name}@{version}"]


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
    """Build the ``name`` binary (``ty`` or ``ruff``) of the ruff workspace in ``ty-blender/ruff-blender``.

    Nothing changed since the last build of that profile makes this a cargo no-op of a few seconds."""
    log(f"Building {name} ({profile} profile)")
    ensure_checkout()
    env = dict(os.environ)
    if profile in INCREMENTAL_PROFILES:
        env[f"CARGO_PROFILE_{profile.upper()}_INCREMENTAL"] = "true"
    run(["cargo", "build", "--profile", profile, "--bin", name], cwd=RUFF_DIR, env=env)
    binary = binary_path(name, profile)
    if not binary.is_file():
        raise StepError(f"{name} binary not found at {binary} after building")
    log(f"{name} binary: {binary}")
    return binary


def add_binary_arguments(parser: argparse.ArgumentParser, name: str) -> None:
    """``--profile``, and ``--<name> <path>`` to use a binary that is already built."""
    group = parser.add_argument_group(f"{name} binary")
    group.add_argument(
        "--profile",
        choices=PROFILES,
        default=DEFAULT_PROFILE,
        help=f"Cargo profile to build {name} with (default: {DEFAULT_PROFILE}, incremental)",
    )
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
    args = parser.parse_args()
    build_ty(args.profile)
    return 0


if __name__ == "__main__":
    main_wrapper(main)
