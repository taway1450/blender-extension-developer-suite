# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""Generate bpy stubs for a Blender version with ``fake-bpy-module`` and Blender's own stub generator.

Both stub generators work from the rst API docs Blender generates:
  fake-bpy-module  the ``fake-bpy-module`` submodule; stubs in ``.cache/bpy-stubs/<version>``
  builtin          Blender's ``doc/python_api/sphinx_stub_gen.py`` (Blender 5.2 and later); stubs in
                   ``.cache/bpy-stubs-builtin/<version>``

Steps:
  1. Create a git worktree of the ``blender`` submodule for the requested version
     (``sphinx_doc_gen.py`` and the bgl sources are taken from it).
  2. Download the matching official Blender binary into ``.cache/blender-bin/`` unless it is
     already there (or ``--blender`` is passed). Versions other than X.Y (e.g. ``main``) name a
     Blender build from source, made with ``build_blender.py`` into the same directory.
  3. Run Blender to generate the rst API docs (cached in ``.cache/bpy-rst/<version>``).
  4. fake-bpy-module: run Blender to generate fake-bpy-module's mod files, then fake-bpy-module's
     ``gen.py`` to turn the rst docs into stubs.
     builtin: run ``sphinx_stub_gen.py`` of the source worktree on the rst docs.

Usage:
  uv run scripts/generate_stubs.py 5.2                       # both generators (builtin where available)
  uv run scripts/generate_stubs.py 5.2 --generator builtin
  uv run scripts/generate_stubs.py main          # after: uv run scripts/build_blender.py main
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
    is_release,
    log,
    main_wrapper,
    run,
    validate_version,
)
from download_blender import cached_blender, download_blender

FAKE_BPY, BUILTIN, ALL = "fake-bpy-module", "builtin", "all"
GENERATORS = (FAKE_BPY, BUILTIN)
STUBS_DIRS = {FAKE_BPY: CACHE_DIR / "bpy-stubs", BUILTIN: CACHE_DIR / "bpy-stubs-builtin"}
RST_DIR = CACHE_DIR / "bpy-rst"
BUILTIN_STUB_GEN = Path("doc") / "python_api" / "sphinx_stub_gen.py"


def resolve_git_ref(version: str, ref_override: str | None) -> str:
    if ref_override:
        return ref_override
    if not is_release(version):
        return version
    return f"blender-v{version}-release"


def resolve_commit(ref: str, fetch: bool = False) -> str:
    """Return the commit ``ref`` names in the blender submodule, fetching it from origin if it is
    not known locally (or always with ``fetch``)."""
    def lookup(candidate: str) -> str | None:
        check = subprocess.run(
            ["git", "-C", str(BLENDER_SUBMODULE), "rev-parse", "--verify", "-q", f"{candidate}^{{commit}}"],
            capture_output=True, text=True,
        )
        return check.stdout.strip() if check.returncode == 0 else None

    if not fetch:
        # Prefer the remote-tracking branch, fall back to whatever the ref names (tag, commit, ...).
        for candidate in (f"origin/{ref}", ref):
            if commit := lookup(candidate):
                return commit
        log(f"Ref {ref!r} not found locally, fetching it from origin")
    run(["git", "-C", BLENDER_SUBMODULE, "fetch", "origin", ref])
    if commit := lookup("FETCH_HEAD"):
        return commit
    raise StepError(f"Could not resolve Blender git ref {ref!r}")


def worktree_commit(version: str) -> str | None:
    """HEAD of the source worktree for ``version``, or None if it is missing or no longer a git worktree."""
    worktree = CACHE_DIR / "blender-src" / version
    if not worktree.exists():
        return None
    check = subprocess.run(["git", "-C", str(worktree), "rev-parse", "HEAD"], capture_output=True, text=True)
    return check.stdout.strip() if check.returncode == 0 else None


def ensure_worktree(version: str, ref: str | None = None, force: bool = False, update: bool = False) -> Path:
    """Return a git worktree of the Blender source for ``version``, creating it if needed.

    With ``update`` the ref is fetched again and an existing worktree is moved to its latest commit.
    """
    ref = resolve_git_ref(version, ref)
    worktree = CACHE_DIR / "blender-src" / version
    # Blender stores test data and some assets in git LFS; we only need the Python sources.
    env = {**os.environ, "GIT_LFS_SKIP_SMUDGE": "1"}
    head = worktree_commit(version)
    if head and not force:
        if update and (commit := resolve_commit(ref, fetch=True)) != head:
            log(f"Updating Blender source worktree {worktree} to {ref} ({head[:10]} -> {commit[:10]})")
            run(["git", "-C", worktree, "checkout", "--detach", commit], env=env)
            return worktree
        log(f"Reusing Blender source worktree {worktree} ({head[:10]})")
        return worktree

    if head:
        log(f"Removing existing worktree {worktree}")
        run(["git", "-C", BLENDER_SUBMODULE, "worktree", "remove", "--force", worktree])
    elif worktree.exists():
        # E.g. its metadata in the submodule's .git/worktrees/ is gone; git can't remove it then.
        log(f"Removing {worktree}, which is no longer a git worktree")
        shutil.rmtree(worktree)
    run(["git", "-C", BLENDER_SUBMODULE, "worktree", "prune"])

    commit = resolve_commit(ref, fetch=update)
    log(f"Creating Blender source worktree for {ref} ({commit[:10]}) at {worktree}")
    worktree.parent.mkdir(parents=True, exist_ok=True)
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
    elif not is_release(version):
        blender = cached_blender(version)
        if not blender:
            raise StepError(f"No Blender build named {version!r}: build it with `mise run blender:build {version}` "
                            "or pass --blender with a matching Blender binary")
    else:
        blender = download_blender(version)

    actual = blender_binary_version(blender)
    if is_release(version) and actual != version:
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


def has_builtin_generator(source: Path) -> bool:
    """Whether the Blender source has its own stub generator (added in Blender 5.2)."""
    return (source / BUILTIN_STUB_GEN).is_file()


def resolve_generators(version: str, ref: str | None, generator: str) -> list[str]:
    """The generators ``generator`` (one of GENERATORS or ALL) stands for; ALL leaves out the builtin
    generator for Blender versions without one."""
    if generator != ALL:
        return [generator]
    if has_builtin_generator(ensure_worktree(version, ref)):
        return list(GENERATORS)
    log(f"Blender {version} has no built-in stub generator ({BUILTIN_STUB_GEN.as_posix()}), using only {FAKE_BPY}")
    return [FAKE_BPY]


def results_name(stem: str, generator: str) -> str:
    """File name for results against ``generator``'s stubs (fake-bpy-module's keep the plain name)."""
    return f"{stem}.txt" if generator == FAKE_BPY else f"{stem}-{generator}.txt"


def generate_rst(version: str, blender: Path, source: Path, force: bool) -> Path:
    """Return the rst API docs (``sphinx-in``) for ``version``, generating them with Blender if needed."""
    rst_dir = RST_DIR / version
    marker = rst_dir / COMPLETE_MARKER
    commit = git_output(source, "rev-parse", "HEAD")
    if marker.exists() and not force and marker.read_text() == commit:
        log(f"Reusing rst documentation {rst_dir / 'sphinx-in'}")
        return rst_dir / "sphinx-in"
    shutil.rmtree(rst_dir, ignore_errors=True)
    rst_dir.mkdir(parents=True)
    log("Generating rst documentation with Blender (sphinx_doc_gen.py)")
    run_blender_script(blender, source / "doc" / "python_api" / "sphinx_doc_gen.py", "--output", rst_dir)
    marker.write_text(commit)
    return rst_dir / "sphinx-in"


def generate_builtin_stubs(source: Path, rst: Path, stubs_dir: Path) -> None:
    log(f"Generating bpy stubs (Blender's {BUILTIN_STUB_GEN.as_posix()})")
    cmd: list[str | Path] = ["uv", "run", "--no-project", "--python", ">=3.11", "--with", "docutils",
                             "python", source / BUILTIN_STUB_GEN, rst, "--output", stubs_dir]
    printable = " ".join(str(c) for c in cmd)
    print(f"    $ {printable}", flush=True)
    result = subprocess.run([str(c) for c in cmd], env={**os.environ, "PYTHONUTF8": "1"})
    if result.returncode == 0:
        return
    # It also fails on parse and documentation errors or failed validation after writing all stubs;
    # those stubs are still usable (and finding such errors is what the check tasks are for).
    if not any(stubs_dir.rglob("*.pyi")):
        raise StepError(f"Command failed with exit code {result.returncode}: {printable}")
    log(f"warning: {BUILTIN_STUB_GEN.name} exited with code {result.returncode} (errors above), "
        "keeping the stubs it wrote")


def generate_stubs(version: str, *, generator: str = FAKE_BPY, ref: str | None = None,
                   blender: Path | None = None, force: bool = False) -> Path:
    """Return the bpy stubs directory of ``generator`` for ``version``, generating the stubs if needed."""
    stubs_dir = STUBS_DIRS[generator] / version
    marker = stubs_dir / COMPLETE_MARKER
    if marker.exists() and not force:
        # Stubs go stale when the worktree moved to another commit (blender:build --update).
        stubs_commit = re.search(r"^commit=(\w+)$", marker.read_text(), re.MULTILINE)
        if not stubs_commit or stubs_commit[1] == worktree_commit(version):
            log(f"Reusing {generator} bpy stubs {stubs_dir}")
            return stubs_dir
        log(f"{generator} bpy stubs {stubs_dir} were generated from another commit, regenerating them")

    source = ensure_worktree(version, ref, force)
    if generator == BUILTIN and not has_builtin_generator(source):
        raise StepError(f"Blender {version} has no built-in stub generator ({BUILTIN_STUB_GEN.as_posix()}, "
                        f"added in Blender 5.2); use --generator {FAKE_BPY}")
    blender = find_blender(version, blender)

    shutil.rmtree(stubs_dir, ignore_errors=True)
    # The rst docs stay cached, so the other generator (or a retry after a failure) can reuse them.
    rst = generate_rst(version, blender, source, force)
    if generator == BUILTIN:
        generate_builtin_stubs(source, rst, stubs_dir)
    else:
        generate_fake_bpy_stubs(version, blender, source, rst, stubs_dir)

    marker.write_text(f"blender={blender}\nsource={source}\ncommit={git_output(source, 'rev-parse', 'HEAD')}\n")
    log(f"{generator} bpy stubs: {stubs_dir}")
    return stubs_dir


def generate_fake_bpy_stubs(version: str, blender: Path, source: Path, rst: Path, stubs_dir: Path) -> None:
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
        # For source builds (e.g. 'main') no mod version is passed, which applies all version-ranged mods.
        target_version = version if is_release(version) else "latest"
        mod_args = ["-m", version] if is_release(version) else []
        run(uv_python_cmd() + [FAKE_BPY_SRC / "gen.py", "-i", rst, "-o", stubs_dir,
                               "-f", "ruff", "-T", "blender", "-t", target_version, "-l", "warn", *mod_args],
            cwd=FAKE_BPY_SRC)
    finally:
        shutil.rmtree(generated_mods, ignore_errors=True)


def add_stubs_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("version", type=validate_version,
                        help="Blender version as X.Y (e.g. 5.2), or the name of a Blender build from source (e.g. main)")
    parser.add_argument("--ref", help="Blender git ref to check out instead of blender-vX.Y-release / the build name")
    parser.add_argument("--blender", type=Path,
                        help="Path to a Blender binary (or its directory) matching the version; by default the "
                             "official release is downloaded into .cache/blender-bin/ (or built there by build_blender.py)")
    parser.add_argument("--force", action="store_true", help="Recreate the source worktree and regenerate the stubs")
    parser.add_argument("--generator", choices=(*GENERATORS, ALL), default=ALL,
                        help=f"Stub generator (default: {ALL}, i.e. both where Blender has its own)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_stubs_arguments(parser)
    args = parser.parse_args()
    for generator in resolve_generators(args.version, args.ref, args.generator):
        generate_stubs(args.version, generator=generator, ref=args.ref, blender=args.blender, force=args.force)
    return 0


if __name__ == "__main__":
    main_wrapper(main)
