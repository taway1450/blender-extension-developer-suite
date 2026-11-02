# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""Download an official Blender release binary into ``.cache/blender-bin/<version>``.

Python port of fake-bpy-module's ``tools/utils/download_blender.sh``: the download URLs and
MD5 checksum URLs are read from ``fake-bpy-module/src/versions.yml``.

Usage:
  uv run scripts/download_blender.py 5.2
  uv run scripts/download_blender.py 5.2 --force
"""

from __future__ import annotations

import argparse
import hashlib
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

from _common import CACHE_DIR, FAKE_BPY_SRC, StepError, exe, log, main_wrapper, validate_release_version

BLENDER_BIN_DIR = CACHE_DIR / "blender-bin"
DOWNLOADS_DIR = CACHE_DIR / "downloads"


def platform_key() -> str:
    if sys.platform == "win32":
        return "WIN64"
    if sys.platform.startswith("linux"):
        return "LINUX"
    if sys.platform == "darwin":
        return "MACOSX"
    raise StepError(f"Unsupported platform {sys.platform!r}")


def blender_executable(install_dir: Path) -> Path:
    if sys.platform == "darwin":
        return install_dir / "Blender.app" / "Contents" / "MacOS" / "Blender"
    return install_dir / exe("blender")


def cached_blender(version: str) -> Path | None:
    blender = blender_executable(BLENDER_BIN_DIR / version)
    return blender if blender.is_file() else None


def release_urls(version: str) -> tuple[str, str]:
    """Return the (download URL, checksum URL) of a Blender release for this platform."""
    import yaml

    versions = yaml.safe_load((FAKE_BPY_SRC / "versions.yml").read_text(encoding="utf-8"))
    key = platform_key()
    if key == "WIN64" and platform.machine().lower() in ("arm64", "aarch64"):
        raise StepError("fake-bpy-module's versions.yml has no Windows ARM64 downloads")
    url = (versions.get(f"BLENDER_DOWNLOAD_URL_{key}") or {}).get(version)
    checksum_url = (versions.get("BLENDER_CHECKSUM_URL") or {}).get(version)
    if not url or not checksum_url:
        supported = ", ".join(versions["SUPPORTED_BLENDER_VERSIONS_BASE"])
        raise StepError(f"No Blender {version} download for {key} in versions.yml (supported: {supported})")
    return url, checksum_url


def fetch(url: str, target: Path) -> None:
    print(f"    GET {url}", flush=True)
    tmp = target.with_name(target.name + ".part")
    with urllib.request.urlopen(url) as response, tmp.open("wb") as out:
        shutil.copyfileobj(response, out, length=1 << 20)
    tmp.replace(target)


def verify_checksum(archive: Path, checksum_url: str) -> bool:
    with urllib.request.urlopen(checksum_url) as response:
        checksums = response.read().decode("utf-8", errors="replace")
    expected = next(
        (line.split()[0] for line in checksums.splitlines() if line.strip().endswith(archive.name)), None
    )
    if expected is None:
        raise StepError(f"Unable to find {archive.name} in {checksum_url}")
    md5 = hashlib.md5()
    with archive.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            md5.update(chunk)
    if md5.hexdigest() != expected.lower():
        print(f"    Checksum mismatch for {archive.name}: expected {expected}, got {md5.hexdigest()}")
        return False
    return True


def extract(archive: Path, target: Path) -> None:
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(target)
    elif archive.name.endswith((".tar.xz", ".tar.bz2", ".tar.gz")):
        with tarfile.open(archive) as tf:
            tf.extractall(target, filter="data")
    elif archive.name.endswith(".dmg") and sys.platform == "darwin":
        mount = target.with_name(target.name + "-mnt")
        mount.mkdir(parents=True)
        subprocess.run(["hdiutil", "attach", "-nobrowse", "-quiet", "-mountpoint", str(mount), str(archive)],
                       check=True)
        try:
            shutil.copytree(mount / "Blender.app", target / "Blender.app", symlinks=True)
        finally:
            subprocess.run(["hdiutil", "detach", "-quiet", str(mount)], check=True)
            mount.rmdir()
    else:
        raise StepError(f"Unknown archive format: {archive.name}")


def download_blender(version: str, force: bool = False) -> Path:
    """Return the cached Blender binary for ``version``, downloading it first if needed."""
    if not force and (blender := cached_blender(version)):
        log(f"Reusing downloaded Blender {version}: {blender}")
        return blender

    url, checksum_url = release_urls(version)
    archive = DOWNLOADS_DIR / url.rsplit("/", 1)[-1]
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    if archive.is_file() and verify_checksum(archive, checksum_url):
        log(f"Found verified Blender {version} download {archive}")
    else:
        log(f"Downloading Blender {version}")
        fetch(url, archive)
        if not verify_checksum(archive, checksum_url):
            archive.unlink()
            raise StepError(f"Blender {version} download from {url} failed the checksum verification")
        log("Checksum verified")

    install_dir = BLENDER_BIN_DIR / version
    tmp_dir = BLENDER_BIN_DIR / f"{version}.tmp"
    shutil.rmtree(tmp_dir, ignore_errors=True)
    tmp_dir.mkdir(parents=True)
    log(f"Extracting {archive.name}")
    extract(archive, tmp_dir)
    # Most archives contain a single top-level directory (e.g. blender-5.2.0-windows-x64/); flatten it.
    entries = list(tmp_dir.iterdir())
    root = entries[0] if len(entries) == 1 and entries[0].is_dir() and entries[0].suffix != ".app" else tmp_dir
    shutil.rmtree(install_dir, ignore_errors=True)
    root.replace(install_dir)
    shutil.rmtree(tmp_dir, ignore_errors=True)

    blender = blender_executable(install_dir)
    if not blender.is_file():
        raise StepError(f"Blender binary not found at {blender} after extracting {archive.name}")
    log(f"Blender {version} installed at {blender}")
    return blender


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("version", type=validate_release_version, help="Blender version as X.Y (e.g. 5.2)")
    parser.add_argument("--force", action="store_true", help="Download and extract again even if cached")
    args = parser.parse_args()
    download_blender(args.version, args.force)
    return 0


if __name__ == "__main__":
    main_wrapper(main)
