# FFmpeg build-option gap in the stubs

Research note, 2026-11-17, for issue #110. Trimmed on 2026-11-18 to the rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings.

The question: the FFmpeg presets reported `build-option-gap` diagnostics on `main`. Which fix is cheaper and more correct: (1) build our Blender with FFmpeg, or (2) have the stub generator emit every RNA member whatever the build options.

Blender citations are at `.cache/blender-src/main` (commit `9a7af0b847`, the `main` build). Paths under `source/`, `build_files/`, `doc/` and `CMakeLists.txt` are relative to it.

Main now: fix (1). `scripts/build_blender.py` turns `WITH_CODEC_FFMPEG`, `WITH_AUDASPACE` and `WITH_INPUT_NDOF` back on for the headless preset (`PRESET_OPTIONS`), so the stubs describe the API that official releases ship.

## Cause

The `main` Blender was built with the `headless` CMake preset. `build_files/cmake/config/blender_headless.cmake:16-28` forces `WITH_AUDASPACE`, `WITH_CODEC_FFMPEG`, `WITH_CODEC_SNDFILE`, the audio backends and `WITH_INPUT_NDOF` OFF, so `makesrna` never defines most `FFmpegSettings` properties or the `FFMPEG` image-format item (`#ifdef WITH_FFMPEG` in `source/blender/makesrna/intern/rna_scene.cc`; `source/blender/makesrna/intern/CMakeLists.txt:312-313` adds `-DWITH_FFMPEG` only `if(WITH_CODEC_FFMPEG)`). `blender_full.cmake` and `blender_release.cmake` turn all three back ON, so official releases ship these members.

## 1. Is (2) feasible? Where the stubs come from

The pipeline that produces the stubs:

1. `makesrna` is a code generator compiled with the same definitions. It writes `rna_*_gen.cc` from the `RNA_def_*` calls that survive the preprocessor. Code inside `#ifdef WITH_FFMPEG` never runs in it, so the properties never enter the RNA database.
2. `scripts/generate_stubs.py` runs `doc/python_api/sphinx_doc_gen.py` inside the built Blender (`--background --factory-startup`). That script introspects the live RNA with `_rna_info.BuildRNAInfo()` and writes RST.
3. `doc/python_api/sphinx_stub_gen.py` turns that RST into `.pyi`. It also reads the enum items from the RST.

So the stubs mirror the runtime RNA of the Blender build that made them, and the stub generator cannot "emit regardless of build options": it reads a runtime dump in which those members do not exist. Nothing at runtime records that a member was compiled out. Both generators (Blender's own and fake-bpy-module) read the same RST, so both have the gap. The ways to do (2) anyway, and why each lost:

- **Patch `rna_scene.cc` to drop the guards.** This is compile-feasible. The enum constants are unconditional (`source/blender/makesdna/DNA_scene_types.h:109,143` and `source/blender/imbuf/movie/MOV_enums.hh:16`). The DNA fields exist in `FFMpegCodecData` (`DNA_scene_types.h:175`), and `FFMPEG_LOSSLESS_OUTPUT` is at `DNA_scene_types.h:170`. The MOV API has non-FFmpeg fallbacks (`source/blender/imbuf/movie/intern/movie_util.cc:695-702`), and `rna_scene.cc:1598` already calls `MOV_codec_supports_alpha` without a guard.

  It is still the wrong fix. It changes runtime behaviour: a Blender without FFmpeg would expose settings that do nothing. It patches an upstream file in the fork, and it covers only this one option. Blender hides these members on purpose.
- **Hand-written stubs** (`doc/python_api/stubs_handwritten/` already exists for `_bpy`, `_cycles`, and others). These are typed members and an enum item to keep in sync with `rna_scene.cc` by hand.
- **Merge RST from another build** (for example the 5.2 release in `.cache/bpy-rst/5.2`). The other build is a different version, so this mixes APIs.

(2) needs either a behaviour-changing patch to upstream RNA or hand-maintained stubs, and it fixes only the options someone remembers to patch. (1) needs no new dependency: the FFmpeg static libraries are in the precompiled library checkout the build already uses, and Audaspace is bundled in `extern/`.

## 2. Other build options that cause the same kind of gap

Every `#if` on a `WITH_*` macro in `source/blender/makesrna/intern/*.cc` was compared with the `main` CMakeCache:

| Option | In the headless build | RNA/API it gates |
|---|---|---|
| `WITH_CODEC_FFMPEG` | OFF | `FFmpegSettings` (all but `audio_mixrate` / `audio_channels`), the `FFMPEG` file format |
| `WITH_INPUT_NDOF` | OFF | `PreferencesInput.ndof_*` (`rna_userdef.cc:6997-7117`), and the operators `view3d.ndof_*`, `view2d.ndof`, `image.view_ndof`, `clip.view_ndof` |
| `WITH_AUDASPACE` | OFF | The parameters of `bpy.ops.sound.mixdown` (`source/blender/editors/sound/sound_ops.cc:778-830`). `Strips.new_sound` keeps its signature through a stub (`rna_sequencer_api.cc:390-433`). The `aud` module is missing, but `sphinx_stub_gen.py` excludes `aud` from the stubs in every build |
| `WITH_OPENVDB`, `WITH_ALEMBIC`, `WITH_USD`, `WITH_CYCLES`, `WITH_BULLET`, `WITH_MOD_FLUID`, `WITH_FREESTYLE`, `WITH_XR_OPENXR`, `WITH_IMAGE_OPENJPEG/CINEON/WEBP`, `WITH_INTERNATIONAL` | ON | e.g. `rna_fluid.cc:603`, `rna_cachefile.cc:44`, `rna_modifier.cc:888`, `rna_userdef.cc:6689`, `rna_scene.cc:317-353` |
| GPU backends, audio devices | OFF/platform | enum items filled at runtime (`rna_userdef.cc:1312,1673-1690`); not a stub gap |

**Cross-check against the official build.** A diff of the RST members of `.cache/bpy-rst/5.2` (official release, all options ON) against `.cache/bpy-rst/main` found, among the missing members, only the FFmpeg, NDOF and `sound.mixdown` rows above from compile-time options. In the enum-item files, the only option-gated item is `FFMPEG` in `image_type_all_items`. The other differences are not build options: version changes between 5.2 and main, and properties that Python add-ons register in the 5.2 docs but not in main (`Scene.cycles`, `Object.selection_sets`, `WindowManager.extension_tags`, the `wm.xr_*` operators).
