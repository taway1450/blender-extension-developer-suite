"""Prototype of a ty build cache: restore ty-blender/ruff-blender/target and repair the source mtimes.

Measured with it on 2026-11-23 (cloud-session-build-cache.md section 0). Not a task: run it by hand.

  python3 -I ty_restore_proto.py backdate
      The CI side: give every source file and directory of ruff-blender the time EPOCH *before* building, so the
      fingerprints cargo records hold that time (a build script with no rerun-if-changed, e.g. ty_vendored's,
      is fingerprinted by the newest mtime of its package as a value, not by comparing mtimes).
  python3 -I ty_restore_proto.py restore <archive.tar.zst> <cache commit> [--fresh-clone] [--no-repair]
      The session side: replace target/ with the archive, then backdate everything except the files that differ
      from <cache commit>, which keep the current time. --fresh-clone first gives every file the current time,
      as a fresh `git clone` does.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path("/home/user/blender-extension-developer-suite/ty-blender/ruff-blender")
EPOCH = 946684800  # 2000-01-01, as in scripts/blender_cache.py


def sources():
    """Every file and directory of the checkout except .git and target/ (directories count: build scripts that
    watch a directory see its mtime)."""
    for directory, subdirs, files in os.walk(REPO):
        if ".git" in subdirs:
            subdirs.remove(".git")
        if Path(directory) == REPO and "target" in subdirs:
            subdirs.remove("target")
        if Path(directory) != REPO:
            yield directory
        for f in files:
            if f != ".git":
                yield os.path.join(directory, f)


def set_all(t: float) -> int:
    n = 0
    for path in sources():
        os.utime(path, (t, t), follow_symlinks=False)
        n += 1
    return n


def git_names(*args: str) -> list[str]:
    out = subprocess.run(["git", "-C", str(REPO), *args], check=True, capture_output=True).stdout
    return [n.decode() for n in out.split(b"\0") if n]


def repair(commit: str) -> None:
    t = time.time()
    n = set_all(EPOCH)
    differing = git_names("diff", "--name-only", "-z", commit, "--") + git_names(
        "ls-files", "--others", "--exclude-standard", "-z"
    )
    now = time.time()
    for name in differing:
        p = REPO / name
        if p.exists():
            os.utime(p, (now, now), follow_symlinks=False)
    subprocess.run(["git", "-C", str(REPO), "update-index", "-q", "--refresh"], capture_output=True)
    print(f"repair {time.time() - t:.1f}s: {n} paths backdated, {len(differing)} differ from {commit[:10]}")


def restore(archive: str, commit: str, *, fresh_clone: bool, no_repair: bool) -> None:
    if fresh_clone:
        print("fresh-clone mtimes on", set_all(time.time()), "paths")
    t = time.time()
    subprocess.run(["rm", "-rf", str(REPO / "target")], check=True)
    subprocess.run(
        ["tar", "--use-compress-program", "zstd -d -T0", "--no-same-owner", "-xf", archive, "-C", str(REPO)],
        check=True,
    )
    print(f"extract {time.time() - t:.1f}s")
    if not no_repair:
        repair(commit)


def main() -> None:
    if sys.argv[1:2] == ["backdate"]:
        print("backdated", set_all(EPOCH), "paths")
    elif sys.argv[1:2] == ["restore"] and len(sys.argv) >= 4:
        restore(
            sys.argv[2], sys.argv[3], fresh_clone="--fresh-clone" in sys.argv, no_repair="--no-repair" in sys.argv
        )
    else:
        sys.exit(__doc__)


main()
