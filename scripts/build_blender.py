# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml", "cmake>=3.21", "ninja"]
# ///
"""Build Blender from source into ``.cache/blender-bin/<name>``, next to the downloaded releases.

Steps:
  1. Create (or with ``--update`` fast-forward) the git worktree ``.cache/blender-src/<name>`` of the
     ``blender`` submodule at the ref (default: the name itself, e.g. ``main``) and pull its git LFS
     files (icons, startup.blend, ...).
  2. Check out the precompiled libraries the source pins (the ``lib/<platform>`` submodule) in a
     clone shared by all builds, ``.cache/blender-libs/<platform>``.
  3. Configure with CMake (Ninja) in ``.cache/blender-build/<name>`` and build the ``install``
     target into ``.cache/blender-bin/<name>``, with CMake and Ninja from PyPI (script dependencies).
     On Windows the Visual Studio environment is loaded with vcvarsall.bat, like Blender's
     ``make.bat`` does.

The other scripts then use the build for ``<name>`` like a downloaded release, e.g.
``uv run scripts/generate_stubs.py main``.

Usage:
  uv run scripts/build_blender.py main
  uv run scripts/build_blender.py main --update                 # fetch main again and rebuild
  uv run scripts/build_blender.py my-feature --ref my-feature-branch
  uv run scripts/build_blender.py pr-12345 --ref refs/pull/12345/head --config lite

See https://developer.blender.org/docs/handbook/building_blender/ for the prerequisites (Visual
Studio with the C++ workload on Windows, Xcode on macOS, the build dependencies on Linux, plus
git LFS).
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from _common import CACHE_DIR, StepError, git_output, log, main_wrapper, run, validate_build_name
from download_blender import BLENDER_BIN_DIR, blender_executable
from generate_stubs import blender_binary_version, ensure_worktree

BUILD_DIR = CACHE_DIR / "blender-build"
LIBS_DIR = CACHE_DIR / "blender-libs"
BUILD_INFO = ".build-info"
CONFIGURE_ARGS = "configure-args.txt"
BUILD_TYPES = ["Release", "RelWithDebInfo", "Debug"]


def is_arm64() -> bool:
    return platform.machine().lower() in ("arm64", "aarch64")


def lib_platform() -> str:
    """Name of the ``lib/<platform>`` submodule with the precompiled libraries for this machine."""
    arch = "arm64" if is_arm64() else "x64"
    if sys.platform == "win32":
        return f"windows_{arch}"
    if sys.platform == "darwin":
        if arch != "arm64":
            raise StepError("Blender only provides precompiled libraries for Apple Silicon Macs")
        return "macos_arm64"
    if sys.platform.startswith("linux"):
        return f"linux_{arch}"
    raise StepError(f"Unsupported platform {sys.platform!r}")


def ensure_libraries(source: Path) -> Path:
    """Check out the precompiled libraries pinned by ``source`` in the shared clone and return it.

    Every Blender worktree would otherwise download several GB of libraries into its own submodule;
    the shared clone only downloads the git LFS files that changed between the pinned commits.
    """
    name = lib_platform()
    submodule = f"lib/{name}"
    url = git_output(source, "config", "-f", ".gitmodules", f"submodule.{submodule}.url")
    tree = git_output(source, "ls-tree", "HEAD", submodule).split()
    if len(tree) < 3 or tree[1] != "commit":
        raise StepError(f"{source} has no {submodule} submodule")
    commit = tree[2]

    libs = LIBS_DIR / name
    if not (libs / ".git").exists():
        log(f"Cloning the precompiled libraries {url} into {libs}")
        shutil.rmtree(libs, ignore_errors=True)
        libs.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--no-checkout", "--filter=blob:none", url, libs])
    if subprocess.run(["git", "-C", str(libs), "cat-file", "-e", f"{commit}^{{commit}}"],
                      capture_output=True).returncode != 0:
        log(f"Fetching library commit {commit[:10]}")
        run(["git", "-C", libs, "fetch", "origin"])

    # Always check out: after `clone --no-checkout` HEAD already names the pinned commit while the
    # working tree is still empty. Files that are already up to date are left alone.
    log(f"Checking out precompiled libraries {name} at {commit[:10]} (downloads the changed git LFS files)")
    run(["git", "-C", libs, "-c", "advice.detachedHead=false", "checkout", "--force", "--detach", commit])
    # A checkout interrupted while downloading leaves LFS pointer files behind; this completes it.
    run(["git", "-C", libs, "lfs", "pull"])
    log(f"Precompiled libraries: {libs} ({commit[:10]})")
    return libs


def visual_studio_env() -> dict[str, str]:
    """The environment of a Visual Studio developer command prompt (compiler, Windows SDK, CMake, Ninja)."""
    vswhere = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                   "Microsoft Visual Studio", "Installer", "vswhere.exe")
    if not vswhere.is_file():
        raise StepError(f"vswhere.exe not found at {vswhere}; install Visual Studio with the C++ workload")
    component = "Microsoft.VisualStudio.Component.VC.Tools." + ("ARM64" if is_arm64() else "x86.x64")
    install = subprocess.run([str(vswhere), "-latest", "-products", "*", "-requires", component,
                              "-property", "installationPath"], capture_output=True, text=True).stdout.strip()
    if not install:
        raise StepError("No Visual Studio installation with the C++ build tools found "
                        "(install the 'Desktop development with C++' workload)")
    vcvars = Path(install, "VC", "Auxiliary", "Build", "vcvarsall.bat")
    log(f"Using Visual Studio at {install}")
    result = subprocess.run(f'"{vcvars}" {"arm64" if is_arm64() else "x64"} >nul && set', shell=True,
                            capture_output=True, text=True, errors="replace")
    if result.returncode != 0:
        raise StepError(f"{vcvars} failed:\n{result.stdout}{result.stderr}")
    env = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line and not line.startswith("="))
    # Make sure CMake picks MSVC and not another compiler on the PATH (e.g. MinGW's gcc).
    env["CC"] = env["CXX"] = "cl"
    return env


def build_env() -> tuple[dict[str, str], Path, Path]:
    """Return the build environment and the CMake and Ninja executables to use in it."""
    env = visual_studio_env() if sys.platform == "win32" else dict(os.environ)
    # `uv run` puts the executables of the cmake and ninja script dependencies first on our PATH
    # (the Visual Studio environment may prefer other copies).
    cmake, ninja = shutil.which("cmake"), shutil.which("ninja")
    if not cmake or not ninja:
        raise StepError("cmake or ninja not found; run this script with `uv run`, which installs them")
    cmake, ninja = Path(cmake), Path(ninja)
    log(f"Using {subprocess.run([cmake, '--version'], capture_output=True, text=True).stdout.splitlines()[0]}")
    return env, cmake, ninja


def build_blender(name: str, *, ref: str | None = None, update: bool = False, config: str = "full",
                  build_type: str = "Release", force: bool = False) -> Path:
    """Build Blender ``name`` from source and return the installed binary."""
    source = ensure_worktree(name, ref, update=update)
    commit = git_output(source, "rev-parse", "HEAD")
    install_dir = BLENDER_BIN_DIR / name
    blender = blender_executable(install_dir)
    build_info = install_dir / BUILD_INFO
    if not force and blender.is_file() and build_info.is_file() and \
            build_info.read_text().startswith(f"commit={commit}\nconfig={config}\nbuild_type={build_type}\n"):
        log(f"Reusing Blender build {blender} ({commit[:10]})")
        return blender

    config_file = source / "build_files" / "cmake" / "config" / f"blender_{config}.cmake"
    if not config_file.is_file():
        available = sorted(p.stem.removeprefix("blender_") for p in config_file.parent.glob("blender_*.cmake"))
        raise StepError(f"Unknown build configuration {config!r} (available: {', '.join(available)})")

    log("Pulling git LFS files of the source worktree")
    run(["git", "-C", source, "lfs", "pull"])
    libs = ensure_libraries(source)
    env, cmake, ninja = build_env()

    build_dir = BUILD_DIR / name
    if force:
        log(f"Removing build directory {build_dir}")
        shutil.rmtree(build_dir, ignore_errors=True)
    build_dir.mkdir(parents=True, exist_ok=True)
    configure_cmd: list[str | Path] = [
        cmake, "-G", "Ninja", "-S", source, "-B", build_dir, f"-C{config_file}",
        f"-DCMAKE_MAKE_PROGRAM={ninja.as_posix()}", f"-DCMAKE_BUILD_TYPE={build_type}", f"-DLIBDIR={libs.as_posix()}",
        f"-DCMAKE_INSTALL_PREFIX={install_dir.as_posix()}",
    ]
    configure_args = build_dir / CONFIGURE_ARGS
    configure_key = "\n".join(str(c) for c in configure_cmd)
    if (build_dir / "build.ninja").is_file() and configure_args.is_file() and \
            configure_args.read_text() == configure_key:
        log(f"Reusing CMake configuration in {build_dir}")
    else:
        log(f"Configuring Blender ({config}, {build_type}) in {build_dir}")
        configure_args.unlink(missing_ok=True)
        # Start from a fresh cache, so features disabled by an earlier failed configure come back.
        (build_dir / "CMakeCache.txt").unlink(missing_ok=True)
        run(configure_cmd, env=env)
        configure_args.write_text(configure_key)

    log(f"Building Blender {name} ({commit[:10]}), this takes a while the first time")
    build_info.unlink(missing_ok=True)
    run([cmake, "--build", build_dir, "--target", "install"], env=env)
    if not blender.is_file():
        raise StepError(f"Blender binary not found at {blender} after building")
    build_info.write_text(f"commit={commit}\nconfig={config}\nbuild_type={build_type}\nsource={source}\n")
    log(f"Blender {blender_binary_version(blender)} ({name}, {commit[:10]}) installed at {blender}")
    return blender


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", type=validate_build_name,
                        help="Build name, used as the version by the other scripts (e.g. main)")
    parser.add_argument("--ref", help="Blender git ref to build (default: the name)")
    parser.add_argument("--update", action="store_true",
                        help="Fetch the ref again and move the existing source worktree to its latest commit")
    parser.add_argument("--config", default="full",
                        help="CMake preset build_files/cmake/config/blender_<config>.cmake (default: full)")
    parser.add_argument("--build-type", choices=BUILD_TYPES, default="Release", help="CMake build type")
    parser.add_argument("--force", action="store_true", help="Delete the build directory and build from scratch")
    args = parser.parse_args()
    build_blender(args.name, ref=args.ref, update=args.update, config=args.config,
                  build_type=args.build_type, force=args.force)
    return 0


if __name__ == "__main__":
    main_wrapper(main)
