# Source stub readers (prototypes)

Three prototypes that write `bpy` stubs from Blender's **source code** instead of from a running Blender or
its API docs, to find out how much a source reader can know, what only it can know, and which approach
upstream could adopt. The findings are in [docs/research/source-stub-generators.md](../../docs/research/source-stub-generators.md).

| Prototype | Reads | Needs |
|---|---|---|
| `regex/` | the C/C++ files as text: a small tokenizer, `#define` expansion and an interpreter for the `RNA_def_*` call sequences, `PyTypeObject` / `PyMethodDef` tables, operator, node and bmesh definitions | Python only |
| `libclang/` | the same files through clang's AST (the pinned `libclang` wheel), using the build's `compile_commands.json`; also the runtime C bodies (`-DRNA_RUNTIME`) and their callees, to classify whether RNA functions can return NULL (`returns.py`, written to `returns.md`) | `libclang` from PyPI, a configured build for the compile flags |
| `makesrna/` | the RNA definitions as makesrna itself runs them, dumped as JSON by `makesrna-json-dump.patch` | a configured Blender build with the patch applied and the `makesrna` target built |

All three share `common/`:

- `model.py`: one JSON model of source facts (RNA structs, properties, functions; operators; Python C types and
  modules; context members; node declarations; bmesh operators; the Python scripts' classes and registrations),
  each fact with its source location.
- `pysource.py`: the `ast` reader of the Python side (`scripts/modules`, `scripts/startup`, `scripts/addons_core`,
  the Cycles add-on), shared by all three.
- `rstdoc.py`: C string literals and the rst signatures in C docstrings.
- `render.py`: one renderer from the model to `.pyi` stubs. It applies no hand tables of its own beyond the
  facts the C code itself encodes (mathutils subtypes, slot dunders, socket classes), so the stubs show what the
  source alone gives.
- `driver.py`: the command line every prototype runs through.
- `compare.py`: compares every stub set (builtin, fake-bpy-module and the three readers), sorting disagreements
  into kinds.
- `audit.py`: checks a hand table of the fork's stub generator (`ENUM_RUNTIME_ITEMS`) against the facts.

## Running

`mise run probe:source-stubs 5.2 --source .cache/blender-src/5.2-src` runs all three readers under the suite's
lock and job limit, then the comparison and the audit (`--tool` picks one reader).

The source tree is a Blender worktree (`mise run blender:build 5.2-src --ref v5.2.0 ...` makes one under
`.cache/blender-src/5.2-src`, plus the build `makesrna` and `libclang` need). Every prototype writes
`facts.json`, `stubs/` and `coverage.md` to `.cache/source-stubs/<version>/<tool>/`. Each step on its own:

```bash
uv run --no-project --python 3.13 python prototypes/source_stubs/regex/run.py 5.2 --source .cache/blender-src/5.2-src
```

```bash
uv run --no-project --python 3.13 --with libclang==18.1.1 python prototypes/source_stubs/libclang/run.py 5.2 --source .cache/blender-src/5.2-src
```

```bash
uv run --no-project --python 3.13 python prototypes/source_stubs/makesrna/run.py 5.2 --source .cache/blender-src/5.2-src
```

Then compare and audit (writes `comparison.md` and `audit.md` next to the outputs):

```bash
uv run --no-project --python 3.13 python prototypes/source_stubs/common/compare.py 5.2
```

```bash
uv run --no-project --python 3.13 python prototypes/source_stubs/common/audit.py 5.2
```

`mise run test:scripts` runs the tests in `tests/`.

These are prototypes: they are not wired into `stubs:generate` or the feature tests.
