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
- any other diagnostic is unexpected, and fails the marker on its line too (``MarkerResult.passed``).

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

from _baseline import FEATURES, record, type_entries
from _common import TYPECHECK_TESTS_DIR, StepError, log, main_wrapper
from _features import evaluate, parse_diagnostics, print_table, select, summary_markdown
from _target import Target, add_target_arguments


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_target_arguments(parser, binary="ty")
    parser.add_argument(
        "features",
        nargs="*",
        help="Features (`properties`) or addons (`properties/props_hosts`) in tests/typecheck/features/ (default: all)",
    )
    parser.add_argument("--update", action="store_true", help="Rewrite the expected results instead of comparing")
    args = parser.parse_args()

    addons = select(args.features)
    target = Target.from_args(args)
    python_version = target.python_version

    changed = False
    for generator, stubs in target.stubs.items():
        cmd = [
            target.binary,
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
        results_dir = target.results_dir(generator)
        (results_dir / "ty.txt").write_text(result.stdout, encoding="utf-8")
        title = f"Feature tests: {generator} stubs, Blender {args.version}"
        (results_dir / "summary.md").write_text(summary_markdown(title, results), encoding="utf-8")
        print_table(results)
        log(f"Summary: {results_dir / 'summary.md'}")

        changed |= record(FEATURES, generator, args.version, type_entries(results), addons, update=args.update)
    return 1 if changed else 0


if __name__ == "__main__":
    main_wrapper(main)
