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
  uv run scripts/build_blender.py 5.2 --ref v5.2.0 --target makesrna --system-libs --config lite

``--target`` builds one CMake target instead of installing Blender (``makesrna`` for the source-stub prototypes,
which also leaves ``compile_commands.json`` in the build directory). ``--system-libs`` configures without the
precompiled libraries, for a target that needs none of them.

See https://developer.blender.org/docs/handbook/building_blender/ for the prerequisites (Visual
Studio with the C++ workload on Windows, Xcode on macOS, the build dependencies on Linux, plus
git LFS).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from _common import CACHE_DIR, StepError, git_output, log, main_wrapper, run, validate_build_name
from download_blender import BLENDER_BIN_DIR, BUILD_INFO, blender_executable
from generate_stubs import blender_binary_version, ensure_worktree

BUILD_DIR = CACHE_DIR / "blender-build"
LIBS_DIR = CACHE_DIR / "blender-libs"
CONFIGURE_ARGS = "configure-args.txt"
BUILD_TYPES = ["Release", "RelWithDebInfo", "Debug"]
# Options turned back on after a preset (``-D`` after ``-C`` overrides its forced cache entries).
# The headless preset turns off FFmpeg, Audaspace and NDOF, and with them the Python API they add
# (``FFmpegSettings`` and the FFMPEG file format, ``sound.mixdown``'s parameters, the NDOF
# preferences), so the stubs generated from a headless build would miss it.
PRESET_OPTIONS = {"headless": ["-DWITH_CODEC_FFMPEG=ON", "-DWITH_AUDASPACE=ON", "-DWITH_INPUT_NDOF=ON"]}


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
    if (
        subprocess.run(
            ["git", "-C", str(libs), "cat-file", "-e", f"{commit}^{{commit}}"], capture_output=True
        ).returncode
        != 0
    ):
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
    vswhere = Path(
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        "Microsoft Visual Studio",
        "Installer",
        "vswhere.exe",
    )
    if not vswhere.is_file():
        raise StepError(f"vswhere.exe not found at {vswhere}; install Visual Studio with the C++ workload")
    component = "Microsoft.VisualStudio.Component.VC.Tools." + ("ARM64" if is_arm64() else "x86.x64")
    install = subprocess.run(
        [str(vswhere), "-latest", "-products", "*", "-requires", component, "-property", "installationPath"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not install:
        raise StepError(
            "No Visual Studio installation with the C++ build tools found "
            "(install the 'Desktop development with C++' workload)"
        )
    vcvars = Path(install, "VC", "Auxiliary", "Build", "vcvarsall.bat")
    log(f"Using Visual Studio at {install}")
    result = subprocess.run(
        f'"{vcvars}" {"arm64" if is_arm64() else "x64"} >nul && set',
        shell=True,
        capture_output=True,
        text=True,
        errors="replace",
    )
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


def preset_file(source: Path, config: str) -> Path:
    return source / "build_files" / "cmake" / "config" / f"blender_{config}.cmake"


def configure_command(
    cmake: Path,
    ninja: Path,
    *,
    source: Path,
    build_dir: Path,
    config: str,
    build_type: str,
    libs: Path | None,
    install_dir: Path,
    defines: tuple[str, ...] = (),
) -> list[str | Path]:
    """The CMake command that configures the build of ``source`` with the preset ``config`` (``libs`` None: system
    libraries)."""
    return [
        cmake,
        "-G",
        "Ninja",
        "-S",
        source,
        "-B",
        build_dir,
        f"-C{preset_file(source, config)}",
        *PRESET_OPTIONS.get(config, []),
        *(f"-D{define}" for define in defines),
        f"-DCMAKE_MAKE_PROGRAM={ninja.as_posix()}",
        f"-DCMAKE_BUILD_TYPE={build_type}",
        *([f"-DLIBDIR={libs.as_posix()}"] if libs else []),
        f"-DCMAKE_INSTALL_PREFIX={install_dir.as_posix()}",
        "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
    ]


def configure_hash(
    *,
    source: Path,
    build_dir: Path,
    config: str,
    build_type: str,
    install_dir: Path,
    system_libs: bool = False,
    defines: tuple[str, ...] = (),
) -> str:
    """Hash of the arguments that configure the build, which ``.build-info`` records. CMake's and Ninja's own paths
    are left out: they come from uv's script environment, which moves when it is recreated."""
    cmd = configure_command(
        Path("cmake"),
        Path("ninja"),
        source=source,
        build_dir=build_dir,
        config=config,
        build_type=build_type,
        libs=None if system_libs else LIBS_DIR / lib_platform(),
        install_dir=install_dir,
        defines=defines,
    )
    return hashlib.sha256("\n".join(str(c) for c in cmd).encode()).hexdigest()[:16]


def build_info_text(*, commit: str, config: str, build_type: str, configure: str, source: Path) -> str:
    return f"commit={commit}\nconfig={config}\nbuild_type={build_type}\nconfigure={configure}\nsource={source}\n"


def is_current_build(build_info: str, *, commit: str, config: str, build_type: str, configure: str) -> bool:
    """Whether the build that ``.build-info`` reads ``build_info`` matches the requested one."""
    fields = dict(line.split("=", 1) for line in build_info.splitlines() if "=" in line)
    wanted = {"commit": commit, "config": config, "build_type": build_type, "configure": configure}
    return all(fields.get(key) == value for key, value in wanted.items())


def build_blender(
    name: str,
    *,
    ref: str | None = None,
    update: bool = False,
    config: str = "full",
    build_type: str = "Release",
    force: bool = False,
    target: str = "install",
    system_libs: bool = False,
    defines: tuple[str, ...] = (),
) -> Path:
    """Build Blender ``name`` from source and return the installed binary (or, for another ``target`` than
    ``install``, the build directory)."""
    source = ensure_worktree(name, ref, update=update)
    commit = git_output(source, "rev-parse", "HEAD")
    install_dir = BLENDER_BIN_DIR / name
    blender = blender_executable(install_dir)
    build_info = install_dir / BUILD_INFO
    build_dir = BUILD_DIR / name
    configure = configure_hash(
        source=source,
        build_dir=build_dir,
        config=config,
        build_type=build_type,
        install_dir=install_dir,
        system_libs=system_libs,
        defines=defines,
    )
    if (
        target == "install"
        and not force
        and blender.is_file()
        and build_info.is_file()
        and is_current_build(
            build_info.read_text(), commit=commit, config=config, build_type=build_type, configure=configure
        )
    ):
        log(f"Reusing Blender build {blender} ({commit[:10]})")
        return blender

    config_file = preset_file(source, config)
    if not config_file.is_file():
        available = sorted(p.stem.removeprefix("blender_") for p in config_file.parent.glob("blender_*.cmake"))
        raise StepError(f"Unknown build configuration {config!r} (available: {', '.join(available)})")

    log("Pulling git LFS files of the source worktree")
    run(["git", "-C", source, "lfs", "pull"])
    libs = None if system_libs else ensure_libraries(source)
    env, cmake, ninja = build_env()

    if force:
        log(f"Removing build directory {build_dir}")
        shutil.rmtree(build_dir, ignore_errors=True)
    build_dir.mkdir(parents=True, exist_ok=True)
    configure_cmd = configure_command(
        cmake,
        ninja,
        source=source,
        build_dir=build_dir,
        config=config,
        build_type=build_type,
        libs=libs,
        install_dir=install_dir,
        defines=defines,
    )
    configure_args = build_dir / CONFIGURE_ARGS
    configure_key = "\n".join(str(c) for c in configure_cmd)
    if (
        (build_dir / "build.ninja").is_file()
        and configure_args.is_file()
        and configure_args.read_text() == configure_key
    ):
        log(f"Reusing CMake configuration in {build_dir}")
    else:
        log(f"Configuring Blender ({config}, {build_type}) in {build_dir}")
        configure_args.unlink(missing_ok=True)
        # Start from a fresh cache, so features disabled by an earlier failed configure come back.
        (build_dir / "CMakeCache.txt").unlink(missing_ok=True)
        run(configure_cmd, env=env)
        configure_args.write_text(configure_key)

    if target != "install":
        log(f"Building the target {target} of Blender {name} ({commit[:10]})")
        run([cmake, "--build", build_dir, "--target", target], env=env)
        log(f"Built {target} in {build_dir}")
        return build_dir

    log(f"Building Blender {name} ({commit[:10]}), this takes a while the first time")
    build_info.unlink(missing_ok=True)
    run([cmake, "--build", build_dir, "--target", "install"], env=env)
    if not blender.is_file():
        raise StepError(f"Blender binary not found at {blender} after building")
    build_info.write_text(
        build_info_text(commit=commit, config=config, build_type=build_type, configure=configure, source=source)
    )
    log(f"Blender {blender_binary_version(blender)} ({name}, {commit[:10]}) installed at {blender}")
    return blender


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "name", type=validate_build_name, help="Build name, used as the version by the other scripts (e.g. main)"
    )
    parser.add_argument("--ref", help="Blender git ref to build (default: the name)")
    parser.add_argument(
        "--update",
        action="store_true",
        help="Fetch the ref again and move the existing source worktree to its latest commit",
    )
    parser.add_argument(
        "--config", default="full", help="CMake preset build_files/cmake/config/blender_<config>.cmake (default: full)"
    )
    parser.add_argument("--build-type", choices=BUILD_TYPES, default="Release", help="CMake build type")
    parser.add_argument("--force", action="store_true", help="Delete the build directory and build from scratch")
    parser.add_argument(
        "--target", default="install", help="CMake target to build instead of installing Blender (e.g. makesrna)"
    )
    parser.add_argument(
        "--system-libs", action="store_true", help="Configure without the precompiled libraries (system libraries)"
    )
    parser.add_argument(
        "--define", action="append", default=[], metavar="VAR=VALUE", help="Extra CMake cache entry (-DVAR=VALUE)"
    )
    args = parser.parse_args()
    build_blender(
        args.name,
        ref=args.ref,
        update=args.update,
        config=args.config,
        build_type=args.build_type,
        force=args.force,
        target=args.target,
        system_libs=args.system_libs,
        defines=tuple(args.define),
    )
    return 0


if __name__ == "__main__":
    main_wrapper(main)
