"""Shared paths and helpers for the scripts in this directory."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BLENDER_SUBMODULE = REPO_ROOT / "blender"
FAKE_BPY_MODULE = REPO_ROOT / "fake-bpy-module"
FAKE_BPY_SRC = FAKE_BPY_MODULE / "src"
TY_SUBMODULE = REPO_ROOT / "ty-blender"
EXAMPLE_ADDONS_DIR = REPO_ROOT / "examples" / "addons"
CATALOG_DIR = REPO_ROOT / "examples" / "catalog"  # the catalog's entries, one folder per topic
TYPECHECK_TESTS_DIR = REPO_ROOT / "tests" / "typecheck"
CACHE_DIR = REPO_ROOT / ".cache"

# Where the git LFS files of the Blender source are: upstream's server. The fork is on GitHub, whose mirror of Blender
# has no LFS objects, and no commit of the fork adds an LFS file, so upstream has every object a fork checkout needs.
BLENDER_LFS_URL = "https://projects.blender.org/blender/blender.git/info/lfs"
# Seconds to wait before each retry of `run_fetch`, space separated; unset or empty: no retry.
FETCH_RETRY_WAITS = "SUITE_FETCH_RETRY_WAITS"

COMPLETE_MARKER = ".complete"


class StepError(RuntimeError):
    pass


def log(message: str) -> None:
    print(f"==> {message}", flush=True)


def example_addons(names: list[str]) -> list[Path]:
    """The example add-ons (the packages in ``examples/addons/``), or only the named ones; none is not an error."""
    found = EXAMPLE_ADDONS_DIR.iterdir() if EXAMPLE_ADDONS_DIR.is_dir() else []
    available = sorted(p.name for p in found if (p / "__init__.py").is_file())
    unknown = set(names) - set(available)
    if unknown:
        raise StepError(f"Unknown addons {', '.join(sorted(unknown))} (available: {', '.join(available) or 'none'})")
    return [EXAMPLE_ADDONS_DIR / name for name in (names or available)]


def catalog_topics() -> list[str]:
    """The topic folders of ``examples/catalog/``."""
    found = CATALOG_DIR.iterdir() if CATALOG_DIR.is_dir() else []
    return sorted(p.name for p in found if p.is_dir() and not p.name.startswith((".", "_")))


def catalog_entries(names: list[str]) -> list[Path]:
    """The catalog's entries, or only those of the named topics (``properties``) and entries (``properties/<id>``,
    where ``<id>`` is the file stem with ``-`` for ``_``); none is not an error. An entry is a ``.py`` file or a
    package directory in a topic folder."""
    available = {}
    for topic in catalog_topics():
        for path in sorted((CATALOG_DIR / topic).iterdir()):
            if path.name.startswith((".", "_")):
                continue
            if path.suffix == ".py" or (path / "__init__.py").is_file():
                available[f"{topic}/{path.stem.replace('_', '-')}"] = path
    if not names:
        return list(available.values())
    selected: list[Path] = []
    for name in names:
        key = name.strip("/").replace("_", "-")
        matches = [path for entry, path in available.items() if key in (entry, entry.partition("/")[0])]
        if not matches:
            topics = ", ".join(catalog_topics()) or "none"
            raise StepError(f"Unknown catalog topic or entry {name!r} (topics: {topics})")
        selected += [path for path in matches if path not in selected]
    return selected


def run(cmd: list[str | Path], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    printable = " ".join(str(c) for c in cmd)
    print(f"    $ {printable}", flush=True)
    # Force UTF-8 I/O in Python subprocesses; Windows' legacy code pages can't encode the generated docs.
    env = {**(env or os.environ), "PYTHONUTF8": "1"}
    result = subprocess.run([str(c) for c in cmd], cwd=cwd, env=env)
    if result.returncode != 0:
        raise StepError(f"Command failed with exit code {result.returncode}: {printable}")


def fetch_retry_waits() -> list[float]:
    try:
        return [float(wait) for wait in os.environ.get(FETCH_RETRY_WAITS, "").split()]
    except ValueError as error:
        raise StepError(f"{FETCH_RETRY_WAITS} must be numbers of seconds separated by spaces: {error}") from None


def run_fetch(cmd: list[str | Path], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    """``run`` for a command that downloads from projects.blender.org, which refuses a client now and then (CI runners
    have got HTTP 403 for hours): after a failure, wait for each of the ``SUITE_FETCH_RETRY_WAITS`` seconds in turn and
    run it again. Without the variable a failure is final, so a wrong URL or a missing login fails at once."""
    waits = fetch_retry_waits()
    for attempt, wait in enumerate([*waits, None], start=1):
        try:
            run(cmd, cwd=cwd, env=env)
            return
        except StepError:
            if wait is None:
                raise
            log(f"Attempt {attempt} of {len(waits) + 1} failed; retrying in {wait:.0f} s")
            time.sleep(wait)


def blender_script_command(
    blender: Path,
    script: Path,
    *script_args: str | Path,
    options: tuple[str, ...] = (),
    factory_startup: bool = True,
) -> list[str]:
    """The command that runs the Python ``script`` with ``script_args`` (after ``--``) in background Blender, from
    factory settings (unless ``factory_startup`` is false) and without audio; Blender exits with code 1 when the
    script raises. ``options`` go to Blender before the script."""
    startup = ["--factory-startup"] if factory_startup else []
    args = [blender, "--background", *startup, *options, "-noaudio", "--python-exit-code", "1"]
    return [str(c) for c in [*args, "--python", script, "--", *script_args]]


def git_output(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def exe(name: str) -> str:
    return f"{name}.exe" if sys.platform == "win32" else name


def is_release(version: str) -> bool:
    """Whether ``version`` names an official release (X.Y) rather than a Blender build from source."""
    return re.fullmatch(r"\d+\.\d+", version) is not None


def validate_version(version: str) -> str:
    """A release version (X.Y) or the name of a Blender build from source (e.g. 'main')."""
    if not re.fullmatch(r"\w[\w.-]*", version):
        raise argparse.ArgumentTypeError(
            f"version must be X.Y or a build name (letters, digits, '.', '-', '_'), got {version!r}"
        )
    return version


def validate_release_version(version: str) -> str:
    if not is_release(version):
        raise argparse.ArgumentTypeError(f"version must be X.Y, got {version!r}")
    return version


def validate_build_name(name: str) -> str:
    if is_release(name):
        raise argparse.ArgumentTypeError(
            f"{name!r} looks like a release version, which is downloaded instead of built; pick another name"
        )
    return validate_version(name)


def main_wrapper(func) -> None:
    """Run ``func`` under the machine-wide resource limits (``_resources.guarded``) and turn a ``StepError`` into an
    error message and exit code 1."""
    from _resources import guarded

    try:
        with guarded():
            code = func()
    except StepError as error:
        print(f"error: {error}", file=sys.stderr)
        code = 1
    sys.exit(code or 0)
