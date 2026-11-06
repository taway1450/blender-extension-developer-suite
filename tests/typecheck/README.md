# Feature tests for the Blender typechecker

Each feature in `features/` is something the typechecker (ty-blender) has to add on top of the bpy stubs, or a runtime
fact the stubs must state, and it is tested by add-ons that cover all its variants. The markers state what Blender does at runtime, so they
deliberately differ from what the stubs say: an annotation `count: IntProperty()` is an `int` on the instance,
`bpy.ops.my_addon.run` exists once `register()` registers it, and so on.

```sh
mise run features:generate            # write the generated add-ons and the ty.toml import roots
mise run check:load main              # every add-on loads in Blender as its _expected/runtime.toml says
mise run check:oracle main            # the markers agree with the reference stubs (stock ty)
mise run check:features main          # ty-blender: assert_type and expected errors
mise run check:ide main               # ty-blender's language server: hover, signature help, completions
mise run check:features main --update # record the current results after a reviewed change
```

| Feature | What the checker adds |
| --- | --- |
| [addon_discovery](features/addon_discovery/README.md) | find add-ons (`blender_manifest.toml`, `bl_info`), their `__init__.py` and `register` |
| [bpy_symbols](features/bpy_symbols/README.md) | recognise `bpy.props`, `bpy.types`, `bpy.utils`, `bpy.ops`, handlers, `mathutils`, `bpy_extras` however imported |
| [properties](features/properties/README.md) | property annotations and registered properties have their runtime types |
| [property_wrappers](features/property_wrappers/README.md) | anything that evaluates to a property counts as that property |
| [registration](features/registration/README.md) | follow `register()` to what it registers |
| [registration_checks](features/registration_checks/README.md) | report registration mistakes; keep add-ons apart |
| [operator_calls](features/operator_calls/README.md) | `bpy.ops.<category>.<name>(...)` with the operator's properties as arguments |
| [operator_properties](features/operator_properties/README.md) | an idname string gives that operator's properties (`layout.operator(...)`, keymaps, ...) |
| [addon_preferences](features/addon_preferences/README.md) | `addons[__package__].preferences` is the add-on's own class |
| [inheritance](features/inheritance/README.md) | unannotated overrides get the parent's types; subclass, mixin and override rules |
| [api_types](features/api_types/README.md) | the stubs state it: pointers and callback parameters that are never None |

## Layout

```text
tests/typecheck/
├── ty.toml                          # rules; the import roots are written by features:generate
├── oracle/<generator>/              # deltas for the bpy stubs, merged before the reference stubs (oracle/README.md)
├── features/<feature>/
│   ├── README.md                    # what the checker must do, the variants, rules and runtime facts
│   ├── <addon>/                     # an add-on, usually a package with several modules
│   │   ├── blender_manifest.toml    # or bl_info in __init__.py
│   │   ├── __init__.py ...          # idiomatic add-on code; markers only for errors in it
│   │   ├── check_<addon>.py         # type markers (check:features, check:oracle)
│   │   ├── ide_<addon>.py           # editor markers (check:ide), optional
│   │   └── _expected/
│   │       ├── stubs/<module>.pyi   # reference stub deltas: bpy.types.pyi, bpy.ops.<category>.pyi, ...
│   │       ├── addon/<path>.pyi     # reference stubs of the add-on's own modules
│   │       └── runtime.toml         # how the add-on loads in Blender (default: it registers)
│   ├── <addon>.py                   # a single-file add-on
│   └── generated/<addon>/           # add-ons written by scripts/feature_generators/<feature>.py
└── expected/<generator>/
    ├── <version>.txt                # check:features results that are not passes
    ├── <version>.ide.md             # check:ide results, passes and failures
    └── <version>.progress.md        # passing markers per feature, written by --update
```

Each add-on is a top-level package (its feature folder is an import root), so add-on names are unique across all
features. `check_*.py` and `ide_*.py` are modules of the add-on (they can use relative imports and `__package__`)
but are never imported, and the manifests exclude them from builds. Generated add-ons must not be edited: change
the generator and run `mise run features:generate`; `--check` fails when they are out of date.

## Type markers (`check_*.py`)

- `assert_type(expr, T)` states the type `expr` has **at runtime in Blender**. It fails when ty reports
  `type-assertion-failure` on that line.
- `# ty: ignore[rule]` marks code that must be rejected. It fails when ty reports `unused-ignore-comment` (the
  error is gone), or `ignore-comment-unknown-rule` for a `blender-*` rule ty does not have yet. Several rules can
  share one comment.
- `# oracle-skip: reason` keeps a line out of the oracle run, for what reference stubs cannot express (a class
  defined in the check file, `__package__`, class-level access after registration).
- `# bare-ok: reason` marks a **guard**: a marker that is meant to hold without ty-blender, such as a stub type
  the checker must keep. The bare run (below) does not flag it, and `progress.md` counts it on its own.
- Any other diagnostic in an add-on folder, `__init__.py` included, is recorded as unexpected. On a marker's line
  it also fails the marker: an `assert_type` whose asserted type does not resolve (`bpy_prop_array[float]` where
  the stubs' `bpy_prop_array` is not generic) compares Unknown with Unknown, so ty reports no
  `type-assertion-failure` although nothing was checked.

Write assertions inside functions that take the objects as parameters (`def _(scene: Scene) -> None:`).

The `blender-*` rules ty-blender is to add:

| Rule | Feature |
| --- | --- |
| `blender-invalid-register`, `blender-invalid-addon-metadata` | addon_discovery |
| `blender-unsupported-property-host`, `blender-legacy-property`, `blender-invalid-property`, `blender-unsupported-property-target` | properties |
| `blender-unregistered-class`, `blender-unreachable-registration`, `blender-register-order`, `blender-duplicate-registration`, `blender-invalid-idname`, `blender-unregister-mismatch` | registration_checks |
| `blender-invalid-operator-property`, `blender-unknown-operator` | operator_calls, operator_properties |
| `blender-preferences-idname` | addon_preferences |
| `blender-invalid-override`, `blender-missing-callback`, `blender-mixin-order`, `blender-invalid-base`, `blender-registered-base` | inheritance |

## Reference stubs and the oracle (`check:oracle`)

Markers are written by hand from Blender's behaviour, and the reference stubs say the same in stub form: what the
checker should synthesise for this add-on. `check:oracle` copies the bpy stubs, merges the baseline in `oracle/`
and the add-on's `_expected/stubs/` deltas into them, puts `_expected/addon/` next to the add-on's modules, and
runs **stock ty** on the add-on. Every marker in its `check_*.py` files must then hold (`blender-*` markers and
`oracle-skip` lines aside). A disagreement means the markers or the reference stubs are wrong, before ty-blender
is involved at all. Deltas are merged per member:

- a member of an existing class or module replaces the stub's member;
- an `@overload` goes in front of the existing definition, which becomes the last overload;
- a class that states different bases or type parameters replaces the stub's class;
- anything else is added; a module the stubs lack is created.

A delta is named after the module it changes (`bpy.types.pyi`, `bpy.ops.my_category.pyi`); a new operator
category also needs `bpy.ops.pyi` with `from bpy.ops import my_category as my_category`.

### The bare run

The oracle shows that the markers are right; the **bare run** shows that they need the checker. `check:oracle` also
runs stock ty on the add-ons with nothing but the bpy stubs: no `oracle/` baseline, no reference stubs. Every marker
should then fail, because each one states something only ty-blender provides. A marker **holds on the bare stubs**
when stock ty reports nothing on its line (apart from unknown `blender-*` rules): an `assert_type` that passes with no
other error on the line, or an expected error whose stock rules stock ty already reports. `oracle-skip` lines are
judged too; `blender-*`-only expected errors and guards are not.

A marker that holds on the bare stubs of **every** generator tests nothing of the checker: make it need the checker,
drop it (in a generator, for generated add-ons), or mark it `# bare-ok: reason` if it is a guard. One that holds on
a single generator is listed for information. The hits go to the end of `oracle.md`, and hits on every generator
fail the task. A run of one `--generator` cannot tell, so there the hits are only reported.

## Runtime check (`check:load`)

Every add-on is imported, registered and unregistered in Blender. `_expected/runtime.toml` says when that is meant
to fail:

```toml
register = "fails"   # "ok" is the default
reason = "PropertyGroup registered after the class that points to it"
packages = ["addons/ws_alpha", "addons/ws_beta"]  # a folder holding several add-ons
load = false         # not an add-on (a library other add-ons import)
error = "to have 2 args, found 1"   # text the error of a failing add-on must contain

[[probe]]            # evaluated in Blender after register(); expect is the value it must give, or "raises"
code = "healthy(addon.MY_PT_parent)"
expect = false
reason = "registering MY_PT_child detached the parent's Python class"
```

A probe is a Python expression with `bpy`, `addon` (the add-on module) and the helpers `healthy(cls)` and
`can_add_node(tree_idname, node_idname)` from `scripts/blender/load_feature_addons.py`. Probes check what an add-on
that loads does wrong (or right) at runtime.

An add-on that fails on purpose stops at its first error. Where the mistakes can be split up, there is one add-on
per mistake (the inheritance feature generates them); otherwise each invalid case in it was checked on its own in
Blender (the add-on's docstring says so).

## Editor markers (`ide_*.py`)

A comment line below the code puts a caret at the column to query. Several markers can stack under one line.

```python
scene.reg_int
#     ^hover
#     ^hover-contains "int"
```

| Marker | Records |
| --- | --- |
| `^hover` | the hover Markdown |
| `^hover-contains "text"` | PASS if the hover text contains `text` |
| `^hover-none` | PASS if there is no hover |
| `^signature` | the signature label, parameters with their docs, and the documentation |
| `^signature-param "text"` | PASS if the active parameter's documentation contains `text` |
| `^completion a b` | `detail`, documentation and deprecated tag of the completion items `a` and `b`; FAIL if one is not offered, or its `detail` holds `Unknown` (ty offers names it cannot type) |
| `^deprecated` | PASS if a `deprecated` diagnostic covers the caret |

Code under a `^completion` caret is unfinished on purpose (`scene.reg_`); `check:features` ignores `ide_*.py`.
IDE test files must be ASCII, because LSP positions count UTF-16 code units.

## Expected results

The `expected/` files record the current state, failures included. `check:features` and `check:ide` fail when the
results differ from the recorded ones, so a checker improvement shows up as a diff just like a regression. Review
the diff, then run the task with `--update`. Running a subset (`mise run check:features main properties`) compares
and updates only those add-ons' entries, plus any entries of add-ons that no longer exist: those show up as gone
and `--update` drops them.

Entries name a line by its text, not its number: `path | rule | source line` in `<version>.txt`, and
`path | ^marker @column | source line` as an `<version>.ide.md` section title. When the same text occurs again in
a file, the later lines get ` #2`, ` #3` ... So adding, removing or moving code changes no entry, unless the code
is a copy of a line further down. The terminal output of a run still shows line numbers.

`<version>.progress.md` counts the markers that pass per feature, for type markers, expected errors and IDE markers
(`^hover` and `^signature` only record, so they are not counted). Guards (`# bare-ok`) get a column of their own. Its last column counts recorded diagnostics on lines
without a marker. `--update` of either task rewrites it for every feature, from the recorded results and the current
markers, so it also stays complete after a partial run.

The marker grammar is parsed in `scripts/_markers.py`, and the recorded results are read and written in
`scripts/_baseline.py`. `mise run test:scripts` runs the harness's own tests (`scripts/tests/`, no ty or Blender
needed): the marker grammar, how ty's diagnostics become marker results and every way a marker fails, the recorded
results and `progress.md`, the oracle's verdict and stub-delta merge, the bare run, IDE rendering and runtime probes.
