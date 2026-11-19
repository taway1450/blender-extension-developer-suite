# A third stub generator: Blender's runtime, introspected

Research note, 2026-11-19.

**Question.** Could a third stub generator compete with fake-bpy-module and Blender's own (builtin) generator by
opening Blender and turning everything it holds at runtime into stubs, with no rst step in between? It would have
two modes. The general mode would run factory startup with the default add-ons and emit the whole API. The add-on
mode would emit what one add-on adds at runtime, plus the content of the add-on's `.blend` files. What does
introspection give and what does it miss? Where are the two existing generators weak? How should the generator be
built, plugged into the suite and validated?

Conventions: `blender/` is the Blender fork at the repo root (`3bd52da81e2`, the commit of
`.cache/bpy-stubs-builtin/main`). Source paths without a prefix are relative to `blender/source/blender/`. `doc/`
is `blender/doc/python_api/` and `scripts/modules/` is `blender/scripts/modules/`. `SB/` is
`.cache/bpy-stubs-builtin/main/`, `SF/` is `.cache/bpy-stubs/main/` and `ty/` is `ty-blender/ruff-blender/crates/`.
Everything here was read from source, the cached stubs and the reports. Nothing was run.

## 1. Answer

1. **The builtin generator is already a runtime generator with an rst detour.** `doc/sphinx_doc_gen.py` runs
   inside Blender and introspects the live RNA (`_rna_info.BuildRNAInfo`, `sphinx_doc_gen.py:182-185`), the Python
   classes (`inspect.signature`, `inspect.get_annotations`, `:1294`, `:2326`) and the fork's probes (Type tags
   `:196`, node sockets `:212`). It writes 49 MB of rst (`.cache/bpy-rst/main`). Then `sphinx_stub_gen.py`
   parses that rst back with docutils, outside Blender (`sphinx_stub_gen.py:27-30`). Its data model and renderer
   do not depend on rst (`MethodInfo` ... `ModuleInfo`, `:66-131`; `render_stub`, `:1408`). Only the front end
   (`parse_rst_file`, `:396`) reads rst. The cheapest strong competitor is therefore **a new in-Blender front
   end that fills that data model straight from introspection, feeding the existing back end**. It is not a third
   pipeline written from scratch.
2. **"No docs" means no rst files, not no docstrings.** None of Blender's C functions has a `__text_signature__`:
   the grep for `--\n\n` and `__text_signature__` in `python/` finds nothing. Their signatures and types exist only
   as rst field lists inside `__doc__` (`mathutils/mathutils_Vector.cc:1099-1109`, `python/intern/bpy_props.cc:3564`).
   For `mathutils`, `gpu`, `bmesh`, `blf`, `imbuf`, `idprop`, `bl_math`, `aud`, `bpy.props` and the C half of
   `freestyle`, the runtime generator still parses rst. It parses the same strings, read from `__doc__`
   instead of from a file.
3. **Runtime wins on everything loaded or registered.** These facts are missing from both existing generators or
   lost on the way:
   - startup classes with their Python members (S10 of `docs/reports/remaining-causes.md:110`);
   - private module members (`MODULE_EXTRA_MEMBERS`, `sphinx_stub_gen.py:1364`, written by hand today);
   - `aud` (missing from the builtin stubs, `docs/reports/fake-bpy-python-module-stubs.md` "What stays");
   - registered properties typed with an add-on's struct (`Scene.cycles`, which the docs drop on purpose,
     `sphinx_doc_gen.py:2893-2913`);
   - protocol presence on C types (`__buffer__`, `__enter__`, `__iter__`: the `fake-bpy-protocol` cause, 44 sites);
   - and, in add-on mode, the add-on's registrations, custom node sockets and live `.blend` content.
4. **Some facts are lost to the runtime and stay hand-written or probed:**
   - the types of `bpy.context` members: only the names are introspectable (`_bpy.context_members()`,
     `python/intern/bpy.cc:535-570`), and the types are the hand table `context_type_map`
     (`sphinx_doc_gen.py:2440`);
   - which struct a refine function returns (`docs/research/type-tag-data-sources.md` §1.2);
   - dynamic enums (RNA does not say whether an enum has an `item_fn`; `_rna_info.py:785-790` guesses);
   - `bmesh.ops` slot types (the runtime `__doc__` has names and defaults only, `bmesh/bmesh_py_ops.cc:108-128`);
   - `id_data` owners (`ID_DATA_OWNERS`, `sphinx_stub_gen.py:1322`);
   - `PROP_NEVER_NULL` beyond what the fork's makesrna sets (`docs/research/never-none.md`).

   The suite's probes (`doc/sphinx_doc_gen_type_tags.py`, `doc/sphinx_doc_gen_node_sockets.py`) are already
   runtime code, so the new generator imports them as they are.
5. **Python modules should be shipped as source, not stubbed by introspection.** fake-bpy-module's `inspect`
   route lost `__init__`, instance attributes, constants and `@contextmanager`. Its fix was to stub from source with
   `ast` (`docs/reports/fake-bpy-python-module-stubs.md`, route B: 637 → 1 site). Even then, stubbing from source
   loses inferred return types that the source gives ("What stays"). Introspection should only decide *which*
   modules and runtime-created members exist.
6. **In add-on mode, the checker already knows most of what the diff would emit.** ty-blender's Add-on index reads
   Registered properties, classes, operators and preferences from source
   (`ty/ty_python_semantic/src/types/dedicated/blender/operators.rs`, `preferences.rs`; `GLOSSARY.md` "Add-on
   index"). The runtime delta is worth emitting for four reasons:
   - as the **ground truth to validate the index against** (a `check:load`-style comparison);
   - for registrations that source analysis cannot read (computed names, opaque declarations, classes built in
     loops);
   - for other add-ons that `uses` this one, and for stock type checkers;
   - for what has no source at all: custom node sockets after `init`, and `.blend` content.
7. **Recommendation.** Build a `runtime` generator as one in-Blender script in the Blender fork, next to
   `sphinx_stub_gen.py`, whose back end it shares. It writes a JSON intermediate form (IR) and renders the builtin
   layout (`bpy/`, `mathutils/`, ...), so `--generator runtime` plugs into `generate_stubs.py` like the other two
   (§4.3). Add-on mode diffs two IRs and writes (a) a delta manifest that ty-blender reads and (b) optionally a
   merged full package for stock tools. It reuses `blender_extract.py`'s approach G, generalised to a generic RNA
   walk, for every `.blend` in the add-on (§4.5). The first slice is `bpy.types` plus `bpy.ops` straight from RNA
   into the existing renderer, diffed against the builtin stubs of the same build (§5).

## 2. What runtime introspection gives, per area

### 2.1 RNA structs and properties (`bl_rna`)

| Fact | How | Caveat |
|---|---|---|
| Struct identifier, base, description, `nested`, `name_property`, `properties`, `functions`, `property_tags` | `Struct` RNA (`makesrna/intern/rna_rna.cc:3241-3318`) | The struct has **no refine** and **no `is_registered`**. Refinement is the Type-tag probe's job. A Python class is registered iff `"bl_rna" in cls.__dict__` (`scripts/modules/_bpy_types.py:969-973`). |
| Property type, `subtype`, `unit`, `srna` (collection wrapper with its own `functions`: `new`/`remove`), `fixed_type` | `rna_rna.cc:3381-3395`, `:3388`, `:3901` | `subtype` picks the mathutils class (`COLOR` → `Color`, `MATRIX` → `Matrix`); `_rna_info.get_type_description` already does this (`_rna_info.py:439+`). |
| Flags: `is_readonly`, `is_required`, `is_argument_optional`, `is_never_none`, `is_output`, `is_registered`, `is_registered_optional`, `is_runtime`, `is_enum_flag`, `is_hidden`, `is_skip_save`, `is_deprecated`, `is_path_supports_*` | `rna_rna.cc:3408-3518` | `is_never_none` is exactly `PROP_NEVER_NULL` (`:769-773`). `is_runtime` is `PROP_INTERN_RUNTIME` (`:888-892`, `makesrna/intern/rna_access.cc:2410-2413`), true for every property Python defined: the add-on diff key. |
| Arrays: `array_length`, `array_dimensions`, `is_array` (dynamic arrays have `array_length` 0), `default_array` | `rna_rna.cc:3678-3684`; `_rna_info.py:329-338` | Covers `float[4][4]` → `Matrix`. |
| Defaults, `hard_min`/`hard_max` | `_rna_info.py:382-430` | Floats need `float_as_string` for stable text (`_rna_info.py:85`). |
| Enum items | `enum_items`, `enum_items_static` (`rna_rna.cc:3805-3838`) | Both call `RNA_property_enum_items_ex` with `C = nullptr` on the *property's* pointer (`rna_rna.cc:1147-1169`). With no context, `item_fn` runs only for `PROP_ENUM_NO_CONTEXT` (`rna_access.cc:1826-1855`), so a dynamic enum yields its static placeholder: `DEFAULT`, `PLACEHOLDER`, `UNSUPPORTED`, or only the built-in render engines (`_rna_info.py:785-790`). Per-instance items need an instance: the node-socket probe sets an invalid value and parses the `TypeError` (`doc/sphinx_doc_gen_node_sockets.py:111-124`). |
| Shared enum names (`rna_enum_object_type_items`) | `_bpy.rna_enum_items_static()` (`python/intern/bpy.cc:583`, `:720`), matched by `enum_pointer` (`_rna_info.py:364-378`, `sphinx_doc_gen.py:415-423`) | Runtime gives them. The builtin generator re-parses them from the rst it wrote (`sphinx_stub_gen.py:718`). |
| Which subclass an instance is | Not in RNA: `RNA_def_struct_refine_func` stores a C function (`type-tag-data-sources.md` §2.1) | Needs the Type-tag probe (`doc/sphinx_doc_gen_type_tags.py`). |

### 2.2 RNA functions

`bl_rna.functions[...]` gives `parameters`, `use_self`, `use_self_type`, `is_registered` (a callback Blender
calls) and `is_registered_optional` (`rna_rna.cc:3590-3625`). Each parameter is a `Property` with the flags above.
Outputs are the parameters with `is_output`. More than one output makes a tuple (`_rna_info.InfoFunctionRNA.build`,
`_rna_info.py:681-693`). Nothing is lost against the docs: the docs are written from exactly this.
`is_registered` with `is_never_none` decides whether a callback parameter is non-None (`never-none.md`
"Callback parameters").

### 2.3 Operators

- `bpy.ops.<m>.<f>.get_rna_type()` gives the properties struct. `.bl_options` is a getter on the function object
  (`python/intern/bpy_operator_function.cc:698`, `:720-727`; for C operators it reads `ot->flag`, `:546-554`).
  `.idname()` / `.idname_py()` give both spellings.
- `poll` cannot be introspected. `bpy.ops.x.y.poll()` evaluates it in the current context
  (`bpy_operator_function.cc:158-200`), which is a state, not a fact.
- A C operator's description is in RNA. A Python operator also has its class:
  `getattr(bpy.types, "OBJECT_OT_x")` (`_rna_info.py:740-745`).
- Macro operators show their sub-operators as `dict` properties (`SB/bpy/ops/object/__init__.pyi`,
  `duplicate_move`).

### 2.4 Python-defined classes and modules

- `inspect.signature` works on every Python function. Annotations are strings under
  `from __future__ import annotations`. `inspect.get_annotations(eval_str=True)` and `typing.get_type_hints` fail
  on names imported only under `TYPE_CHECKING`, so the doc generator falls back to the raw strings
  (`sphinx_doc_gen.py:2326-2328`).
- What `inspect` misses, as fake-bpy-module measured: instance attributes, classes built by `namedtuple()` with
  methods attached, the wrapped generator behind `@contextmanager`, and unannotated returns
  (`fake-bpy-python-module-stubs.md` "Route A").
- `ast` on the source gets all of these except inferred returns. Shipping the `.py` gets everything, which is how
  the builtin stubs behave: "Blender's own stubs ... resolve these modules to the source" (same report, "What
  stays"), and `check:blender` puts `scripts/modules`, `scripts/startup` and `scripts/addons_core` on the search
  path (`scripts/check_blender.py:72-74`).
- Introspection still adds what source cannot show: which modules factory startup loaded (`sys.modules`), members
  set by C (`bpy.utils` functions that come from `_bpy`), and the `__module__` of each registered class.
- Property declarations on a Property host are live `_PropertyDeferred` objects with `.function` and `.keywords`
  (`sphinx_doc_gen.py:2356-2440`). After `register()`, the same members are RNA properties with `is_runtime`.

### 2.5 C extension modules

| What | Introspectable | Only from docstrings (rst field lists in `__doc__`) or tables |
|---|---|---|
| Module members, classes, `__mro__`, slot wrappers (`__getitem__`, `__len__`, `__iter__`, `__enter__`, `__buffer__` since Python 3.12, `__lt__`, `__neg__`, `__matmul__`) | yes. Blender main uses Python 3.13 (`build_files/build_environment/cmake/versions.cmake:385`) | Operand and return types of the slots: tables today (`sphinx_stub_gen.py:1271-1290`, element types and buffer protocol) |
| Function and method signatures | no `__text_signature__` anywhere (grep) | `.. method:: cross(other, /)` plus `:type:` / `:rtype:` (`mathutils_Vector.cc:1099-1109`) |
| getset descriptors (`gpu.types.GPUShader.name`) | name and `__doc__` | `:type:` in the docstring |
| struct sequences (`bpy.app`, `bpy.app.handlers`) | fields and field docs. Handler argument types are in the field docs (`python/intern/bpy_app_handlers.cc:110-140`) | — |
| `bmesh.ops.*` | `__doc__` = `bmesh.ops.x(bmesh, slot=default, ...) -> dict(out, ...)` (`bmesh_py_ops.cc:108-128`) | slot types: `doc/rst_from_bmesh_opdefines.py` parses `bmesh_opdefines.cc`, a source step |
| `_bpy`, `_cycles`, `_freestyle`, `_bpy_hydra` | names | the hand stubs in `doc/stubs_handwritten/` (`sphinx_stub_gen.py:770-787`) |
| Freestyle's positional overrides | — | `Director.cpp` calls `__call__`, `traverse`, `shade` positionally (`sphinx_stub_gen.py:1292-1301`) |

### 2.6 `bpy.context`

There are two kinds of member (`docs/research/context-members.md` "How a Context member is read"):

- The RNA properties of `Context` (`window`, `scene`, ...) are introspectable like any struct.
- The screen-context members (`object`, `active_object`, `selected_objects`, ...) are answered by C callbacks
  (`pyrna_struct_getattro` falls through to `CTX_data_get`, `python/intern/bpy_rna.cc:4871-4928`). Only their names
  per editor are exposed (`_bpy.context_members()`, `bpy.cc:535-570`, from `screen_context_dir` and the eight space
  `*_context_dir` tables).

The builtin generator types them with `context_type_map` and `context_store_type_map`
(`sphinx_doc_gen.py:2440-2570`). It fails when a runtime name is missing from the table (`:2647-2655`). That
check is the right design for the runtime generator too. A probe under `context.temp_override(area=...)` in each
editor could confirm a type, but only for members that are non-None in the probed state. The table stays the
source, and the runtime list checks that it is complete.

### 2.7 `bpy.app`, `bpy.props`, `bpy.msgbus`, `bpy.utils`, `bpy.path`

- `bpy.app` is a struct sequence: introspectable, with values that are build facts (`build_options`, `version`).
- `bpy.app.handlers` holds lists whose argument types are in the field docs (§2.5). The doc generator empties the
  lists first, because registered handlers would leak into the docs (`setup_blender`, `sphinx_doc_gen.py:4326-4337`).
- `bpy.app.timers`, `bpy.app.translations`, `bpy.msgbus` and `bpy.props` are C modules documented in their
  docstrings (`bpy_props.cc:3564`).
- `bpy.utils` and `bpy.path` are Python (`scripts/modules/bpy/`) with C members from `_bpy`.
- Private members such as `bpy.app.handlers._extension_repos_update_pre` are in `dir()`. Today they are a hand
  fragment (`sphinx_stub_gen.py:1364-1376`).

### 2.8 Registered classes and properties

- Registered classes are reached through `dir(bpy.types)` and then `__subclasses__()` of every RNA class
  (`_rna_info.py:849-900`). That is how `cycles.properties.CyclesRenderSettings` is found.
  `InfoStructRNA.module_name` is the class's `__module__` unless `bpy.types` has it (`_rna_info.py:161-168`).
- Node classes registered by Python are not in `bpy.types`; `check:load` adds a node to find them
  (`scripts/blender/load_feature_addons.py:33-44`).
- Registered properties appear in the host struct's `bl_rna.properties` with `is_runtime`. Their `fixed_type` may be
  an add-on struct, which the docs drop (`RNA_EXCLUDE`, `sphinx_doc_gen.py:2893-2913`). That is why `SB/` has no
  `Scene.cycles`.
- A class's `bl_idname`, `bl_label`, `bl_options`, `bl_space_type` and other registration properties are RNA
  properties with `is_registered` / `is_registered_optional`, so they read like any other property.

### 2.9 Who has which fact

| Fact | Docs or source only | Runtime only |
|---|---|---|
| C signatures and types | the rst in `__doc__` (the same text at runtime) | — |
| `bmesh.ops` slot types | `rst_from_bmesh_opdefines.py` (C source) | — |
| Context member types | `context_type_map` | names per editor |
| Shared enum aliases | rst re-parse (builtin) | `_bpy.rna_enum_items_static()` |
| Python modules | source text (annotations, instance attributes, inferred returns) | which modules are loaded, members set by C |
| Startup classes' Python members | — (S10) | `__dict__` of the registered class, then its source |
| Registered properties typed by an add-on's struct (`Scene.cycles`) | dropped by the docs | `bl_rna.properties` |
| Protocols on C types | tables | slot wrappers, `__buffer__` |
| Refined subclass, per-node sockets, per-instance enum items | — | probes |
| Add-on registrations, custom node sockets after `init`, `.blend` content | the add-on's source (the Add-on index) | after `register()` / `open_mainfile` |
| Build options (`WITH_FFMPEG` members) | — | present only if compiled in (`docs/research/ffmpeg-build-option-gap.md`) |

## 3. The existing generators

### 3.1 fake-bpy-module

`scripts/generate_stubs.py:404-480` describes it:

1. In Blender, it runs `gen_external_modules_modfile.py` twice (for `addon_utils` and the startup modules) and
   `gen_node_inputs_outputs_for_node_class.py` when the rst lacks socket tables (`:397-403`). It also runs
   `gen_bgl_modfile.py` on the C source.
2. Outside Blender, `gen.py` parses the rst with docutils (`fake_bpy_module/analyzer/`), runs 20 transformers
   (`fake_bpy_module/transformer/`), applies the hand-written mods (`src/mods/blender/<version>+`) and the source
   stubs (`source_stub.py`), and writes `<module>-stubs/` packages (8.9 MB).

Weak points (`docs/reports/fake-bpy-module-leftovers.md`):

- protocols on C types (44 sites);
- nullability rewritten by heuristics in `data_type_refiner.py` (43);
- the library key `(name, None)` (23);
- `_bpy_types` aliases, and registered classes declared as instances (10);
- before route B, Python modules (234, later 637).

It works for old releases, because its mods are versioned.

### 3.2 Builtin (`sphinx_doc_gen.py` → rst → `sphinx_stub_gen.py`)

`generate_stubs.py:295-341`. It covers Blender 5.2 and later only (`:219-231`), and runs the worktree's own
generator, so the generator moves with the Blender commit. Weak points:

- **Python modules.** Undocumented Python modules and `__all__` members are absent, and startup-registered classes
  come without their Python members (`SB/bpy/types/__init__.pyi:50261`: `class VIEW3D_PT_active_spline(Panel): ...`).
  This is S10, plus 8 `unresolved-import` sites (`remaining-causes.md:110`, `:399-402`).
- **Hand-written data.** Everything the docs leave out is a hand table or fragment: `CLASS_EXTRA_MEMBERS`,
  `ID_DATA_OWNERS`, `MODULE_EXTRA_MEMBERS`, the math protocol tables and `stubs_handwritten/`
  (`sphinx_stub_gen.py:1234-1376`, `:770`).
- **Doc-shaped choices.** Properties with add-on struct types are dropped (§2.8), and handlers are cleared.
- **Facts not in RNA.** S1 (`animation_data_create() -> AnimData`), S5 (`ShapeKey.data` items), S9
  (`_DriverFCurve`), S11 (`GIZMO_GT_*`) and S12 are generator rules or probes that are not RNA flags
  (`remaining-causes.md:99-112`).
- **The rst round trip.** Every type is serialised to rst and parsed back. `TypeRefError` and the many
  `strip_*` / `resolve_*` helpers (`sphinx_stub_gen.py:855-1230`) exist for that round trip.

### 3.3 The suite's stub facts: free or reimplemented

| Fact | Today | Runtime generator |
|---|---|---|
| Type tags, tag views, constructor overloads | fork probe at doc time (`sphinx_doc_gen_type_tags.py`, `probe()` `:621`) | free: import and call it in the same process |
| Node sockets per built-in node | fork probe (`sphinx_doc_gen_node_sockets.py:320`) | free. Add-on mode extends it to the add-on's own nodes, which the probe skips today (`:15-20`) |
| `id_data` owners | hand table (`sphinx_stub_gen.py:1322-1351`) | reimplement. Keep the table, and add a probe (walk instances from every ID, record `type(x.id_data)`) as a consistency check, not as the source |
| Never-None | `is_never_none` from the fork's makesrna hook; `scripts/probe_never_none.py` as evidence | free from the flag (on fork builds; a release build has fewer flags). The probe stays research evidence and is not emitted |
| Context member types | `context_type_map` | reimplement: same table, checked against `_bpy.context_members()` |
| Shared enum aliases (`_rna_enums`) | rst re-parse | free (§2.1) |
| Protocols, `Buffer` | tables, S2 | presence free, element types table |
| Dynamic enums typed `str` | placeholder list (`_rna_info.py:785-790`) | the same heuristic. Optionally typed by the current state's items, but as an Assumption, not a stub fact (§4.7) |
| Private members, startup classes, `aud` | hand fragments / missing | free |

## 4. Design

### 4.1 Architecture

```
blender -b --factory-startup -Y -noaudio --python runtime_stub_gen.py -- --output DIR [--addon PATH] [--blend F ...]
  1. collect   -> IR (JSON): modules, classes, functions, data, in sphinx_stub_gen's data model,
                  plus provenance per member: core | startup | default-addon:<name> | addon:<name>
  2. probes    -> type tags, node sockets (+ the add-on's nodes), context check
  3. render    -> .pyi with sphinx_stub_gen's back end (render_stub, write_class, write_attribute, ...)
```

- **Where the code lives.** It goes in the Blender fork, as `doc/python_api/runtime_stub_gen.py` on the long-lived
  branch. It imports `_rna_info`, the two probes and `sphinx_stub_gen`'s back end. The back end must stop importing
  docutils at module level (`sphinx_stub_gen.py:27-30`), because Blender's Python has none: move the four imports
  into `setup_docutils_once` and `parse_document`.
- **Version independence.** Unlike the builtin generator, the suite runs the *fork's current* script against any
  Blender binary, as fake-bpy-module does. The script must therefore detect features rather than assume them:
  `_rna_info` versus `rna_info` before 4.4 (`scripts/blender/dump_rna_flags.py:31-34`), and missing RNA flags.
- **`-Y` (`--disable-autoexec`, `creator/creator_args.cc:3159`).** It keeps `.blend` scripts from running. The
  factory userdef enables autoexec unless the build has `WITH_PYTHON_SECURITY` (`blenkernel/intern/blendfile.cc`,
  after the add-on list).
- **Front end per area:**
  - RNA: `_rna_info.BuildRNAInfo(keep_ui=True)` plus `get_type_description`, which already writes the stub type
    strings (`Literal[...]`, `| None`, `bpy_prop_collection[T]`).
  - C modules: `__doc__` parsed with `sphinx_stub_gen`'s rst field helpers on a docstring instead of a file.
  - Python modules: copied `.py`.
  - Context: the table, checked against `_bpy.context_members()`.
- **Crash safety.** Reuse `dump_rna_flags.py`'s progress file and `--crashed` skip list (`:16-18`, `build_pool`
  `:140`) for the probes.

The IR is the generator's real output. Rendering is a pure function of it. Add-on mode diffs IRs (§4.4), and the
IR is what a test compares against the builtin stubs (§5.2).

### 4.2 General mode

- **Startup state.** `--factory-startup` loads the factory userdef, whose add-on list is `io_anim_bvh`,
  `io_curve_svg`, `io_mesh_uv_layout`, `io_scene_fbx`, `io_scene_gltf2`, `cycles`, `pose_library` and `bl_pkg`
  (`blendfile.cc:1541-1556`; the checker mirrors it as `DEFAULT_ADDONS`, `ty/ty_blender/src/external.rs:22-31`).
  **To verify in the prototype:** whether background factory startup actually enables them. `SB/` has no
  `Scene.cycles`, but that is explained by `RNA_EXCLUDE` (§2.8), so it proves nothing.
- **Output modules:**
  - `bpy` (`types`, `ops`, `props`, `utils`, `app`, `path`, `msgbus`), `_rna_enums`, `mathutils`, `gpu`,
    `gpu_extras`, `bmesh`, `bpy_extras`, `freestyle`, `aud`, `blf`, `imbuf`, `idprop` and `bl_math`;
  - the private C modules from the hand stubs;
  - the `.py` of `scripts/modules`, `scripts/startup` and the enabled add-ons, copied (112 + 125 + 318 files,
    10.5 MB of source).
- **Provenance.**
  - Registrations by `bl_ui` / `bl_operators` are always present, like the checker's `STARTUP_PACKAGES`
    (`external.rs:18`).
  - Registrations by default add-ons go into the IR with `provenance = default-addon:<name>`. They are **not**
    rendered as plain attributes, because the checker reports them as an Assumption: the user may disable those
    add-ons (`GLOSSARY.md` "External registration"). They are rendered into a side manifest (§4.6).

### 4.3 Plugging into the suite

- `scripts/generate_stubs.py`:
  - add `RUNTIME = "runtime"` to `GENERATORS` and `.cache/bpy-stubs-runtime` to `STUBS_DIRS` (`:60-62`);
  - add a `generate_runtime_stubs(blender, stubs_dir)` that is one `run_blender_script` call (`:201`) with the
    fork's script, and needs neither rst nor docutils;
  - set `generator_revision` to the tree hash of the script plus `_rna_info.py` plus the probes;
  - reuse the stale marker (commit, generator revision, Blender fingerprint) unchanged (`:265-282`).
- `resolve_generators` (`:224-233`): keep `runtime` out of `ALL` until it replaces one generator. Otherwise every
  check task runs a third time.
- **Layout.** Use the builtin layout (`bpy/`, no `-stubs`). `check:oracle` already accepts both layouts
  (`scripts/check_oracle.py:75-77`). `report_flags.py:241` picks `"bpy"` for anything but fake-bpy-module.
  `_target.Target` needs no change (`scripts/_target.py:56-70`).
- **Baselines.** New `tests/typecheck/expected/runtime/`, `tests/blender/expected/runtime/`, and `_buckets.py`
  causes for runtime-only shapes, if any appear. Seed the baselines from `builtin` and review the diff (§5.2).
- **The contract with ty-blender.** ty-blender reads stub *shapes*: value-form `type: Literal[...]` on refined
  subclasses, `_Object_MESH` tag views, `_ShaderNodeBsdfPrincipled_inputs` socket views, the `bpy_prop_collection`
  overloads with the `(name, library)` key, and `rna_enum_*` aliases. Rendering through the builtin back end keeps
  them identical by construction. That is the main reason not to write a new renderer.

### 4.4 Add-on mode

1. Start as in §4.2, and collect the **pre IR** without probes (seconds).
2. Enable the add-on:
   - **Legacy add-on:** put the parent folder on `sys.path`, then call `addon_utils.enable(name, default_set=False,
     handle_error=...)` (`scripts/modules/addon_utils.py:339`).
   - **Extension:** add a temporary repository with `preferences.extensions.repos.new(name, module="suite_runtime",
     custom_directory=parent)` (`makesrna/intern/rna_userdef.cc:7609`, `:893-903`), then enable
     `bl_ext.suite_runtime.<id>` (`addon_utils.py:99-125`). Install the manifest's `wheels` into a temporary
     `site-packages` first.
3. Collect the **post IR**. The delta holds:
   - new structs, keyed by `__module__` under the add-on package, including Python node and socket classes found
     through `__subclasses__`;
   - new properties on existing structs (`is_runtime`);
   - new operators, with `bl_options` and properties;
   - the `AddonPreferences` class;
   - changed enum items (`RenderSettings.engine` gains the add-on's engine);
   - new `sys.modules` entries under the package;
   - new keymap items (`window_manager.keyconfigs.addon`: idname and properties, for checking idnames);
   - new handlers and timers (check the callbacks' arity against the field docs of §2.5).
4. Probe the add-on's own nodes. Add each registered node class to every tree type whose `poll` accepts it, and
   record its sockets after `init`. Re-use `probe_node` (`sphinx_doc_gen_node_sockets.py:296`) with the add-on's
   classes, which the probe excludes today.
5. Load each `.blend` under the add-on root (§4.5).

**What is worth emitting, given the Add-on index.**

- **Ground truth.** A new comparison (in `check:load`, or a `check:runtime-index` task) between the runtime delta
  and what ty-blender's index says. Every mismatch is a typechecker bug or an unreadable registration. This is the
  highest-value use for the suite itself.
- **Registrations the index cannot read.** Emit them as External registrations of the add-on, reported as such.
- **Facts with no source.** Custom node sockets, live enum items for the add-on's own dynamic `EnumProperty` in
  factory state, and `.blend` content.
- **For dependants.** Another add-on that declares `uses = ["this_addon"]` reads this delta instead of re-reading
  the source.

### 4.5 `.blend` content

This supersedes approach G (`prototypes/blend_typing/blender_extract.py`) with a generic RNA walk instead of a
hand list of 21 collections and node fields (`blender_extract.py:21-25`, `:33-45`):

- For every `BlendData` collection property, take every ID. Record its refined class
  (`type(id).bl_rna.identifier`; a light is `AreaLight` and not `Light`, `blend-file-typing.md` §8), its library,
  and the keys and Python types of its custom properties.
- From each ID, walk properties to depth *N* (3 is enough for `object.modifiers[name]` and
  `material.node_tree.nodes[name].inputs[name]`):
  - for a collection whose item struct has a `name_property`, record `name → refined class`;
  - for an ID pointer, record a reference by name (`Object.data` → `meshes["Cube"]`);
  - for an embedded struct (`Material.node_tree`), recurse.
- Sockets take `identifier` first, then `name`, as `rna_NodeInputs_lookup_string` does
  (`blend-file-typing.md` §4.6).
- The output is the B/G manifest schema extended with these tiers, so ty-blender needs one reader whichever tool
  wrote the manifest (`blend-file-typing.md` §8 verdict).
- It records the **loaded** state after versioning, which a raw reader cannot (the Principled BSDF gains two sockets
  on load, §8). Opening a file takes 4-8 ms (`blend-file-typing.md` §8).

Exposure: the note's recommendation stands. The primary output is a **manifest read by ty-blender** (B + D:
`[tool.blender] blend-files`, `blender-assumed-blend-content`). An **overlay** (approach C, `gen_stubs.py`) is a
secondary output for stock tools. With one generator rendering both the general stubs and the overlay, the C
problem of overlays fighting another generator's signatures disappears (`blend-file-typing.md` §8, bullet C). A
subscript that names an object resolves to the existing tag view (`_Object_MESH`, `blend-file-typing.md` §4.6), so
no new class kinds are needed.

### 4.6 Layering

A second search path cannot add members to `bpy.types`: the first `bpy/types/__init__.pyi` found wins the whole
module. So:

| Consumer | General | Add-on |
|---|---|---|
| ty-blender | `.cache/bpy-stubs-runtime/<version>/` | a delta manifest `<addon>/.blender-runtime.json` (registrations, sockets, blend content, provenance), read through `source_text` like the blend manifest, and fed into the Add-on index as External registrations |
| stock ty, pyright, mypy | the same package | a **merged** full package per add-on (general IR + delta, re-rendered: about 3 MB, seconds), on its own search path instead of the general one |
| default add-ons' registrations | not rendered into `bpy.types` | the same manifest form, `provenance = default-addon:<name>`, so `blender-assumed-*` keeps reporting them |

### 4.7 Soundness

- **The state is factory startup.** Dynamic enum items, the default add-ons' registrations and the render engines
  are facts of that state. Stub only what holds in every state: static items, with dynamic enums kept `str`. Put
  state facts in the manifest, where the checker reports them as Assumptions.
- **Nullable pointers.** Use only `is_never_none`. Probe counts (`probe:never-none`) are evidence for RNA patches,
  never a stub fact, because a pointer that was never None in a corpus can still be None.
- **Refinement and sockets** are probed over enumerated states (`MAX_STATES = 512`,
  `sphinx_doc_gen_node_sockets.py:57`). A socket missed in all states is a hole, as it is in the builtin stubs
  today.
- **Build options and platform.** The runtime reflects one build (`ffmpeg-build-option-gap.md`). Keep generating
  from `full` builds, and record `bpy.app.build_options` and `sys.platform` in the stub marker.
- **Add-on mode runs user code.** `register()` may need a GPU or window, defer work to a timer (timers do not fire
  in `--background` without an event loop), or branch on platform. Report a failed or partial registration as a
  diagnostic of the run. Never silently emit a partial delta.
- **`.blend` facts** are a snapshot (`blend-file-typing.md` §5), and stay an Assumption.

### 4.8 Versioning, determinism, size, speed

- **Versioning.**
  - The IR records `bpy.app.version`, `build_hash`, the generator revision and the build options.
  - The fork's probes and flags are richer than a release's. A release run lacks the makesrna never-null hook, so
    expect more `| None` there than in fork builds, as the builtin stubs on 5.2 already show.
  - Unlike builtin (5.2+), the generator runs on any release whose Python API it detects.
- **Determinism.**
  - Sort structs, members, operators and modules by identifier. Keep enum items in RNA order.
  - Format floats with `float_as_string`, and sort sets.
  - Empty handler lists as `setup_blender` does.
  - Never write `as_pointer()` values, which serve only as keys (`enum_pointer`).
  - Probes create their data with a fixed name (`NAME = "node_socket_probe"`) in a fresh factory state.
- **Size.** About the builtin package (3.0 MB, 147 `.pyi`, 4879 classes of which 1053 private, 2566 operators,
  measured in `SB/`), plus 10.5 MB of copied Python source. fake-bpy-module's output is 8.9 MB.
- **Speed.** Not measured here. The build was busy, which is why nothing was run.
  - The type-tag probe finished about 2 s into the doc run (`.cache/bs5-stubs.log:160-163`).
  - Factory startup and `BuildRNAInfo` take seconds. The node-socket probe is the slow part, up to 512 states per
    node.
  - The generator saves sphinx_doc_gen's 49 MB rst write and sphinx_stub_gen's docutils parse.
  - Expected: general mode well under a minute; add-on mode one Blender start plus seconds per add-on and
    milliseconds per `.blend`.

## 5. Prototype plan

### 5.1 Slices

1. **R0: IR and renderer seam.** Make `sphinx_stub_gen`'s back end importable without docutils. Write
   `runtime_stub_gen.py` that builds `ModuleInfo` for `bpy.types` from `BuildRNAInfo` (with
   `get_type_description` strings) and for `bpy.ops` from `get_rna_type()`, plus the type-tag and socket probes.
   Render. Output: `bpy/types`, `bpy/ops` and `_rna_enums`.
2. **R1: The rest of the general package.** Add the C modules from `__doc__`, the struct sequences, `bpy.props`,
   the hand stubs, context from the table plus the runtime check, the Python modules copied as `.py`, and the
   private members. Retire `MODULE_EXTRA_MEMBERS`.
3. **R2: Suite integration.** Add `--generator runtime` in `generate_stubs.py` (§4.3), and seed the
   baselines from builtin.
4. **R3: Add-on delta.** Write the pre/post IR diff and the delta manifest, for legacy add-ons and extensions.
   Compare the delta against `tests/typecheck/features/*` `_expected/runtime.toml` probes and against the Add-on
   index.
5. **R4: `.blend` walk.** Generalise `blender_extract.py` to the generic RNA walk (§4.5), in the manifest schema.
   Run it on `prototypes/blend_typing/examples/` against G's manifests.
6. **R5 (later): checker side.** Make ty-blender read the delta and blend manifests, and render merged packages for
   stock tools.

### 5.2 Validation

- **Structural diff against builtin on the same build.** Parse both `bpy/types/__init__.pyi` with `ast` and diff by
  `(class, member) → annotation`. Expected differences, each to be explained:
  - startup classes gain members;
  - `aud` and private members appear;
  - registered properties with add-on types appear (in the manifest, not in `bpy.types`).

  Anything else is a front-end bug. This is a cheap gate before any typechecking.
- **The suite's checks with `--generator runtime`:**
  - `check:stubs` (the stubs type-check);
  - `check:oracle` and `check:features` / `check:ide` against the builtin baselines;
  - `check:blender main` summary against `tests/blender/expected/builtin/main-summary.txt`. The S10 sites and the 8
    `unresolved-import` sites should go.
- **`report:flags`** compares RNA flags with probed behaviour per generator
  (`scripts/report_flags.py:1007`). The runtime stubs should agree with RNA wherever builtin does.
- **Add-on mode:**
  - `check:load` probes already state what each feature add-on does after `register()`; the delta must contain each
    of them;
  - every Add-on index mismatch gets a feature-test marker.

### 5.3 Risks

- **Maintaining two front ends for one renderer.** The fork would carry both rst and runtime front ends. The
  mitigation is that the runtime front end replaces the rst one for stubs, while rst stays for the HTML docs only.
- **The hand tables stay.** `context_type_map`, `ID_DATA_OWNERS`, the protocol element types and
  `stubs_handwritten/` all remain. The new generator does not remove that maintenance, it only shares it with
  builtin.
- **Docstring parsing.** It moves into Blender's Python, which has no docutils. The `:type:` / `:rtype:` field
  lists need a small parser of their own, or a docutils wheel vendored for the run.
- **Factory-startup facts leaking into stubs.** Dynamic enums and default add-ons could end up as stub facts
  (§4.7). Provenance in the IR is the guard.
- **Add-on mode depends on the add-on running headless.** Many UI add-ons register fine. Some need a GPU context,
  network access or a timer.
- **The ty-blender contract.** Any shape drift breaks hooks silently. The structural diff of §5.2 must run in CI
  for every fork bump.

## 6. Open questions

- Does `--background --factory-startup` enable the default add-ons (§4.2)? It decides whether the general mode
  needs explicit `addon_utils.enable` calls.
- Should the runtime front end eventually also write the rst for the HTML docs, making it the single introspection
  pass upstream?
- How much of `context_type_map` could a per-editor `temp_override` probe confirm in factory startup? This needs a
  run.
- The delta manifest schema: one file per add-on, or merged into the blend manifest of
  `blend-file-typing.md` §6?
