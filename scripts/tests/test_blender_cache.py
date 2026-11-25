"""The parts of blender_cache.py that decide what a restored build rebuilds, and which caches a checkout refuses."""

import hashlib
import json
import os
import platform
import shutil
import sys
from pathlib import Path

import pytest
from test_stub_cache import git

import _build_cache
import blender_cache
import build_blender
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


@pytest.mark.parametrize(
    ("link_flags", "expected"),
    [
        ("-no-pie -Wl,--dependency-file=bin/makesdna.dir/link.d", None),
        ("-fuse-ld=lld -no-pie   -latomic", "lld"),
        ("-shared  -fuse-ld=mold -Wl,--dependency-file=x/link.d", "mold"),
        ('-fuse-ld="/usr/bin/ld.lld" -no-pie', "lld"),
    ],
)
def test_the_linker_is_read_from_the_link_commands(tmp_path, monkeypatch, link_flags, expected):
    monkeypatch.setattr(blender_cache, "BUILD_DIR", tmp_path)
    (tmp_path / "main").mkdir()
    (tmp_path / "main" / "build.ninja").write_text(
        "build a.o: C_COMPILER a.c\n  FLAGS = -fuse-ld=not-a-link-command\n"
        f"build bin/makesdna: CXX_EXECUTABLE_LINKER a.o\n  LINK_FLAGS = {link_flags}\n"
    )
    assert blender_cache.recorded_linker("main") == expected


@pytest.mark.parametrize(
    ("cached", "here", "warned"),
    [(None, None, False), ("lld", "lld", False), (None, "lld", True), ("lld", None, True), ("mold", "lld", True)],
)
def test_another_linker_than_the_cache_used_is_warned_about(monkeypatch, capsys, cached, here, warned):
    monkeypatch.setattr(blender_cache, "machine_linker", lambda compiler: here)
    compilers = {"CC": {"path": sys.executable, "version": ""}}
    blender_cache.check_manifest(manifest(compilers=compilers, linker=cached), "main", ccache_only=False)
    assert ("links everything again" in capsys.readouterr().out) is warned


def test_a_cache_without_a_recorded_linker_is_not_compared(monkeypatch, capsys):
    monkeypatch.setattr(blender_cache, "machine_linker", lambda compiler: "lld")
    compilers = {"CC": {"path": sys.executable, "version": ""}}
    blender_cache.check_manifest(manifest(compilers=compilers), "main", ccache_only=False)
    assert "links everything again" not in capsys.readouterr().out


def test_the_files_of_the_cmake_install_get_the_old_time(tmp_path):
    cmake = tmp_path / "site-packages" / "cmake" / "data" / "bin" / "cmake"
    module = (
        tmp_path / "site-packages" / "cmake" / "data" / "share" / "cmake-4.4" / "Modules" / "CMakeCInformation.cmake"
    )
    outside = tmp_path / "site-packages" / "cmake" / "__init__.py"
    for file in (cmake, module, outside):
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("")
    # The binary, the module and the three directories bin, share/cmake-4.4 and its Modules... all under data/.
    assert blender_cache.backdate_cmake(str(cmake)) == 6
    assert (cmake.stat().st_mtime, module.stat().st_mtime) == (EPOCH, EPOCH)
    assert outside.stat().st_mtime != EPOCH


def test_a_dry_run_without_a_cmake_run_gives_the_number_of_steps():
    stdout = "[1/8] Generating buildinfo.h\n[2/8] Building CXX object a.o\n[8/8] Install the project...\n"
    assert blender_cache.describe_dry_run(stdout, "") == "runs 3 build steps"


def test_a_dry_run_that_stops_at_cmake_says_why_instead_of_one_step():
    explanations = (
        "ninja explain: output build.ninja older than most recent input /uv/cmake/Modules/CMakeCInformation.cmake "
        "(1 vs 2)\nninja explain: build.ninja is dirty\n"
    )
    planned = blender_cache.describe_dry_run("[0/1] Re-running CMake...\n", explanations)
    assert planned.startswith("re-runs CMake first (output build.ninja older than most recent input /uv/cmake/")
    assert "1 build steps" not in planned


def test_a_cache_of_a_commit_the_remote_lost_is_refused_with_the_reason(monkeypatch):
    fetched = []
    monkeypatch.setattr(blender_cache, "has_blender_commit", lambda commit: False)
    monkeypatch.setattr(blender_cache, "run", lambda cmd: fetched.append(cmd[-2:]))
    with pytest.raises(StepError, match="was the branch rebased"):
        blender_cache.ensure_blender_commit("a" * 40, "typecheck-fixes")
    assert fetched == [["origin", "typecheck-fixes"]]


def test_a_commit_the_submodule_has_is_not_fetched(monkeypatch):
    monkeypatch.setattr(blender_cache, "has_blender_commit", lambda commit: True)
    monkeypatch.setattr(blender_cache, "run", lambda cmd: pytest.fail("fetched"))
    blender_cache.ensure_blender_commit("a" * 40, "typecheck-fixes")


def test_ccache_and_lfs_objects_are_restored_before_a_lost_commit_stops_the_restore(tmp_path, monkeypatch):
    done = []
    monkeypatch.setattr(blender_cache, "require_linux", lambda what: None)
    monkeypatch.setattr(blender_cache, "require_tools", lambda *tools: None)
    monkeypatch.setattr(blender_cache, "ensure_build_environment", lambda: None)
    for constant in ("OUT_DIR", "BUILD_DIR", "BLENDER_BIN_DIR", "CACHE_DIR"):
        monkeypatch.setattr(blender_cache, constant, tmp_path / constant)
    cache = manifest(commit="a" * 40, config="full", build_type="Release", created="", os="")
    cache["assets"] = {name: {} for name in ("ccache-main.tar.zst", "blender-build-main.tar.zst")}
    monkeypatch.setattr(blender_cache, "download_manifest", lambda url, downloads: (cache, "https://host/release"))
    monkeypatch.setattr(blender_cache, "download", lambda url, target, expected: done.append(target.name) or target)
    monkeypatch.setattr(blender_cache, "tar_extract", lambda archive, root: archive.touch())
    monkeypatch.setattr(blender_cache, "restore_lfs_objects", lambda *args: done.append("lfs objects"))

    def lost(commit, ref):
        raise StepError("The cache was built from Blender aaaaaaaaaa, which typecheck-fixes does not contain")

    monkeypatch.setattr(blender_cache, "ensure_blender_commit", lost)
    with pytest.raises(StepError, match="ccache and git LFS objects are restored"):
        blender_cache.restore("main")
    # The 900 MB build directory, of no use without the commit, is not downloaded.
    assert done == ["ccache-main.tar.zst", "lfs objects"]


def test_ccache_only_works_from_another_path():
    blender_cache.check_manifest(manifest(repo_root="/elsewhere"), "main", ccache_only=True)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("blender-libs-linux_x64.tar.zst", True),
        ("blender-libs-linux_x64.tar.zst.000", True),
        ("blender-libs-linux_x64.tar.zst.012", True),
        ("blender-libs-linux_x64.tar.zst.part", False),
        ("blender-libs-linux_x64.tar.zst.0000", False),
        ("blender-libs-linux_x64_debug.tar.zst.000", False),
        ("manifest.json", False),
    ],
)
def test_an_archive_is_one_file_or_numbered_parts(name, expected):
    assert _build_cache.is_archive_part(name, "blender-libs-linux_x64.tar.zst") is expected


def test_parts_are_listed_in_order_and_only_those_of_the_archive(tmp_path):
    for name in ("a.tar.zst.001", "a.tar.zst.000", "a.tar.zst.010", "b.tar.zst", "manifest.json"):
        (tmp_path / name).write_bytes(b"x")
    assert [p.name for p in _build_cache.archive_parts(tmp_path, "a.tar.zst")] == [
        "a.tar.zst.000",
        "a.tar.zst.001",
        "a.tar.zst.010",
    ]


def test_manifest_lists_archives_and_parts_with_their_checksums(tmp_path):
    (tmp_path / "a.tar.zst.000").write_bytes(b"first")
    (tmp_path / "a.tar.zst.001").write_bytes(b"second")
    (tmp_path / "b.tar.zst").write_bytes(b"whole")
    (tmp_path / "manifest.json").write_text("{}")
    assets = _build_cache.asset_table(tmp_path)
    assert list(assets) == ["a.tar.zst.000", "a.tar.zst.001", "b.tar.zst"]
    assert assets["a.tar.zst.001"] == {"sha256": hashlib.sha256(b"second").hexdigest(), "size": 6}


def test_a_part_over_the_asset_limit_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(_build_cache, "MAX_ASSET_BYTES", 3)
    (tmp_path / "a.tar.zst.000").write_bytes(b"four")
    with pytest.raises(StepError, match=r"a\.tar\.zst\.000 is .* over GitHub's 2 GiB limit"):
        _build_cache.asset_table(tmp_path)


def test_an_archive_is_downloaded_part_by_part_in_order(tmp_path, monkeypatch):
    fetched = []
    monkeypatch.setattr(
        _build_cache, "download", lambda url, target, expected: fetched.append((url, expected)) or target
    )
    assets = {"a.tar.zst.001": {"size": 2}, "a.tar.zst.000": {"size": 1}, "b.tar.zst": {"size": 3}}
    parts = _build_cache.download_archive("https://host/release", "a.tar.zst", assets, tmp_path)
    assert parts == [tmp_path / "a.tar.zst.000", tmp_path / "a.tar.zst.001"]
    assert fetched == [
        ("https://host/release/a.tar.zst.000", {"size": 1}),
        ("https://host/release/a.tar.zst.001", {"size": 2}),
    ]
    assert _build_cache.download_archive("https://host/release", "c.tar.zst", assets, tmp_path) == []


needs_archive_tools = pytest.mark.skipif(
    sys.platform == "win32" or not all(shutil.which(tool) for tool in ("tar", "zstd", "split")),
    reason="needs GNU tar, zstd and split",
)


@needs_archive_tools
def test_split_archive_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(_build_cache, "PART_BYTES", 4096)
    root, out, target = tmp_path / "root", tmp_path / "out", tmp_path / "target"
    for directory in (root / "libs" / "sub", root / "libs" / ".git" / "lfs", out, target):
        directory.mkdir(parents=True)
    content = os.urandom(10_000)  # does not compress, so the archive needs three parts
    (root / "libs" / "sub" / "data.bin").write_bytes(content)
    (root / "libs" / ".git" / "config").write_text("[core]\n")
    (root / "libs" / ".git" / "lfs" / "object").write_bytes(b"a copy of the checkout")

    parts = _build_cache.tar_create_split(out / "libs.tar.zst", root, ["libs"], exclude=("libs/.git/lfs",))
    assert [p.name for p in parts] == ["libs.tar.zst.000", "libs.tar.zst.001", "libs.tar.zst.002"]
    assert all(p.stat().st_size <= 4096 for p in parts)

    _build_cache.tar_extract_parts(parts, target, remove=True)
    assert (target / "libs" / "sub" / "data.bin").read_bytes() == content
    assert (target / "libs" / ".git" / "config").is_file()
    assert not (target / "libs" / ".git" / "lfs").exists()
    assert list(out.iterdir()) == []


@needs_archive_tools
def test_a_broken_archive_fails_to_extract(tmp_path):
    part = tmp_path / "a.tar.zst.000"
    part.write_bytes(b"not an archive")
    with pytest.raises(StepError, match=r"Extracting a\.tar\.zst\.000 failed"):
        _build_cache.tar_extract_parts([part], tmp_path)


LIBS_COMMIT = "0123456789abcdef0123456789abcdef01234567"


@pytest.fixture
def libs_pack(tmp_path, monkeypatch):
    """``pack_libraries`` on any machine: no tools needed, the libraries are an empty directory, and the archive is a
    stand-in file. Gives what was packed (the arguments of ``tar_create_split``)."""
    packed = []
    libs = tmp_path / "blender-libs" / "linux_x64"
    libs.mkdir(parents=True)
    monkeypatch.setattr(blender_cache, "require_linux", lambda what: None)
    monkeypatch.setattr(blender_cache, "require_tools", lambda *tools: None)
    monkeypatch.setattr(blender_cache, "OUT_DIR", tmp_path / "blender-cache")
    monkeypatch.setattr(blender_cache, "LIBS_DIR", libs.parent)
    monkeypatch.setattr(blender_cache, "pinned_libraries", lambda source: ("linux_x64", "url", LIBS_COMMIT))
    monkeypatch.setattr(blender_cache, "ensure_libraries", lambda source: libs)

    def tar_create_split(archive, root, members, exclude=()):
        packed.append((archive.name, root, members, exclude))
        Path(f"{archive}.000").write_bytes(b"part")
        return [Path(f"{archive}.000")]

    monkeypatch.setattr(blender_cache, "tar_create_split", tar_create_split)
    return packed


def test_libraries_are_packed_without_their_lfs_objects(tmp_path, monkeypatch, libs_pack):
    monkeypatch.setattr(blender_cache, "release_exists", lambda tag: False)
    out = blender_cache.pack_libraries(tmp_path / "source")
    assert out == tmp_path / "blender-cache" / "libs-linux_x64"
    assert libs_pack == [
        ("blender-libs-linux_x64.tar.zst", tmp_path / "blender-libs", ["linux_x64"], ("linux_x64/.git/lfs",))
    ]
    written = json.loads((out / "manifest.json").read_text())
    assert written["format"] == build_blender.LIBS_FORMAT
    assert (written["platform"], written["commit"]) == ("linux_x64", LIBS_COMMIT)
    assert written["tag"] == "blender-libs-linux_x64-0123456789"
    assert list(written["assets"]) == ["blender-libs-linux_x64.tar.zst.000"]


def test_published_libraries_are_not_packed_again(tmp_path, monkeypatch, libs_pack):
    asked = []
    stale = tmp_path / "blender-cache" / "libs-linux_x64"
    stale.mkdir(parents=True)
    (stale / "blender-libs-linux_x64.tar.zst.000").write_bytes(b"of an earlier commit")
    monkeypatch.setattr(blender_cache, "release_exists", lambda tag: asked.append(tag) or True)
    assert blender_cache.pack_libraries(tmp_path / "source") is None
    assert asked == ["blender-libs-linux_x64-0123456789"]
    assert libs_pack == []
    # Nothing is left for CI to upload.
    assert not stale.exists()


def test_lfs_only_needs_a_cache_with_the_lfs_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(blender_cache, "require_linux", lambda what: None)
    monkeypatch.setattr(blender_cache, "require_tools", lambda *tools: None)
    monkeypatch.setattr(blender_cache, "OUT_DIR", tmp_path)
    old = manifest(repo_root="/elsewhere", commit="a" * 40, config="headless", build_type="Release", created="", os="")
    old["assets"] = {"blender-build-main.tar.zst": {"sha256": "", "size": 0}}
    monkeypatch.setattr(blender_cache, "download_manifest", lambda url, downloads: (old, "https://host/release"))
    with pytest.raises(StepError, match="no git LFS archive"):
        blender_cache.restore("main", lfs_only=True)


def test_lfs_objects_are_extracted_next_to_the_ones_the_submodule_has(tmp_path, monkeypatch):
    lfs = tmp_path / "modules" / "blender" / "lfs"
    extracted = []
    monkeypatch.setattr(blender_cache, "lfs_directory", lambda: lfs)
    monkeypatch.setattr(_build_cache, "download", lambda url, target, expected: target)
    monkeypatch.setattr(
        blender_cache, "tar_extract_parts", lambda parts, root, remove=False: extracted.append((parts, root, remove))
    )
    assets = {"blender-lfs-main.tar.zst.000": {}, "blender-build-main.tar.zst": {}}
    assert blender_cache.restore_lfs_objects("main", "https://host/release", assets, tmp_path)
    assert extracted == [([tmp_path / "blender-lfs-main.tar.zst.000"], lfs.parent, True)]
    assert lfs.is_dir()
    assert not blender_cache.restore_lfs_objects("other", "https://host/release", assets, tmp_path)


def test_only_the_lfs_objects_of_the_checkout_are_packed(tmp_path, monkeypatch):
    lfs = tmp_path / "lfs"
    here, other, missing = "ab" + "1" * 62, "cd" + "2" * 62, "ef" + "3" * 62
    for oid in (here, other):
        (lfs / "objects" / oid[:2] / oid[2:4]).mkdir(parents=True)
        (lfs / "objects" / oid[:2] / oid[2:4] / oid).write_bytes(b"x")
    listing = f"{here} * release/datafiles/splash.png\n{missing} - tests/files/pointer.blend\n{here} * copy.png\n"
    monkeypatch.setattr(blender_cache, "git_output", lambda repo, *args: listing)
    assert blender_cache.lfs_object_paths(tmp_path / "source", lfs) == [f"lfs/objects/ab/11/{here}"]


@needs_archive_tools
def test_lfs_archive_holds_the_listed_objects(tmp_path, monkeypatch):
    lfs, out, target = tmp_path / "git" / "lfs", tmp_path / "out", tmp_path / "target"
    for directory in (lfs / "objects" / "ab" / "cd", out, target):
        directory.mkdir(parents=True)
    (lfs / "objects" / "ab" / "cd" / "wanted").write_bytes(b"wanted")
    (lfs / "objects" / "ab" / "cd" / "old").write_bytes(b"of another commit")
    monkeypatch.setattr(blender_cache, "lfs_directory", lambda: lfs)
    monkeypatch.setattr(blender_cache, "lfs_object_paths", lambda source, lfs: ["lfs/objects/ab/cd/wanted"])
    blender_cache.pack_lfs_objects("main", tmp_path / "source", out)
    assert [p.name for p in out.iterdir()] == ["blender-lfs-main.tar.zst.000"]

    _build_cache.tar_extract_parts(list(out.iterdir()), target)
    assert [p.name for p in (target / "lfs" / "objects" / "ab" / "cd").iterdir()] == ["wanted"]
