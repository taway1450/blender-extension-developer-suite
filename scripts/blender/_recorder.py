"""Shared by the probe scripts that run inside Blender: the arguments after ``--`` and each check's outcome, which the
driver reads back (``scripts/_probe.py``).

A probe script makes this directory importable first (Blender's ``--python`` does not)::

  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
"""

from __future__ import annotations

import json
import sys
import traceback


def script_args() -> list[str]:
    """The script's own arguments, after Blender's ``--``."""
    return sys.argv[sys.argv.index("--") + 1 :]


def failure() -> dict:
    """The outcome of a check that raised: the traceback of the exception being handled."""
    return {"ok": False, "error": traceback.format_exc()}


def check(results: dict, name: str, fn, *, skip: str = "") -> None:
    """Record ``fn()``'s value as ``results[name]``, or its traceback when it raises; ``skip`` records why the check
    was not run instead."""
    if skip:
        results[name] = {"ok": True, "skipped": skip}
        return
    try:
        results[name] = {"ok": True, "value": fn()}
    except Exception:
        results[name] = failure()


def write_results(path: str, results, indent: int = 2) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=indent)
