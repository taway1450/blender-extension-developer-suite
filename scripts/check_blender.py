# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""Type-check the Blender source code of a given version with ty.

Builds ty (see build_ty.py), makes sure the source worktree and bpy stubs exist (see
generate_stubs.py) and runs ty on all Python files of the worktree (excluding ``lib/`` and
``extern/``). The full output goes to ``.cache/ty-results/<version>.txt``.

Usage:
  uv run scripts/check_blender.py 5.2
  uv run scripts/check_blender.py 5.2 --debug
  uv run scripts/check_blender.py main --blender "C:/path/to/blender-5.4/blender.exe"
"""

from __future__ import annotations

import argparse
import collections
import re
import subprocess
import sys
import time
from pathlib import Path

from _common import CACHE_DIR, StepError, log, main_wrapper
from build_ty import build_ty
from generate_stubs import add_stubs_arguments, blender_python_version, ensure_worktree, generate_stubs

EXCLUDED_DIRS = ["lib", "extern"]
# Directories (relative to the Blender source root) that Blender puts on ``sys.path``.
# The generated stubs are searched before these.
BLENDER_SEARCH_PATHS = [
    "scripts/modules",
    "scripts/startup",
    "scripts/addons_core",
    "scripts/freestyle/modules",
]

DIAGNOSTIC_RE = re.compile(r"^.+?:\d+:\d+: (?P<severity>\w+)\[(?P<rule>[\w-]+)\]", re.MULTILINE)


def run_ty(ty: Path, version: str, source: Path, stubs: Path) -> Path:
    python_version = blender_python_version(source)
    results = CACHE_DIR / "ty-results" / f"{version}.txt"
    results.parent.mkdir(parents=True, exist_ok=True)

    cmd: list[str | Path] = [ty, "check", "--project", source, "--python-version", python_version,
                             "--output-format", "concise", "--no-progress", "--color", "never",
                             "--extra-search-path", stubs]
    for path in BLENDER_SEARCH_PATHS:
        cmd += ["--extra-search-path", source / path]
    for excluded in EXCLUDED_DIRS:
        cmd += ["--exclude", f"{excluded}/"]
    cmd.append(source)

    log(f"Running ty (Python {python_version}) on {source}")
    print(f"    $ {' '.join(str(c) for c in cmd)}", flush=True)
    start = time.monotonic()
    result = subprocess.run([str(c) for c in cmd], cwd=source, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    elapsed = time.monotonic() - start
    results.write_text(result.stdout + result.stderr, encoding="utf-8")

    # ty exits with 1 when it reports diagnostics; anything else non-zero is a failure of ty itself.
    if result.returncode not in (0, 1):
        sys.stderr.write(result.stderr[-5000:])
        raise StepError(f"ty failed with exit code {result.returncode} (full output in {results})")

    counts = collections.Counter((m["severity"], m["rule"]) for m in DIAGNOSTIC_RE.finditer(result.stdout))
    by_severity = collections.Counter()
    for (severity, _), count in counts.items():
        by_severity[severity] += count

    log(f"ty finished in {elapsed:.1f}s: {sum(counts.values())} diagnostics "
        f"({', '.join(f'{n} {s}' for s, n in by_severity.most_common()) or 'none'})")
    if counts:
        width = max(len(rule) for _, rule in counts)
        for (severity, rule), count in counts.most_common():
            print(f"    {count:>7}  {rule:<{width}}  ({severity})")
    log(f"Full output: {results}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_stubs_arguments(parser)
    parser.add_argument("--debug", action="store_true", help="Use a debug build of ty")
    args = parser.parse_args()

    stubs = generate_stubs(args.version, ref=args.ref, blender=args.blender, force=args.force)
    source = ensure_worktree(args.version, args.ref)
    ty = build_ty(args.debug)
    run_ty(ty, args.version, source, stubs)
    return 0


if __name__ == "__main__":
    main_wrapper(main)
