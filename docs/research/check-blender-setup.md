# check:blender setup: Cycles, numpy and the bucket report (#73)

Research for map #67. Blender `main` at `dc491af090` (`.cache/blender-src/main`), binary in
`.cache/blender-bin/main` (Blender 5.4), ty-blender as pinned on `main` of this repo. Inputs: the full
outputs `.cache/analysis/main-builtin.txt` / `main-fake.txt` and the prototype `.cache/analysis/bucket.py`.
Nothing here was verified by a new ty run (`check:blender` builds ty); the numbers come from re-classifying the
recorded outputs.

## Answer in short

- **Cycles needs no search path and no Discovery override.** Its files are already checked (they sit under the
  project root and outside `lib/` / `extern/`) and ty-blender already discovers `intern/cycles/blender/addon` as a
  Legacy add-on by its `bl_info`. `Scene.cycles` fails for a different reason: Cycles assigns its Registered
  properties in a `PropertyGroup.register()` **classmethod**, which Blender calls from `register_class`, and the
  `register()` walk does not follow it. That is a ty-blender registration gap (a marker in `registration` /
  `properties`), not a setup step. Uses outside the add-on (presets, `tests/`) stay unresolved by design
  (add-ons are kept apart).
- **numpy:** `.cache/blender-bin/main/5.4/python/lib/site-packages/numpy` (numpy 2.3.4, ships `.pyi` and
  `py.typed`). Put only numpy on the search path, through a directory of links under `.cache/`, not the whole
  `site-packages` (which would shadow typeshed's `typing_extensions`).
- **Bucket report:** the rules below give the map's eight buckets and three areas, reproduce the map's numbers
  within a few percent, and are stable against line shifts by construction (the summary has no line numbers,
  and each diagnostic is classified from the source line of the same worktree ty just read).

## Cycles

**How Blender installs it.** `intern/cycles/CMakeLists.txt` sets `CYCLES_INSTALL_PATH` to
`scripts/addons_core/cycles` (lines 8-19), and `intern/cycles/blender/CMakeLists.txt` installs the ten files of
`ADDON_FILES` (`addon/__init__.py` ... `addon/version_update.py`) there with
`delayed_install(${CMAKE_CURRENT_SOURCE_DIR} "${ADDON_FILES}" ${CYCLES_INSTALL_PATH})` (lines 85-113). So at
runtime the package is `cycles` on the `addons_core` path; in the source tree it is the folder `addon`.

**What ty-blender already does with it.** `crates/ty_blender/src/discovery.rs` (`folder_addon`) makes any folder
whose `__init__.py` has a top-level `bl_info` a Legacy add-on named after the folder; Cycles'
`addon/__init__.py` has one. So Cycles is an add-on today, named `addon` instead of `cycles`. The name only
matters where code spells the Add-on name, and Cycles reaches its preferences through `__package__`. A Discovery
override would not help: it turns the listed root into an Extension named by manifest `id` or folder, so still
`addon`, and a `[tool.blender]` table in Blender's root `pyproject.toml` would replace discovery for the whole
tree.

**Why `Scene.cycles` does not resolve.** The output has 74 `has no attribute cycles*` diagnostics
(`Scene | None` 69, `ViewLayer | None` 3, `World | None` 1, `cycles_curves` 1): 50 inside the Cycles add-on
(48 in `ui.py`), 12 in `scripts/presets/cycles/`, 12 in `tests/`. Inside the add-on the cause is the shape of
the registration in `addon/properties.py`:

```python
class CyclesRenderSettings(bpy.types.PropertyGroup):
    @classmethod
    def register(cls):
        bpy.types.Scene.cycles = PointerProperty(..., type=cls)
```

Blender calls that classmethod from `bpy.utils.register_class`: `pyrna_register_class` in
`source/blender/python/intern/bpy_rna.cc` ("Call classed register method", about line 10736) looks up
`register` on the class and calls it with no arguments; `unregister` is called the same way (about line 10869).
The `register()` walk (`ty_python_semantic/src/types/dedicated/blender/walk.rs`) records `register_class(C)` as a
class event (`class_event`) but never runs `C.register`, and since Cycles' walk completes, the directory-walk
fallback in `index.rs` (which would find the assignment syntactically) is not consulted. **Fix:** when the walk
registers a class that defines a `register` classmethod, run it as a call (and `unregister` on
`unregister_class`). It belongs in the spec as a `registration` / `properties` marker (a PropertyGroup whose
`register` classmethod assigns a Registered property), not in `check_blender.py`.

**Outside the add-on.** Presets (`bpy.context.scene.cycles`) and tests read Cycles' properties from code that is
in no add-on or another one; the settled rule "what one add-on registers is not visible in another"
(`registration_checks` README) keeps those 24 unresolved. They are classified `check-setup` so they stay visible
in one place.

**Optional, low value:** `scripts/modules/_bpy_internal/system_info/text_generate_runtime.py:240` does
`import cycles`. Resolving it would need a `cycles` link to the add-on folder on an extra search path, which gives
ty a second path to the same files; one diagnostic does not justify it.

**What stays:** 33 `import-not-found` for `_cycles` (31 in `engine.py` and friends), the compiled module Blender
builds. No stub exists; it stays in `check-setup`.

## numpy

- Location: `<blender-bin>/<X.Y>/python/lib/site-packages/numpy` on Windows
  (`.cache/blender-bin/main/5.4/...`, and `.cache/blender-bin/5.2/5.2/...` for 5.2, also numpy 2.3.4);
  on Linux Blender's layout is `<X.Y>/python/lib/python3.13/site-packages`. Find it from `find_blender(...)`
  (`scripts/generate_stubs.py`) as `blender.parent.glob("*/python/lib/**/site-packages/numpy")`.
- It is typed: `numpy/py.typed`, 263 `.pyi` files, `numpy-2.3.4.dist-info`.
- 63 diagnostics today are `Cannot resolve imported module numpy` (the largest import group).
- **Only numpy.** `--extra-search-path` takes directories, and Blender's `site-packages` also holds
  `typing_extensions.py`, `setuptools`, `pip`, `Cython`, `mesonbuild` and others. Extra search paths come before
  typeshed in ty's resolution order, so the whole folder would put a runtime `typing_extensions.py` in front of
  typeshed's stub. Instead create `.cache/blender-site/<version>/` holding a link `numpy` → the bundled package
  (a directory junction on Windows via `_winapi.CreateJunction`, which needs no admin rights; `os.symlink`
  elsewhere), recreated when missing, and pass that folder as one more `--extra-search-path` after the stubs.
  Keep the list of linked packages a constant (`BLENDER_SITE_PACKAGES = ["numpy"]`) so others can join later
  (`requests` 6, `zstandard` 3, `cattrs` 6 and `docutils` 5 diagnostics are the next candidates).
- Extra search paths are not first-party roots (`SearchPath::extra` in `ty_module_resolver/src/path.rs`;
  `is_first_party` in `dedicated/blender/addon.rs` only counts `FirstParty` paths), so numpy is never taken for
  add-on code by the register walk.
- Expect some diagnostics to move rather than vanish: code that was `Unknown` through a missing numpy gets real
  numpy types.

## Bucket report

### Areas

| Area | Paths (relative to the source root, first match) |
| --- | --- |
| `shipped` | `scripts/startup/`, `scripts/modules/`, `scripts/addons_core/`, `scripts/freestyle/`, `intern/cycles/blender/addon/` |
| `presets` | `scripts/presets/` |
| `other` | everything else: `tests/`, `doc/`, `tools/`, `build_files/`, plus `scripts/templates_py/` (137), `release/` (11), `source/` (5), `intern/cycles/{app,doc,hydra}` (17) |

The prototype counted `tools/` and `build_files/` as product and missed the Cycles path; this fixes both. Paths in
ty's concise output are relative with `\` on Windows: normalise to `/` first.

### Buckets (first matching rule wins)

`text` is the source line the diagnostic points at, read from the checked worktree; `msg` the message.

| # | Bucket | Recognised by |
| --- | --- | --- |
| 1 | `check-setup` | rule `import-not-found` / `unresolved-import` / `possibly-missing-submodule`, or `Cannot resolve imported` in msg; or `Object of type ... has no attribute cycles*` (Cycles' Registered properties) |
| 2 | `dynamic` | `Self@` in msg (mixins without a Blender base) or `ToolDef` in msg (monkeypatched `ToolDef.from_fn`) |
| 3 | `operator-call` | `bpy.ops.` in text, or `OperatorProperties` in msg (`layout.operator(...)` results), or `too-many-positional-arguments` with a string literal on the line (positional `execution_context`) |
| 4 | `type-tag` | msg names `` `ID` `` / `` `ID \| None` `` and `data` is in text (`ob.data` by `ob.type`) |
| 5 | `context-member` | nullable msg (`\| None` in a type) and either the attribute in `Attribute X is not defined on None` follows a context member on the line (`context.<m>.X`, also `bpy.context`, `C`, `ctx`), or the union is one of `Scene / ViewLayer / WindowManager / Preferences / ToolSettings / Space / Region / Area / Screen / Window / WorkSpace / Context \| None`, or `Object \| None` with a context expression on the line |
| 6 | `type-tag` | nullable msg on a type-discriminated settings pointer (`DomainSettings`, `FlowSettings`, `EffectorSettings`, `RigidBody*`, `FieldSettings`, `ParticleSettings`, `Brush*Settings`, `SceneEEVEE`) |
| 7 | `pointer-none` | any other nullable msg (pointer properties, plus plain `Optional`s in tools) |
| 8 | `type-tag` | `unresolved-attribute` on a base class that needs its subtype (`NodeSocket`, `Node`, `Constraint`, `Modifier`, `Strip`, `ActionStrip`, `Light`, `Curve`, `Texture`, `Space`, `ID`) |
| 9 | `stub-gap` | rules `not-iterable` / `unsupported-operator` / `not-subscriptable`, override rules (`invalid-method-override`, `invalid-attribute-override`, `invalid-property-type-override`, `invalid-mutable-override`), `bl_rna` or `object.__init__` in msg, `Module X has no member` |
| 10 | `rest` | everything else, `blender-*` rules included (the per-rule table shows them) |

The prototype's context regex ended in a `\w+` catch-all, so any `context.x` on the line counted; rule 5 ties the
missing attribute to the member before it instead, and keeps the prototype's type-based "indirect" case
(`scene = context.scene` then `scene.render`). The order puts `dynamic` and `operator-call` before the nullable
rules so a `Self@` or `bpy.ops` line is not counted twice in spirit; each diagnostic gets exactly one bucket.

### Result on the recorded outputs (`dc491af090`)

Blender's own stubs (14,077):

```text
bucket            shipped  presets    other    total
context-member       2757      277     1126     4160
pointer-none         2126      411     1190     3727
type-tag             1031       70      516     1617
stub-gap              531        0      225      756
operator-call          89        0      183      272
check-setup           204       12      132      348
dynamic               588        0      199      787
rest                 1293       12     1105     2410
total                8619      782     4676    14077
```

fake-bpy-module (17,154):

```text
bucket            shipped  presets    other    total
context-member       1145      439      689     2273
pointer-none         5329      568     1807     7704
type-tag              922       16      596     1534
stub-gap              920        0      364     1284
operator-call          29        0      142      171
check-setup           211       12      139      362
dynamic               692        0      204      896
rest                 1723        8     1199     2930
total               10971     1043     5140    17154
```

Against the map's estimates (builtin): context ~4,460 → 4,160, pointer ~3,600 → 3,727, Type tag ~1,540 → 1,617,
stub gaps ~900 → 756, operator calls ~130 → 272 (now also counts `bpy.ops` lines in `doc/` and `tests/`), setup
~350 → 348, dynamic ~800 → 787. With fake-bpy-module almost every pointer is `None |`, so `pointer-none`
dominates; that is the known, out-of-scope nullability.

### Summary format and baseline

`tests/blender/expected/<generator>/main-summary.txt` (generator `builtin` or `fake-bpy-module`):

```text
# check:blender main, <generator> stubs, Blender <short commit>
bucket            shipped  presets    other    total
context-member       2757      277     1126     4160
...
total                8619      782     4676    14077

rule                              count
unresolved-attribute               ....
...
```

- One fixed row per bucket in the order above, also when zero, and fixed columns: a diff shows which bucket in
  which area moved.
- The per-rule counts that `check_blender.py` already prints (`run_ty_with_summary`) follow, sorted by rule name
  (not by count, so a change does not reorder lines). They make a `blender-*` regression visible.
- No samples and no line numbers in the baseline; samples go to `.cache/ty-results/<version>-<generator>-buckets.txt`
  next to the full output, for reading.
- Written only for `main` (the path names it); other versions get the `.cache` copy without a baseline compare.
- On a mismatch the task prints the diff and still exits 0 (the map sets no numeric target); `--update` copies the
  new summary over the baseline, as the feature tasks do.

### Stability against line shifts

- The summary holds counts per bucket and area only, so moved lines in Blender change nothing by themselves; a
  baseline diff means diagnostics were added, removed or reworded.
- Each diagnostic is classified from its own source line in the worktree ty just checked (same commit), so a
  Blender bump cannot misalign message and line. Recording `check:blender` and classification in one run keeps it
  so; classifying an old output against a newer worktree would not.
- What does move buckets: (1) ty wording changes on a rebase of the fork (`is not defined on None in union`,
  `Self@`, `Module X has no member`); the pytest cases only catch this if their messages are copied from real
  output, so take them from `main-builtin.txt` and refresh them when a rebase changes the wording. (2) Code reformatting that splits an
  expression so the reported line no longer holds `context.` or `bpy.ops.`. (3) The heuristics themselves:
  `pointer-none` also takes plain `str | None` in `build_files/`, and `context-member` misses members reached
  through a local of type `Object | None`. These are tolerable for a secondary measure.

### Tests (`scripts/tests`, no markers)

Table-driven pytest over `bucket(rule, msg, text)` and `area(path)`: one case per row of the rule table, each
taken from a real line of `main-builtin.txt` (for example
`intern/cycles/blender/addon/ui.py:230` → `check-setup`, `scripts/presets/cycles/sampling/Final.py:2` →
`check-setup` / `presets`, an `Attribute render is not defined on None in union Scene | None` line →
`context-member`), plus one case per area including a Windows `\` path, and one for the summary writer (all
buckets present, rules sorted).

The numbers above come from a throwaway re-implementation of exactly this rule table run over the recorded
outputs; it is not committed, and the build ticket writes the real one into `scripts/` (next to
`check_blender.py`, for example `_buckets.py`).
