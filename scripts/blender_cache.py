# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml", "ninja==1.13.2"]
# ///
"""Publish a Blender build from source as a cache (``pack``, in CI) and restore it in a fresh checkout so that the
next ``blender:build`` is incremental (``restore``, in a cloud session). Linux only.

``pack <name>`` writes three files to ``.cache/blender-cache/<name>/``, which CI uploads to the GitHub release
``blender-cache-<name>-<date>-<commit>`` and keeps the last few of; the release ``blender-cache-<name>`` holds a copy
of the newest manifest that points there (``.github/workflows/blender-cache.yml``):

  - ``blender-build-<name>.tar.zst``: the build directory ``.cache/blender-build/<name>`` and the install
    ``.cache/blender-bin/<name>``, timestamps included (Ninja decides what to rebuild by them);
  - ``ccache-<name>.tar.zst``: the ccache directory ``.cache/ccache``, if the build used ``--ccache``;
  - ``manifest.json``: what was built (Blender commit, libraries commit, config), with which toolchain, from
    which absolute path, and the archives' checksums. Written last, so a restore never sees a manifest whose
    archives are not uploaded yet.

``restore <name>`` downloads them and recreates the state Ninja expects:

  1. the source worktree (at the cache's commit if there is none yet) and the precompiled libraries, as
     ``blender:build`` would;
  2. the build directory, install and ccache from the archives;
  3. the timestamps: every source and library file gets an old fixed time, except the files that differ from
     the commits the cache was built from (committed, uncommitted or untracked), which get the current time.
     A fresh checkout gives every file the current time, which would make Ninja rebuild everything.

The build directory only works at the absolute path it was built at (CMake refuses another source directory, and
every compile command contains the paths), with the same compiler and ccache paths: restore checks these. The
ccache archive works anywhere (``--ccache-only``), but then the first build replays every compile from the cache.

Usage:
  uv run scripts/blender_cache.py pack main
  uv run scripts/blender_cache.py restore main
  uv run scripts/blender_cache.py restore main --ccache-only
  uv run scripts/blender_cache.py restore main --release blender-cache-main-20261123-faa17d9072
  uv run scripts/blender_cache.py restore main --url https://example.com/blender-cache-main
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from _build_cache import (
    asset_table,
    download,
    download_manifest,
    first_line,
    os_name,
    release_url,
    repair_timestamps,
    require_linux,
    require_tools,
    tar_create,
    tar_extract,
    write_manifest,
)
from _common import (
    BLENDER_LFS_URL,
    BLENDER_SUBMODULE,
    CACHE_DIR,
    REPO_ROOT,
    StepError,
    git_output,
    log,
    main_wrapper,
    run,
    validate_build_name,
)
from build_blender import (
    BUILD_DIR,
    CCACHE_DIR,
    CONFIGURE_ARGS,
    LIBS_DIR,
    ensure_libraries,
    pinned_libraries,
    pull_lfs_files,
)
from download_blender import BLENDER_BIN_DIR, read_build_info
from generate_stubs import ensure_worktree, worktree_commit

FORMAT = 2
OUT_DIR = CACHE_DIR / "blender-cache"


def build_archive(name: str) -> str:
    return f"blender-build-{name}.tar.zst"


def ccache_archive(name: str) -> str:
    return f"ccache-{name}.tar.zst"


def default_url(name: str) -> str:
    """Where CI publishes the newest cache of the build ``name``; ``BLENDER_CACHE_URL`` overrides it.

    The release ``blender-cache-<name>`` only holds the newest build's manifest, whose ``archives_url`` names the
    release with its archives, ``blender-cache-<name>-<date>-<commit>``; CI keeps the last few of those.
    """
    return os.environ.get("BLENDER_CACHE_URL") or release_url(f"blender-cache-{name}")


def recorded_configuration(name: str) -> tuple[dict[str, str], str | None]:
    """The compilers (``CC``/``CXX``) the build directory of ``name`` was configured with, and the ccache program
    its compile commands start with (None without ``--ccache``)."""
    build_dir = BUILD_DIR / name
    lines = (build_dir / CONFIGURE_ARGS).read_text().splitlines()
    compilers = dict(line.split("=", 1) for line in lines if line.startswith(("CC=", "CXX=")))
    ccache = None
    if "-DWITH_COMPILER_CCACHE=ON" in lines:
        for line in (build_dir / "CMakeCache.txt").read_text().splitlines():
            if line.startswith("CCACHE_PROGRAM:"):
                ccache = line.split("=", 1)[1]
    return compilers, ccache


def recorded_cmake(name: str) -> str:
    """The CMake binary the build directory of ``name`` re-runs itself with (``build.ninja`` depends on it and its
    modules). It lives in build_blender.py's uv script environment, under ``lib/python3.<minor>/``, so it moves
    with the Python version uv picks for that script."""
    for line in (BUILD_DIR / name / "CMakeCache.txt").read_text().splitlines():
        if line.startswith("CMAKE_COMMAND:"):
            return line.split("=", 1)[1]
    raise StepError(f"No CMAKE_COMMAND in the CMake cache of {name}")


def ensure_build_environment() -> None:
    """Create (or update) build_blender.py's uv script environment, where the cache's CMake has to be."""
    run(["uv", "sync", "--quiet", "--script", str(Path(__file__).with_name("build_blender.py"))])


# --- pack ----------------------------------------------------------------------------------------------------------


def pack(name: str) -> Path:
    """Write the cache of the build ``name`` to ``.cache/blender-cache/<name>/`` and return that directory."""
    require_linux("Blender build")
    require_tools("tar", "zstd")
    info = read_build_info(name)
    if not info:
        raise StepError(f"No Blender build named {name!r}: build it with `mise run blender:build {name}` first")
    if info.get("revision") != info.get("commit"):
        raise StepError(
            f"The build {name!r} was made from uncommitted changes ({info.get('revision')}); pack a clean one"
        )
    source = Path(info["source"])
    libs_platform, _, libs_commit = pinned_libraries(source)
    compilers, ccache = recorded_configuration(name)

    out = OUT_DIR / name
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    log(f"Packing the build directory and install of {name} ({info['commit'][:10]})")
    tar_create(
        out / build_archive(name),
        CACHE_DIR,
        [
            (BUILD_DIR / name).relative_to(CACHE_DIR).as_posix(),
            (BLENDER_BIN_DIR / name).relative_to(CACHE_DIR).as_posix(),
        ],
    )
    if ccache and CCACHE_DIR.is_dir():
        log(f"Packing the ccache directory {CCACHE_DIR}")
        tar_create(out / ccache_archive(name), CACHE_DIR, [CCACHE_DIR.relative_to(CACHE_DIR).as_posix()])

    assets = asset_table(out)
    manifest = {
        "format": FORMAT,
        "name": name,
        "commit": info["commit"],
        "config": info["config"],
        "build_type": info["build_type"],
        "libs": {"platform": libs_platform, "commit": libs_commit},
        "repo_root": str(REPO_ROOT),
        "machine": platform.machine(),
        "os": os_name(),
        "compilers": {
            var: {"path": path, "version": first_line([path, "--version"])} for var, path in compilers.items()
        },
        "ccache": {"path": ccache, "version": first_line([ccache, "--version"])} if ccache else None,
        "cmake": recorded_cmake(name),
        "suite_commit": git_output(REPO_ROOT, "rev-parse", "HEAD"),
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "assets": assets,
    }
    write_manifest(out, manifest)
    log(f"Blender build cache for {name}: {out}")
    return out


# --- restore -------------------------------------------------------------------------------------------------------


def check_manifest(manifest: dict, name: str, *, ccache_only: bool) -> None:
    """Refuse a cache this checkout and machine cannot use."""
    if manifest.get("format") != FORMAT:
        raise StepError(f"Unsupported cache format {manifest.get('format')!r} (expected {FORMAT})")
    if manifest.get("name") != name:
        raise StepError(f"The cache is for the build {manifest.get('name')!r}, not {name!r}")
    if manifest.get("machine") != platform.machine():
        raise StepError(f"The cache was built on {manifest.get('machine')}, this machine is {platform.machine()}")
    if ccache_only:
        return
    if manifest.get("repo_root") != str(REPO_ROOT):
        raise StepError(
            f"The build directory was built at {manifest.get('repo_root')}, but this checkout is at {REPO_ROOT}; "
            "only --ccache-only works from another path"
        )
    for var, compiler in manifest.get("compilers", {}).items():
        if not shutil.which(compiler["path"]):
            raise StepError(f"The cache was built with {var}={compiler['path']}, which is not installed here")
        version = first_line([compiler["path"], "--version"])
        if version != compiler["version"]:
            log(f"Warning: {compiler['path']} is {version!r} here, the cache used {compiler['version']!r}")
    if (ccache := manifest.get("ccache")) and not Path(ccache["path"]).is_file():
        raise StepError(
            f"The cache's compile commands run ccache from {ccache['path']} ({ccache['version']}), which is missing"
        )
    if (cmake := manifest.get("cmake")) and not Path(cmake).is_file():
        raise StepError(
            f"The cache's build re-runs CMake from {cmake}, which is missing: uv runs build_blender.py with another "
            "Python here (the path has its version), so the build would fail"
        )


def ensure_blender_commit(commit: str, ref: str) -> None:
    """Make ``commit`` available in the blender submodule, fetching ``ref`` (which should contain it) if needed."""
    known = subprocess.run(
        ["git", "-C", str(BLENDER_SUBMODULE), "cat-file", "-e", f"{commit}^{{commit}}"], capture_output=True
    )
    if known.returncode != 0:
        log(f"Fetching {ref} for the cache's Blender commit {commit[:10]}")
        run(["git", "-C", BLENDER_SUBMODULE, "fetch", "origin", ref])


def planned_steps(name: str) -> int | None:
    """How many steps the next build of ``name`` runs, from a Ninja dry run (None if Ninja can't tell)."""
    ninja = shutil.which("ninja")
    if not ninja:
        return None
    result = subprocess.run([ninja, "-C", str(BUILD_DIR / name), "-n", "install"], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return sum(1 for line in result.stdout.splitlines() if line.startswith("["))


def restore(name: str, url: str | None = None, *, force: bool = False, ccache_only: bool = False) -> None:
    require_linux("Blender build")
    require_tools("tar", "zstd")
    downloads = OUT_DIR / name
    shutil.rmtree(downloads, ignore_errors=True)
    downloads.mkdir(parents=True)
    manifest, url = download_manifest(url or default_url(name), downloads)
    if not ccache_only:
        ensure_build_environment()
    check_manifest(manifest, name, ccache_only=ccache_only)
    log(
        f"Cache of {name}: Blender {manifest['commit'][:10]}, {manifest['config']} {manifest['build_type']}, "
        f"built {manifest['created']} on {manifest['os']}"
    )
    assets = manifest["assets"]

    if ccache_archive(name) in assets:
        archive = download(
            f"{url}/{ccache_archive(name)}", downloads / ccache_archive(name), assets[ccache_archive(name)]
        )
        log(f"Extracting ccache into {CCACHE_DIR}")
        tar_extract(archive, CACHE_DIR)
        archive.unlink()
    elif ccache_only:
        raise StepError("The cache has no ccache archive (it was built without --ccache)")
    if ccache_only:
        log(f"Restored the ccache of {name}; `mise run blender:build {name} --ccache` replays every compile from it")
        return

    build_dir, install_dir = BUILD_DIR / name, BLENDER_BIN_DIR / name
    if not force and (build_dir.exists() or install_dir.exists()):
        raise StepError(f"{build_dir} or {install_dir} exists already; --force replaces them with the cache")
    archive = download(f"{url}/{build_archive(name)}", downloads / build_archive(name), assets[build_archive(name)])

    # The source and the libraries, as blender:build would prepare them. An existing worktree stays where it is:
    # what differs from the cache's commit just gets rebuilt.
    commit = manifest["commit"]
    if worktree_commit(name):
        source = ensure_worktree(name)
    else:
        ensure_blender_commit(commit, name)
        source = ensure_worktree(name, commit)
    pull_lfs_files(source, BLENDER_LFS_URL)
    libs = ensure_libraries(source)
    if not (LIBS_DIR / manifest["libs"]["platform"]).samefile(libs):
        raise StepError(f"The cache used the {manifest['libs']['platform']} libraries, this machine uses {libs.name}")

    log(f"Extracting the build directory and install of {name}")
    shutil.rmtree(build_dir, ignore_errors=True)
    shutil.rmtree(install_dir, ignore_errors=True)
    tar_extract(archive, CACHE_DIR)
    archive.unlink()

    log("Setting the timestamps of the sources and libraries that match the cache's commits to an old time")
    changed = repair_timestamps(source, commit)
    log(f"Source worktree: {changed} files differ from {commit[:10]}")
    changed = repair_timestamps(libs, manifest["libs"]["commit"])
    log(f"Precompiled libraries: {changed} files differ from {manifest['libs']['commit'][:10]}")

    steps = planned_steps(name)
    log(
        f"Restored the Blender build {name}"
        + (f"; the next `mise run blender:build {name}` runs {steps} build steps" if steps is not None else "")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    pack_parser = commands.add_parser("pack", help="Write the cache of a build to .cache/blender-cache/<name>/")
    pack_parser.add_argument("name", type=validate_build_name)
    restore_parser = commands.add_parser("restore", help="Download and restore the cache of a build")
    restore_parser.add_argument("name", type=validate_build_name)
    source = restore_parser.add_mutually_exclusive_group()
    source.add_argument("--url", help="Where the cache's files are (default: the newest build CI published)")
    source.add_argument(
        "--release",
        help="Restore this release of the repo instead of the newest, e.g. blender-cache-main-20261123-faa17d9072",
    )
    restore_parser.add_argument(
        "--force", action="store_true", help="Replace an existing build directory and install with the cache"
    )
    restore_parser.add_argument(
        "--ccache-only", action="store_true", help="Only restore ccache (works at any path; the build replays it)"
    )
    args = parser.parse_args()
    if args.command == "pack":
        pack(args.name)
    else:
        url = release_url(args.release) if args.release else args.url
        restore(args.name, url, force=args.force, ccache_only=args.ccache_only)
    return 0


if __name__ == "__main__":
    main_wrapper(main)
