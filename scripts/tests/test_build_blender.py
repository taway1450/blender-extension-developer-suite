"""The configure arguments ``build_blender`` passes, and when it reuses the installed build: only for the same
source (uncommitted edits included), preset, build type and configure arguments."""

from pathlib import Path

import pytest
from test_stub_cache import git

import build_blender
import download_blender
import generate_stubs
from _common import StepError
from build_blender import PRESET_OPTIONS, build_info_text, configure_command, configure_hash, is_current_build


def command(config: str) -> list[str]:
    return [
        str(arg)
        for arg in configure_command(
            Path("cmake"),
            Path("ninja"),
            source=Path("src"),
            build_dir=Path("build"),
            config=config,
            build_type="Release",
            libs=Path("libs"),
            install_dir=Path("bin"),
        )
    ]


def test_headless_build_turns_the_api_options_back_on_after_its_preset():
    # The headless preset turns off FFmpeg, Audaspace and NDOF, and with them the Python API
    # they add (FFmpegSettings, sound.mixdown, the NDOF preferences), so the stubs would miss it.
    # A -D after the -C preset overrides the preset's forced cache entries.
    cmd = command("headless")
    preset = next(i for i, arg in enumerate(cmd) if arg.startswith("-C"))
    assert cmd[preset] == f"-C{Path('src/build_files/cmake/config/blender_headless.cmake')}"
    assert PRESET_OPTIONS["headless"]
    assert all(option in cmd[preset + 1 :] for option in PRESET_OPTIONS["headless"])


def test_other_presets_keep_their_options():
    assert not set(PRESET_OPTIONS["headless"]) & set(command("full"))


def hash_of(build_type: str = "Release", config: str = "headless") -> str:
    return configure_hash(
        source=Path("src"), build_dir=Path("build"), config=config, build_type=build_type, install_dir=Path("bin")
    )


def test_configure_hash_is_stable_and_follows_the_configure_arguments(monkeypatch):
    assert hash_of() == hash_of()
    assert hash_of(build_type="Debug") != hash_of()
    assert hash_of(config="full") != hash_of()
    before = hash_of()
    monkeypatch.setitem(PRESET_OPTIONS, "headless", [*PRESET_OPTIONS["headless"], "-DWITH_CYCLES=OFF"])
    assert hash_of() != before


INFO = build_info_text(
    commit="abc", revision="abc", config="headless", build_type="Release", configure="h1", source=Path("s")
)


def test_build_info_matching_everything_is_current():
    assert is_current_build(INFO, revision="abc", config="headless", build_type="Release", configure="h1")


@pytest.mark.parametrize(
    "changed",
    [{"revision": "def"}, {"config": "full"}, {"build_type": "Debug"}, {"configure": "h2"}],
)
def test_build_info_differing_in_anything_is_stale(changed):
    current = {"revision": "abc", "config": "headless", "build_type": "Release", "configure": "h1"}
    assert not is_current_build(INFO, **{**current, **changed})


def test_build_info_without_configure_hash_is_stale():
    """Builds recorded before the configure hash say nothing about their options (e.g. PRESET_OPTIONS)."""
    old = "commit=abc\nrevision=abc\nconfig=headless\nbuild_type=Release\nsource=s\n"
    assert not is_current_build(old, revision="abc", config="headless", build_type="Release", configure="h1")


def test_build_info_without_revision_is_stale():
    """Builds recorded before the revision say nothing about uncommitted edits."""
    old = "commit=abc\nconfig=headless\nbuild_type=Release\nconfigure=h1\nsource=s\n"
    assert not is_current_build(old, revision="abc", config="headless", build_type="Release", configure="h1")


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
    configure = build_blender.configure_hash(
        source=worktree,
        build_dir=build_blender.BUILD_DIR / "main",
        config="full",
        build_type="Release",
        install_dir=bin_dir / "main",
    )
    (bin_dir / "main" / download_blender.BUILD_INFO).write_text(
        build_info_text(
            commit=commit, revision=commit, config="full", build_type="Release", configure=configure, source=worktree
        )
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
