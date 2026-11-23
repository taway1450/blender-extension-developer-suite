"""What ty_cache.py's restore leaves cargo to rebuild, and which caches a checkout refuses."""

import os
import platform

import pytest
from test_stub_cache import git

import ty_cache
from _build_cache import EPOCH, backdate, repair_timestamps
from _common import REPO_ROOT, StepError


@pytest.fixture
def repo(tmp_path):
    """A crate checkout with its build output in target/ (gitignored)."""
    (tmp_path / "crates" / "vendored" / "typeshed").mkdir(parents=True)
    (tmp_path / "crates" / "vendored" / "typeshed" / "os.pyi").write_text("")
    (tmp_path / "crates" / "lib.rs").write_text("// lib\n")
    (tmp_path / ".gitignore").write_text("target/\n")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "one")
    (tmp_path / "target" / "debug").mkdir(parents=True)
    (tmp_path / "target" / "debug" / "ty").write_text("")
    return tmp_path


def test_backdate_covers_directories_but_not_the_skipped_target(repo):
    target_time = (repo / "target" / "debug" / "ty").stat().st_mtime
    backdate(repo, skip=("target",))
    # A build script that watches a directory sees the directory's time.
    assert (repo / "crates" / "vendored" / "typeshed").stat().st_mtime == EPOCH
    assert (repo / "crates" / "lib.rs").stat().st_mtime == EPOCH
    assert (repo / "target" / "debug" / "ty").stat().st_mtime == target_time
    assert (repo / "target").stat().st_mtime != EPOCH


def test_repair_keeps_the_current_time_on_what_differs_and_leaves_target_alone(repo):
    cache_commit = git(repo, "rev-parse", "HEAD")
    (repo / "crates" / "lib.rs").write_text("// edited\n")
    target_time = (repo / "target" / "debug" / "ty").stat().st_mtime

    assert repair_timestamps(repo, cache_commit, skip=("target",)) == 1
    assert (repo / "crates" / "lib.rs").stat().st_mtime > EPOCH
    assert (repo / "crates" / "vendored" / "typeshed" / "os.pyi").stat().st_mtime == EPOCH
    assert (repo / "target" / "debug" / "ty").stat().st_mtime == target_time


def manifest(**overrides):
    return {
        "format": ty_cache.FORMAT,
        "machine": platform.machine(),
        "repo_root": str(REPO_ROOT),
        "cargo_home": ty_cache.cargo_home(),
    } | overrides


def test_matching_manifest_is_accepted():
    ty_cache.check_manifest(manifest())


@pytest.mark.parametrize(
    "overrides",
    [{"format": 0}, {"machine": "sparc"}, {"repo_root": os.path.join(os.sep, "elsewhere")}],
)
def test_unusable_manifest_is_refused(overrides):
    with pytest.raises(StepError):
        ty_cache.check_manifest(manifest(**overrides))


def test_other_cargo_home_only_warns(capsys):
    ty_cache.check_manifest(manifest(cargo_home=os.path.join(os.sep, "other", ".cargo")))
    assert "CARGO_HOME" in capsys.readouterr().out
