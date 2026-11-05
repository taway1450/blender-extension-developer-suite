# Agent notes

Tooling runs as mise tasks: `mise tasks` lists them, `mise run <task> --help` gives the options, and every output lands in `.cache/`. Use a Blender version already in `.cache/blender-bin/` (`main`, `5.2`): any other one downloads or builds Blender first. Narrow each check to the feature or add-on you touched (`mise run check:features main properties`). Domain terms are in [GLOSSARY.md](GLOSSARY.md).

Run cargo, ty and Blender only through the mise tasks, never directly (not even `target/debug/ty.exe`). The tasks share one machine-wide lock across every checkout and worktree, so parallel agents queue instead of piling up, and they use half the CPUs and at most half the RAM (`scripts/_resources.py`; `SUITE_JOBS` and `SUITE_MEMORY_LIMIT_GB` override). A run outside the tasks has none of these limits, and parallel runs have exhausted the machine's memory before.

Only `ty:test` and five check tasks build ty-blender: `check:features`, `check:ide`, `check:addons`, `check:stubs` and `check:blender`. They build with the incremental `dev` profile by default, and a build with nothing changed is a cargo no-op. Every other task needs no build: `check:oracle` runs stock ty and `lint:*` / `format:*` run stock ruff (both through `uvx`, pinned to the fork's base version), while `check:load`, `features:generate`, `stubs:generate` and the `*:scripts` tasks never touch ty.

## Editing the typechecker (`ty-blender/ruff-blender`)

- The Blender support lives in `crates/ty_blender` and `crates/ty_python_semantic`. Its spec and tests are the feature tests in `tests/typecheck/`: a new behaviour gets markers there, and the fork's Rust tests and mdtests stay upstream's.
- Keep edits to upstream's files minimal, so the fork rebases cleanly. New code goes in `crates/ty_blender` (type-free facts) or in new files under `ty_python_semantic/src/types/dedicated/blender/`, and an existing file gets at most a one-line hook that calls into them.
- Drive everything through mise, run from this repo: `check:features` / `check:ide` rebuild ty incrementally first (about 25 s after a change, a second when nothing changed), so edit, then rerun the narrowed check. `--update` re-records baselines with that same build.
- Before committing, `mise run ty:test` runs upstream's tests and mdtests as a regression check (`--mdtest <path>` for one file); a failure there is a regression to fix.
- A change ships as three commits: in `ruff-blender`, then the pointer bump in `ty-blender`, then the pointer bump here alongside the test changes.

## Editing the feature tests (`tests/typecheck/`)

- Read [tests/typecheck/README.md](tests/typecheck/README.md) for markers and layout. Files under `features/*/generated/` are written by `scripts/feature_generators/`: edit the generator, then `mise run features:generate`.
- Validate new markers first with the tasks that build nothing: `check:oracle` (the markers agree with the `_expected/` reference stubs) and `check:load` (the add-on behaves so in Blender). Then run `check:features` / `check:ide`, and `--update` only after reviewing the diff.

## Editing the scripts (`scripts/`)

- `mise run test:scripts` (pytest) and `mise run lint:scripts` (prek with stock ruff, rewrites files) take seconds and build nothing; run both before committing.
- `_target.Target` prepares what every task needs (worktree, stubs per generator, Python version, ty binary); `build_ty.py` alone decides where ty and ruff come from (a cargo build or `stock_command`). A new task gets its entry in `mise.toml` and a row in the README table.
