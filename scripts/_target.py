"""The Blender version a task runs against, and the tool binary it runs.

Every check, lint and report task starts the same way: take a Blender version (and ``--ref``, ``--blender``,
``--generator``, ``--force``), prepare its source worktree, generate the bpy stubs of each stub generator, read
Blender's Python version, and build ty or ruff. ``Target`` does all of that once:

    parser = argparse.ArgumentParser(...)
    add_target_arguments(parser, binary="ty")   # or None for a task that builds nothing
    args = parser.parse_args()
    target = Target.from_args(args)
    for generator, stubs in target.stubs.items():
        run(target.binary, ..., "--python-version", target.python_version, "--extra-search-path", stubs)

The binary comes from ``--profile`` (dev by default, see build_ty.py) or is given with ``--ty <path>``, which
skips the build.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from _common import CACHE_DIR
from build_ty import add_binary_arguments, binary_from_args
from generate_stubs import (
    add_stubs_arguments,
    blender_python_version,
    ensure_worktree,
    generate_stubs,
    resolve_generators,
)

TYPECHECK_RESULTS_DIR = CACHE_DIR / "typecheck-results"


def add_target_arguments(parser: argparse.ArgumentParser, binary: str | None) -> None:
    """The version and stub arguments, plus the arguments choosing the ``binary`` (``ty``, ``ruff`` or None)."""
    add_stubs_arguments(parser)
    if binary is not None:
        add_binary_arguments(parser, binary)
    parser.set_defaults(target_binary=binary)


@dataclass(frozen=True)
class Target:
    version: str  # a release (X.Y) or the name of a Blender build from source
    source: Path  # the Blender source worktree of that version
    python_version: str  # Blender's Python, X.Y
    stubs: dict[str, Path]  # bpy stubs per stub generator, in generator order; empty with ``stubs=False``
    binary: Path | None  # the ty or ruff binary ``add_target_arguments`` was asked for

    @classmethod
    def from_args(cls, args: argparse.Namespace, *, stubs: bool = True) -> Target:
        """Prepare everything ``args`` (from ``add_target_arguments``) asks for: the worktree, the stubs unless
        ``stubs`` is false, and the binary. The binary is built last, after the slower one-off steps."""
        source = ensure_worktree(args.version, args.ref, args.force)
        all_stubs = {}
        if stubs:
            for generator in resolve_generators(args.version, source, args.generator):
                all_stubs[generator] = generate_stubs(
                    args.version,
                    generator=generator,
                    ref=args.ref,
                    blender=args.blender,
                    force=args.force,
                    source=source,
                )
        name = args.target_binary
        return cls(
            version=args.version,
            source=source,
            python_version=blender_python_version(source),
            stubs=all_stubs,
            binary=binary_from_args(args, name) if name else None,
        )

    def results_dir(self, generator: str) -> Path:
        """``.cache/typecheck-results/<version>/<generator>/``, created, for the feature-test tasks' outputs."""
        path = TYPECHECK_RESULTS_DIR / self.version / generator
        path.mkdir(parents=True, exist_ok=True)
        return path
