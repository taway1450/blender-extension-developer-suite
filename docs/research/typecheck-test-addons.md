# Feature test addons for type-checking the bpy stubs

Research note, 2026-11-04. The question was how to structure example addons so that running the type
checker on them shows both the problems and the expected types, and how to generate test data on top
of that: testing every Blender function, fuzzing, random addon generation.

Every fact has a source next to it, either a URL or a `path:line` in this repo or its submodules.
My own recommendations are marked **Recommendation** or written as "I recommend".
Output marked *Verified locally* came from running this repo's ty build
(`ty-blender/ruff/target/release/ty.exe`, `ty 0.0.95 (48c5ea1ba 2026-10-29)`) against `.cache/bpy-stubs/5.2`
on 2026-11-04.

---

## 1. What the repo already has

- **The type checker is ty only.** It is built from the `ty-blender` submodule (`mise.toml`, `ty:build`;
  `scripts/build_ty.py`). No mypy or pyright config exists in the repo. Blender's own stub checker uses
  mypy (`blender/doc/python_api/check_stubs.py:38-62`), not this repo.
- **How stubs reach ty.** `scripts/check_addons.py:55-57` runs
  `ty check --project examples/addons --python-version <Blender's Python> --extra-search-path <stubs> <addon dirs>`
  once for each stub generator. It exits non-zero if ty reports anything (`scripts/check_addons.py:62-64`).
- **Two stub generators.** fake-bpy-module writes to `.cache/bpy-stubs/<version>`. Blender's own
  `doc/python_api/sphinx_stub_gen.py` (5.2+) writes to `.cache/bpy-stubs-builtin/<version>` (`README.md`, task table).
  Both are generated from the RST API docs (`README.md`, `stubs:generate` row;
  `blender/doc/python_api/sphinx_stub_gen.py:7-9`: "Generate Python type stubs (.pyi) from RST API documentation").
  **Consequence:** a test whose expected types come straight from RNA at runtime is an oracle that does
  not depend on either generator, since neither generator reads RNA directly.
- **The existing example addon.** `examples/addons/simple_scatter/` is a real extension: it has
  `blender_manifest.toml` and an `__init__.py` with `register`/`unregister`. Its README says its job is to
  show "which Blender idioms ty does not understand yet" (`examples/addons/README.md`).
  It only fails or passes as a whole: it has no assertions about what *should* happen.
- **An RNA introspection pipeline already exists.** `scripts/blender/dump_rna_flags.py` runs inside Blender
  and does three things:
  - It walks the documented API with the same `rna_info` calls as `sphinx_doc_gen.py` (`dump_rna_flags.py:1-19`).
  - It seeds data so that most types have instances (`seed_data`, `:44`; `build_pool`, `:136`).
  - It probes properties and functions at runtime without executing them (`:10-14`).

  `scripts/report_flags.py` then parses the stubs with `ast` (`report_flags.py:222-228`) and compares them
  against those probes. That comparison is purely textual: it never asks the type checker what it *infers*.

*Verified locally:* running ty on `simple_scatter` with the fake-bpy-module 5.2 stubs gives 12 diagnostics.
They are good seeds for the first feature tests:

| Diagnostic | Idiom |
| --- | --- |
| `invalid-type-form` "Function calls are not allowed in type expressions" (lines 14, 15, 17) | `count: IntProperty(...)` annotations |
| `invalid-method-override` on `poll`, `execute`, `draw` | fake-bpy-module declares `execute(self, context: Context \| None) -> set[Literal[...OperatorReturnItems]]` (`.cache/bpy-stubs/5.2/bpy-stubs/types/__init__.pyi:84258-84260`). Blender's builtin stubs use `context: Context` and `set[rna_enum_operator_return_items]` (`.cache/bpy-stubs-builtin/main/bpy/types/__init__.pyi:19205`). |
| `unresolved-attribute` `Scene.simple_scatter` | `bpy.types.Scene.x = PointerProperty(...)` assigned at runtime |
| `unresolved-attribute` on `None \| Scene` / `None \| UILayout` | nullability of `context.scene` and `Panel.layout` |

## 2. Primary-source survey

### 2.1 How stub packages are tested with type assertions

- **typeshed `test_cases`** (https://github.com/python/typeshed/blob/main/tests/REGRESSION.md):
  - **Layout.** Tests live in `stdlib/@tests/test_cases` and `stubs/<dist>/@tests/test_cases`, as one
    `check_<module>.py` file per stub. A file can be split into a directory with one file per object.
    Version-specific files are named `check_foo-py311.py`.
  - **Positive tests** use `assert_type` to check that the checker infers the expected type.
  - **Expected errors** are marked with `# type: ignore`. Unused ignores are reported through mypy
    `--warn-unused-ignores` and pyright `reportUnnecessaryTypeIgnoreComment`, which are enabled for all
    test-case directories. So a marker that no longer suppresses an error fails the test.
  - **Scope.** Only things that "have caused problems in the past" get tests. 100% coverage is "neither
    necessary nor desirable".
  - **Runners.** mypy runs through `tests/regr_test.py` and pyright through CI. typeshed also has a
    `ty_test.py` (https://github.com/python/typeshed/blob/main/tests/README.md).
- **`typing.assert_type` / `reveal_type`** (https://docs.python.org/3/library/typing.html#typing.assert_type):
  - Both were added in Python 3.11.
  - At runtime `assert_type` "returns the first argument unchanged with no checks".
  - At runtime `reveal_type` prints the runtime type to stderr and returns its argument.
- **pyright.** `reportUnnecessaryTypeIgnoreComment` flags "a `# type: ignore` or `# pyright: ignore` comment
  that would have no effect if removed". Its default is `"none"`
  (https://github.com/microsoft/pyright/blob/main/docs/configuration.md).
- **mypy's own test-data format** (https://github.com/python/mypy/blob/master/test-data/unit/README.md):
  - Cases start with `[case name]`, and a `-xfail` suffix marks a known failure.
  - Inline `# E: message` markers state expected errors. `W:` and `N:` do the same for warnings and notes,
    and `# E:12` adds a column.
  - `[out]` blocks hold whole-output expectations.
  - `[file x.py]` adds extra modules.
- **pytest-mypy-plugins** (https://pypi.org/project/pytest-mypy-plugins/):
  - Test cases are YAML items with `case`, `main`, `out`, optional `regex`, `parametrized`, `files` and `mypy_config`.
  - It is described as a "pytest plugin for testing mypy types, stubs, and plugins", so it is tied to mypy.
- **ty**, which is what this repo uses:
  - **Suppression comments.** `# ty: ignore[<rule>]` suppresses one rule
    (`ty-blender/docs/suppression.md:13-17`). `# type: ignore[ty:<rule>]` does the same, and codes without
    the `ty:` prefix are ignored. One comment can therefore carry mypy and ty codes together:
    `# type: ignore[arg-type, ty:invalid-argument-type]` (`suppression.md:70-80`).
  - **Unused-ignore rules.** `unused-ignore-comment` reports unused `ty: ignore` comments.
    `unused-type-ignore-comment` reports unused `type: ignore` comments. Both default to `warn`
    (`ty-blender/docs/reference/rules.md`, sections `unused-ignore-comment` and `unused-type-ignore-comment`).
    Rule levels can be set in `ty.toml` under `[rules]` (`ty-blender/docs/rules.md:50-58`).
  - **Doc inconsistency.** `suppression.md:98-99` says `unused-ignore-comment` also covers `type: ignore`.
    `rules.md` and the ty output disagree: `.cache/ty-results/main.txt` contains
    `warning[unused-type-ignore-comment]`. Enable both.
  - **Other relevant rules.** `type-assertion-failure` (default `error`) fires when the type passed to
    `assert_type` does not match the actual type (`rules.md`, section `type-assertion-failure`).
    `undefined-reveal` fires for `reveal_type` used without an import.
  - **Output formats.** `ty check --output-format` accepts `full`, `concise`, `gitlab`, `github`, `junit`
    and `sarif` (`ty-blender/docs/reference/cli.md:73-81`).
  - **Diagnostic baselines (preview).** `--baseline <path>` and `--update-baseline` exist, and the JSON
    format "may change between ty releases" (`cli.md`; `ty-blender/docs/reference/configuration.md:4-10`).
  - *Verified locally:*
    - `--output-format concise` prints one line per diagnostic: `path:line:col: severity[rule] message`.
    - `reveal_type` produces `info[revealed-type] Revealed type: \`Object | None\``.
    - A `# ty: ignore[invalid-assignment]` on a line without an error produces
      `warning[unused-ignore-comment] Unused \`ty: ignore\` directive`.
    - A baseline file stores `rule`, `startColumn`, `endColumn` and `lineCount` for each file, but no line
      numbers or messages.
    - `info`-level `revealed-type` diagnostics are not baselined. With a baseline and only info diagnostics
      left, ty exits with 0.
- **ty's own test framework, mdtest** (`ty-blender/ruff/crates/ty_test/README.md`):
  - Tests are Markdown files with fenced `py` and `pyi` blocks.
  - Assertions are inline comments: `# revealed: <type>`, which must match `reveal_type` output exactly
    (`:46-69`), and `# error: [rule] "text"` with an optional column (`:71-90`). Assertions can stack on
    the lines above the code (`:92-118`).
  - `# snapshot` creates inline diagnostic snapshots, updated with `MDTEST_UPDATE_SNAPSHOTS=1` (`:145-204`).
  - It has TOML configuration, including `environment.extra-paths` (`:322-340`, `:416-456`). Each test runs
    in an in-memory file system (`:24-27`), and external packages come from `uv sync` with lockfiles
    (`:342-400`).
  - It runs through `cargo test -p ty_python_semantic` (`:535-548`).
  - **Assessment (Recommendation):** the comment syntax is the best model to copy. The harness itself is a
    poor fit, because loading the multi-MB locally generated stubs into its in-memory file system for each
    test would need changes to the fork. I recommend copying the comment syntax, not the harness.

### 2.2 How fake-bpy-module and Blender test their stubs

- **fake-bpy-module CI** (`fake-bpy-module/.github/workflows/fake-bpy-module-ci.yml:95-169`) runs:
  - unit tests of the generator itself (`tests/python/fake_bpy_module_test/.../analyzer_test.py`, `generator_test.py`);
  - an import test for every generated module (`tests/python/import_module_test/template.py.tpl`);
  - `ruff check --select=PYI` on the stubs (`tools/pip_package/run_ruff_flake8_pyi.sh`);
  - pylint over the Cycles addon source against the stubs (`tests/pylint_cycles.sh`).

  There are **no `assert_type` or expected-error tests**.
- **Blender's validator** (`blender/doc/python_api/sphinx_stub_validate.py:7-15`) parses every `.pyi` and
  checks that the names it uses resolve. It then loads each module with a custom finder to surface
  base-class and evaluation errors.
- **Blender's `check_stubs.py`** (`blender/doc/python_api/check_stubs.py:7-19, 38-62, 80-87`) runs mypy over
  this corpus, one process per file, with `MYPYPATH=stubs`:
  - `doc/python_api/examples/*.py` (113 files)
  - `scripts/templates_py/*.py`
  - `tests/python/*.py`
  - `scripts/modules`, `scripts/startup` and `scripts/addons_core`

  It filters out known noise. By its own description, it is a check that "the stubs are valid" and work,
  not a zero-error target.
- **RNA introspection** (`blender/scripts/modules/_rna_info.py`; the module is imported as `_rna_info` in
  4.4+ and as `rna_info` before that, see `scripts/blender/dump_rna_flags.py:31-34`):
  - `BuildRNAInfo()` (`:766`) returns the structs, functions, operators and properties.
  - `InfoStructRNA` (`:119`) has bases, properties and functions.
  - `InfoPropertyRNA` (`:273`) has `fixed_type` for pointers and collections (`:346`), `enum_items` (`:355-357`),
    `is_required`, `is_never_none` (`:327-329`) and `get_type_description` (`:425`).
  - `InfoFunctionRNA` (`:629`) and `InfoOperatorRNA` (`:674`) cover functions and operators.

  That is all the input needed to enumerate every type, property, function, parameter, return value and
  operator. `sphinx_doc_gen.py` uses the same module (`blender/doc/python_api/sphinx_doc_gen.py:71`).

### 2.3 Addon structure that matters for type-checking

- **Extensions and legacy addons.**
  - An extension add-on needs at least `blender_manifest.toml` and `__init__.py`.
  - Required manifest fields are `schema_version`, `id`, `version`, `name`, `tagline`, `maintainer`, `type`,
    `license` and `blender_version_min` (≥ 4.2.0).
  - `blender --command extension build` / `validate` build and check a package
    (https://docs.blender.org/manual/en/latest/advanced/extensions/getting_started.html).
  - Legacy `bl_info` add-ons are deprecated since 4.2 but still supported. Extensions should use relative
    imports and `__package__` for the preferences `bl_idname`
    (https://docs.blender.org/manual/en/latest/advanced/extensions/addons.html).
  - Reference manifest: `blender/scripts/addons_core/bl_pkg/example_extension/blender_manifest.toml`.
    Validator: `blender/scripts/addons_core/bl_pkg/cli/blender_ext.py:1683ff`.
- **Property registration idioms** (`blender/doc/python_api/rst/info_overview.rst`):
  - Annotations inside a `PropertyGroup`, plus `bpy.types.Material.my_custom_props = bpy.props.PointerProperty(type=...)`
    after `register_class` (`:364-373`).
  - Nested groups (`:391-409`).
  - **Annotation statements on existing classes:** `bpy.types.Object.my_float: bpy.props.FloatProperty()`,
    `del bpy.types.Object.my_float`, and `MyPropGroup.my_float: bpy.props.FloatProperty()` after the class
    body (`:430-449`). This is an unusual form and each variant deserves its own test.
- **Signatures.** In both stub sets the `bpy.props.*Property` functions return `_PropertyDeferred`
  (`.cache/bpy-stubs-builtin/main/bpy/props/__init__.pyi:22-24`; `.cache/bpy-stubs/5.2/bpy-stubs/props/__init__.pyi:612`).
  At runtime, however, the instance attribute is the value (`int` and so on). This gap is the central
  "expected type" question. Operator return values are enum sets
  (`blender/source/blender/makesrna/intern/rna_wm.cc:596-604`; `doc/python_api/examples/bpy.types.Operator.0.py:28`),
  and fake-bpy-module types enums as `Literal`, so `return {"FINISH"}` can be a meaningful negative test.

### 2.4 Dynamic and generated test data: tools

- **mypy stubtest** (https://mypy.readthedocs.io/en/stable/stubtest.html):
  - It "will import your code and introspect your code objects at runtime" and compares them with the stubs.
  - Allowlists are set with `--allowlist` and `--generate-allowlist`. `--ignore-missing-stub` and `--concise` are also available.
  - It "cannot tell if a return type of a function is accurately typed".
  - mypy must be installed in the same environment as the runtime package.
  - For bpy that means running inside Blender's Python, or using the `bpy` PyPI module
    (`blender/doc/python_api/rst/info_advanced_blender_as_bpy.rst:10-16`, which behaves like `--factory-startup`, `:84-90`).
- **hypothesmith** (https://github.com/Zac-HD/hypothesmith):
  - `from_grammar()` and `from_node()` (LibCST) generate syntactically valid Python.
  - It makes no claim about semantic validity and says "DO NOT EXECUTE CODE GENERATED BY THESE STRATEGIES".
  - It describes itself as "definitely pre-alpha".
- **Hypothesis** (https://hypothesis.readthedocs.io/) offers composite and recursive strategies and
  shrinks failing examples to minimal ones. These are the building blocks for a *model-based* addon generator.

---

## 3. Recommended layout (Recommendation)

Keep the two kinds of example separate:

- **`examples/addons/`** stays as it is: realistic addons, used as a smoke test of whether real code type-checks.
- **A new `tests/typecheck/` tree** holds *feature* tests. Each feature folder is still a valid, installable
  extension, so the same code can also be loaded in Blender to confirm that the expected types are true.

```text
tests/typecheck/
├── ty.toml                         # rule levels for test files (see below)
├── README.md                       # the conventions in this section
├── features/                       # hand-written; one folder = one feature = one installable extension
│   ├── props_annotations/
│   │   ├── blender_manifest.toml
│   │   ├── __init__.py             # classes + register()/unregister(); idiomatic, no assertions
│   │   └── check_props_annotations.py   # assert_type + expected-error markers (imports from __init__)
│   ├── props_pointer_on_id/        # bpy.types.Scene.x = PointerProperty(...), annotation-on-class form, del
│   ├── props_collection/           # CollectionProperty: add(), iteration, indexing types
│   ├── operator_basics/            # execute/invoke/modal/poll signatures, return sets, bl_options, report()
│   ├── operator_props/             # self.<prop> types inside execute, FloatVectorProperty subtypes
│   ├── panel_draw/                 # Panel.draw, self.layout nullability, UILayout.prop/operator
│   ├── context_members/            # context.active_object, scene, selected_objects, temp_override
│   ├── addon_preferences/          # AddonPreferences with bl_idname = __package__
│   ├── ui_list/                    # UIList.draw_item signature
│   ├── handlers_timers/            # bpy.app.handlers / bpy.app.timers callback signatures
│   ├── mathutils/                  # Vector/Matrix operators, swizzles
│   └── legacy_bl_info/             # a bl_info addon, to keep the legacy path covered
├── corpus/                         # optional: list of external files to check (Blender templates_py etc.)
│   └── sources.txt
└── expected/                       # current status per (generator, version); regenerated, reviewed in diffs
    ├── fake-bpy-module/5.2.txt
    └── builtin/main.txt

.cache/typecheck-generated/<version>/  # generated tests (section 5); never committed
.cache/typecheck-results/<version>/<generator>/
```

Conventions:

1. **Spec files, named like typeshed's.** Files called `check_*.py` contain only assertions and are never
   imported by `__init__.py`, so the addon still runs in Blender. The assertions describe **what is true at
   runtime in Blender**, not what the stubs currently say. A failing assertion means "the stubs are wrong
   here, or ty does not support it".
2. **Assert on parameters, not runtime instances.** Put assertions in functions such as `def _(ctx: Context) -> None:`,
   so nothing needs a real `Context`. This is the typeshed style.
3. **Two marker kinds, both native to ty, so no harness is needed to *run* them:**
   - **Positive:** `assert_type(expr, T)`. A mismatch is reported as `type-assertion-failure`.
   - **Negative:** `# ty: ignore[<rule>]` on code that must be rejected. With
     `unused-ignore-comment = "error"`, the test fails if ty stops reporting the error.

   Optionally write `# type: ignore[<mypy-code>, ty:<rule>]` instead. One comment then serves ty and mypy,
   which Blender's own `check_stubs.py` uses (`suppression.md:70-80`).
4. **`reveal_type` only for snapshots.** It produces `info` output, not failures. Section 5.3 uses it for
   golden files.
5. **The extension skeleton is fixed and boring.** The manifest is copied from `simple_scatter`, and
   `__init__.py` follows `info_overview.rst` exactly. This makes a failure point at one idiom, not at the
   scaffolding.

`tests/typecheck/ty.toml`:

```toml
[rules]
unused-ignore-comment = "error"        # an expected error that did not happen is a failure
unused-type-ignore-comment = "error"
type-assertion-failure = "error"       # default already, stated for clarity
undefined-reveal = "ignore"            # allow bare reveal_type in snapshot files
```

## 4. Example feature test (Recommendation; semantics illustrated with ty 0.0.95)

`tests/typecheck/features/props_annotations/__init__.py`, written idiomatically as in `info_overview.rst:364-409`:

```python
from __future__ import annotations

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatVectorProperty, IntProperty,
                       PointerProperty, StringProperty)
from bpy.types import PropertyGroup


class Item(PropertyGroup):
    label: StringProperty(name="Label")


class Settings(PropertyGroup):
    count: IntProperty(name="Count", default=1, min=0)
    enabled: BoolProperty(name="Enabled")
    offset: FloatVectorProperty(name="Offset", subtype="TRANSLATION", size=3)
    mode: EnumProperty(items=[("A", "A", ""), ("B", "B", "")])
    target: PointerProperty(type=bpy.types.Object)
    items: CollectionProperty(type=Item)


classes = (Item, Settings)


def register() -> None:
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.props_annotations = PointerProperty(type=Settings)


def unregister() -> None:
    del bpy.types.Scene.props_annotations
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
```

`tests/typecheck/features/props_annotations/check_props_annotations.py`:

```python
"""Expected types of PropertyGroup annotations, as observed at runtime in Blender."""
from __future__ import annotations

from typing import assert_type

import bpy
from bpy.types import Context, Object, bpy_prop_collection
from mathutils import Vector

from . import Item, Settings


def instance_values(s: Settings) -> None:
    assert_type(s.count, int)                 # today: Unknown -> type-assertion-failure (verified)
    assert_type(s.enabled, bool)
    assert_type(s.offset, Vector)             # TRANSLATION subtype -> mathutils.Vector (verify at runtime)
    assert_type(s.mode, str)
    assert_type(s.target, Object | None)
    assert_type(s.items, bpy_prop_collection[Item])   # exact spelling depends on the stubs' generic


def assignments(s: Settings) -> None:
    s.count = 3
    s.count = "3"  # ty: ignore[invalid-assignment]
    s.target = None


def scene_attribute(ctx: Context) -> None:
    scene = ctx.scene
    assert scene is not None
    assert_type(scene.props_annotations, Settings)   # needs a stub/plugin story for runtime-added attributes
```

`tests/typecheck/features/operator_basics/check_operator_basics.py`, with negative tests that only make
sense because the stubs type enums as `Literal`:

```python
from __future__ import annotations

from typing import assert_type

from bpy.types import Context, Event, Operator


class GoodOp(Operator):
    bl_idname = "test.good"
    bl_label = "Good"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: Context) -> bool:          # today: invalid-method-override with fake-bpy-module
        return True

    def execute(self, context: Context) -> set[str]:  # the common idiom; should it be accepted?
        return {"FINISHED"}


class BadReturn(Operator):
    bl_idname = "test.bad"
    bl_label = "Bad"

    def execute(self, context: Context):
        return {"FINISH"}  # ty: ignore[invalid-return-type]


class BadOptions(Operator):
    bl_idname = "test.bad_options"
    bl_label = "Bad options"
    bl_options = {"REGISTR"}  # ty: ignore[invalid-assignment]


def report(op: Operator) -> None:
    op.report({"INFO"}, "ok")
    op.report({"NOPE"}, "x")  # ty: ignore[invalid-argument-type]
```

**Open design decision.** Is `-> set[str]` "correct"? It is idiomatic Blender code, but under strict
override rules it is incompatible with a `set[Literal[...]]` base. The tests are where that policy gets
written down.

### How the task runner invokes it (Recommendation)

Add a `check:features` task next to `check:addons`, copying `scripts/check_addons.py`, which already
resolves generators, stubs and the Python version:

```toml
[tasks."check:features"]
description = "Type-check the feature tests in tests/typecheck/ and compare with tests/typecheck/expected/"
usage = '''
arg "<version>" help="Blender version as X.Y (e.g. 5.2), or the name of a blender:build build (e.g. main)"
arg "[features]" var=#true help="Feature directory names (default: all)"
flag "--generator <generator>" default="all" { choices "fake-bpy-module" "builtin" "all" }
flag "--update" help="Rewrite tests/typecheck/expected/<generator>/<version>.txt"
flag "--generated" help="Also check the generated tests in .cache/typecheck-generated/<version>/"
'''
run = 'uv run scripts/check_features.py {{usage.version}} ...'
```

`scripts/check_features.py` would do five things:

1. Run the existing command shape once per generator:
   `ty check --project tests/typecheck --config-file tests/typecheck/ty.toml --python-version <py> --extra-search-path <stubs> --output-format concise <dirs>`.
2. Parse each line `path:line:col: severity[rule] message` (verified format) and attribute it to the
   assertion on that line. An `assert_type` line is a fail if `type-assertion-failure` is reported there.
   A `ty: ignore` line is a fail if `unused-ignore-comment` is reported there. Any other diagnostic is an
   unexpected error.
3. Write `.cache/typecheck-results/<version>/<generator>/summary.md`: a feature × generator pass/fail matrix,
   matching the style of `report:flags` (`report_flags.py:17-23`).
4. Compare normalized results (`file:line:rule`, without messages) with
   `tests/typecheck/expected/<generator>/<version>.txt`, and exit non-zero only on a **change**. The
   expectation file plays the role of mypy's `-xfail`: it records known failures, so improvements and
   regressions both show up as diffs.
5. With `--update`, rewrite the expectation file.

**Why not ty's `--baseline`?** It is preview and its format may change (`configuration.md:10`). It stores
no line numbers, and *verified locally* it hides baselined failures entirely, so a fixed failure would not
show up. A plain-text file of known failures that the harness owns is easier to review.

---

## 5. Generated and dynamic testing

### 5.1 RNA-generated assertion files (highest value per cost)

**What.** A Blender-side script, either a sibling of `scripts/blender/dump_rna_flags.py` or a new mode of
it, dumps for every struct:

- each property's RNA type, `fixed_type`, `is_never_none`, array length and subtype, and enum items
  (`_rna_info.py:327-357`);
- function parameters and return values;
- and, where the probe pool has an instance (`build_pool`, `dump_rna_flags.py:136`), the **runtime
  `type()` of the actual value**.

A host-side generator then writes `.cache/typecheck-generated/<version>/check_<Struct>.py`:

```python
def _(x: bpy.types.Object) -> None:
    assert_type(x.location, Vector)              # RNA: FLOAT[3] TRANSLATION; runtime: Vector
    assert_type(x.parent, Object | None)         # RNA: POINTER, not never_none
    assert_type(x.modifiers, ObjectModifiers)    # RNA: COLLECTION with srna
    x.type = "MESH"
    x.type = "NOT_A_TYPE"  # ty: ignore[invalid-assignment]   # from enum_items
```

**The oracle.** Expected types come from runtime facts: the RNA metadata, cross-checked against the
observed `type()`. They do not come from the docs, so the tests are independent of both generators (§1).
The RNA→Python mapping table (`FLOAT` + `TRANSLATION` → `Vector`, `POINTER` + nullable → `T | None`, …)
becomes the reviewed spec. Where the mapping and the observed runtime type disagree, report it rather than
guessing.

**Cost.** Medium. The Blender launch, crash-skipping and instance pool already exist (`dump_rna_flags.py:16-19`).
The new parts are the generator, the mapping table and the harness from §4.
`.cache/ty-results/main.txt` shows ty handles 21 651 diagnostics over Blender's source, so tens of thousands
of generated assertions should be within reach. That is my inference, not measured.

**How it differs from `report:flags`.** That task compares stub *text*. This one asks the checker what it
*infers*, so it catches inheritance, generics, overloads, `Self`, `__getattr__` and import-resolution
problems that a text comparison cannot see.

**Extensions:**
- Functions: generate a call with only the required args (positive) and one with a missing or extra
  keyword (negative, `ty: ignore[missing-argument]` / `[unknown-argument]`).
- Operators: `bpy.ops.<mod>.<op>(**kw)` with each argument's RNA type, and a wrong-typed keyword as the
  negative case.

### 5.2 Differential runs over existing corpora (cheap)

Run the same `ty check` against **both** generators over the corpus Blender itself uses
(`doc/python_api/examples`, `scripts/templates_py`, `scripts/addons_core`; `check_stubs.py:80-87`). Then
diff the normalized diagnostics. A diagnostic that appears with only one generator points at a stub
difference.

`check:blender` already produces the raw output (`.cache/ty-results/<version>.txt` and `-builtin.txt`).
Only the normalize-and-diff step is new.

**Cost:** low. **Value:** triage input for which hand-written features to add next.

### 5.3 Golden `reveal_type` snapshots (cheap once 5.1 exists)

Generate `reveal_type(x.<prop>)` for every property and store the normalized `info[revealed-type]` lines
(verified format) as `.cache/typecheck-results/<version>/<generator>/revealed.txt`. Diffs between versions,
generators or ty builds then show every inferred type that changed.

This is the same idea as mdtest's `# revealed:` and inline snapshots (`ty_test/README.md:46-69, 145-204`),
done outside cargo. The snapshots are for review, not pass/fail. Commit only small curated subsets.

### 5.4 Runtime confirmation of the hand-written expectations (medium)

Load each feature extension in Blender (`blender --background --factory-startup --python <runner>`, the
same style as `report_flags.py` uses) and call `register()`. Then import the `check_*.py` module after
replacing `typing.assert_type` with a checking version. `from typing import assert_type` binds the module
attribute at import time, so a replacement installed first is the one the check file uses.

The checking version would do an `isinstance` check, or use `typeguard.check_type` for unions and
generics. To call `_(x)` functions it needs instances: a `bpy.context` override, or instances from the
probe pool.

This proves the "expected types" in the spec files are true.

**Limits.** Stub-only types such as `_PropertyDeferred`, and generic subscripts that may not be
subscriptable at runtime (`bpy_prop_collection[Item]`), would need a skip list. **Not verified.**

### 5.5 Model-based random addon generation (high cost)

**Not hypothesmith.** Its output is syntactically valid but semantically random, and it warns against
executing it (§2.4). For stubs this would mostly produce unresolved-name noise.

**Instead (Recommendation):**
1. Write Hypothesis strategies over a small *addon model*: PropertyGroups with N properties of random kinds
   and keyword arguments (nested `PointerProperty` / `CollectionProperty`), Operators with random
   `bl_options` and return sets, and Panels whose `draw` calls `UILayout` functions taken from the RNA dump.
2. Render the model to source and derive the expected types from the model.
3. **Mutation mode:** inject exactly one known error, such as a wrong enum literal, a wrong property type
   assignment or a missing required argument, and assert that ty reports exactly that rule on that line.
4. Optionally load the generated addon in Blender to confirm it registers.

Hypothesis shrinking then turns a failure into a minimal reproducer.

**Throughput.** Each `ty check` loads the full stub set, so running one subprocess per Hypothesis example
is slow. Generate seeded batches of a few hundred files, run one ty pass, then shrink only the failures.
This is my inference; the per-run cost was not measured.

### 5.6 stubtest (experiment only)

It would have to run in a Python where both `bpy` and mypy import: Blender's bundled Python with mypy
installed, or the `bpy` PyPI module. bpy is a poor fit for three reasons:

- RNA properties are exposed dynamically through `bpy_struct`. Whether stubtest's attribute introspection
  sees them is **unverified**.
- `bpy_func` / operator callables may not expose signatures stubtest can read (**unverified**).
- It does not check return types (§2.4).

The repo's own RNA-based probe (`dump_rna_flags.py`) already does what stubtest would do here, using the
RNA metadata. At most, try one `--ignore-missing-stub --concise` run to see how noisy it is.

### Recommended order of investment

1. **§3–4:** `tests/typecheck/` with 5–10 hand-written features seeded from the 12 `simple_scatter`
   diagnostics, `ty.toml` with unused ignores set to error, the `check:features` task and expectation files.
2. **§5.2:** generator-differential over Blender's corpus. Almost free, since it reuses `check:blender` output.
3. **§5.1:** RNA-generated `assert_type` / enum / call-shape files, reusing the probe pool.
4. **§5.3:** `reveal_type` golden snapshots, generated next to 5.1.
5. **§5.4:** runtime confirmation of the hand-written specs in Blender.
6. **§5.5:** model-based random addons plus mutation. Do this only once 1–3 stop finding new classes of bug.
7. **§5.6:** stubtest, only as a one-off experiment.

---

## 6. Open questions

- **Policy for runtime-added attributes.** `bpy.types.Scene.x = PointerProperty(...)` does not exist
  statically. What should a feature test expect: an error, `Any`, or a plugin or special case in the ty fork?
- **What a property annotation should infer to.** Today it is `invalid-type-form` and `Unknown`
  (verified). The options are teaching the ty fork about `_PropertyDeferred` or changing the stubs, for
  example making `IntProperty(...)` return a descriptor-like type. The tests should encode the desired end
  state either way.
- **Override strictness.** Should `execute(self, context) -> set[str]` and `poll(cls, context: Context)`
  be accepted (§4)? fake-bpy-module's `Context | None` parameter makes the idiomatic override invalid.
- **Different expectations per generator.** Use one spec plus expectation files per generator (proposed),
  or allow generator-specific markers?
- **The Python version for `assert_type`.** It needs 3.11 (`typing` docs). `check_addons.py` passes
  Blender's Python version, so older Blender versions would need `typing_extensions` in the stub search
  path. Not checked.
- **`tests/typecheck/` vs `examples/features/`.** Placing it under `examples/` matches `EXAMPLE_ADDONS_DIR`
  in `scripts/_common.py:17` but mixes realistic examples with specs.
- **mypy and pyright.** Should the spec files also be run with them, using
  `# type: ignore[<mypy>, ty:<rule>]` markers? That would compare checkers as well as stubs.
