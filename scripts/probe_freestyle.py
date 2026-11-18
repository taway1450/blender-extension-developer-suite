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

import argparse
import json
import subprocess
from pathlib import Path

from _common import CACHE_DIR, REPO_ROOT, StepError, log, main_wrapper, validate_version
from generate_stubs import find_blender

PROBE = REPO_ROOT / "scripts" / "blender" / "probe_freestyle.py"


def failures(results: dict, output: str) -> list[str]:
    """What went wrong, from the probe's results and Blender's output."""
    problems = [f"{name} raised:\n{r['error']}" for name, r in results.items() if not r["ok"]]
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
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("version", type=validate_version, help="Blender version (X.Y) or build name (e.g. main)")
    parser.add_argument("--blender", type=Path, help="Blender binary (or its directory) to use")
    args = parser.parse_args()

    blender = find_blender(args.version, args.blender)
    out = CACHE_DIR / "freestyle-probe" / args.version
    out.mkdir(parents=True, exist_ok=True)
    result_path = out / "result.json"
    result_path.unlink(missing_ok=True)

    # Auto-run lets the style module, a text data-block, run.
    cmd = [blender, "--background", "--factory-startup", "--enable-autoexec", "-noaudio", "--python-exit-code", "1"]
    cmd += ["--python", PROBE]
    proc = subprocess.run([str(c) for c in [*cmd, "--", result_path]], capture_output=True, text=True)
    output = proc.stdout + proc.stderr
    (out / "blender.log").write_text(output, encoding="utf-8")
    if proc.returncode or not result_path.exists():
        raise StepError(f"Blender failed with exit code {proc.returncode}:\n{output[-3000:]}")

    results = json.loads(result_path.read_text(encoding="utf-8"))
    problems = failures(results, output)
    strokes = len(results["script_first"].get("value") or [])
    if problems:
        raise StepError("Freestyle probe failed:\n" + "\n".join(problems))
    log(f"Freestyle drew {strokes} strokes twice with the same colours, the parameter editor rendered")
    return 0


if __name__ == "__main__":
    main_wrapper(main)
