"""Shared paths and helpers for the scripts in this directory."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BLENDER_SUBMODULE = REPO_ROOT / "blender"
FAKE_BPY_MODULE = REPO_ROOT / "fake-bpy-module"
FAKE_BPY_SRC = FAKE_BPY_MODULE / "src"
TY_SUBMODULE = REPO_ROOT / "ty-blender"
EXAMPLE_ADDONS_DIR = REPO_ROOT / "examples" / "addons"
CACHE_DIR = REPO_ROOT / ".cache"

COMPLETE_MARKER = ".complete"


class StepError(RuntimeError):
    pass


def log(message: str) -> None:
    print(f"==> {message}", flush=True)


def run(cmd: list[str | Path], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    printable = " ".join(str(c) for c in cmd)
    print(f"    $ {printable}", flush=True)
    # Force UTF-8 I/O in Python subprocesses; Windows' legacy code pages can't encode the generated docs.
    env = {**(env or os.environ), "PYTHONUTF8": "1"}
    result = subprocess.run([str(c) for c in cmd], cwd=cwd, env=env)
    if result.returncode != 0:
        raise StepError(f"Command failed with exit code {result.returncode}: {printable}")


def git_output(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def exe(name: str) -> str:
    return f"{name}.exe" if sys.platform == "win32" else name


def validate_version(version: str) -> str:
    if version != "main" and not re.fullmatch(r"\d+\.\d+", version):
        raise argparse.ArgumentTypeError(f"version must be X.Y or 'main', got {version!r}")
    return version


def main_wrapper(func) -> None:
    """Run ``func`` and turn a ``StepError`` into an error message and exit code 1."""
    try:
        code = func()
    except StepError as error:
        print(f"error: {error}", file=sys.stderr)
        code = 1
    sys.exit(code or 0)
