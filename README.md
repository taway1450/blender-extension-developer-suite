# blender-extension-developer-suite
A suite of tools for developing Blender extensions.

## Tasks

The tooling runs as [mise](https://mise.jdx.dev) tasks (`mise tasks` lists them, `mise run <task> --help`
shows the options). They need `uv`, `git` and, for building ty, `cargo`. Everything they produce is
cached under `.cache/`.

| Task | What it does |
| --- | --- |
| `mise run ty:build [--debug]` | Build ty from the `ty-blender` submodule (release or debug). |
| `mise run blender:download <version>` | Download the official Blender release into `.cache/blender-bin/<version>` (URLs and checksums from `fake-bpy-module/src/versions.yml`). |
| `mise run stubs:generate <version>` | Generate bpy stubs into `.cache/bpy-stubs/<version>` with `fake-bpy-module`, using a worktree of the `blender` submodule and the downloaded Blender binary. |
| `mise run check:blender <version> [--debug]` | Type-check the Blender source of that version with ty; the full output goes to `.cache/ty-results/<version>.txt`. |
| `mise run check:addons <version> [addon...] [--debug]` | Type-check the example addons in `examples/addons/` with ty against the bpy stubs. |

`<version>` is a Blender version such as `5.2`, or `main` together with `--blender <path>` pointing at a
matching Blender build. The check tasks build ty and generate missing stubs themselves.
