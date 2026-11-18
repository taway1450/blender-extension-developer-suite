# /// script
# requires-python = ">=3.12"
# ///
"""Render with Freestyle in background Blender and check that its style modules run (#136).

Runs ``scripts/blender/probe_freestyle.py`` in Blender (background, factory startup): a style module that uses
``pyShuffleBP1D`` and ``pyRandomColorShader`` renders twice, and a parameter-editor line set with the noise and
``stroke_normal`` modifiers renders once. Fails when a render or a style module raises (Freestyle prints a style
module's traceback and carries on), when the module draws no strokes, when the seeded colours differ between the
two renders, or when ``random.seed`` is no longer callable afterwards. Blender's output goes to
``.cache/freestyle-probe/<version>/blender.log``, the results to ``result.json``.

Usage:
  uv run scripts/probe_freestyle.py main
"""

from __future__ import annotations

from _common import REPO_ROOT, StepError, log, main_wrapper
from _probe import failed_checks, probe_dir, probe_parser, run_probe
from generate_stubs import find_blender

PROBE = REPO_ROOT / "scripts" / "blender" / "probe_freestyle.py"


def failures(results: dict, output: str) -> list[str]:
    """What went wrong, from the probe's results and Blender's output."""
    problems = failed_checks(results, verb="raised")
    if "Traceback" in output:
        problems.append("a style module raised (see blender.log)")
    first, second = results.get("script_first", {}), results.get("script_second", {})
    if first.get("ok") and second.get("ok"):
        if not first["value"]:
            problems.append("the style module drew no strokes")
        elif first["value"] != second["value"]:
            problems.append("pyRandomColorShader(7) gave different colours in two renders")
    return problems


def main() -> int:
    args = probe_parser(__doc__).parse_args()
    blender = find_blender(args.version, args.blender)
    out = probe_dir("freestyle-probe", args.version)
    # Auto-run lets the style module, a text data-block, run.
    results, output = run_probe(blender, PROBE, out / "result.json", options=("--enable-autoexec",))
    problems = failures(results, output)
    strokes = len(results["script_first"].get("value") or [])
    if problems:
        raise StepError("Freestyle probe failed:\n" + "\n".join(problems))
    log(f"Freestyle drew {strokes} strokes twice with the same colours, the parameter editor rendered")
    return 0


if __name__ == "__main__":
    main_wrapper(main)
