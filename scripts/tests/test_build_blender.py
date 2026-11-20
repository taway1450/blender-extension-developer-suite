from pathlib import Path

import pytest

from build_blender import (
    PRESET_OPTIONS,
    ConfigureOptions,
    build_info_text,
    configure_command,
    configure_hash,
    is_current_build,
)


def command(config: str, *, libs: Path | None = Path("libs"), defines: tuple[str, ...] = ()) -> list[str]:
    return [
        str(arg)
        for arg in configure_command(
            Path("cmake"),
            Path("ninja"),
            source=Path("src"),
            build_dir=Path("build"),
            options=ConfigureOptions(config=config, build_type="Release", defines=defines),
            libs=libs,
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


def hash_of(build_type: str = "Release", config: str = "headless", **options) -> str:
    return configure_hash(
        source=Path("src"),
        build_dir=Path("build"),
        options=ConfigureOptions(config=config, build_type=build_type, **options),
        install_dir=Path("bin"),
    )


def test_configure_hash_is_stable_and_follows_the_configure_arguments(monkeypatch):
    assert hash_of() == hash_of()
    assert hash_of(build_type="Debug") != hash_of()
    assert hash_of(config="full") != hash_of()
    before = hash_of()
    monkeypatch.setitem(PRESET_OPTIONS, "headless", [*PRESET_OPTIONS["headless"], "-DWITH_CYCLES=OFF"])
    assert hash_of() != before


def test_system_libraries_drop_libdir_and_defines_follow_the_preset():
    assert any(arg.startswith("-DLIBDIR=") for arg in command("full"))
    assert not any(arg.startswith("-DLIBDIR=") for arg in command("full", libs=None))
    cmd = command("headless", defines=("CMAKE_C_COMPILER=clang",))
    assert cmd.index("-DCMAKE_C_COMPILER=clang") > max(cmd.index(o) for o in PRESET_OPTIONS["headless"])
    assert "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON" in cmd


def test_configure_hash_follows_system_libs_and_defines():
    assert hash_of(system_libs=True) != hash_of()
    assert hash_of(defines=("A=1",)) != hash_of()


INFO = build_info_text(commit="abc", config="headless", build_type="Release", configure="h1", source=Path("s"))


def test_build_info_matching_everything_is_current():
    assert is_current_build(INFO, commit="abc", config="headless", build_type="Release", configure="h1")


@pytest.mark.parametrize(
    "changed",
    [{"commit": "def"}, {"config": "full"}, {"build_type": "Debug"}, {"configure": "h2"}],
)
def test_build_info_differing_in_anything_is_stale(changed):
    current = {"commit": "abc", "config": "headless", "build_type": "Release", "configure": "h1"}
    assert not is_current_build(INFO, **{**current, **changed})


def test_build_info_without_configure_hash_is_stale():
    """Builds recorded before the configure hash say nothing about their options (e.g. PRESET_OPTIONS)."""
    old = "commit=abc\nconfig=headless\nbuild_type=Release\nsource=s\n"
    assert not is_current_build(old, commit="abc", config="headless", build_type="Release", configure="h1")


def test_codegen_builds_only_the_generated_sources():
    """``--target codegen``: the custom-command outputs a parser of the sources needs (generated headers and
    sources), not the shader caches, dependency files, archives or utility stamps."""
    from build_blender import generated_sources

    build = Path("/b")
    listing = """/b/source/blender/makesrna/RNA_prototypes.hh
/b/source/blender/makesrna/intern/rna_object_gen.cc
/b/source/blender/datatoc/startup.blend.c
/b/source/blender/makesdna/intern/dna_type_offsets.h
/b/source/blender/compositor/shaders/x.glsl.d
/b/source/blender/compositor/shaders/x.glsl.tmp
/b/release/Blender.tar.xz
/b/CMakeFiles/generate_datamodels
/elsewhere/written_outside.h
"""
    assert generated_sources(listing, build) == [
        "source/blender/datatoc/startup.blend.c",
        "source/blender/makesdna/intern/dna_type_offsets.h",
        "source/blender/makesrna/RNA_prototypes.hh",
        "source/blender/makesrna/intern/rna_object_gen.cc",
    ]
