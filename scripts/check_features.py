# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""Type-check the feature tests in ``tests/typecheck/`` with ty and compare with the recorded results.

Every folder in ``tests/typecheck/features/`` is a type-checker feature made of addons
(``features/<feature>/<addon>/`` and ``features/<feature>/generated/<addon>/``). Markers in the addons' files
(see ``tests/typecheck/README.md``):

- ``assert_type(expr, T)`` passes unless ty reports ``type-assertion-failure`` on its line;
- ``# ty: ignore[rule]`` (an expected error) passes unless ty reports ``unused-ignore-comment`` on its line,
  or ``ignore-comment-unknown-rule`` for a ``blender-*`` rule ty does not know yet;
- any other diagnostic is unexpected.

The results that are not passes go to ``tests/typecheck/expected/<generator>/<version>.txt`` (see ``_baseline.py``).
The task fails when they differ from that file, so both regressions and fixes show up; ``--update`` rewrites it
and the progress table ``<version>.progress.md``. A summary per
addon and the full ty output go to ``.cache/typecheck-results/<version>/<generator>/``.

Usage:
  uv run scripts/check_features.py main                       # all features, both stub generators
  uv run scripts/check_features.py 5.2 properties --generator fake-bpy-module
  uv run scripts/check_features.py main properties/props_hosts --update
"""

from __future__ import annotations

import argparse
import subprocess

from _baseline import compare, features_file, merge, read_lines, type_entries, write_lines, write_progress
from _common import CACHE_DIR, TYPECHECK_TESTS_DIR, StepError, log, main_wrapper
from _features import all_addons, evaluate, parse_diagnostics, print_table, select, summary_markdown
from build_ty import build_ty
from generate_stubs import (
    add_stubs_arguments,
    blender_python_version,
    ensure_worktree,
    generate_stubs,
    resolve_generators,
)

RESULTS_DIR = CACHE_DIR / "typecheck-results"


def header(generator: str, version: str) -> list[str]:
    return [
        f"Feature-test results that are not passes, {generator} stubs, Blender {version}.",
        f"`mise run check:features {version}` fails when they change; `--update` rewrites this file.",
        "Format: path | rule | source line (with #2, #3 ... when the same text occurs again in the file)",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_stubs_arguments(parser)
    parser.add_argument(
        "features",
        nargs="*",
        help="Features (`properties`) or addons (`properties/props_hosts`) in tests/typecheck/features/ (default: all)",
    )
    parser.add_argument("--debug", action="store_true", help="Use a debug build of ty")
    parser.add_argument("--update", action="store_true", help="Rewrite the expected results instead of comparing")
    args = parser.parse_args()

    addons = select(args.features)

    generators = resolve_generators(args.version, args.ref, args.generator)
    all_stubs = {
        g: generate_stubs(args.version, generator=g, ref=args.ref, blender=args.blender, force=args.force)
        for g in generators
    }
    python_version = blender_python_version(ensure_worktree(args.version, args.ref))
    ty = build_ty(args.debug)

    changed = False
    for generator, stubs in all_stubs.items():
        cmd = [
            ty,
            "check",
            "--project",
            TYPECHECK_TESTS_DIR,
            "--python-version",
            python_version,
            "--extra-search-path",
            stubs,
            "--output-format",
            "concise",
            "--no-progress",
            *(a.path for a in addons),
        ]
        log(f"Running ty (Python {python_version}, Blender {args.version}, {generator} stubs) on {len(addons)} addons")
        result = subprocess.run(
            [str(c) for c in cmd], cwd=TYPECHECK_TESTS_DIR, capture_output=True, text=True, encoding="utf-8"
        )
        if result.returncode not in (0, 1):
            raise StepError(f"ty failed with exit code {result.returncode}:\n{result.stderr}")

        results = evaluate(addons, parse_diagnostics(result.stdout))
        results_dir = RESULTS_DIR / args.version / generator
        results_dir.mkdir(parents=True, exist_ok=True)
        (results_dir / "ty.txt").write_text(result.stdout, encoding="utf-8")
        title = f"Feature tests: {generator} stubs, Blender {args.version}"
        (results_dir / "summary.md").write_text(summary_markdown(title, results), encoding="utf-8")
        print_table(results)
        log(f"Summary: {results_dir / 'summary.md'}")

        path = features_file(generator, args.version)
        shown = path.relative_to(TYPECHECK_TESTS_DIR.parent.parent)
        actual = dict.fromkeys(type_entries(results), "")
        recorded = read_lines(path)
        existing = all_addons()
        if args.update:
            write_lines(path, header(generator, args.version), merge(recorded, actual, addons, existing))
            log(f"Wrote {path} and {write_progress(generator, args.version)}")
            continue
        if not path.is_file():
            log(f"No recorded results in {path}; run with --update to record them")
            changed = True
            continue
        changes = compare(recorded, actual, addons, existing)
        if changes:
            changed = True
            log(
                f"Results changed against {shown} ({len(changes.new)} new, {len(changes.gone)} gone; --update records them):"
            )
            for line in changes.gone:
                print(f"    - {line}", flush=True)
            for line in changes.new:
                print(f"    + {line}", flush=True)
        else:
            log(f"Results match {shown}")
    return 1 if changed else 0


if __name__ == "__main__":
    main_wrapper(main)
