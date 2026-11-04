# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""Lint or format-check Blender code with the ruff built from the ``ty-blender`` submodule.

Builds ruff (see build_ruff.py) and runs it on one target, twice: with stock ruff settings (``--isolated``) and
with this repo's profile for the target (``config/ruff/<profile>.toml``). The formatter only checks
(``ruff format --check --diff``) and never writes files. The full output of each run goes to
``.cache/ruff-results/<tool>-<target>-<version>[-builtin]-{default,profile}.txt``, and the finding counts of
both runs are printed side by side.

Targets:
  blender   the Blender source worktree of the version, without lib/ and extern/ (profile: blender.toml)
  stubs     the generated bpy stubs, once per stub generator (profile: stubs.toml)
  addons    the example add-ons in examples/addons/ (profile: addons.toml); exits non-zero when the profile
            run has findings, like check:addons
  features  the feature-test add-ons in tests/typecheck/features/, without _expected/ (profile: features.toml)

The target Python version is the one of the Blender version. Only the stubs target needs the stubs.

Usage:
  uv run scripts/run_ruff.py lint blender 5.2
  uv run scripts/run_ruff.py format stubs 5.2 --generator builtin
  uv run scripts/run_ruff.py lint addons 5.2 simple_scatter
  uv run scripts/run_ruff.py format features 5.2 properties
"""

from __future__ import annotations

import argparse
import collections
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from _common import CACHE_DIR, EXAMPLE_ADDONS_DIR, REPO_ROOT, StepError, log, main_wrapper
from _features import EXPECTED_STUBS, FEATURES_DIR, select
from build_ruff import build_ruff
from check_blender import EXCLUDED_DIRS
from generate_stubs import (
    add_stubs_arguments,
    blender_python_version,
    ensure_worktree,
    generate_stubs,
    resolve_generators,
    results_name,
)

TOOLS = ("lint", "format")
TARGETS = ("blender", "stubs", "addons", "features")
PROFILES_DIR = REPO_ROOT / "config" / "ruff"
PROFILE_OF_TARGET = {"blender": "blender", "stubs": "stubs", "addons": "addons", "features": "features"}
CONFIGS = ("default", "profile")
RESULTS_DIR = CACHE_DIR / "ruff-results"
RUFF_CACHE = CACHE_DIR / "ruff-cache"

# ruff check --output-format concise: `path:line:col: CODE [*] message`, syntax errors as `invalid-syntax`.
LINT_RE = re.compile(r"^.+?:\d+:\d+: (?P<rule>[A-Z]+\d+|[a-z][\w-]*)\b", re.MULTILINE)
# ruff format --diff: one `--- a/path` / `+++ b/path` header pair per file it would change.
DIFF_FILE_RE = re.compile(r"^\+\+\+ (?:b/)?(?P<path>.+?)(?:\t.*)?$", re.MULTILINE)
FORMAT_ERROR_RE = re.compile(r"^error: .*$", re.MULTILINE)


@dataclass
class Run:
    config: str
    results: Path
    counts: collections.Counter[str]
    total: int


@dataclass
class Job:
    """One target to run ruff on: the paths, the directory ruff runs in and the result file stem."""

    label: str
    paths: list[Path]
    cwd: Path
    stem: str
    exclude: list[str]


def ruff_command(ruff: Path, tool: str, config: str, profile: str, python_version: str, job: Job) -> list[str | Path]:
    cmd: list[str | Path] = [ruff, "check" if tool == "lint" else "format"]
    cmd += ["--isolated"] if config == "default" else ["--config", PROFILES_DIR / f"{profile}.toml"]
    cmd += ["--target-version", f"py{python_version.replace('.', '')}", "--cache-dir", RUFF_CACHE]
    if tool == "lint":
        cmd += ["--no-fix", "--output-format", "concise"]
    else:
        cmd += ["--check", "--diff"]
    for pattern in job.exclude:
        cmd += ["--extend-exclude", pattern]
    return [*cmd, *job.paths]


def run_once(cmd: list[str | Path], tool: str, config: str, job: Job, results: Path) -> Run:
    results.parent.mkdir(parents=True, exist_ok=True)
    print(f"    $ {' '.join(str(c) for c in cmd)}", flush=True)
    start = time.monotonic()
    result = subprocess.run(
        [str(c) for c in cmd], cwd=job.cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    elapsed = time.monotonic() - start
    results.write_text(result.stdout + result.stderr, encoding="utf-8")

    if tool == "lint":
        # ruff check exits with 1 when it reports findings, 2 when ruff itself fails.
        if result.returncode not in (0, 1):
            sys.stderr.write(result.stderr[-5000:])
            raise StepError(f"ruff check failed with exit code {result.returncode} (full output in {results})")
        counts = collections.Counter(m["rule"] for m in LINT_RE.finditer(result.stdout))
        total = sum(counts.values())
        log(f"ruff check ({config}) finished in {elapsed:.1f}s: {total} findings")
    else:
        # ruff format --check exits with 1 when it would change files and with 2 on errors, which include
        # files it cannot parse; those are counted, not fatal, unless nothing was checked at all.
        files = {m["path"] for m in DIFF_FILE_RE.finditer(result.stdout)}
        errors = FORMAT_ERROR_RE.findall(result.stderr)
        if result.returncode not in (0, 1) and not (errors and (files or "formatted" in result.stderr)):
            sys.stderr.write(result.stderr[-5000:])
            raise StepError(f"ruff format failed with exit code {result.returncode} (full output in {results})")
        counts = collections.Counter({"would reformat": len(files)} if files else {})
        if errors:
            counts["error"] = len(errors)
        total = len(files)
        log(
            f"ruff format ({config}) finished in {elapsed:.1f}s: {len(files)} files would be reformatted"
            f"{f', {len(errors)} errors' if errors else ''}"
        )
    return Run(config, results, counts, total)


def print_side_by_side(runs: list[Run]) -> None:
    rules = sorted(
        {rule for run in runs for rule in run.counts}, key=lambda rule: (-max(run.counts[rule] for run in runs), rule)
    )
    if not rules:
        return
    width = max(len(rule) for rule in [*rules, "total"])
    print(f"    {'':<{width}}  {'default':>8}  {'profile':>8}", flush=True)
    for rule in rules:
        print(f"    {rule:<{width}}  {runs[0].counts[rule]:>8}  {runs[1].counts[rule]:>8}")
    print(f"    {'total':<{width}}  {runs[0].total:>8}  {runs[1].total:>8}")


def run_job(ruff: Path, tool: str, profile: str, python_version: str, job: Job) -> list[Run]:
    log(f"Running ruff {'check' if tool == 'lint' else 'format --check'} (Python {python_version}) on {job.label}")
    runs = []
    for config in CONFIGS:
        results = RESULTS_DIR / f"{job.stem}-{config}.txt"
        runs.append(
            run_once(ruff_command(ruff, tool, config, profile, python_version, job), tool, config, job, results)
        )
    print_side_by_side(runs)
    log(f"Full output: {', '.join(str(run.results) for run in runs)}")
    return runs


def jobs_for(tool: str, args: argparse.Namespace) -> list[Job]:
    stem = f"{tool}-{args.target}"
    if args.target == "blender":
        source = ensure_worktree(args.version, args.ref, force=args.force)
        return [
            Job(
                f"the Blender {args.version} source {source}",
                [source],
                source,
                f"{stem}-{args.version}",
                [f"{(source / d).as_posix()}/" for d in EXCLUDED_DIRS],
            )
        ]
    if args.target == "stubs":
        generators = resolve_generators(args.version, args.ref, args.generator)
        jobs = []
        for generator in generators:
            stubs = generate_stubs(
                args.version, generator=generator, ref=args.ref, blender=args.blender, force=args.force
            )
            jobs.append(
                Job(
                    f"the {generator} bpy stubs {stubs}",
                    [stubs],
                    stubs,
                    results_name(f"{stem}-{args.version}", generator).removesuffix(".txt"),
                    [],
                )
            )
        return jobs
    if args.target == "addons":
        available = sorted(p.name for p in EXAMPLE_ADDONS_DIR.iterdir() if (p / "__init__.py").is_file())
        unknown = set(args.names) - set(available)
        if unknown:
            raise StepError(f"Unknown addons {', '.join(sorted(unknown))} (available: {', '.join(available)})")
        names = args.names or available
        return [
            Job(
                f"the example addons {', '.join(names)}",
                [EXAMPLE_ADDONS_DIR / n for n in names],
                EXAMPLE_ADDONS_DIR,
                f"{stem}-{args.version}",
                [],
            )
        ]
    addons = select(args.names)
    return [
        Job(
            f"{len(addons)} feature-test addons",
            [a.path for a in addons],
            FEATURES_DIR.parent,
            f"{stem}-{args.version}",
            [EXPECTED_STUBS],
        )
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("tool", choices=TOOLS, help="lint (ruff check) or format (ruff format --check --diff)")
    parser.add_argument("target", choices=TARGETS, help="What to run ruff on")
    add_stubs_arguments(parser)
    parser.add_argument(
        "names",
        nargs="*",
        help="addons: addon directory names in examples/addons/; features: features or "
        "feature/addon in tests/typecheck/features/ (default: all)",
    )
    parser.add_argument("--debug", action="store_true", help="Use a debug build of ruff")
    args = parser.parse_args()
    if args.names and args.target not in ("addons", "features"):
        parser.error(f"the {args.target} target takes no names")

    jobs = jobs_for(args.tool, args)
    python_version = blender_python_version(ensure_worktree(args.version, args.ref))
    ruff = build_ruff(args.debug)
    profile = PROFILE_OF_TARGET[args.target]

    code = 0
    for job in jobs:
        runs = run_job(ruff, args.tool, profile, python_version, job)
        if args.target == "addons" and runs[1].total:
            code = 1
    return code


if __name__ == "__main__":
    main_wrapper(main)
