# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""Type-check the example add-ons in ``examples/addons/`` with ty and compare with the recorded results.

The example add-ons are realistic add-ons that together demonstrate every feature (``examples/addons/README.md``).
ty runs on them once per stub generator (``--generator``). What it reports is judged as in the feature tests
(``_features.py``, ``tests/typecheck/README.md``):

- a diagnostic on the add-on's own code is a finding the example shows on purpose (or a regression);
- an ``assert_type`` marker in the add-on's ``check_<addon>.py`` states a type the code relies on, and fails with
  ``type-assertion-failure`` while the checker does not give it yet.

Everything that is not a pass goes to ``examples/expected/<generator>/<version>.txt`` (see ``_baseline.py``). The
task fails when the results differ from that file, so both a regression and a gap that closed show up;
``--update`` rewrites it. The full ty output and a summary per add-on go to
``.cache/typecheck-results/<version>/<generator>/examples-*``.

Usage:
  uv run scripts/check_addons.py main                  # all example add-ons
  uv run scripts/check_addons.py 5.2 scatter_tools     # only the named add-ons
  uv run scripts/check_addons.py main --update
"""

from __future__ import annotations

import argparse

from _baseline import EXAMPLES, EXAMPLES_EXPECTED_DIR, record, type_entries
from _common import EXAMPLE_ADDONS_DIR, log, main_wrapper
from _features import (
    evaluate,
    example_addon_list,
    parse_diagnostics,
    print_table,
    run_ty,
    summary_markdown,
)
from _target import Target, add_target_arguments


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_target_arguments(parser, binary="ty")
    parser.add_argument("addons", nargs="*", help=f"Addon directory names in {EXAMPLE_ADDONS_DIR} (default: all)")
    parser.add_argument("--update", action="store_true", help="Rewrite the expected results instead of comparing")
    args = parser.parse_args()

    addons = example_addon_list(args.addons)
    if not addons:
        log(f"No example add-ons in {EXAMPLE_ADDONS_DIR}")
        return 0
    existing = example_addon_list([])

    target = Target.from_args(args)
    python_version = target.python_version

    changed = False
    for generator, stubs in target.stubs.items():
        ty_cmd = [target.binary, "check", "--python-version", python_version, "--extra-search-path", stubs]
        ty_cmd += ["--output-format", "concise", "--no-progress", "--project", EXAMPLE_ADDONS_DIR]
        log(
            f"Running ty (Python {python_version}, Blender {args.version}, {generator} stubs) "
            f"on {', '.join(a.name for a in addons)}"
        )
        output = run_ty([*ty_cmd, *(a.path for a in addons)], EXAMPLE_ADDONS_DIR)

        results = evaluate(addons, parse_diagnostics(output, EXAMPLE_ADDONS_DIR))
        results_dir = target.results_dir(generator)
        (results_dir / "examples-ty.txt").write_text(output, encoding="utf-8")
        title = f"Example add-ons: {generator} stubs, Blender {args.version}"
        (results_dir / "examples-summary.md").write_text(summary_markdown(title, results), encoding="utf-8")
        print_table(results)
        log(f"Summary: {results_dir / 'examples-summary.md'}")

        changed |= record(
            EXAMPLES,
            generator,
            args.version,
            type_entries(results),
            addons,
            update=args.update,
            directory=EXAMPLES_EXPECTED_DIR,
            existing=existing,
        )
    return 1 if changed else 0


if __name__ == "__main__":
    main_wrapper(main)
