"""Regenerate ty-blender's generated files: ``cargo dev generate-all`` in ``ty-blender/ruff-blender``.

ruff-blender asks for it after a change to lint rules, configuration options, CLI arguments or environment
variables: it rewrites the rule reference (``crates/ty/docs/rules.md``), the configuration schema
(``ty.schema.json``) and the other generated docs. It builds ``ruff_dev`` with the dev profile, in the same
incremental ``target/`` as the ty the check tasks build. Commit what it changes in ruff-blender.

Usage:
  uv run scripts/generate_ty.py
"""

from __future__ import annotations

import argparse

from _common import log, main_wrapper, run
from build_ty import RUFF_DIR, ensure_checkout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args()
    ensure_checkout()
    log("Regenerating ty-blender's generated files (cargo dev generate-all, dev profile)")
    run(["cargo", "dev", "generate-all"], cwd=RUFF_DIR)
    return 0


if __name__ == "__main__":
    main_wrapper(main)
