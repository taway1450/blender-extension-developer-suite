"""Publish ty's cargo build (the ``dev`` profile's ``target/``) as a cache (``pack``, in CI) and restore it in a fresh
checkout so that the next ``ty:build`` is a no-op or incremental instead of a 9-minute cold build (``restore``, in a
cloud session or its setup script). Linux only.

``pack`` builds ty from a clean ``ty-blender/ruff-blender`` checkout and writes two files to ``.cache/ty-cache/``,
which CI uploads to the GitHub release ``ty-cache-<date>-<commit>`` and keeps the last few of; the release
``ty-cache`` holds a copy of the newest manifest that points there (``.github/workflows/ty-cache.yml``):

  - ``ty-target-dev.tar.zst``: ``target/debug`` with rustc's incremental data, so an edit after a restore rebuilds
    in the usual ~20 s;
  - ``manifest.json``: the ``ruff-blender`` commit, the toolchain, the absolute paths it was built at, and the
    archive's checksum.

Cargo decides what to rebuild by comparing source and output timestamps, which a fresh checkout resets, and it
records the newest timestamp of a package whose build script names no inputs (``ty_vendored``) as a value. So:

  - ``pack`` first gives every source file and directory the old time ``EPOCH``, then builds, so the recorded
    values are ``EPOCH``;
  - ``restore`` gives every source that matches the cache's commit ``EPOCH`` too, and the files that differ from it
    (committed, uncommitted or untracked) the current time, so cargo rebuilds exactly those.

Measured in docs/research/cloud-session-build-cache.md section 0: a restore after a fresh clone makes the next
build a 1.4-s no-op; without the timestamp repair it would recompile every workspace crate (30 s).

Usage:
  uv run scripts/ty_cache.py pack
  uv run scripts/ty_cache.py restore
  uv run scripts/ty_cache.py restore --release ty-cache-20261123-3872f740fc
  uv run scripts/ty_cache.py restore --url https://example.com/ty-cache
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import time
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from _build_cache import (
    asset_table,
    backdate,
    differing_files,
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
    walk_paths,
    write_manifest,
)
from _common import CACHE_DIR, REPO_ROOT, TY_SUBMODULE, StepError, git_output, log, main_wrapper
from build_ty import RUFF_DIR, build_ty, ensure_checkout

FORMAT = 2
PROFILE = "dev"
OUT_DIR = CACHE_DIR / "ty-cache"
ARCHIVE = f"ty-target-{PROFILE}.tar.zst"
TARGET = RUFF_DIR / "target"
# The parts of target/ the dev profile uses; another profile's directory would only make the archive bigger.
MEMBERS = ("debug", ".rustc_info.json", "CACHEDIR.TAG")
# Variables that change which crates cargo compiles incrementally, and with that every workspace crate's fingerprint.
# Cargo also turns incremental compilation off by default when ``CI`` is set (as on every GitHub runner).
INCREMENTAL_OVERRIDES = ("CARGO_INCREMENTAL", "CARGO_PROFILE_DEV_INCREMENTAL", "CARGO_BUILD_INCREMENTAL", "CI")


def default_url() -> str:
    """Where CI publishes the newest cache; ``TY_CACHE_URL`` overrides it. The release ``ty-cache`` only holds the
    newest manifest, whose ``archives_url`` names the release with the archive."""
    return os.environ.get("TY_CACHE_URL") or release_url("ty-cache")


def cargo_home() -> str:
    return str(Path(os.environ.get("CARGO_HOME") or Path.home() / ".cargo").resolve())


def toolchain() -> str:
    """The Rust toolchain ``ruff-blender`` pins (``rust-toolchain.toml``)."""
    pinned = tomllib.loads((RUFF_DIR / "rust-toolchain.toml").read_text(encoding="utf-8"))
    return pinned["toolchain"]["channel"]


# --- pack ----------------------------------------------------------------------------------------------------------


def pack() -> Path:
    """Build ty from the clean ``ruff-blender`` checkout and write its cache to ``.cache/ty-cache/``."""
    require_linux("ty build")
    require_tools("tar", "zstd")
    ensure_checkout()
    commit = git_output(RUFF_DIR, "rev-parse", "HEAD")
    if dirty := differing_files(RUFF_DIR, commit):
        raise StepError(f"ruff-blender has uncommitted changes ({', '.join(dirty[:5])}...); pack a clean checkout")

    # A cloud session builds with cargo's defaults: incremental for the workspace crates only. An override (on
    # GitHub's runners, ``CI=true``) changes every workspace crate's fingerprint and drops rustc's incremental data,
    # so the restored build would recompile them all.
    for var in INCREMENTAL_OVERRIDES:
        if os.environ.pop(var, None) is not None:
            log(f"Unsetting {var}: the cache has to match a build with cargo's defaults")
    log(f"Setting every source of ruff-blender to an old time, so cargo records that time ({commit[:10]})")
    backdate(RUFF_DIR, skip=("target",))
    build_ty(PROFILE)
    incremental = TARGET / "debug" / "incremental"
    if not incremental.is_dir() or not any(incremental.iterdir()):
        raise StepError(f"{incremental} is empty: the build was not incremental, so a restore would recompile it all")

    out = OUT_DIR
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    log(f"Packing {TARGET / 'debug'}")
    tar_create(out / ARCHIVE, TARGET, [m for m in MEMBERS if (TARGET / m).exists()])
    rustc = subprocess.run(["rustc", "--version"], cwd=RUFF_DIR, capture_output=True, text=True).stdout.strip()
    manifest = {
        "format": FORMAT,
        "profile": PROFILE,
        "commit": commit,
        "ty_blender_commit": git_output(TY_SUBMODULE, "rev-parse", "HEAD"),
        "toolchain": toolchain(),
        "rustc": rustc,
        "repo_root": str(REPO_ROOT),
        "cargo_home": cargo_home(),
        "machine": platform.machine(),
        "os": os_name(),
        "cc": first_line(["cc", "--version"]),
        "suite_commit": git_output(REPO_ROOT, "rev-parse", "HEAD"),
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "assets": asset_table(out),
    }
    write_manifest(out, manifest)
    log(f"ty build cache: {out}")
    return out


# --- restore -------------------------------------------------------------------------------------------------------


def check_manifest(manifest: dict) -> None:
    """Refuse a cache this checkout and machine cannot use; warn about one cargo will mostly rebuild."""
    if manifest.get("format") != FORMAT:
        raise StepError(f"Unsupported cache format {manifest.get('format')!r} (expected {FORMAT})")
    if manifest.get("machine") != platform.machine():
        raise StepError(f"The cache was built on {manifest.get('machine')}, this machine is {platform.machine()}")
    if manifest.get("repo_root") != str(REPO_ROOT):
        # rustc's incremental data and every dep-info file hold absolute paths.
        raise StepError(f"The cache was built at {manifest.get('repo_root')}, but this checkout is at {REPO_ROOT}")
    if manifest.get("cargo_home") != cargo_home():
        log(f"Warning: the cache was built with CARGO_HOME={manifest.get('cargo_home')}, here it is {cargo_home()}")


def ensure_commit(commit: str) -> bool:
    """Whether ``commit`` is in the ruff-blender checkout, fetching it from its remote if needed."""

    def known() -> bool:
        cmd = ["git", "-C", str(RUFF_DIR), "cat-file", "-e", f"{commit}^{{commit}}"]
        return subprocess.run(cmd, capture_output=True).returncode == 0

    if known():
        return True
    log(f"Fetching the cache's ruff-blender commit {commit[:10]}")
    subprocess.run(["git", "-C", str(RUFF_DIR), "fetch", "-q", "origin", commit])
    return known()


def touch_all(repo: Path, skip: tuple[str, ...]) -> None:
    """Give every source the current time, so cargo checks all of them (correct, but every workspace crate
    recompiles)."""
    now = time.time()
    for path in walk_paths(repo, skip):
        os.utime(path, (now, now), follow_symlinks=False)


def restore(url: str | None = None, *, force: bool = False) -> None:
    require_linux("ty build")
    require_tools("tar", "zstd")
    shutil.rmtree(OUT_DIR, ignore_errors=True)
    OUT_DIR.mkdir(parents=True)
    manifest, url = download_manifest(url or default_url(), OUT_DIR)
    check_manifest(manifest)
    commit = manifest["commit"]
    log(f"ty build cache: ruff-blender {commit[:10]}, Rust {manifest['toolchain']}, built {manifest['created']}")

    ensure_checkout()
    if (TARGET / "debug").exists() and not force:
        raise StepError(f"{TARGET / 'debug'} exists already; --force replaces it with the cache")
    if overrides := [var for var in INCREMENTAL_OVERRIDES if var in os.environ]:
        log(f"Warning: {', '.join(overrides)} is set here; the cache was built without it, so cargo will rebuild it")
    if manifest["toolchain"] != toolchain():
        log(
            f"Warning: the cache was built with Rust {manifest['toolchain']}, ruff-blender now pins {toolchain()}; "
            "cargo will rebuild everything"
        )
    archive = download(f"{url}/{ARCHIVE}", OUT_DIR / ARCHIVE, manifest["assets"][ARCHIVE])

    log(f"Extracting into {TARGET}")
    shutil.rmtree(TARGET / "debug", ignore_errors=True)
    TARGET.mkdir(exist_ok=True)
    tar_extract(archive, TARGET)
    archive.unlink()

    if ensure_commit(commit):
        changed = repair_timestamps(RUFF_DIR, commit, skip=("target",))
        log(f"ruff-blender: {changed} files differ from the cache's commit {commit[:10]}, the rest got an old time")
    else:
        log(f"Warning: the cache's commit {commit[:10]} is not in ruff-blender; every crate of it will recompile")
        touch_all(RUFF_DIR, skip=("target",))
    log("Restored ty's build; the next `mise run ty:build` rebuilds only what differs")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("pack", help="Build ty from a clean checkout and write its cache to .cache/ty-cache/")
    restore_parser = commands.add_parser("restore", help="Download and restore ty's build cache")
    source = restore_parser.add_mutually_exclusive_group()
    source.add_argument("--url", help="Where the cache's files are (default: the newest build CI published)")
    source.add_argument(
        "--release", help="Restore this release instead of the newest, e.g. ty-cache-20261123-3872f740fc"
    )
    restore_parser.add_argument("--force", action="store_true", help="Replace an existing target/debug with the cache")
    args = parser.parse_args()
    if args.command == "pack":
        pack()
    else:
        restore(release_url(args.release) if args.release else args.url, force=args.force)
    return 0


if __name__ == "__main__":
    main_wrapper(main)
