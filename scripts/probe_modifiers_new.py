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

from _common import REPO_ROOT, StepError, log, main_wrapper
from _probe import failed_checks, probe_dir, probe_parser, run_probe
from generate_stubs import find_blender, worktree_path

PROBE = REPO_ROOT / "scripts" / "blender" / "probe_modifiers_new.py"


def failures(results: dict, output: str) -> list[str]:
    """What went wrong, from the probe's results and Blender's output."""
    problems = failed_checks(results)
    if "Traceback" in output:
        problems.append("Blender printed a traceback (see blender.log)")
    return problems


def main() -> int:
    args = probe_parser(__doc__).parse_args()
    blender = find_blender(args.version, args.blender)
    fbx_dir = worktree_path(args.version) / "tests" / "files" / "io_tests" / "fbx"
    out = probe_dir("modifiers-new-probe", args.version)
    results, output = run_probe(blender, PROBE, out / "result.json", fbx_dir)
    problems = failures(results, output)
    if problems:
        raise StepError("modifiers.new() probe failed:\n" + "\n".join(problems))
    skipped = [name for name, r in results.items() if "skipped" in r]
    log(f"{len(results) - len(skipped)} checks passed" + (f", skipped: {', '.join(skipped)}" if skipped else ""))
    return 0


if __name__ == "__main__":
    main_wrapper(main)
