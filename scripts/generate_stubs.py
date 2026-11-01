# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""Generate bpy stubs for a Blender version with the ``fake-bpy-module`` submodule.

Steps:
  1. Create a git worktree of the ``blender`` submodule for the requested version
     (``sphinx_doc_gen.py`` and the bgl sources are taken from it).
  2. Download the matching official Blender binary into ``.cache/blender-bin/`` unless it is
     already there (or ``--blender`` is passed).
  3. Run Blender to generate the rst API docs and fake-bpy-module's mod files, then run
     fake-bpy-module's ``gen.py`` to turn them into stubs in ``.cache/bpy-stubs/<version>``.

Usage:
  uv run scripts/generate_stubs.py 5.2
  uv run scripts/generate_stubs.py main --blender "C:/path/to/blender-5.4/blender.exe"

Everything is cached under ``.cache/``; pass ``--force`` to regenerate the worktree and stubs.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path

from _common import (
    BLENDER_SUBMODULE,
    CACHE_DIR,
    COMPLETE_MARKER,
    FAKE_BPY_SRC,
    StepError,
    exe,
    git_output,
    log,
    main_wrapper,
    run,
    validate_version,
)
from download_blender import download_blender

STUBS_DIR = CACHE_DIR / "bpy-stubs"


def resolve_git_ref(version: str, ref_override: str | None) -> str:
    if ref_override:
        return ref_override
    if version == "main":
        return "main"
    return f"blender-v{version}-release"


def ensure_worktree(version: str, ref: str | None = None, force: bool = False) -> Path:
    """Return a git worktree of the Blender source for ``version``, creating it if needed."""
    ref = resolve_git_ref(version, ref)
    worktree = CACHE_DIR / "blender-src" / version
    if worktree.exists() and not force:
        log(f"Reusing Blender source worktree {worktree} ({git_output(worktree, 'rev-parse', '--short', 'HEAD')})")
        return worktree

    if worktree.exists():
        log(f"Removing existing worktree {worktree}")
        run(["git", "-C", BLENDER_SUBMODULE, "worktree", "remove", "--force", worktree])
    run(["git", "-C", BLENDER_SUBMODULE, "worktree", "prune"])

    # Prefer the remote-tracking branch, fall back to whatever the ref names (tag, commit, ...).
    candidates = [f"origin/{ref}", ref]
    commit = None
    for _ in range(2):
        for candidate in candidates:
            check = subprocess.run(
                ["git", "-C", str(BLENDER_SUBMODULE), "rev-parse", "--verify", "-q", f"{candidate}^{{commit}}"],
                capture_output=True, text=True,
            )
            if check.returncode == 0:
                commit = check.stdout.strip()
                break
        if commit:
            break
        log(f"Ref {ref!r} not found locally, fetching it from origin")
        run(["git", "-C", BLENDER_SUBMODULE, "fetch", "origin", ref])
        candidates.append("FETCH_HEAD")
    if not commit:
        raise StepError(f"Could not resolve Blender git ref {ref!r}")

    log(f"Creating Blender source worktree for {ref} ({commit[:10]}) at {worktree}")
    worktree.parent.mkdir(parents=True, exist_ok=True)
    # Blender stores test data and some assets in git LFS; we only need the Python sources.
    env = {**os.environ, "GIT_LFS_SKIP_SMUDGE": "1"}
    run(["git", "-C", BLENDER_SUBMODULE, "worktree", "add", "--detach", worktree, commit], env=env)
    return worktree


def blender_python_version(source: Path) -> str:
    versions_cmake = source / "build_files" / "build_environment" / "cmake" / "versions.cmake"
    match = re.search(r"set\(PYTHON_SHORT_VERSION (\d+\.\d+)\)", versions_cmake.read_text(encoding="utf-8"))
    if not match:
        raise StepError(f"Could not find PYTHON_SHORT_VERSION in {versions_cmake}")
    return match.group(1)


def blender_binary_version(blender: Path) -> str:
    output = subprocess.run([str(blender), "--version"], capture_output=True, text=True).stdout
    match = re.search(r"^Blender (\d+\.\d+)", output, re.MULTILINE)
    if not match:
        raise StepError(f"Could not determine the version of {blender}:\n{output}")
    return match.group(1)


def find_blender(version: str, explicit: Path | None) -> Path:
    if explicit:
        blender = explicit
        if blender.is_dir():
            blender = blender / exe("blender")
        if not blender.is_file():
            raise StepError(f"Blender binary {blender} does not exist")
    elif version == "main":
        raise StepError("Version 'main' requires an explicit --blender path to a matching Blender build")
    else:
        blender = download_blender(version)

    actual = blender_binary_version(blender)
    if version != "main" and actual != version:
        raise StepError(f"{blender} is Blender {actual}, but stubs for Blender {version} were requested")
    log(f"Using Blender {actual} binary {blender}")
    return blender


def run_blender_script(blender: Path, script: Path, *script_args: str | Path) -> None:
    run([blender, "--background", "--factory-startup", "-noaudio", "--python-exit-code", "1",
         "--python", script, "--", *script_args])


def uv_python_cmd() -> list[str | Path]:
    """Python with fake-bpy-module's requirements installed (in an ephemeral uv environment)."""
    return ["uv", "run", "--no-project", "--python", ">=3.11",
            "--with-requirements", FAKE_BPY_SRC / "requirements.txt", "python"]


def generate_stubs(version: str, *, ref: str | None = None, blender: Path | None = None,
                   force: bool = False) -> Path:
    """Return the bpy stubs directory for ``version``, generating the stubs if needed."""
    stubs_dir = STUBS_DIR / version
    if (stubs_dir / COMPLETE_MARKER).exists() and not force:
        log(f"Reusing bpy stubs {stubs_dir}")
        return stubs_dir

    blender = find_blender(version, blender)
    source = ensure_worktree(version, ref, force)

    shutil.rmtree(stubs_dir, ignore_errors=True)
    # The rst output is kept until the stubs are complete, so a failed generation can be retried quickly.
    tmp_dir = CACHE_DIR / "bpy-stubs-tmp" / version
    rst_complete = tmp_dir / COMPLETE_MARKER
    if rst_complete.exists() and not force:
        log(f"Reusing rst documentation {tmp_dir / 'sphinx-in'}")
    else:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir.mkdir(parents=True)
        log("Generating rst documentation with Blender (sphinx_doc_gen.py)")
        run_blender_script(blender, source / "doc" / "python_api" / "sphinx_doc_gen.py", "--output", tmp_dir)
        rst_complete.touch()

    # gen.py always reads generated mod files from this fixed location inside the submodule (gitignored).
    generated_mods = FAKE_BPY_SRC / "mods" / "generated_mods"
    shutil.rmtree(generated_mods, ignore_errors=True)
    generated_mods.mkdir(parents=True)
    gen_modfile = FAKE_BPY_SRC / "gen_modfile"
    try:
        log("Generating fake-bpy-module mod files")
        run_blender_script(blender, gen_modfile / "gen_external_modules_modfile.py",
                           "-m", "addon_utils", "-o", generated_mods / "gen_modules_modfile", "-f", "rst")
        run_blender_script(blender, gen_modfile / "gen_external_modules_modfile.py",
                           "-m", "keyingsets_builtins", "-a", "-o", generated_mods / "gen_startup_modfile", "-f", "rst")
        run_blender_script(blender, gen_modfile / "gen_node_inputs_outputs_for_node_class.py",
                           "-o", generated_mods / "gen_node_inputs_outputs_for_node_class", "-f", "rst")
        bgl_source = next((p for p in (source / "source/blender/python/generic/bgl.cc",
                                       source / "source/blender/python/generic/bgl.c") if p.exists()), None)
        if bgl_source:
            (generated_mods / "gen_bgl_modfile").mkdir()
            run(uv_python_cmd() + [gen_modfile / "gen_bgl_modfile.py", "-i", bgl_source,
                                   "-o", generated_mods / "gen_bgl_modfile" / "bgl.mod.rst", "-f", "rst"])

        log("Generating bpy stubs (fake-bpy-module gen.py)")
        # Same convention as fake-bpy-module's release tooling: the mod version is the Blender version.
        # For 'main' no mod version is passed, which applies all version-ranged mods.
        target_version = "latest" if version == "main" else version
        mod_args = [] if version == "main" else ["-m", version]
        run(uv_python_cmd() + [FAKE_BPY_SRC / "gen.py", "-i", tmp_dir / "sphinx-in", "-o", stubs_dir,
                               "-f", "ruff", "-T", "blender", "-t", target_version, "-l", "warn", *mod_args],
            cwd=FAKE_BPY_SRC)
    finally:
        shutil.rmtree(generated_mods, ignore_errors=True)

    shutil.rmtree(tmp_dir, ignore_errors=True)
    (stubs_dir / COMPLETE_MARKER).write_text(f"blender={blender}\nsource={source}\n")
    log(f"bpy stubs: {stubs_dir}")
    return stubs_dir


def add_stubs_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("version", type=validate_version, help="Blender version as X.Y (e.g. 5.2), or 'main'")
    parser.add_argument("--ref", help="Blender git ref to check out instead of blender-vX.Y-release / main")
    parser.add_argument("--blender", type=Path,
                        help="Path to a Blender binary (or its directory) matching the version; "
                             "by default the official release is downloaded into .cache/blender-bin/")
    parser.add_argument("--force", action="store_true", help="Recreate the source worktree and regenerate the stubs")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_stubs_arguments(parser)
    args = parser.parse_args()
    generate_stubs(args.version, ref=args.ref, blender=args.blender, force=args.force)
    return 0


if __name__ == "__main__":
    main_wrapper(main)
