"""regex: read Blender's C/C++ source with plain Python (regular expressions and a small tokenizer), no compiler.

A comment stripper, a preprocessor-lite (``#if``/``#ifdef RNA_RUNTIME``/``#else`` nesting, ``#define`` macros),
a tokenizer, a top-level splitter, and a tiny symbolic executor of definition code (``RNA_def_*``, ``ot->...``)
that follows helper calls with the caller's struct/property bound. See README.md.
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from common.driver import main  # noqa: E402
from common.model import SourceModel  # noqa: E402

AREAS = ["rna", "operators", "nodes", "pyapi", "context", "bmesh"]


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--areas", default=",".join(AREAS), help=f"Comma-separated areas (default: all: {','.join(AREAS)})")


def extract(source: Path, model: SourceModel, args: argparse.Namespace) -> None:
    from ctok import Tree
    from extract import run_areas

    tree = Tree(source)
    areas = [a.strip() for a in args.areas.split(",") if a.strip()]
    run_areas(tree, model, areas)


if __name__ == "__main__":
    sys.exit(main("regex", extract, __doc__, add_arguments))
