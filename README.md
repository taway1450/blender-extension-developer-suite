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
| `mise run blender:build <name> [--ref <ref>] [--update]` | Build Blender from source: a worktree of the `blender` submodule at `<ref>` (default `<name>`, e.g. `main`) in `.cache/blender-src/<name>`, CMake/Ninja build in `.cache/blender-build/<name>`, installed into `.cache/blender-bin/<name>` like a download. The precompiled libraries are shared by all builds in `.cache/blender-libs/`. `--update` fetches the ref again and rebuilds incrementally; `--config lite` builds faster. |
| `mise run stubs:generate <version>` | Generate bpy stubs with `fake-bpy-module` into `.cache/bpy-stubs/<version>` and with Blender's own stub generator (`doc/python_api/sphinx_stub_gen.py`, Blender 5.2 and later) into `.cache/bpy-stubs-builtin/<version>`, using a worktree of the `blender` submodule and the downloaded Blender binary. Both work from the rst API docs Blender generates, cached in `.cache/bpy-rst/<version>`. |
| `mise run check:blender <version> [--debug]` | Type-check the Blender source of that version with ty; the full output goes to `.cache/ty-results/<version>.txt` (`<version>-builtin.txt` with Blender's own stubs). |
| `mise run check:stubs <version> [--debug]` | Type-check the generated bpy stubs themselves with ty; the full output goes to `.cache/ty-results/stubs-<version>.txt` (`stubs-<version>-builtin.txt` for Blender's own stubs). |
| `mise run check:addons <version> [addon...] [--debug]` | Type-check the example addons in `examples/addons/` with ty against the bpy stubs. |
| `mise run check:features <version> [feature...] [--update]` | Type-check the feature tests in `tests/typecheck/features/` (`assert_type` and expected-error markers) and compare with `tests/typecheck/expected/<generator>/<version>.txt`; fails when the results change. A summary per feature goes to `.cache/typecheck-results/<version>/<generator>/summary.md`. See [tests/typecheck/README.md](tests/typecheck/README.md). |
| `mise run check:ide <version> [feature...] [--update]` | Query ty's language server at the `^hover` / `^signature` / `^completion` / `^deprecated` markers in `tests/typecheck/` and compare with `tests/typecheck/expected/<generator>/<version>.ide.md`; fails when the results change. |
| `mise run report:flags <version>` | For every documented class, property, function, parameter, return value and operator argument, compare its RNA flags with the behaviour probed in Blender, the API docs and the bpy stubs; per-flag counts and wrong flag combinations go to `.cache/flag-report/<version>/summary.md`, all rows to `rows.md` / `rows.csv`. |

`<version>` is either a Blender release such as `5.2`, which is downloaded when needed, or the name of a
build made with `blender:build` (e.g. `main`), which has to be built first:

```sh
mise run blender:build main               # once; takes a while and needs several GB for libraries and build
mise run check:addons main
mise run blender:build main --update      # later: fetch main again, rebuild and (automatically) regenerate the stubs
mise run blender:build my-fix --ref my-feature-branch
```

`--blender <path>` uses any other Blender binary instead. The check tasks build ty and generate missing stubs
themselves.

The stub, check and report tasks run once per stub generator: `fake-bpy-module` and, for Blender 5.2 and later,
`builtin` (Blender's own). `--generator fake-bpy-module` or `--generator builtin` picks one; the report against
Blender's own stubs goes to `.cache/flag-report/<version>/builtin/`.

Building Blender needs the tools from the [Blender build docs](https://developer.blender.org/docs/handbook/building_blender/)
and git LFS: on Windows Visual Studio 2022 or newer with the "Desktop development with C++" workload (the
task loads the Visual Studio environment itself), on macOS Xcode and on Linux the packages from
`build_files/build_environment/install_linux_packages.py`. CMake and Ninja come from PyPI. Branches that only exist on a
fork need that fork as the `origin` of the `blender` submodule (`git submodule sync blender`).
