# blender-extension-developer-suite
A suite of tools for developing Blender extensions.

## Tasks

The tooling runs as [mise](https://mise.jdx.dev) tasks (`mise tasks` lists them, `mise run <task> --help`
shows the options). They need `uv`, `git` and, for building ty, `cargo`. Everything they produce is
cached under `.cache/`.

| Task | What it does |
| --- | --- |
| `mise run ty:build [--profile dev|profiling|release]` | Build ty from the `ty-blender` submodule. `dev` (the default) is incremental and rebuilds in well under a minute; `profiling` has release optimisations without LTO (fast binary, rebuilds take minutes); `release` is what ty ships, with fat LTO. |
| `mise run ty:test [--mdtest <path>]` | Run ty-blender's upstream Rust tests and mdtests (`ty_python_semantic`, `ty_blender`) with the dev build, without updating snapshots: a regression check for a change to the fork, whose Blender support is tested by the feature tests here. |
| `mise run ty:generate` | Run `cargo dev generate-all` in `ty-blender/ruff-blender` (dev profile): rewrites the rule reference (`crates/ty/docs/rules.md`), `ty.schema.json` and the other generated docs, which ruff-blender asks for after a change to its lint rules or options. Commit what it changes there. |
| `mise run ruff:build [--profile ...]` | Build ruff from the `ty-blender` submodule, in the same cargo `target/` as ty. Only to test a change to ruff itself: the fork changes no ruff crate, so the `lint:*` / `format:*` tasks run stock ruff. |
| `mise run blender:download <version>` | Download the official Blender release into `.cache/blender-bin/<version>` (URLs and checksums from `fake-bpy-module/src/versions.yml`). |
| `mise run blender:build <name> [--ref <ref>] [--update]` | Build Blender from source: a worktree of the `blender` submodule at `<ref>` (default `<name>`, e.g. `main`) in `.cache/blender-src/<name>`, CMake/Ninja build in `.cache/blender-build/<name>`, installed into `.cache/blender-bin/<name>` like a download. The precompiled libraries are shared by all builds in `.cache/blender-libs/`. `--update` fetches the ref again and rebuilds incrementally; `--config lite` builds faster. |
| `mise run stubs:generate <version>` | Generate bpy stubs with `fake-bpy-module` into `.cache/bpy-stubs/<version>` and with Blender's own stub generator (`doc/python_api/sphinx_stub_gen.py`, Blender 5.2 and later) into `.cache/bpy-stubs-builtin/<version>`, using a worktree of the `blender` submodule and the downloaded Blender binary. Both work from the rst API docs Blender generates, cached in `.cache/bpy-rst/<version>`. Stubs are regenerated when the Blender worktree moves to another commit or their generator changes: a new `fake-bpy-module` submodule commit or uncommitted edits to its `src/`, or edits to `sphinx_stub_gen.py` in the worktree (`--force` regenerates them anyway). |
| `mise run check:blender <version> [--update]` | Type-check the Blender source of that version with ty, with Blender's bundled numpy on the search path (linked from `.cache/blender-site/<version>/`); the full output goes to `.cache/ty-results/<version>.txt` (`<version>-builtin.txt` with Blender's own stubs). Each diagnostic is sorted into a root-cause bucket and an area (`scripts/_buckets.py`); the bucket × area table and the counts per rule go to `.cache/ty-results/<version>-<generator>-summary.txt`, samples per bucket to `...-buckets.txt`. For `main` the summary is compared with `tests/blender/expected/<generator>/main-summary.txt`: a difference is printed but doesn't fail the task, and `--update` records it. |
| `mise run check:stubs <version>` | Type-check the generated bpy stubs themselves with ty; the full output goes to `.cache/ty-results/stubs-<version>.txt` (`stubs-<version>-builtin.txt` for Blender's own stubs). |
| `mise run check:addons <version> [addon...]` | Type-check the example addons in `examples/addons/` with ty against the bpy stubs. |
| `mise run check:features <version> [feature...] [--update]` | Type-check the feature tests in `tests/typecheck/features/` (`assert_type` and expected-error markers) with ty-blender and compare with `tests/typecheck/expected/<generator>/<version>.txt`; fails when the results change. A summary per feature goes to `.cache/typecheck-results/<version>/<generator>/summary.md`. See [tests/typecheck/README.md](tests/typecheck/README.md). |
| `mise run check:ide <version> [feature...] [--update]` | Query ty's language server at the `^hover` / `^signature` / `^completion` / `^deprecated` markers in `tests/typecheck/` and compare with `tests/typecheck/expected/<generator>/<version>.ide.md`; fails when the results change. |
| `mise run check:oracle <version> [feature...]` | Run stock ty on each feature-test add-on with its reference stubs (`_expected/` deltas merged into the bpy stubs of both generators) and check that every marker holds; a disagreement means the hand-written expectations are inconsistent. Summary in `.cache/typecheck-results/<version>/<generator>/oracle.md`. |
| `mise run check:load <version> [feature...]` | Import, register and unregister every feature-test add-on in Blender and compare with its `_expected/runtime.toml`: add-ons that fail on purpose say so and with which error, and probes check what an add-on does at runtime after register. |
| `mise run features:generate [--check]` | Write the generated feature-test add-ons (`tests/typecheck/features/*/generated/`, from `scripts/feature_generators/`) and the import roots in `tests/typecheck/ty.toml`; `--check` fails if they are out of date. |
| `mise run lint:blender <version>`, `lint:stubs`, `lint:addons [addon...]`, `lint:features [feature...]` | Lint the Blender source (without `lib/` and `extern/`), the generated bpy stubs (once per stub generator), the example add-ons or the feature-test add-ons with stock ruff (`uvx ruff@<version ruff-blender is based on>`, or `--ruff <path>`), twice: with stock settings (`--isolated`) and with the profile in `config/ruff/` (`blender.toml`, `stubs.toml`, `addons.toml`, `features.toml`). The counts per rule of both runs are printed side by side; the full output goes to `.cache/ruff-results/lint-<target>-<version>[-builtin]-{default,profile}.txt`. `lint:addons` fails when the profile run has findings. |
| `mise run format:blender <version>`, `format:stubs`, `format:addons`, `format:features` | The same targets and configurations with `ruff format --check --diff`, which never writes files; the diffs go to `.cache/ruff-results/format-…`. |
| `mise run lint:scripts` | Lint (with fixes) and format the tooling in `scripts/` with the pinned upstream ruff through [prek](https://github.com/j178/prek) (`.pre-commit-config.yaml`, settings in `scripts/ruff.toml`). `uvx prek@0.5.6 install` runs the hooks on every commit. |
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
themselves. The ty tasks take `--profile dev|profiling|release` for that build (default `dev`, incremental), or
`--ty <path>` to use a binary that is already built; `check:oracle` and the ruff tasks build nothing:

```sh
mise run check:features main properties
mise run check:ide main properties --ty ty-blender/ruff-blender/target/debug/ty.exe
```

When results change, `check:features` and `check:ide` list each entry as `-` gone, `~` changed or `+` new, with
ty's message under a new `check:features` entry and a diff under a changed `check:ide` section, then the counts
per feature.

The stub, check and report tasks run once per stub generator: `fake-bpy-module` and, for Blender 5.2 and later,
`builtin` (Blender's own). `--generator fake-bpy-module` or `--generator builtin` picks one; the report against
Blender's own stubs goes to `.cache/flag-report/<version>/builtin/`.

Building Blender needs the tools from the [Blender build docs](https://developer.blender.org/docs/handbook/building_blender/)
and git LFS: on Windows Visual Studio 2022 or newer with the "Desktop development with C++" workload (the
task loads the Visual Studio environment itself), on macOS Xcode and on Linux the packages from
`build_files/build_environment/install_linux_packages.py`. CMake and Ninja come from PyPI. Branches that only exist on a
fork need that fork as the `origin` of the `blender` submodule (`git submodule sync blender`).
