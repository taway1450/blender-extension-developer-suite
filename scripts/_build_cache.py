"""What the build caches CI publishes as GitHub releases have in common: Blender's (``blender_cache.py``) and ty's
(``ty_cache.py``). Each is a few ``.tar.zst`` archives plus a ``manifest.json`` (written last, with the archives'
checksums) in a release ``<prefix>-<date>-<commit>``; CI keeps the newest few, and the release ``<prefix>`` holds a
copy of the newest manifest whose ``archives_url`` names the release with the archives. An archive that may outgrow
one release asset is published in parts, ``<archive>.000``, ``<archive>.001``, ... (``tar_create_split``).

Both build systems decide what to rebuild by timestamps, which a fresh checkout resets to the current time, so a
restore gives every source the old time ``EPOCH`` except the files that differ from the cache's commit
(``repair_timestamps``).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path

from _common import StepError, log, run

GITHUB_REPO = "taway1450/blender-extension-developer-suite"
MANIFEST = "manifest.json"
# GitHub's limit for one release asset.
MAX_ASSET_BYTES = 2 * 1024**3
# The size of the parts of a split archive.
PART_BYTES = 1900 * 1024**2
# The time unchanged sources get on restore: older than anything a cache was built from.
EPOCH = 946684800  # 2000-01-01T00:00:00Z


def release_url(tag: str) -> str:
    return f"https://github.com/{GITHUB_REPO}/releases/download/{tag}"


def require_linux(what: str) -> None:
    if not sys.platform.startswith("linux"):
        raise StepError(f"The {what} cache is only published for Linux")


def require_tools(*tools: str) -> None:
    missing = [tool for tool in tools if not shutil.which(tool)]
    if missing:
        raise StepError(f"Missing {', '.join(missing)} (e.g. `apt-get install {' '.join(missing)}`)")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def first_line(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.splitlines()[0] if result.returncode == 0 and result.stdout else ""


def os_name() -> str:
    try:
        fields = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)
    except OSError:
        return platform.platform()
    return fields.get("PRETTY_NAME", "").strip('"') or platform.platform()


def tar_create(archive: Path, root: Path, members: list[str]) -> None:
    run(["tar", "--use-compress-program", "zstd -T0 -3", "-cf", archive, "-C", root, *members])


def tar_extract(archive: Path, root: Path) -> None:
    # CI builds as another user than the cloud session's root; keep the extracting user as the owner.
    run(["tar", "--use-compress-program", "zstd -d -T0", "--no-same-owner", "-xf", archive, "-C", root])


def tar_create_split(archive: Path, root: Path, members: list[str], exclude: tuple[str, ...] = ()) -> list[Path]:
    """Like ``tar_create``, but written as the parts ``<archive>.000``, ``<archive>.001``, ... of at most
    ``PART_BYTES`` each, without the paths ``exclude`` (relative to ``root``, like the members)."""
    tar_cmd = ["tar", "--use-compress-program", "zstd -T0 -3", "-cf", "-", "-C", str(root)]
    tar_cmd += [f"--exclude={path}" for path in exclude] + members
    split_cmd = ["split", "-b", str(PART_BYTES), "-d", "-a", "3", "-", f"{archive}."]
    print(f"    $ {' '.join(tar_cmd)} | {' '.join(split_cmd)}", flush=True)
    with subprocess.Popen(tar_cmd, stdout=subprocess.PIPE) as tar:
        split = subprocess.run(split_cmd, stdin=tar.stdout)
    if tar.returncode != 0 or split.returncode != 0:
        raise StepError(f"Packing {archive.name} failed (tar: {tar.returncode}, split: {split.returncode})")
    return archive_parts(archive.parent, archive.name)


def archive_parts(directory: Path, archive: str) -> list[Path]:
    """The files of the archive ``archive`` in ``directory``, in order: the archive itself, or its parts."""
    return sorted(p for p in directory.iterdir() if is_archive_part(p.name, archive))


def is_archive_part(name: str, archive: str) -> bool:
    suffix = name.removeprefix(archive)
    return name.startswith(archive) and (not suffix or (len(suffix) == 4 and suffix[0] == "." and suffix[1:].isdigit()))


def tar_extract_parts(parts: list[Path], root: Path, *, remove: bool = False) -> None:
    """Extract the archive whose parts are ``parts``, in that order, into ``root``; with ``remove``, each part is
    deleted once it is read, so the archive and its content never need the disk at the same time."""
    cmd = ["tar", "--use-compress-program", "zstd -d -T0", "--no-same-owner", "-xf", "-", "-C", str(root)]
    print(f"    $ cat {' '.join(part.name for part in parts)} | {' '.join(cmd)}", flush=True)
    with subprocess.Popen(cmd, stdin=subprocess.PIPE) as tar:
        try:
            for part in parts:
                with part.open("rb") as source:
                    shutil.copyfileobj(source, tar.stdin, length=1 << 20)
                if remove:
                    part.unlink()
        except BrokenPipeError:
            pass  # tar gave up; its exit code says so
        finally:
            tar.stdin.close()
    if tar.returncode != 0:
        raise StepError(f"Extracting {parts[0].name} failed with exit code {tar.returncode}")


def asset_table(out: Path) -> dict[str, dict]:
    """Checksum and size of every archive (or part of one) in ``out``, for the manifest; refuses one GitHub would
    not take."""
    assets = {}
    for archive in sorted(p for p in out.iterdir() if ".tar.zst" in p.name):
        size = archive.stat().st_size
        if size > MAX_ASSET_BYTES:
            raise StepError(f"{archive.name} is {size / 1024**3:.2f} GiB, over GitHub's 2 GiB limit per release asset")
        assets[archive.name] = {"sha256": sha256(archive), "size": size}
        log(f"{archive.name}: {size / 1024**2:.0f} MB")
    return assets


def write_manifest(out: Path, manifest: dict) -> None:
    (out / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n")


def download(url: str, target: Path, expected: dict | None = None) -> Path:
    print(f"    GET {url}", flush=True)
    started = time.monotonic()
    tmp = target.with_name(target.name + ".part")
    with urllib.request.urlopen(url) as response, tmp.open("wb") as out:
        shutil.copyfileobj(response, out, length=1 << 20)
    tmp.replace(target)
    size = target.stat().st_size
    log(f"Downloaded {target.name}: {size / 1024**2:.0f} MB in {time.monotonic() - started:.0f} s")
    if expected and (size != expected["size"] or sha256(target) != expected["sha256"]):
        raise StepError(f"{target.name} does not match the manifest (the cache may be being republished; retry)")
    return target


def download_archive(url: str, archive: str, assets: dict[str, dict], downloads: Path) -> list[Path]:
    """Download the archive ``archive`` (or its parts) that the manifest's ``assets`` list from the release ``url``,
    checked against their checksums; no files if the manifest has none."""
    names = sorted(name for name in assets if is_archive_part(name, archive))
    return [download(f"{url}/{name}", downloads / name, assets[name]) for name in names]


def release_exists(tag: str) -> bool:
    """Whether the release ``tag`` of the repo is published with its manifest (the last file uploaded)."""
    try:
        with urllib.request.urlopen(f"{release_url(tag)}/{MANIFEST}") as response:
            return response.status == 200
    except OSError:
        return False


def download_manifest(url: str, downloads: Path) -> tuple[dict, str]:
    """The manifest at ``url`` and the URL of the release with its archives (``archives_url`` for the pointer
    release, else ``url`` itself)."""
    url = url.rstrip("/")
    manifest = json.loads(download(f"{url}/{MANIFEST}", downloads / MANIFEST).read_text())
    if archives_url := manifest.get("archives_url"):
        url = archives_url.rstrip("/")
        log(f"Newest cache: {url}")
    return manifest, url


def set_mtime(path: str | os.PathLike[str], when: float) -> None:
    """Give ``path`` itself the access and modification time ``when``. A symlink gets its own time where the
    platform can set it (Linux, macOS); elsewhere (Windows) it is left alone, since setting it would change the
    file it points to."""
    if os.utime in os.supports_follow_symlinks:
        os.utime(path, (when, when), follow_symlinks=False)
    elif not os.path.islink(path):
        os.utime(path, (when, when))


def walk_paths(repo: Path, skip: tuple[str, ...] = ()) -> Iterator[str]:
    """Every file and directory under ``repo``, except ``.git`` anywhere and the top-level entries ``skip``."""
    for directory, subdirs, files in os.walk(repo):
        if ".git" in subdirs:
            subdirs.remove(".git")
        if directory == str(repo):
            subdirs[:] = [d for d in subdirs if d not in skip]
        else:
            # Directories count too: a cargo build script may watch one.
            yield directory
        for file in files:
            if file != ".git" and not (directory == str(repo) and file in skip):
                yield os.path.join(directory, file)


def backdate(repo: Path, skip: tuple[str, ...] = ()) -> int:
    """Give every path of ``repo`` (see ``walk_paths``) the time ``EPOCH``; return how many."""
    count = 0
    for path in walk_paths(repo, skip):
        set_mtime(path, EPOCH)
        count += 1
    return count


def differing_files(repo: Path, base_commit: str) -> list[str]:
    """The files of the checkout ``repo`` that differ from ``base_commit``: committed, uncommitted or untracked."""

    def names(*args: str) -> list[str]:
        out = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout
        return [n.decode() for n in out.split(b"\0") if n]

    return names("diff", "--name-only", "-z", base_commit, "--") + names(
        "ls-files", "--others", "--exclude-standard", "-z"
    )


def repair_timestamps(repo: Path, base_commit: str, skip: tuple[str, ...] = ()) -> int:
    """Give every file and directory of the checkout ``repo`` the old time ``EPOCH``, except the files that differ
    from ``base_commit`` (``differing_files``), which get the current time. Return how many differ.

    The build then sees exactly those files as newer than the restored outputs. ``skip`` leaves top-level entries
    alone, e.g. the build's own output directory inside the checkout.
    """
    differing = differing_files(repo, base_commit)
    backdate(repo, skip)
    now = time.time()
    count = 0
    for name in differing:
        path = repo / name
        if path.exists() or path.is_symlink():
            set_mtime(path, now)
            count += 1
    # Store the new timestamps in the index, so the next `git status` does not rehash every file.
    subprocess.run(["git", "-C", str(repo), "update-index", "-q", "--refresh"], capture_output=True)
    return count
