# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml", "ninja==1.13.2"]
# ///
"""Publish a Blender build from source as a cache (``pack``, in CI) and restore it in a fresh checkout so that the
next ``blender:build`` is incremental (``restore``, in a cloud session). Linux only.

``pack <name>`` writes these files to ``.cache/blender-cache/<name>/``, which CI uploads to the GitHub release
``blender-cache-<name>-<date>-<commit>`` and keeps the last few of; the release ``blender-cache-<name>`` holds a copy
of the newest manifest that points there (``.github/workflows/blender-cache.yml``):

  - ``blender-build-<name>.tar.zst``: the build directory ``.cache/blender-build/<name>`` and the install
    ``.cache/blender-bin/<name>``, timestamps included (Ninja decides what to rebuild by them);
  - ``ccache-<name>.tar.zst``: the ccache directory ``.cache/ccache``, if the build used ``--ccache``;
  - ``blender-lfs-<name>.tar.zst.000``, ...: the git LFS objects of the source (icons, fonts, test files), in parts;
  - ``manifest.json``: what was built (Blender commit, libraries commit, config), with which toolchain (compilers,
    linker, ccache, CMake), from which absolute path, and the archives' checksums. Written last, so a restore never
    sees a manifest whose archives are not uploaded yet.

The precompiled libraries change far less often than the source, so they get a release of their own,
``blender-libs-<platform>-<commit>``: ``pack`` writes the shared clone ``.cache/blender-libs/<platform>`` (the
checkout and its ``.git``, without the LFS objects, which only repeat the checkout) in parts to
``.cache/blender-cache/libs-<platform>/`` unless that release exists already; ``pack --libs-only`` does only that
and needs no build. ``blender:build`` extracts it instead of cloning (``build_blender.restore_libraries``). With
the LFS objects and the libraries from releases, a checkout needs projects.blender.org, which refuses a client now
and then, only for what changed since.

``restore <name>`` downloads them and recreates the state Ninja expects:

  1. ccache and the source's LFS objects from the archives: they are of use whatever is built next, so they are
     there even if the rest fails (the cache's commit is gone from the fork after a rebase);
  2. the source worktree (at the cache's commit if there is none yet) and the precompiled libraries, as
     ``blender:build`` would;
  3. the build directory and install from the archive;
  4. the timestamps: every source and library file and every file of CMake itself gets an old fixed time, except
     the sources that differ from the commits the cache was built from (committed, uncommitted or untracked), which
     get the current time. A fresh checkout gives every file the current time, which would make Ninja rebuild
     everything, and a fresh install of CMake makes it re-run CMake.

The build directory only works at the absolute path it was built at (CMake refuses another source directory, and
every compile command contains the paths), with the same compiler and ccache paths: restore checks these. It also
warns when this machine would link with another linker than the cache did (Blender's configure takes the fastest
one installed): the first build that re-runs CMake would then link everything again. The ccache archive works
anywhere (``--ccache-only``), but then the first build replays every compile from the cache.

Usage:
  uv run scripts/blender_cache.py pack main
  uv run scripts/blender_cache.py restore main
  uv run scripts/blender_cache.py pack main --libs-only
  uv run scripts/blender_cache.py restore main --ccache-only
  uv run scripts/blender_cache.py restore main --lfs-only
  uv run scripts/blender_cache.py restore main --release blender-cache-main-20261123-faa17d9072
  uv run scripts/blender_cache.py restore main --url https://example.com/blender-cache-main
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from _build_cache import (
    asset_table,
    backdate,
    download,
    download_archive,
    download_manifest,
    first_line,
    os_name,
    release_exists,
    release_url,
    repair_timestamps,
    require_linux,
    require_tools,
    tar_create,
    tar_create_split,
    tar_extract,
    tar_extract_parts,
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
    LIBS_FORMAT,
    ensure_libraries,
    libs_archive,
    libs_release,
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


def lfs_archive(name: str) -> str:
    return f"blender-lfs-{name}.tar.zst"


def lfs_directory() -> Path:
    """Where git LFS keeps the objects of the blender submodule and of its worktrees."""
    return Path(git_output(BLENDER_SUBMODULE, "rev-parse", "--path-format=absolute", "--git-common-dir")) / "lfs"


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


def recorded_linker(name: str) -> str | None:
    """The linker the build directory of ``name`` links with: ``lld``, ``mold``, or None for the compiler's default.
    No configure argument sets it: Blender's configure takes mold or lld when it finds one installed."""
    with (BUILD_DIR / name / "build.ninja").open(encoding="utf-8", errors="replace") as build_file:
        for line in build_file:
            if "LINK_FLAGS" in line and (match := re.search(r'-fuse-ld="?([^\s"]+)', line)):
                return Path(match.group(1)).name.removeprefix("ld.")
    return None


def machine_linker(compiler: str) -> str | None:
    """The linker Blender's configure takes on this machine with the GCC ``compiler``, like ``recorded_linker``
    (``build_files/cmake/platform/platform_unix.cmake``: mold if it is installed, else lld if the compiler finds it)."""
    if shutil.which("mold"):
        return "mold"
    probe = subprocess.run([compiler, "-fuse-ld=lld", "-Wl,--version"], capture_output=True, text=True)
    return "lld" if "LLD" in probe.stdout else None


def backdate_cmake(cmake: str) -> int:
    """Give every file of the CMake install that has the binary ``cmake`` (``<install>/bin/cmake``) the old time
    ``EPOCH``; return how many. ``build.ninja`` depends on the CMake modules it was generated from, and uv installs
    them with the time of the install: in a fresh session they are newer than the cache, so Ninja re-ran CMake
    before the first build (measured), and a CMake run on another machine than CI's can change what is built."""
    return backdate(Path(cmake).parent.parent)


def ensure_build_environment() -> None:
    """Create (or update) build_blender.py's uv script environment, where the cache's CMake has to be."""
    run(["uv", "sync", "--quiet", "--script", str(Path(__file__).with_name("build_blender.py"))])


# --- pack ----------------------------------------------------------------------------------------------------------


def pack_libraries(source: Path) -> Path | None:
    """Write the shared clone of the libraries ``source`` pins to ``.cache/blender-cache/libs-<platform>/`` and
    return that directory, unless CI published it already (None then)."""
    require_linux("Blender libraries")
    require_tools("tar", "zstd", "split")
    platform_name, _, commit = pinned_libraries(source)
    out = OUT_DIR / f"libs-{platform_name}"
    shutil.rmtree(out, ignore_errors=True)
    tag = libs_release(platform_name, commit)
    if release_exists(tag):
        log(f"The precompiled libraries {platform_name} at {commit[:10]} are published already ({tag})")
        return None
    libs = ensure_libraries(source)
    out.mkdir(parents=True)
    log(f"Packing the precompiled libraries {libs} ({commit[:10]})")
    # The LFS objects are a second copy of the checkout; git needs them neither to see it is clean nor to move on.
    tar_create_split(out / libs_archive(platform_name), LIBS_DIR, [libs.name], exclude=(f"{libs.name}/.git/lfs",))
    write_manifest(
        out,
        {
            "format": LIBS_FORMAT,
            "platform": platform_name,
            "commit": commit,
            "tag": tag,
            "created": datetime.now(UTC).isoformat(timespec="seconds"),
            "assets": asset_table(out),
        },
    )
    log(f"Blender libraries cache for {platform_name}: {out}")
    return out


def lfs_object_paths(source: Path, lfs: Path) -> list[str]:
    """The git LFS objects of the files checked out in ``source`` that the LFS directory ``lfs`` has, as paths
    relative to its parent; the objects of other commits, which it may have too, are not among them."""
    listing = git_output(source, "lfs", "ls-files", "--long")
    oids = {line.split(maxsplit=1)[0] for line in listing.splitlines() if line.strip()}
    paths = (f"objects/{oid[:2]}/{oid[2:4]}/{oid}" for oid in oids)
    return sorted(f"{lfs.name}/{path}" for path in paths if (lfs / path).is_file())


def pack_lfs_objects(name: str, source: Path, out: Path) -> None:
    """Write the git LFS objects ``source`` needs to ``out`` as the parts of ``lfs_archive(name)``, if it has any."""
    lfs = lfs_directory()
    paths = lfs_object_paths(source, lfs)
    if not paths:
        return
    log(f"Packing {len(paths)} git LFS objects of {source}")
    # Thousands of paths: too many for a command line.
    listing = out / "lfs-objects.txt"
    listing.write_text("".join(f"{path}\n" for path in paths))
    tar_create_split(out / lfs_archive(name), lfs.parent, ["--verbatim-files-from", f"--files-from={listing}"])
    listing.unlink()


def pack(name: str, *, libs_only: bool = False) -> Path | None:
    """Write the cache of the build ``name`` to ``.cache/blender-cache/<name>/`` and return that directory; with
    ``libs_only`` only the libraries its source pins (``pack_libraries``), for which nothing has to be built."""
    require_linux("Blender build")
    require_tools("tar", "zstd", "split")
    if libs_only:
        return pack_libraries(ensure_worktree(name))
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
    pack_lfs_objects(name, source, out)

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
        "linker": recorded_linker(name),
        "cmake": recorded_cmake(name),
        "suite_commit": git_output(REPO_ROOT, "rev-parse", "HEAD"),
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "assets": assets,
    }
    write_manifest(out, manifest)
    log(f"Blender build cache for {name}: {out}")
    pack_libraries(source)
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
    # Caches packed before the linker was recorded have no "linker" at all; None is the compiler's default.
    if "linker" in manifest and (compiler := manifest.get("compilers", {}).get("CC")):
        cached, here = (
            linker or "the compiler's default" for linker in (manifest["linker"], machine_linker(compiler["path"]))
        )
        if cached != here:
            log(
                f"Warning: the cache links with {cached}, but Blender's configure takes {here} on this machine: the "
                "first build that re-runs CMake (a changed CMakeLists.txt, a new source file) links everything again "
                "and regenerates what the relinked tools write"
            )
    if (ccache := manifest.get("ccache")) and not Path(ccache["path"]).is_file():
        raise StepError(
            f"The cache's compile commands run ccache from {ccache['path']} ({ccache['version']}), which is missing"
        )
    if (cmake := manifest.get("cmake")) and not Path(cmake).is_file():
        raise StepError(
            f"The cache's build re-runs CMake from {cmake}, which is missing: uv runs build_blender.py with another "
            "Python here (the path has its version), so the build would fail"
        )


def has_blender_commit(commit: str) -> bool:
    known = subprocess.run(
        ["git", "-C", str(BLENDER_SUBMODULE), "cat-file", "-e", f"{commit}^{{commit}}"], capture_output=True
    )
    return known.returncode == 0


def ensure_blender_commit(commit: str, ref: str) -> None:
    """Make ``commit`` available in the blender submodule, fetching ``ref`` (which should contain it) if needed.

    It is gone for good once the branch was rebased and pushed: GitHub does not serve a commit no branch contains
    (``not our ref``, measured), and without it nothing can tell which sources changed since the cache."""
    if has_blender_commit(commit):
        return
    log(f"Fetching {ref} for the cache's Blender commit {commit[:10]}")
    try:
        run(["git", "-C", BLENDER_SUBMODULE, "fetch", "origin", ref])
    except StepError as error:
        log(f"{error}")
    if not has_blender_commit(commit):
        raise StepError(
            f"The cache was built from Blender {commit[:10]}, which {ref} of the blender submodule's remote does "
            "not contain (was the branch rebased since?), so its build directory cannot be used"
        )


def planned_build(name: str) -> str | None:
    """What the next build of ``name`` runs, from a Ninja dry run, as the end of a sentence (None if Ninja can't
    tell): how many build steps, or that it re-runs CMake first and why. The dry run stops at the CMake run (it
    would write a new ``build.ninja``), so its one step says nothing about how much is built after it."""
    ninja = shutil.which("ninja")
    if not ninja:
        return None
    result = subprocess.run(
        [ninja, "-C", str(BUILD_DIR / name), "-n", "-d", "explain", "install"], capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    return describe_dry_run(result.stdout, result.stderr)


def describe_dry_run(stdout: str, explanations: str) -> str:
    """``planned_build`` for the output of the Ninja dry run and its ``-d explain`` lines."""
    steps = [line for line in stdout.splitlines() if line.startswith("[")]
    if not any("Re-running CMake" in step for step in steps):
        return f"runs {len(steps)} build steps"
    reasons = [line for line in explanations.splitlines() if " build.ninja " in line]
    reason = reasons[0].removeprefix("ninja explain: ") if reasons else "an input of build.ninja changed"
    return f"re-runs CMake first ({reason}); what it builds after that depends on the new build.ninja"


def restore_lfs_objects(name: str, url: str, assets: dict[str, dict], downloads: Path) -> bool:
    """Extract the cache's git LFS objects into the blender submodule's LFS directory, next to the ones it has, so
    that pulling the source's LFS files finds them there; False if the cache has none."""
    parts = download_archive(url, lfs_archive(name), assets, downloads)
    if not parts:
        return False
    lfs = lfs_directory()
    log(f"Extracting the git LFS objects into {lfs}")
    lfs.mkdir(parents=True, exist_ok=True)
    tar_extract_parts(parts, lfs.parent, remove=True)
    return True


def restore(
    name: str, url: str | None = None, *, force: bool = False, ccache_only: bool = False, lfs_only: bool = False
) -> None:
    require_linux("Blender build")
    require_tools("tar", "zstd")
    downloads = OUT_DIR / name
    shutil.rmtree(downloads, ignore_errors=True)
    downloads.mkdir(parents=True)
    manifest, url = download_manifest(url or default_url(name), downloads)
    if not (ccache_only or lfs_only):
        ensure_build_environment()
    check_manifest(manifest, name, ccache_only=ccache_only or lfs_only)
    commit = manifest["commit"]
    log(
        f"Cache of {name}: Blender {manifest['commit'][:10]}, {manifest['config']} {manifest['build_type']}, "
        f"built {manifest['created']} on {manifest['os']}"
    )
    assets = manifest["assets"]

    if lfs_only:
        if not restore_lfs_objects(name, url, assets, downloads):
            raise StepError("The cache has no git LFS archive (it was packed before they were added)")
        log(f"Restored the git LFS objects of {name}; `mise run blender:build {name}` pulls only the ones that changed")
        return
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
    # Before anything that needs the cache's commit: like ccache, the LFS objects serve any build of the source.
    restore_lfs_objects(name, url, assets, downloads)
    try:
        ensure_blender_commit(commit, name)
    except StepError as error:
        raise StepError(
            f"{error}. The cache's ccache and git LFS objects are restored: `mise run blender:build {name} --ccache` "
            "builds everything, with the compiles the cache has from ccache"
        ) from None
    archive = download(f"{url}/{build_archive(name)}", downloads / build_archive(name), assets[build_archive(name)])

    # The source and the libraries, as blender:build would prepare them. An existing worktree stays where it is:
    # what differs from the cache's commit just gets rebuilt.
    source = ensure_worktree(name) if worktree_commit(name) else ensure_worktree(name, commit)
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
    if cmake := manifest.get("cmake"):
        log(f"CMake: {backdate_cmake(cmake)} files of {Path(cmake).parent.parent} set to the old time")

    planned = planned_build(name)
    log(
        f"Restored the Blender build {name}"
        + (f"; the next `mise run blender:build {name}` {planned}" if planned is not None else "")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    pack_parser = commands.add_parser("pack", help="Write the cache of a build to .cache/blender-cache/<name>/")
    pack_parser.add_argument("name", type=validate_build_name)
    pack_parser.add_argument(
        "--libs-only",
        action="store_true",
        help="Only pack the precompiled libraries the source of <name> pins (needs no build), unless CI has them",
    )
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
    only = restore_parser.add_mutually_exclusive_group()
    only.add_argument(
        "--ccache-only", action="store_true", help="Only restore ccache (works at any path; the build replays it)"
    )
    only.add_argument(
        "--lfs-only", action="store_true", help="Only restore the source's git LFS objects (works at any path)"
    )
    args = parser.parse_args()
    if args.command == "pack":
        pack(args.name, libs_only=args.libs_only)
    else:
        url = release_url(args.release) if args.release else args.url
        restore(args.name, url, force=args.force, ccache_only=args.ccache_only, lfs_only=args.lfs_only)
    return 0


if __name__ == "__main__":
    main_wrapper(main)
