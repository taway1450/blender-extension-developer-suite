# /// script
# requires-python = ">=3.12"
# ///
"""Run glTF's import, export and round-trip tests and generate Rigify rigs in background Blender (#137).

- **glTF:** runs Blender's own ``tests/python/io_gltf_{import,export,roundtrip}_test.py`` from the source worktree
  ``.cache/blender-src/<version>`` against its ``tests/files/io_tests/gltf/{import,export,roundtrip}``, as
  ``tests/python/CMakeLists.txt`` registers them. A test fails when Blender exits non-zero (unittest's exit code).
- **Rigify:** runs ``scripts/blender/probe_rigify.py``, which generates a rig with ``bpy.ops.pose.rigify_generate()``
  from every metarig and every rig type's sample. A case fails when it raises or generates no rig.

Each run's output goes to ``.cache/gltf-rigify-probe/<version>/<name>.log``, the glTF reports to ``gltf-<test>/``
and the Rigify results to ``rigify.json``.

Usage:
  uv run scripts/probe_gltf_rigify.py main
  uv run scripts/probe_gltf_rigify.py main --only rigify
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from _common import CACHE_DIR, REPO_ROOT, StepError, log, main_wrapper, validate_version
from generate_stubs import find_blender, worktree_path

RIGIFY_PROBE = REPO_ROOT / "scripts" / "blender" / "probe_rigify.py"
GLTF_TESTS = ("import", "export", "roundtrip")
BLENDER_ARGS = ["--background", "--factory-startup", "-noaudio", "--python-exit-code", "1"]


def run_blender(blender: Path, args: list[str | Path], log_path: Path) -> int:
    proc = subprocess.run([str(c) for c in [blender, *BLENDER_ARGS, *args]], capture_output=True, text=True)
    log_path.write_text(proc.stdout + proc.stderr, encoding="utf-8")
    return proc.returncode


def gltf_failures(blender: Path, source: Path, out: Path) -> list[str]:
    problems = []
    for test in GLTF_TESTS:
        script = source / "tests" / "python" / f"io_gltf_{test}_test.py"
        testdir = source / "tests" / "files" / "io_tests" / "gltf" / test
        if not script.is_file() or not testdir.is_dir():
            raise StepError(f"{script} or {testdir} is missing")
        args = ["--python", script, "--", "--testdir", testdir, "--outdir", out / f"gltf-{test}"]
        code = run_blender(blender, args, out / f"gltf-{test}.log")
        log(f"glTF {test}: {'passed' if code == 0 else f'FAILED (exit code {code})'}")
        if code:
            problems.append(f"glTF {test} test failed (see {out / f'gltf-{test}.log'})")
    return problems


def rigify_failures(blender: Path, out: Path) -> list[str]:
    result_path = out / "rigify.json"
    result_path.unlink(missing_ok=True)
    code = run_blender(blender, ["--python", RIGIFY_PROBE, "--", result_path], out / "rigify.log")
    if code or not result_path.exists():
        return [f"Rigify probe failed with exit code {code} (see {out / 'rigify.log'})"]
    results = json.loads(result_path.read_text(encoding="utf-8"))
    passed = [name for name, r in results.items() if r["ok"]]
    log(f"Rigify: {len(passed)} of {len(results)} rigs generated")
    return [f"Rigify {name} failed:\n{r['error']}" for name, r in results.items() if not r["ok"]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("version", type=validate_version, help="Blender version (X.Y) or build name (e.g. main)")
    parser.add_argument("--blender", type=Path, help="Blender binary (or its directory) to use")
    parser.add_argument("--only", choices=["gltf", "rigify"], help="Run only the glTF tests or only Rigify")
    args = parser.parse_args()

    blender = find_blender(args.version, args.blender)
    out = CACHE_DIR / "gltf-rigify-probe" / args.version
    out.mkdir(parents=True, exist_ok=True)
    problems = []
    if args.only in (None, "gltf"):
        problems += gltf_failures(blender, worktree_path(args.version), out)
    if args.only in (None, "rigify"):
        problems += rigify_failures(blender, out)
    if problems:
        raise StepError("glTF / Rigify probe failed:\n" + "\n".join(problems))
    log("glTF tests passed and every Rigify rig generated")
    return 0


if __name__ == "__main__":
    main_wrapper(main)
