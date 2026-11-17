from pathlib import Path

from build_blender import configure_command

API_OPTIONS = ["-DWITH_CODEC_FFMPEG=ON", "-DWITH_AUDASPACE=ON", "-DWITH_INPUT_NDOF=ON"]


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
    assert all(option in cmd[preset + 1 :] for option in API_OPTIONS)


def test_other_presets_keep_their_options():
    assert not set(API_OPTIONS) & set(command("full"))
