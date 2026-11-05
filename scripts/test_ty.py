"""Run ty-blender's own (upstream) Rust tests and mdtests, as a regression check for a change to the fork.

The Blender support has no tests of its own in the fork: the feature tests in this repo (check:features, check:ide)
test it. These tests show that a Blender change left upstream ty's behaviour alone. They build with the dev profile,
in the same incremental ``target/`` as the ty the check tasks build, and never update snapshots: a failing snapshot
is a regression to fix, not a result to record.

Usage:
  uv run scripts/test_ty.py                               # ty_python_semantic and ty_blender
  uv run scripts/test_ty.py --mdtest narrow/isinstance.md # one mdtest file (relative to resources/mdtest)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess

from _common import log, main_wrapper, run
from build_ty import RUFF_DIR, ensure_checkout

CRATES = ("ty_python_semantic", "ty_blender")


def has_nextest() -> bool:
    if shutil.which("cargo") is None:
        return False
    return subprocess.run(["cargo", "nextest", "--version"], capture_output=True).returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mdtest", help="Run only this mdtest file, relative to ty_python_semantic/resources/mdtest")
    args = parser.parse_args()
    ensure_checkout()

    nextest = has_nextest()
    cmd = ["cargo", "nextest", "run"] if nextest else ["cargo", "test"]
    if args.mdtest:
        path = args.mdtest.replace("\\", "/")
        cmd += ["-p", "ty_python_semantic", "--test", "mdtest", "--", f"mdtest::{path}" if nextest else path]
    else:
        for crate in CRATES:
            cmd += ["-p", crate]
        if nextest:
            cmd += ["--no-tests", "pass"]  # ty_blender has no tests yet
    env = {k: v for k, v in os.environ.items() if not k.startswith(("INSTA_", "MDTEST_UPDATE"))}
    log(f"Running ty-blender's upstream tests with {'nextest' if nextest else 'cargo test'} (dev profile)")
    run(cmd, cwd=RUFF_DIR, env=env)
    return 0


if __name__ == "__main__":
    main_wrapper(main)
