"""The configure arguments ``build_blender`` passes, and when it reuses the installed build: only for the same
source (uncommitted edits included), preset, build type and configure arguments."""

from pathlib import Path

import pytest
from test_stub_cache import git

import _common
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


def test_ccache_build_runs_with_one_locale_whatever_the_machine_has():
    env = {"LANG": "de_DE.UTF-8", "LC_ALL": "de_DE.UTF-8", "LC_MESSAGES": "fr_FR.UTF-8", "CCACHE_DIR": "/elsewhere"}
    build_blender.use_ccache(env)
    # ccache hashes these four: CI and a cloud session must agree on them for a compile to hit.
    assert {var: env.get(var) for var in ("LANG", "LC_ALL", "LC_CTYPE", "LC_MESSAGES")} == {
        "LANG": "C.UTF-8",
        "LC_ALL": None,
        "LC_CTYPE": None,
        "LC_MESSAGES": None,
    }
    # A ccache setting of the caller wins over the default.
    assert env["CCACHE_DIR"] == "/elsewhere"
    assert env["CCACHE_COMPILERCHECK"] == "content"


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


@pytest.fixture
def lfs_commands(monkeypatch):
    """A repo whose LFS listing has one pointer file; records the commands ``pull_lfs_files`` runs."""
    commands = []
    monkeypatch.setattr(build_blender, "git_output", lambda repo, *args: "0a1b * full.png\n2c3d - pointer.png")
    monkeypatch.setattr(build_blender, "run_fetch", commands.append)
    return commands


def test_lfs_pull_uses_the_repo_remote_by_default(lfs_commands):
    build_blender.pull_lfs_files(Path("repo"))
    assert lfs_commands == [["git", "-C", Path("repo"), "lfs", "pull"]]


def test_lfs_pull_from_another_server_is_for_that_command_only(lfs_commands):
    build_blender.pull_lfs_files(Path("repo"), "https://example.com/lfs")
    assert lfs_commands == [["git", "-C", Path("repo"), "-c", "lfs.url=https://example.com/lfs", "lfs", "pull"]]


def test_no_lfs_pull_without_pointer_files(monkeypatch, lfs_commands):
    monkeypatch.setattr(build_blender, "git_output", lambda repo, *args: "0a1b * full.png")
    build_blender.pull_lfs_files(Path("repo"), "https://example.com/lfs")
    assert lfs_commands == []


@pytest.fixture
def failing_runs(monkeypatch):
    """Makes ``_common.run`` fail the given number of times first; records the calls and the sleeps."""
    state = {"failures": 0, "runs": 0, "sleeps": []}

    def run(cmd, *, cwd=None, env=None):
        state["runs"] += 1
        if state["runs"] <= state["failures"]:
            raise StepError("refused")

    monkeypatch.setattr(_common, "run", run)
    monkeypatch.setattr(_common.time, "sleep", state["sleeps"].append)
    return state


def test_fetch_is_not_retried_without_the_variable(monkeypatch, failing_runs):
    monkeypatch.delenv(_common.FETCH_RETRY_WAITS, raising=False)
    failing_runs["failures"] = 1
    with pytest.raises(StepError):
        _common.run_fetch(["git", "fetch"])
    assert failing_runs["runs"] == 1


def test_fetch_is_retried_after_each_wait(monkeypatch, failing_runs):
    monkeypatch.setenv(_common.FETCH_RETRY_WAITS, "1 2 3")
    failing_runs["failures"] = 2
    _common.run_fetch(["git", "fetch"])
    assert (failing_runs["runs"], failing_runs["sleeps"]) == (3, [1.0, 2.0])


def test_fetch_fails_after_the_last_wait(monkeypatch, failing_runs):
    monkeypatch.setenv(_common.FETCH_RETRY_WAITS, "1 2")
    failing_runs["failures"] = 5
    with pytest.raises(StepError):
        _common.run_fetch(["git", "fetch"])
    assert (failing_runs["runs"], failing_runs["sleeps"]) == (3, [1.0, 2.0])


LIBS_COMMIT = "0123456789abcdef0123456789abcdef01234567"
PINNED, NEWEST = "blender-libs-linux_x64-0123456789", "blender-libs-linux_x64"


@pytest.fixture
def libs_releases(tmp_path, monkeypatch):
    """Stand-ins for the releases CI publishes the libraries in: ``published`` maps a release to its manifest;
    ``asked`` lists the releases looked at and ``extracted`` the archive parts extracted, in order."""
    published, asked, extracted = {}, [], []
    monkeypatch.setattr(build_blender, "LIBS_DIR", tmp_path / "libs")
    monkeypatch.setattr(build_blender.shutil, "which", lambda tool: tool)

    def download_manifest(url, downloads):
        assert downloads.is_dir()
        tag = url.rsplit("/", 1)[1]
        asked.append(tag)
        if tag not in published:
            raise OSError("HTTP Error 404: Not Found")
        return published[tag], f"https://host/{published[tag].get('tag', tag)}"

    def download_archive(url, archive, assets, downloads):
        names = sorted(name for name in assets if name.startswith(archive))
        for name in names:
            (downloads / name).write_bytes(b"part")
        return [downloads / name for name in names]

    def tar_extract_parts(parts, root, *, remove=False):
        extracted.extend(part.name for part in parts)
        (root / "linux_x64" / ".git").mkdir(parents=True)

    monkeypatch.setattr(build_blender, "download_manifest", download_manifest)
    monkeypatch.setattr(build_blender, "download_archive", download_archive)
    monkeypatch.setattr(build_blender, "tar_extract_parts", tar_extract_parts)
    return published, asked, extracted


def libs_manifest(commit: str = LIBS_COMMIT, **overrides) -> dict:
    parts = {f"blender-libs-linux_x64.tar.zst.00{n}": {"sha256": "", "size": 4} for n in range(2)}
    base = {"format": build_blender.LIBS_FORMAT, "platform": "linux_x64", "commit": commit, "assets": parts}
    return {**base, "tag": f"blender-libs-linux_x64-{commit[:10]}", **overrides}


def test_libraries_come_from_the_release_of_the_pinned_commit(tmp_path, libs_releases):
    published, asked, extracted = libs_releases
    published[PINNED] = published[NEWEST] = libs_manifest()
    assert build_blender.restore_libraries("linux_x64", LIBS_COMMIT)
    assert asked == [PINNED]
    assert extracted == ["blender-libs-linux_x64.tar.zst.000", "blender-libs-linux_x64.tar.zst.001"]
    assert (tmp_path / "libs" / "linux_x64" / ".git").is_dir()
    assert not (tmp_path / "libs" / "linux_x64.download").exists()


def test_libraries_of_another_commit_come_from_the_newest_release(libs_releases):
    published, asked, extracted = libs_releases
    published[NEWEST] = libs_manifest("f" * 40)
    assert build_blender.restore_libraries("linux_x64", LIBS_COMMIT)
    assert asked == [PINNED, NEWEST]
    assert len(extracted) == 2


def test_without_a_libraries_release_the_caller_clones(tmp_path, libs_releases):
    _, asked, extracted = libs_releases
    assert not build_blender.restore_libraries("linux_x64", LIBS_COMMIT)
    assert asked == [PINNED, NEWEST]
    assert extracted == []
    assert not (tmp_path / "libs" / "linux_x64").exists()


@pytest.mark.parametrize("overrides", [{"format": 99}, {"platform": "linux_arm64"}, {"assets": {}}])
def test_an_unusable_libraries_release_is_skipped(libs_releases, overrides):
    published, asked, extracted = libs_releases
    published[PINNED] = libs_manifest(**overrides)
    assert not build_blender.restore_libraries("linux_x64", LIBS_COMMIT)
    assert asked == [PINNED, NEWEST]
    assert extracted == []


def test_a_failed_extraction_leaves_no_half_clone(tmp_path, monkeypatch, libs_releases):
    published, _, _ = libs_releases
    published[PINNED] = libs_manifest()

    def broken(parts, root, *, remove=False):
        (root / "linux_x64" / ".git").mkdir(parents=True)
        raise StepError("Extracting failed")

    monkeypatch.setattr(build_blender, "tar_extract_parts", broken)
    assert not build_blender.restore_libraries("linux_x64", LIBS_COMMIT)
    assert not (tmp_path / "libs" / "linux_x64").exists()


def test_no_libraries_release_is_tried_without_the_archive_tools(monkeypatch, libs_releases):
    published, asked, _ = libs_releases
    published[PINNED] = libs_manifest()
    monkeypatch.setattr(build_blender.shutil, "which", lambda tool: None)
    assert not build_blender.restore_libraries("linux_x64", LIBS_COMMIT)
    assert asked == []
