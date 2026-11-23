"""The parts of blender_cache.py that decide what a restored build rebuilds, and which caches a checkout refuses."""

import os
import platform

import pytest
from test_stub_cache import git

import blender_cache
from _build_cache import EPOCH
from _common import REPO_ROOT, StepError


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "src").mkdir()
    for name in ("a.c", "b.c", "c.c"):
        (tmp_path / "src" / name).write_text(f"// {name}\n")
    (tmp_path / "empty.h").write_text("")
    (tmp_path / ".gitignore").write_text("ignored/\n")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "one")
    return tmp_path


def mtimes(repo):
    return {
        str(path.relative_to(repo)): path.stat().st_mtime
        for path in repo.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }


def test_unchanged_files_get_the_old_time(repo):
    assert blender_cache.repair_timestamps(repo, git(repo, "rev-parse", "HEAD")) == 0
    assert set(mtimes(repo).values()) == {EPOCH}


def test_files_differing_from_the_cache_commit_get_the_current_time(repo):
    cache_commit = git(repo, "rev-parse", "HEAD")
    (repo / "src" / "a.c").write_text("// committed later\n")
    git(repo, "commit", "-q", "-am", "two")
    (repo / "src" / "b.c").write_text("// uncommitted\n")
    (repo / "src" / "new.c").write_text("// untracked\n")
    (repo / "ignored").mkdir()
    (repo / "ignored" / "out.o").write_text("")
    (repo / "src" / "c.c").unlink()

    assert blender_cache.repair_timestamps(repo, cache_commit) == 3
    times = mtimes(repo)
    new = {name for name, mtime in times.items() if mtime != EPOCH}
    assert new == {os.path.join("src", "a.c"), os.path.join("src", "b.c"), os.path.join("src", "new.c")}
    # Ignored files are not sources: they keep the old time like everything else.
    assert times[os.path.join("ignored", "out.o")] == EPOCH


def test_index_is_refreshed(repo):
    blender_cache.repair_timestamps(repo, git(repo, "rev-parse", "HEAD"))
    assert git(repo, "status", "--porcelain") == ""
    assert git(repo, "diff-files", "--name-only") == ""


def manifest(**overrides):
    base = {
        "format": blender_cache.FORMAT,
        "name": "main",
        "machine": platform.machine(),
        "repo_root": str(REPO_ROOT),
        "compilers": {},
        "ccache": None,
    }
    return {**base, **overrides}


def test_a_matching_manifest_is_accepted():
    blender_cache.check_manifest(manifest(), "main", ccache_only=False)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"format": 99}, "Unsupported cache format"),
        ({"name": "other"}, "for the build 'other'"),
        ({"machine": "riscv"}, "built on riscv"),
        ({"repo_root": "/elsewhere"}, "only --ccache-only works"),
        ({"compilers": {"CC": {"path": "no-such-compiler-xyz", "version": ""}}}, "not installed here"),
        ({"cmake": "/root/.cache/uv/environments-v2/x/lib/python3.0/site-packages/cmake/data/bin/cmake"}, "CMake"),
        ({"ccache": {"path": "/no/such/ccache", "version": "ccache 4"}}, "which is missing"),
    ],
)
def test_unusable_caches_are_refused(overrides, message):
    with pytest.raises(StepError, match=message):
        blender_cache.check_manifest(manifest(**overrides), "main", ccache_only=False)


def test_ccache_only_works_from_another_path():
    blender_cache.check_manifest(manifest(repo_root="/elsewhere"), "main", ccache_only=True)
