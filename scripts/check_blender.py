# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""Type-check the Blender source code of a given version with ty.

Builds ty (see build_ty.py), makes sure the source worktree and bpy stubs exist (see
generate_stubs.py) and runs ty on all Python files of the worktree (excluding ``lib/`` and
``extern/``), once per stub generator (``--generator``). The full output goes to
``.cache/ty-results/<version>.txt`` (fake-bpy-module stubs) and ``<version>-builtin.txt`` (Blender's own stubs).

Blender's bundled numpy is on the search path, through a link in ``.cache/blender-site/<version>/`` (only numpy:
the whole ``site-packages`` would put a runtime ``typing_extensions.py`` in front of typeshed's).

Each diagnostic is sorted into a bucket and an area (see _buckets.py). The bucket x area table and the counts per
rule go to ``.cache/ty-results/<version>-<generator>-summary.txt``, samples per bucket to ``...-buckets.txt``. For
``main`` the summary is compared with ``tests/blender/expected/<generator>/main-summary.txt``: a difference is
printed (the task still succeeds), and ``--update`` records the new summary.

Usage:
  uv run scripts/check_blender.py 5.2
  uv run scripts/check_blender.py 5.2 --profile profiling
  uv run scripts/check_blender.py main --blender "C:/path/to/blender-5.4/blender.exe"
  uv run scripts/check_blender.py main --update
"""

from __future__ import annotations

import argparse
import collections
import difflib
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from _buckets import read_diagnostics, samples, summary
from _common import CACHE_DIR, REPO_ROOT, StepError, git_output, log, main_wrapper
from _target import Target, add_target_arguments
from download_blender import BLENDER_BIN_DIR
from generate_stubs import results_name

EXCLUDED_DIRS = ["lib", "extern"]
# Directories (relative to the Blender source root) that Blender puts on ``sys.path``.
# The generated stubs are searched before these.
BLENDER_SEARCH_PATHS = [
    "scripts/modules",
    "scripts/startup",
    "scripts/addons_core",
    "scripts/freestyle/modules",
]

DIAGNOSTIC_RE = re.compile(r"^.+?:\d+:\d+: (?P<severity>\w+)\[(?P<rule>[\w-]+)\]", re.MULTILINE)

# Packages of Blender's bundled Python put on the search path, each through a link in BLENDER_SITE_DIR/<version>/.
BLENDER_SITE_PACKAGES = ["numpy"]
BLENDER_SITE_DIR = CACHE_DIR / "blender-site"
# The recorded bucket summaries, per stub generator; only BASELINE_VERSION has one.
EXPECTED_DIR = REPO_ROOT / "tests" / "blender" / "expected"
BASELINE_VERSION = "main"


def blender_site(version: str, blender: Path | None) -> Path | None:
    """``.cache/blender-site/<version>/`` with a link to each of BLENDER_SITE_PACKAGES in Blender's bundled
    ``site-packages`` (a junction on Windows), or None when that Blender has none of them."""
    install = blender or BLENDER_BIN_DIR / version
    if install.is_file():
        install = install.parent
    site = BLENDER_SITE_DIR / version
    linked = False
    for package in BLENDER_SITE_PACKAGES:
        found = sorted(install.glob(f"*/python/lib/**/site-packages/{package}"))
        if not found:
            log(f"Blender's bundled {package} not found under {install}; checking without it")
            continue
        linked = True
        link = site / package
        if link.exists() and link.resolve() == found[0].resolve():
            continue
        if os.path.lexists(link):  # stale: points elsewhere or nowhere
            if link.is_symlink():
                link.unlink()
            else:
                link.rmdir()  # a junction is removed like a directory, without touching its target
        site.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            import _winapi

            _winapi.CreateJunction(str(found[0]), str(link))
        else:
            link.symlink_to(found[0], target_is_directory=True)
        log(f"Linked {link} -> {found[0]}")
    return site if linked else None


def run_ty(target: Target, generator: str, site: Path | None) -> Path:
    assert target.binary is not None
    source, stubs, python_version = target.source, target.stubs[generator], target.python_version
    results = CACHE_DIR / "ty-results" / results_name(target.version, generator)

    cmd: list[str | Path] = [
        target.binary,
        "check",
        "--project",
        source,
        "--python-version",
        python_version,
        "--output-format",
        "concise",
        "--no-progress",
        "--color",
        "never",
        "--extra-search-path",
        stubs,
    ]
    if site is not None:
        cmd += ["--extra-search-path", site]
    for path in BLENDER_SEARCH_PATHS:
        cmd += ["--extra-search-path", source / path]
    for excluded in EXCLUDED_DIRS:
        cmd += ["--exclude", f"{excluded}/"]
    cmd.append(source)

    log(f"Running ty (Python {python_version}, {generator} stubs) on {source}")
    return run_ty_with_summary(cmd, source, results)


def run_ty_with_summary(cmd: list[str | Path], cwd: Path, results: Path) -> Path:
    """Run a ``ty check`` command, write its output to ``results`` and print diagnostic counts per rule."""
    results.parent.mkdir(parents=True, exist_ok=True)
    print(f"    $ {' '.join(str(c) for c in cmd)}", flush=True)
    start = time.monotonic()
    result = subprocess.run(
        [str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    elapsed = time.monotonic() - start
    results.write_text(result.stdout + result.stderr, encoding="utf-8")

    # ty exits with 1 when it reports diagnostics; anything else non-zero is a failure of ty itself.
    if result.returncode not in (0, 1):
        sys.stderr.write(result.stderr[-5000:])
        raise StepError(f"ty failed with exit code {result.returncode} (full output in {results})")

    counts = collections.Counter((m["severity"], m["rule"]) for m in DIAGNOSTIC_RE.finditer(result.stdout))
    by_severity = collections.Counter()
    for (severity, _), count in counts.items():
        by_severity[severity] += count

    log(
        f"ty finished in {elapsed:.1f}s: {sum(counts.values())} diagnostics "
        f"({', '.join(f'{n} {s}' for s, n in by_severity.most_common()) or 'none'})"
    )
    if counts:
        width = max(len(rule) for _, rule in counts)
        for (severity, rule), count in counts.most_common():
            print(f"    {count:>7}  {rule:<{width}}  ({severity})")
    log(f"Full output: {results}")
    return results


def report_buckets(target: Target, generator: str, results: Path, *, update: bool) -> None:
    """Sort the diagnostics in ``results`` into buckets, write the summary and samples next to it and, for
    BASELINE_VERSION, compare the summary with the recorded one (or record it with ``update``)."""
    diagnostics = read_diagnostics(results.read_text(encoding="utf-8"), target.source)
    commit = git_output(target.source, "rev-parse", "--short=10", "HEAD")
    title = f"# check:blender {target.version}, {generator} stubs, Blender {commit}"
    text = summary(title, ((d.bucket, d.area, d.rule) for d in diagnostics))
    out_dir = CACHE_DIR / "ty-results"
    (out_dir / f"{target.version}-{generator}-summary.txt").write_text(text, encoding="utf-8")
    buckets = out_dir / f"{target.version}-{generator}-buckets.txt"
    buckets.write_text(samples(diagnostics), encoding="utf-8")
    print(text, flush=True)
    log(f"Samples per bucket: {buckets}")

    if target.version != BASELINE_VERSION:
        return
    expected = EXPECTED_DIR / generator / f"{BASELINE_VERSION}-summary.txt"
    shown = expected.relative_to(REPO_ROOT).as_posix()
    recorded = expected.read_text(encoding="utf-8") if expected.exists() else None
    if update:
        expected.parent.mkdir(parents=True, exist_ok=True)
        expected.write_text(text, encoding="utf-8")
        log(f"Recorded the bucket summary in {shown}")
    elif recorded is None:
        log(f"No recorded bucket summary in {shown}; run with --update to record it")
    elif recorded != text:
        log(f"The bucket summary differs from {shown} (`--update` records it):")
        diff = difflib.unified_diff(recorded.splitlines(True), text.splitlines(True), shown, "this run")
        sys.stdout.writelines(diff)
    else:
        log(f"The bucket summary matches {shown}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_target_arguments(parser, binary="ty")
    parser.add_argument(
        "--update",
        action="store_true",
        help=f"Record the bucket summary ({BASELINE_VERSION} only) instead of comparing",
    )
    args = parser.parse_args()

    target = Target.from_args(args)
    site = blender_site(args.version, args.blender)
    for generator in target.stubs:
        results = run_ty(target, generator, site)
        report_buckets(target, generator, results, update=args.update)
    return 0


if __name__ == "__main__":
    main_wrapper(main)
