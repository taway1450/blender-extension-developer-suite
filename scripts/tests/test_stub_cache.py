import subprocess

import pytest

from _common import StepError
from generate_stubs import stale_reason, tree_revision


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "gen.py").write_text("print(1)\n")
    (tmp_path / "README").write_text("outside src\n")
    (tmp_path / ".gitignore").write_text("src/generated/\n")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_clean_tree_is_its_commit(repo):
    assert tree_revision(repo, "src") == git(repo, "rev-parse", "HEAD")


def test_new_commit_changes_the_revision(repo):
    before = tree_revision(repo, "src")
    (repo / "src" / "gen.py").write_text("print(2)\n")
    git(repo, "commit", "-q", "-am", "fix")
    assert tree_revision(repo, "src") not in (before, f"{before}+dirty")
    assert tree_revision(repo, "src") == git(repo, "rev-parse", "HEAD")


def test_uncommitted_edits_change_the_revision(repo):
    commit = tree_revision(repo, "src")
    (repo / "src" / "gen.py").write_text("print(2)\n")
    first = tree_revision(repo, "src")
    assert first.startswith(f"{commit}+dirty.")
    assert tree_revision(repo, "src") == first
    (repo / "src" / "gen.py").write_text("print(3)\n")
    assert tree_revision(repo, "src") not in (commit, first)
    (repo / "src" / "gen.py").write_text("print(1)\n")
    assert tree_revision(repo, "src") == commit


def test_untracked_files_count_but_ignored_and_outside_files_do_not(repo):
    commit = tree_revision(repo, "src")
    (repo / "README").write_text("changed\n")
    (repo / "src" / "generated").mkdir()
    (repo / "src" / "generated" / "mod.rst").write_text("generated\n")
    assert tree_revision(repo, "src") == commit
    (repo / "src" / "new_mod.py").write_text("a\n")
    first = tree_revision(repo, "src")
    assert first.startswith(f"{commit}+dirty.")
    (repo / "src" / "new_mod.py").write_text("b\n")
    assert tree_revision(repo, "src") != first


def test_directory_that_is_not_a_checkout_is_an_error(repo):
    """An uninitialised submodule is an empty directory inside the superproject, whose HEAD git would report."""
    (repo / "submodule").mkdir()
    with pytest.raises(StepError):
        tree_revision(repo / "submodule", "src")


MARKER = "blender=b.exe\nsource=s\ncommit=abc\ngenerator_rev=def+dirty.123\n"


def test_marker_matching_commit_and_generator_is_current():
    assert stale_reason(MARKER, "abc", "def+dirty.123") is None


@pytest.mark.parametrize(
    ("commit", "generator_rev", "reason"),
    [
        ("other", "def+dirty.123", "another Blender commit"),
        (None, None, "another Blender commit"),
        ("abc", "def", "another version of the stub generator"),
        ("abc", None, "another version of the stub generator"),
    ],
)
def test_marker_stale(commit, generator_rev, reason):
    assert reason in stale_reason(MARKER, commit, generator_rev)


def test_marker_without_generator_rev_is_stale():
    """Markers written before the generator was recorded say nothing about it, so their stubs are regenerated."""
    assert "stub generator" in stale_reason("commit=abc\n", "abc", "def")
