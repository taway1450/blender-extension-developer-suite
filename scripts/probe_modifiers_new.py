# /// script
# requires-python = ">=3.12"
# ///
"""Check in background Blender that the shipped callers of ``modifiers.new()`` handle a rejected modifier (#139).

Runs ``scripts/blender/probe_modifiers_new.py`` in Blender (background, factory startup): an empty rejects
``SUBSURF`` (``new()`` returns None); each quick-effects operator (Fur, Explode, Smoke, Liquid) finishes and adds its
modifiers on the default cube, and cancels with an error report when its objects reject the modifier; the Python
FBX importer adds the armature and subdivision modifiers, importing files from
``.cache/blender-src/<version>/tests/files/io_tests/fbx``. Fails when a check raises or does not hold. Blender's
output goes to ``.cache/modifiers-new-probe/<version>/blender.log``, the results to ``result.json``.

Usage:
  uv run scripts/probe_modifiers_new.py main
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from _common import CACHE_DIR, REPO_ROOT, StepError, log, main_wrapper, validate_version
from generate_stubs import find_blender, worktree_path

PROBE = REPO_ROOT / "scripts" / "blender" / "probe_modifiers_new.py"


def failures(results: dict, output: str) -> list[str]:
    """What went wrong, from the probe's results and Blender's output."""
    problems = [f"{name} failed:\n{r['error']}" for name, r in results.items() if not r["ok"]]
    if "Traceback" in output:
        problems.append("Blender printed a traceback (see blender.log)")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("version", type=validate_version, help="Blender version (X.Y) or build name (e.g. main)")
    parser.add_argument("--blender", type=Path, help="Blender binary (or its directory) to use")
    args = parser.parse_args()

    blender = find_blender(args.version, args.blender)
    fbx_dir = worktree_path(args.version) / "tests" / "files" / "io_tests" / "fbx"
    out = CACHE_DIR / "modifiers-new-probe" / args.version
    out.mkdir(parents=True, exist_ok=True)
    result_path = out / "result.json"
    result_path.unlink(missing_ok=True)

    cmd = [blender, "--background", "--factory-startup", "-noaudio", "--python-exit-code", "1", "--python", PROBE]
    proc = subprocess.run([str(c) for c in [*cmd, "--", result_path, fbx_dir]], capture_output=True, text=True)
    output = proc.stdout + proc.stderr
    (out / "blender.log").write_text(output, encoding="utf-8")
    if proc.returncode or not result_path.exists():
        raise StepError(f"Blender failed with exit code {proc.returncode}:\n{output[-3000:]}")

    results = json.loads(result_path.read_text(encoding="utf-8"))
    problems = failures(results, output)
    if problems:
        raise StepError("modifiers.new() probe failed:\n" + "\n".join(problems))
    skipped = [name for name, r in results.items() if "skipped" in r]
    log(f"{len(results) - len(skipped)} checks passed" + (f", skipped: {', '.join(skipped)}" if skipped else ""))
    return 0


if __name__ == "__main__":
    main_wrapper(main)
