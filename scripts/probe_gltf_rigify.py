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

from pathlib import Path

from _common import REPO_ROOT, StepError, log, main_wrapper
from _probe import failed_checks, probe_dir, probe_parser, run_blender, run_probe
from generate_stubs import find_blender, worktree_path

RIGIFY_PROBE = REPO_ROOT / "scripts" / "blender" / "probe_rigify.py"
GLTF_TESTS = ("import", "export", "roundtrip")


def gltf_failures(blender: Path, source: Path, out: Path) -> list[str]:
    problems = []
    for test in GLTF_TESTS:
        script = source / "tests" / "python" / f"io_gltf_{test}_test.py"
        testdir = source / "tests" / "files" / "io_tests" / "gltf" / test
        if not script.is_file() or not testdir.is_dir():
            raise StepError(f"{script} or {testdir} is missing")
        args = ["--testdir", testdir, "--outdir", out / f"gltf-{test}"]
        code, _ = run_blender(blender, script, *args, log_path=out / f"gltf-{test}.log")
        log(f"glTF {test}: {'passed' if code == 0 else f'FAILED (exit code {code})'}")
        if code:
            problems.append(f"glTF {test} test failed (see {out / f'gltf-{test}.log'})")
    return problems


def rigify_failures(blender: Path, out: Path) -> list[str]:
    try:
        results, _ = run_probe(blender, RIGIFY_PROBE, out / "rigify.json", log_path=out / "rigify.log")
    except StepError as error:
        return [f"Rigify probe: {error}"]
    passed = [name for name, r in results.items() if r["ok"]]
    log(f"Rigify: {len(passed)} of {len(results)} rigs generated")
    return failed_checks(results, prefix="Rigify ")


def main() -> int:
    parser = probe_parser(__doc__)
    parser.add_argument("--only", choices=["gltf", "rigify"], help="Run only the glTF tests or only Rigify")
    args = parser.parse_args()

    blender = find_blender(args.version, args.blender)
    out = probe_dir("gltf-rigify-probe", args.version)
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
