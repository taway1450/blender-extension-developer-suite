# Feature tests for the bpy stubs

Small extensions that each exercise one Blender idiom, with markers that state what a type checker and an
editor should report. Two tasks run them against both stub generators (fake-bpy-module and Blender's own):

```sh
mise run check:features main          # types: assert_type and expected errors
mise run check:ide main               # editor: hover, signature help, completions, deprecation
mise run check:features main --update # record the current results after a reviewed change
```

Background and design: [docs/research/typecheck-test-addons.md](../../docs/research/typecheck-test-addons.md) and
[docs/research/hover-docstring-testing.md](../../docs/research/hover-docstring-testing.md).

## Layout

```text
tests/typecheck/
├── ty.toml                       # unused ignore comments are errors; extensions are top-level packages
├── features/<feature>/           # one installable extension per idiom
│   ├── blender_manifest.toml
│   ├── __init__.py               # idiomatic addon code, no markers
│   ├── check_<feature>.py        # type markers (check:features)
│   └── ide_<feature>.py          # editor markers (check:ide), optional
├── ide/<feature>/ide_<feature>.py  # editor tests that need no addon of their own
└── expected/<generator>/
    ├── <version>.txt             # check:features results that are not passes
    └── <version>.ide.md          # check:ide results, passes and failures
```

`check_*.py` and `ide_*.py` are never imported by `__init__.py`, so every feature still loads in Blender.

## Type markers (`check_*.py`)

- `assert_type(expr, T)` states the type `expr` has **at runtime in Blender**, not what the stubs say today.
  It fails when ty reports `type-assertion-failure` on that line.
- `# ty: ignore[rule]` marks code that must be rejected. It fails when ty reports `unused-ignore-comment`,
  i.e. when the error is no longer found.
- Any other diagnostic in a feature folder (also in `__init__.py`) is recorded as unexpected.

Write assertions inside functions that take the objects as parameters (`def _(obj: Object) -> None:`), so no
real instance is needed. For enums, whose stubs may use `Literal` unions, check assignability instead
(`mode: str = context.mode`).

## Editor markers (`ide_*.py`)

A comment line below the code puts a caret at the column to query. Several markers can stack under one line.

```python
obj.location
#   ^hover
#   ^hover-contains "Location of the object"
```

| Marker | Records |
| --- | --- |
| `^hover` | the hover Markdown |
| `^hover-contains "text"` | PASS if the hover text contains `text` |
| `^hover-none` | PASS if there is no hover |
| `^signature` | the signature label, parameters with their docs, and the documentation |
| `^signature-param "text"` | PASS if the active parameter's documentation contains `text` |
| `^completion a b` | `detail`, documentation and deprecated tag of the completion items `a` and `b` |
| `^deprecated` | PASS if a `deprecated` diagnostic covers the caret |

Code under a `^completion` caret is unfinished on purpose (`obj.locat`); `check:features` ignores `ide_*.py`.
IDE test files must be ASCII, because LSP positions count UTF-16 code units.

## Expected results

The `expected/` files record the current state, failures included. Both tasks fail when the results
differ from the recorded ones, so a stub fix shows up as a diff just like a regression. Review the diff, then
run the task with `--update`. Running a subset of features (`mise run check:features main props_annotations`)
compares and updates only those features' entries.
