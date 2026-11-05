# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""Type-check the example addons in ``examples/addons/`` with ty against the bpy stubs.

Builds ty (see build_ty.py) and makes sure the bpy stubs for the Blender version exist (see
generate_stubs.py), then runs ty once per stub generator (``--generator``). Exits with a non-zero
code if ty reports any diagnostics.

Usage:
  uv run scripts/check_addons.py 5.2                  # all example addons
  uv run scripts/check_addons.py 5.2 hello_cube       # only the named addons
  uv run scripts/check_addons.py 5.2 --debug
"""

from __future__ import annotations

import argparse
import subprocess

from _common import EXAMPLE_ADDONS_DIR, StepError, log, main_wrapper
from _target import Target, add_target_arguments


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_target_arguments(parser, binary="ty")
    parser.add_argument("addons", nargs="*", help=f"Addon directory names in {EXAMPLE_ADDONS_DIR} (default: all)")
    args = parser.parse_args()

    available = sorted(p.name for p in EXAMPLE_ADDONS_DIR.iterdir() if (p / "__init__.py").is_file())
    unknown = set(args.addons) - set(available)
    if unknown:
        raise StepError(f"Unknown addons {', '.join(sorted(unknown))} (available: {', '.join(available)})")
    addons = [EXAMPLE_ADDONS_DIR / name for name in (args.addons or available)]

    target = Target.from_args(args)
    python_version = target.python_version

    code = 0
    for generator, stubs in target.stubs.items():
        cmd = [
            target.binary,
            "check",
            "--project",
            EXAMPLE_ADDONS_DIR,
            "--python-version",
            python_version,
            "--extra-search-path",
            stubs,
            *addons,
        ]
        log(
            f"Running ty (Python {python_version}, Blender {args.version}, {generator} stubs) "
            f"on {', '.join(a.name for a in addons)}"
        )
        print(f"    $ {' '.join(str(c) for c in cmd)}", flush=True)
        result = subprocess.run([str(c) for c in cmd], cwd=EXAMPLE_ADDONS_DIR)
        if result.returncode not in (0, 1):
            raise StepError(f"ty failed with exit code {result.returncode}")
        code = max(code, result.returncode)
    return code


if __name__ == "__main__":
    main_wrapper(main)
