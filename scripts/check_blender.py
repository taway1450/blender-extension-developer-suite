# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""Type-check the Blender source code of a given version with ty.

Builds ty (see build_ty.py), makes sure the source worktree and bpy stubs exist (see
generate_stubs.py) and runs ty on all Python files of the worktree (excluding ``lib/``, ``extern/`` and the 2.7x
test scripts ``tests/python/CMakeLists.txt`` never runs), once per stub generator (``--generator``). The full output goes to
``.cache/ty-results/<version>.txt`` (fake-bpy-module stubs) and ``<version>-builtin.txt`` (Blender's own stubs).

The packages of Blender's bundled Python that its code imports (numpy, setuptools, requests, USD, ...) are on the
search path, through links in ``.cache/blender-site/<version>/`` (not the whole ``site-packages``: it would put a
runtime ``typing_extensions.py`` in front of typeshed's). Cycles' add-on source is linked there too, as ``cycles``,
so the checker reads what it registers (``scene.cycles``). The directories Blender's tools and tests add to
``sys.path`` themselves are on the search path as well. Modules nothing can resolve (compiled into Blender, given by GDB, or a developer tool's
own requirements) are allowed to be unresolved, so ``import-not-found`` reports only real gaps.

Each diagnostic is sorted into a cause, which has a group, and an area (see _buckets.py). The cause x area table,
the totals per group, errors and warnings, and the counts per rule and severity go to
``.cache/ty-results/<version>-<generator>-summary.txt``, samples per cause to ``...-buckets.txt``. For
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

# Paths (relative to the Blender source root) left out of the check: libraries; the dead 2.7x scripts (tests and the
# Cycles XML exporter, which still use `tessfaces` and `register_module`); and the gdb extension with the type hints of
# gdb's API it imports, written as `.py` modules with `pass` bodies rather than as stubs (every diagnostic there was
# about the hints, none about Blender).
EXCLUDED = [
    "lib/",
    "extern/",
    "tools/debug/gdb/",
    "tests/python/view_layer/",
    "tests/python/bl_mesh_modifiers.py",
    "tests/python/rna_array.py",
    "intern/cycles/app/io_export_cycles_xml.py",
]
# Rules check:blender does not report: the unused `# type: ignore` comments are all written for Blender's mypy check
# (`tools/check_source/check_mypy.py`), which has no bpy stubs, so they say nothing about Blender's typing.
IGNORED_RULES = ["unused-type-ignore-comment"]
# The platform ty checks for, whatever the host: ty takes the host's by default, so `os.getuid`, `fcntl` and
# `termios` were errors on Windows only and the recorded summaries depended on the machine. Linux, where Blender's
# tools and tests run most.
PYTHON_PLATFORM = "linux"
# Directories (relative to the Blender source root) that Blender puts on ``sys.path``.
# The generated stubs are searched before these.
BLENDER_SEARCH_PATHS = [
    "scripts/modules",
    "scripts/startup",
    "scripts/addons_core",
    "scripts/freestyle/modules",
]
# Directories (relative to the Blender source root) that Blender's own tools and tests put on ``sys.path`` before
# importing from them (``sys.path.append(os.path.join(PWD, "modules"))``).
SCRIPT_SEARCH_PATHS = [
    "tools/modules",
    "tools/utils_maintenance/modules",
    "scripts/addons_core/bl_pkg/tests/modules",
]
# Modules no search path can give ty: compiled into Blender (``aud``, ``_bpy_path``, ``_cycles``) or bundled compiled
# without stubs (``pxr``, ``PyOpenColorIO``), given by the program
# that runs the script (``gdb``), or third-party packages that only a developer tool needs, which Blender does not
# bundle. ty does not report them as unresolved; every other unresolved import is a real gap.
ALLOWED_UNRESOLVED_IMPORTS = [
    # Compiled into Blender, or bundled as compiled modules without stubs (linking these would make every member
    # they import from their extension module unknown to ty).
    "aud",
    "_bpy_path",
    "_cycles",
    "MaterialX.**",
    "OpenEXR",
    "openvdb",
    "oslquery",
    "pxr.**",
    "PyOpenColorIO",
    "pyopenvdb",
    # Given by the program that runs the script.
    "gdb.**",
    # CPython's private hash modules, which typeshed leaves out (`hashlib` falls back on them).
    "_md5",
    "_sha1",
    "_sha2",
    # Requirements of developer tools and the documentation build.
    "autopep8",
    "clang.**",
    "cython",
    "docformatter",
    "enchant",
    "iso8601",
    "matplotlib.**",
    "pygments.**",
    "retry",
    "scipy.**",
    "sphinx.**",
    "sphobjinv",
    "wheel.**",
    "yarl",
]

DIAGNOSTIC_RE = re.compile(r"^.+?:\d+:\d+: (?P<severity>\w+)\[(?P<rule>[\w-]+)\]", re.MULTILINE)

# Packages of Blender's bundled Python that its code imports and that ty can read (Python source, or a compiled
# module with stubs), put on the search path, each through a link in
# BLENDER_SITE_DIR/<version>/ (not the whole ``site-packages``, whose ``typing_extensions.py`` would shadow typeshed's).
BLENDER_SITE_PACKAGES = [
    "numpy",
    "setuptools",
    "requests",
    "urllib3",
    "certifi",
    "cattrs",
    "docutils",
    "zstandard",
    "OpenImageIO",
    "opentimelineio",
]
# The add-ons Blender enables by default whose source is not on BLENDER_SEARCH_PATHS, by the module name Blender
# imports them as, and their folder in the Blender source: the checker reads what they register (`scene.cycles`).
BLENDER_SOURCE_PACKAGES = {"cycles": "intern/cycles/blender/addon"}
BLENDER_SITE_DIR = CACHE_DIR / "blender-site"
# The recorded bucket summaries, per stub generator; only BASELINE_VERSION has one.
EXPECTED_DIR = REPO_ROOT / "tests" / "blender" / "expected"
BASELINE_VERSION = "main"


def blender_site(version: str, blender: Path | None, source: Path | None = None) -> Path | None:
    """``.cache/blender-site/<version>/`` with a link to each of BLENDER_SITE_PACKAGES in Blender's bundled
    ``site-packages`` and to each of BLENDER_SOURCE_PACKAGES in ``source`` (a junction on Windows), and no other
    link, or None when it would have no link."""
    install = blender or BLENDER_BIN_DIR / version
    if install.is_file():
        install = install.parent
    targets: dict[str, Path] = {}
    for package in BLENDER_SITE_PACKAGES:
        found = sorted(install.glob(f"*/python/lib/**/site-packages/{package}"))
        if found:
            targets[package] = found[0]
        else:
            log(f"Blender's bundled {package} not found under {install}; checking without it")
    for package, folder in BLENDER_SOURCE_PACKAGES.items():
        if source is not None and (source / folder).is_dir():
            targets[package] = source / folder
    site = BLENDER_SITE_DIR / version
    for stale in site.iterdir() if site.is_dir() else ():
        if stale.name not in targets:
            unlink(stale)
            log(f"Removed {stale}: no longer linked")
    for package, target in targets.items():
        link = site / package
        if link.exists() and link.resolve() == target.resolve():
            continue
        if os.path.lexists(link):  # stale: points elsewhere or nowhere
            unlink(link)
        site.mkdir(parents=True, exist_ok=True)
        link_directory(link, target)
        log(f"Linked {link} -> {target}")
    return site if targets else None


def link_directory(link: Path, target: Path) -> None:
    """Make ``link`` point to the directory ``target``: a junction on Windows, which needs no symlink privilege."""
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


def unlink(link: Path) -> None:
    """Remove a package link of BLENDER_SITE_DIR without touching its target."""
    if link.is_symlink():
        link.unlink()
    else:
        link.rmdir()  # a junction is removed like a directory, without touching its target


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
        "--python-platform",
        PYTHON_PLATFORM,
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
    for path in BLENDER_SEARCH_PATHS + SCRIPT_SEARCH_PATHS:
        cmd += ["--extra-search-path", source / path]
    allowed = ", ".join(f'"{module}"' for module in ALLOWED_UNRESOLVED_IMPORTS)
    cmd += ["--config", f"analysis.allowed-unresolved-imports = [{allowed}]"]
    for excluded in EXCLUDED:
        cmd += ["--exclude", excluded]
    for rule in IGNORED_RULES:
        cmd += ["--ignore", rule]
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
    """Sort the diagnostics in ``results`` into causes, write the summary and samples next to it and, for
    BASELINE_VERSION, compare the summary with the recorded one (or record it with ``update``)."""
    diagnostics = read_diagnostics(results.read_text(encoding="utf-8"), target.source)
    commit = git_output(target.source, "rev-parse", "--short=10", "HEAD")
    title = f"# check:blender {target.version}, {generator} stubs, Blender {commit}"
    text = summary(title, ((d.cause.name, d.area, d.rule, d.severity) for d in diagnostics))
    out_dir = CACHE_DIR / "ty-results"
    (out_dir / f"{target.version}-{generator}-summary.txt").write_text(text, encoding="utf-8")
    buckets = out_dir / f"{target.version}-{generator}-buckets.txt"
    buckets.write_text(samples(diagnostics), encoding="utf-8")
    print(text, flush=True)
    log(f"Samples per cause: {buckets}")

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
    site = blender_site(args.version, args.blender, target.source)
    for generator in target.stubs:
        results = run_ty(target, generator, site)
        report_buckets(target, generator, results, update=args.update)
    return 0


if __name__ == "__main__":
    main_wrapper(main)
