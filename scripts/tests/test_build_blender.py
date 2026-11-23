"""When ``build_blender`` reuses the installed build: only for the same source, uncommitted edits included."""

import pytest

import build_blender
import download_blender
import generate_stubs
from _common import StepError
from test_stub_cache import git


@pytest.fixture
def source(tmp_path, monkeypatch):
    """A Blender "worktree" and an install dir for the build ``main``, built from its clean commit."""
    worktree = tmp_path / "src"
    worktree.mkdir()
    (worktree / "main.c").write_text("int main(void) { return 0; }\n")
    git(worktree, "init", "-q")
    git(worktree, "add", ".")
    git(worktree, "commit", "-q", "-m", "init")
    bin_dir = tmp_path / "bin"
    monkeypatch.setattr(download_blender, "BLENDER_BIN_DIR", bin_dir)
    monkeypatch.setattr(build_blender, "BLENDER_BIN_DIR", bin_dir)
    monkeypatch.setattr(build_blender, "ensure_worktree", lambda name, ref, update: worktree)
    blender = download_blender.blender_executable(bin_dir / "main")
    blender.parent.mkdir(parents=True)
    blender.write_text("")
    commit = git(worktree, "rev-parse", "HEAD")
    (bin_dir / "main" / download_blender.BUILD_INFO).write_text(
        f"commit={commit}\nrevision={commit}\nconfig=full\nbuild_type=Release\nsource={worktree}\n"
    )
    return worktree


def builds(**kwargs) -> bool:
    """Whether ``build_blender`` goes on to build; the fake worktree has no CMake preset, so building fails early."""
    try:
        build_blender.build_blender("main", **kwargs)
    except StepError as error:
        assert "Unknown build configuration" in str(error)
        return True
    return False


def test_same_source_reuses_the_build(source):
    assert not builds()


def test_uncommitted_edit_is_built(source):
    (source / "main.c").write_text("int main(void) { return 1; }\n")
    assert builds()


def test_new_untracked_file_is_built(source):
    (source / "extra.c").write_text("int extra;\n")
    assert builds()


def test_reverting_an_edit_built_before_builds_again(source):
    """The installed build has the edit; going back to the clean commit must not reuse it."""
    (source / "main.c").write_text("int main(void) { return 1; }\n")
    dirty = generate_stubs.tree_revision(source, ".")
    info = download_blender.BLENDER_BIN_DIR / "main" / download_blender.BUILD_INFO
    info.write_text(info.read_text().replace(f"revision={git(source, 'rev-parse', 'HEAD')}", f"revision={dirty}"))
    assert not builds()
    git(source, "checkout", "--", "main.c")
    assert builds()


def test_other_config_or_build_type_is_built(source):
    assert builds(config="lite")
    assert builds(build_type="Debug")


def test_stubs_follow_the_build_not_the_worktree_commit(source, monkeypatch):
    commit = git(source, "rev-parse", "HEAD")
    assert generate_stubs.blender_revision("main", source) == commit
    (source / "main.c").write_text("int main(void) { return 1; }\n")
    dirty = generate_stubs.tree_revision(source, ".")
    info = download_blender.BLENDER_BIN_DIR / "main" / download_blender.BUILD_INFO
    info.write_text(info.read_text().replace(f"revision={commit}", f"revision={dirty}"))
    assert generate_stubs.blender_revision("main", source) == dirty
    # A release has no build info: its stubs follow the source worktree's commit.
    assert generate_stubs.blender_revision("5.2", source) == commit


def test_explicit_ref_moves_an_existing_worktree(tmp_path, monkeypatch):
    """``--ref other`` on a build whose worktree exists checks ``other`` out instead of reusing the old checkout."""
    upstream = tmp_path / "blender"
    upstream.mkdir()
    (upstream / "f").write_text("1\n")
    git(upstream, "init", "-q", "-b", "main")
    git(upstream, "add", ".")
    git(upstream, "commit", "-q", "-m", "one")
    first = git(upstream, "rev-parse", "HEAD")
    (upstream / "f").write_text("2\n")
    git(upstream, "commit", "-q", "-am", "two")
    git(upstream, "branch", "other")
    git(upstream, "reset", "-q", "--hard", first)
    monkeypatch.setattr(generate_stubs, "BLENDER_SUBMODULE", upstream)
    monkeypatch.setattr(generate_stubs, "CACHE_DIR", tmp_path / "cache")

    worktree = generate_stubs.ensure_worktree("feature", "main")
    assert git(worktree, "rev-parse", "HEAD") == first
    assert generate_stubs.ensure_worktree("feature") == worktree
    assert git(worktree, "rev-parse", "HEAD") == first
    generate_stubs.ensure_worktree("feature", "other")
    assert git(worktree, "rev-parse", "HEAD") == git(upstream, "rev-parse", "other")
