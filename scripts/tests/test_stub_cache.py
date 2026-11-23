import subprocess

import pytest

import generate_stubs
from _common import StepError
from generate_stubs import blender_fingerprint, rst_is_current, stale_reason, tree_revision


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


MARKER = "blender=build-1\nblender_path=b.exe\nsource=s\ncommit=abc\ngenerator_rev=def+dirty.123\n"


def test_marker_matching_commit_build_and_generator_is_current():
    assert stale_reason(MARKER, "abc", "def+dirty.123", "build-1") is None


@pytest.mark.parametrize(
    ("commit", "generator_rev", "blender", "reason"),
    [
        ("other", "def+dirty.123", "build-1", "another Blender commit"),
        (None, None, None, "another Blender commit"),
        ("abc", "def+dirty.123", "build-2", "another Blender build"),
        ("abc", "def+dirty.123", None, "another Blender build"),
        ("abc", "def", "build-1", "another version of the stub generator"),
        ("abc", None, "build-1", "another version of the stub generator"),
    ],
)
def test_marker_stale(commit, generator_rev, blender, reason):
    assert reason in stale_reason(MARKER, commit, generator_rev, blender)


def test_marker_without_generator_rev_is_stale():
    """Markers written before the generator was recorded say nothing about it, so their stubs are regenerated."""
    assert "stub generator" in stale_reason("commit=abc\nblender=build-1\n", "abc", "def", "build-1")


def test_marker_recording_the_binary_path_instead_of_the_build_is_stale():
    """Markers written before the build was recorded name the binary, which a rebuild replaces in place."""
    old = "blender=/bin/blender\nsource=s\ncommit=abc\ngenerator_rev=def\n"
    assert "another Blender build" in stale_reason(old, "abc", "def", "commit=abc,config=headless")


def test_rst_marker_is_current_for_the_same_commit_and_build():
    marker = "commit=abc\nblender=build-1\n"
    assert rst_is_current(marker, "abc", "build-1")
    assert not rst_is_current(marker, "def", "build-1")
    assert not rst_is_current(marker, "abc", "build-2")


def test_rst_marker_of_only_the_commit_is_stale():
    """The old marker held the bare commit and nothing about the build."""
    assert not rst_is_current("abc", "abc", "build-1")


def test_fingerprint_of_a_source_build_is_its_build_info(tmp_path):
    (tmp_path / ".build-info").write_text("commit=abc\nconfig=headless\nconfigure=h1\nsource=s\n")
    (tmp_path / "blender").write_text("")
    fingerprint = blender_fingerprint(tmp_path / "blender")
    assert "\n" not in fingerprint
    assert all(part in fingerprint for part in ("commit=abc", "config=headless", "configure=h1"))
    (tmp_path / ".build-info").write_text("commit=abc\nconfig=headless\nconfigure=h2\nsource=s\n")
    assert blender_fingerprint(tmp_path / "blender") != fingerprint


def test_fingerprint_of_a_macos_source_build_finds_the_build_info_above_the_bundle(tmp_path):
    (tmp_path / ".build-info").write_text("commit=abc\n")
    binary = tmp_path / "Blender.app" / "Contents" / "MacOS" / "Blender"
    binary.parent.mkdir(parents=True)
    binary.write_text("")
    assert "commit=abc" in blender_fingerprint(binary)


def test_fingerprint_of_a_release_is_its_version(tmp_path, monkeypatch):
    output = "Color management: ignored\nBlender 5.2.0\n\tbuild date: 2026-07-01\n\tbuild hash: 1234abcd\n"
    monkeypatch.setattr(generate_stubs, "blender_version_output", lambda blender: output)
    (tmp_path / "blender").write_text("")
    assert blender_fingerprint(tmp_path / "blender") == "Blender 5.2.0, build date: 2026-07-01, build hash: 1234abcd"


def test_node_socket_views_replace_fake_bpy_module_generator(tmp_path):
    """Blender's fork writes each built-in node's socket view; fake-bpy-module's own default-state one then stands
    aside, so its classes don't sit unused next to Blender's."""
    (tmp_path / "bpy.types.ShaderNodeMath.rst").write_text("")
    assert not generate_stubs.blender_declares_node_sockets(tmp_path)
    (tmp_path / "bpy.types._ShaderNodeMath_inputs.rst").write_text("")
    assert generate_stubs.blender_declares_node_sockets(tmp_path)


def test_all_generators_leave_out_runtime(tmp_path):
    (tmp_path / generate_stubs.BUILTIN_STUB_GEN).parent.mkdir(parents=True)
    (tmp_path / generate_stubs.BUILTIN_STUB_GEN).write_text("", encoding="utf-8")
    (tmp_path / generate_stubs.RUNTIME_STUB_GEN).write_text("", encoding="utf-8")

    assert generate_stubs.resolve_generators("main", tmp_path, generate_stubs.ALL) == [
        generate_stubs.FAKE_BPY,
        generate_stubs.BUILTIN,
    ]
    assert generate_stubs.resolve_generators("main", tmp_path, generate_stubs.RUNTIME) == [generate_stubs.RUNTIME]


def test_runtime_revision_covers_the_whole_python_api_folder(repo):
    (repo / "doc" / "python_api").mkdir(parents=True)
    (repo / "doc" / "python_api" / "sphinx_doc_gen.py").write_text("print(1)\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "docs")
    clean = generate_stubs.generator_revision(generate_stubs.RUNTIME, repo)

    (repo / "doc" / "python_api" / "sphinx_doc_gen.py").write_text("print(2)\n")

    assert generate_stubs.generator_revision(generate_stubs.RUNTIME, repo) != clean
    assert generate_stubs.generator_revision(generate_stubs.BUILTIN, repo) == clean
