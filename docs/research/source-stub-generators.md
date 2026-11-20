# Stubs from Blender's source: three readers compared

Research note, 2026-11-20.

**Question.** How many `bpy` stubs and facts can be read straight from Blender's source code, with no running
Blender and no API docs? What can only a source reader find? Which tool should do the reading: plain Python,
libclang or makesrna? Could upstream adopt it?

**Method.** Three prototypes were built in `prototypes/source_stubs/` (see its README), one per tool. They share a
JSON model of facts (`common/model.py`), an `ast` reader for the Python side (`common/pysource.py`) and one renderer
(`common/render.py`). Each was run on the Blender 5.2.0 source (`v5.2.0`, `fbe6228777e7`, worktree
`.cache/blender-src/5.2-src`; the coverage files record `038a2fc3c26a`, which is `v5.2.0` plus the makesrna patch). Their stubs were compared with Blender's builtin 5.2 stubs
(`.cache/bpy-stubs-builtin/5.2`), fake-bpy-module 5.2 (`.cache/bpy-stubs/5.2`) and each other
(`common/compare.py`). `mise run probe:source-stubs 5.2 --source .cache/blender-src/5.2-src` reruns all of it. The outputs are in `.cache/source-stubs/5.2/`: `<tool>/facts.json`, `<tool>/stubs/`,
`<tool>/coverage.md`, `comparison.md` and `audit.md`.

## 1. Answer

1. **Most of the API can be read from source, by all three tools.**
   - The readers agree with the builtin stubs on about 80% of the members both have (regex 82%, libclang 80%,
     makesrna 82%; on operators regex 92%, libclang 91%). Builtin and fake-bpy agree with each other on only 63%.
   - With one exception, the readers find every RNA struct and every C operator the builtin stubs have. The
     exception is the 55 classes registered from Python (`*_UL_*`, `*_AST_*`, `*_FH_*`).
   - The disagreements left are mostly facts the readers have right and the builtin stubs miss (section 4), or
     conventions (enum alias vs inline `Literal`).
2. **On RNA, the plain-Python reader matches makesrna.**
   - regex and makesrna agree on 100% of the members both have (32,027 same, 33 different).
   - regex reads 95% of makesrna's properties: 10,103 of 10,634.
   - makesrna is exact by construction, because it runs the definitions. The regex reader interprets the same
     `RNA_def_*` call sequences with a small C tokenizer, `#define` expansion and an interpreter that runs both
     branches of a condition it cannot decide.
3. **Only regex and libclang reach beyond RNA.** makesrna knows RNA only. Operators, the Python C API, context
   members, node declarations and bmesh operators are not RNA definitions.
   - regex and libclang read all six areas.
   - They agree with each other on 99% of shared members (37,202 same, 456 different).
4. **What only a source reader knows** (section 4) is what the generators lose at runtime or in the rst:
   - the names of callbacks (item function, refine, poll, editable, getter/setter);
   - never-null and required flags on parameters;
   - positional-only parameters from the C argument parsers;
   - typed node sockets per node;
   - context members per editor;
   - DNA field names;
   - a source location for every fact.
5. **Recommendation.**
   - **For upstream: makesrna's JSON dump plus a plain-Python reader for the rest.**
     - The makesrna patch is about 480 lines. It is exact, costs one second per run, and needs no new dependency,
       since makesrna is already built by every build.
     - The non-RNA areas are C tables and short call sequences. A plain-Python reader handles them in the style of
       upstream's own `rst_from_bmesh_opdefines.py`, with no build and no dependency.
   - **libclang is the most capable and the most expensive.** It is the right tool for questions that need real C
     semantics: classifying item callbacks, following function pointers, resolving types of locals, and deciding
     which RNA functions can return NULL (section 5.1). It is the wrong one for generating stubs on every build:
     23 minutes cold, a pinned wheel, and the build's
     `compile_commands.json`.

## 2. The three tools

| | regex (plain Python) | libclang | makesrna |
|---|---|---|---|
| Reads | C/C++ as text: tokenizer, `#define` expansion, call interpreter, table readers | clang's AST (`libclang==18.1.1` from PyPI), flags from `compile_commands.json` | RNA definitions as makesrna runs them, dumped by `makesrna-json-dump.patch` |
| Needs | Python 3, the source tree | the wheel, a configured build for compile flags (`--synthesize-flags` works without one, with more errors) | a configured build with the patch and the `makesrna` target built |
| Areas | RNA, operators, nodes, Python C API, context, bmesh | the same | RNA only |
| Time (5.2) | 55 s extract + 5 s Python | ~23 min cold (833 units, plus 227 for returns, 2 processes), 24 s warm | 1 s extract + 6 s Python |
| Code | 6,084 lines | 3,735 lines | 195 lines + 483-line C++ patch |
| Exact | tables (`PyTypeObject`, `PyMethodDef`, bmesh, sockets), DNA array sizes, define helpers | call targets, enum values, constant arithmetic, initializer fields, expression types, loops with known bounds, calls through function pointers | everything RNA defines, as defined |
| Heuristic | unknown conditions run both branches; unknown ternaries take the first; context types from C variable types | unknown conditions run both branches; context types from `&x->id`; bmesh docs from text near AST positions | none |

The shared part (`common/`, 2,412 lines): the model, the `ast` reader, the renderer, the comparison and the audit.

### 2.1 Coverage per area (5.2)

| Area | regex | libclang | makesrna |
|---|---|---|---|
| RNA structs / properties / functions | 1,725 / 10,103 / 2,989 | 1,725 / 9,980 / 3,005 | 1,724 / 10,634 / 3,014 |
| Dynamic enums (item function named) | 244 | 229 | 205 |
| Operators / their properties | 2,146 / 5,263 | 2,136 / 4,967 | - |
| Python C types / module functions | 255 / 205 | 255 / 228 | - |
| Signatures from C docstrings | 728 | 718 | - |
| Context members (typed) | 104 (98) | 104 (56) | - |
| Node declarations / sockets | 516 / 2,498 | 515 / 2,490 | - |
| bmesh operators | 83 | 82 | - |
| Python modules / classes / registrations (shared `ast` reader) | 555 / 3,048 / 82 | same | same |
| Stub files | 707 | 722 | 626 |

makesrna has more properties because it sees exactly what the build enabled and every builtin property. The source
readers see what the text shows.

### 2.2 Agreement with the other stub sets

Share of members both sets have whose annotations agree. Enum aliases are spelled out and the operator call
convention (positional `execution_context`, `undo`) is left out first; `comparison.md` has every area.

| | builtin | fake-bpy | regex | libclang | makesrna |
|---|---|---|---|---|---|
| regex | 82% | 74% | | 99% | 100% |
| libclang | 80% | 72% | 99% | | 99% |
| makesrna | 82% | 85% | 100% | 99% | |
| builtin | | 63% | | | |

Per area against builtin, for regex: `bpy.types` 82%, `bpy.ops` 92%, `mathutils` 85%, `gpu` 34%, `bmesh` 32%,
other C modules 46%. The low figures for `gpu`, `bmesh` and the C modules are mostly parameter names and kinds:
the readers take positional-only from the argument parser and keyword-only from bmesh slots, and builtin has
neither.

Kinds of disagreement with builtin, for makesrna (the cleanest case, RNA only):

| Kind | Count | Who is right |
|---|---|---|
| Return `X \| None` vs `X` | 1,379 | Split. Builtin never makes a return nullable, which is wrong for lookups (`FCurves.find`, `Object.find_armature` return NULL when nothing matches). The readers make every pointer return nullable, which is over-cautious for `new()`-style functions: they report an error and pyrna raises instead of returning `None`. |
| Parameter `X` vs `X \| None` | 553 | makesrna: the parameters are `PROP_NEVER_NULL` (e.g. `AOVs.remove(aov)`), and `None` raises (section 4.1). |
| `Literal` vs `str` (dynamic enum) | 200 | Builtin keeps the static items of enums with an item function; the readers say `str` (section 6). |
| One side untyped | 124 + 24 | Builtin: Python-script functions the `ast` reader leaves untyped (it renders annotations only). |
| Parameter names or count | 44 | Mostly Python-script functions and dunders. |
| Parameter types | 21 | Mixed. |

Positional-only and keyword-only no longer differ for RNA functions: the readers now make every parameter after the
first optional one keyword-only, as `pyrna_func_call` (`bpy_rna.cc`) requires ("optional arguments must be
keywords"), and as builtin already did.

## 3. Upstream tools that already exist

- **makesrna** (`source/blender/makesrna/intern/makesrna.cc`). In define mode it keeps every callback as the name
  of its C function (`refine`, `itemf`, `typef`, `poll`, `editable`, get/set), each property's DNA field and each
  struct's file. It throws these away when it writes C. The patch dumps them as JSON when `RNA_JSON_DUMP` is set
  and changes nothing otherwise. It is recorded as the local branch `source-facts-makesrna` in
  `.cache/blender-src/5.2-src`, pushed to `projects.blender.org/Simon-Sak/blender` as `source-facts-makesrna`
  (on `v5.2.0`).
- **`doc/python_api/rst_from_bmesh_opdefines.py`**. A regex reader of `bmesh_opdefines.cc` that writes the bmesh
  ops rst. Its header says it "makes assumptions about formatting" and should be rewritten "using a real parser or
  add introspection into `bmesh.ops`". The regex prototype's bmesh reader is that rewrite: tokenized, with enum
  items and slot docs. It finds 83 of 83 ops.
- **`tools/check_source/static_check_clang.py` + `project_source_info.py`**. Upstream already runs libclang over the
  build's compile commands for source checks (struct comments, and so on). The libclang prototype uses the same
  approach, so upstream has the dependency in its tooling, but not in the build.
- **`doc/python_api/sphinx_doc_gen.py` / `sphinx_stub_gen.py`**. The builtin generator introspects a running
  Blender. A source reader can feed its data model (section 7) or check its hand tables (section 6).

## 4. Facts only a source reader has

Each was found by at least one prototype and is missing or wrong in the builtin 5.2 stubs.

1. **Never-null parameters.** 812 RNA function pointer parameters are required and `PROP_NEVER_NULL`
   (`AOVs.remove(aov)`, `Action.flip_with_pose(object)`); for 553 of the members both sets have, builtin types
   such a parameter `X | None`.
   - *How the readers know:* the `RNA_def_parameter_flags(parm, PROP_NEVER_NULL, PARM_REQUIRED)` call right after
     the parameter is defined. makesrna dumps the flag it keeps; regex and libclang read the call.
   - *Why builtin misses it:* the runtime does expose the flag (`is_never_none`), but 5.2's
     `scripts/modules/_rna_info.py:562` adds `| None` to any argument whose default renders as `None`, which every
     pointer parameter's does, before looking at `is_never_none`. The fork's `_rna_info` checks the flag first.
   - *Who is right:* `pyrna_py_to_prop` raises `TypeError` for `None` on a never-null pointer.
2. **Positional-only C functions.** The argument parsers say which parameters have no keyword:
   - `METH_VARARGS` functions;
   - empty `_keywords[]` entries, 488 parameters;
   - `bl_math.clamp`, `lerp` and `smoothstep`.

   Builtin allows keywords for all of them.
3. **bmesh operators.** `bm` is positional-only and every slot keyword-only (`python/bmesh/bmesh_py_ops_call.cc`
   expects "a single BMesh positional argument" and reads the slots from `**kw`). Builtin has neither marker. Both have the enum slots as `Literal`s; builtin also has the slots'
   defaults, which the readers render as `...`.
4. **Typed node sockets.** For example `GeometryNodeMeshCube.inputs['Size']` is a vector with subtype translation,
   and `GeometryNodeSetPosition.inputs['Position']` is a `NodeSocketVector`. The readers render per-node
   `inputs` / `outputs` views with `Literal` overloads. Builtin has only the generic `NodeInputs`.
5. **Context members per editor and their real types:**
   - `Context.annotation_data` is `Annotation` in 5.2, where builtin says `GreasePencil`;
   - `Context.texture_slot` is `ParticleSettingsTextureSlot | LineStyleTextureSlot`, where builtin says
     `TextureSlot`;
   - `Context.edit_mask` is `Mask | None`, answered by the sequencer, clip and image editors.
6. **Callbacks by name.** For each enum, its item function (205-244 of them); for each struct, its refine function
   (1,103); for each pointer, its poll (111) and type function (9); 96 editable functions; getters and setters.
   These are what a stub generator needs to decide whether static items are real (section 6) or a pointer's type
   is narrower than declared.
7. **DNA mapping.** Each property's DNA field (`Object.location` reads `Object.loc`; 8,796 properties in
   makesrna's facts) and each struct's DNA name (1,635 by libclang). The runtime has no such link.
8. **Operator property flags**, e.g. `MESH_OT_primitive_cube_add_gizmo.matrix` is hidden and skip-save.
9. **A source location for every fact**, so a wrong stub points at the line that defines it.

Facts no source reader can get, so they still need the runtime or the docs:

- DNA defaults: makesrna applies `DNA_*_defaults.h` at build time, and the readers see only `RNA_def_*` defaults.
- Items an item function builds at runtime.
- Sockets whose type depends on node storage: zones, bundles, menus, 133 sockets.
- Identifiers built at runtime.
- `#ifdef` branches the build disabled, as seen by libclang. regex runs both and makesrna sees the build's.
- Everything registered from Python by add-ons that are not in the scanned roots.

## 5. All the generators: where each fact comes from

| Fact | builtin 5.2 | fake-bpy 5.2 | source readers |
|---|---|---|---|
| RNA structs, properties, functions | runtime `bpy.types` via `_rna_info` → rst → stubs | the same rst | `RNA_def_*` calls (makesrna runs them) |
| Never-null parameters | lost (`_rna_info.py:562`, section 4.1) | lost: every pointer argument and every optional argument is `\| None` (`FCurves.ensure(index: int \| None = 0)`) | `RNA_def_parameter_flags` |
| Nullable returns | never | rarely | regex, makesrna: every pointer return; libclang: from the C body (section 5.1) |
| Optional RNA parameters keyword-only | yes | yes | yes (`pyrna_func_call`) |
| Array and math arguments | `Sequence[...]` | `Sequence[...]` | `Vector \| Sequence[float]`, as `pyrna_py_to_array` accepts any sequence |
| Dynamic enums | the items the item function gives at runtime | the same | `str`, with the item function's name |
| Context members | a hand table in `sphinx_doc_gen` (stale: `annotation_data`) | the same rst | the `CTX_data_*_set` calls in each editor's context callback |
| Positional-only C parameters | no (`/` missing from docstring signatures) | no | `METH_VARARGS`, empty `_keywords[]` entries |
| bmesh slots | defaults, no markers | the same | positional `bm`, keyword-only slots, no defaults |
| Node sockets per node | no | no | `declare()` builders |
| `bpy.app` members, freestyle, Python-registered `*_UL_*` classes | yes | yes | no (`bpy.app` is a struct sequence and the readers model it as classes; freestyle's Python package re-exports from `_freestyle` are not read; `*_UL_*` come from add-on registration) |
| Python-script functions | typed from docstrings | typed | annotations only (`?` elsewhere) |
| DNA field names, callbacks, source locations | no | no | yes |

**The fork's runtime generator** (`stubs:generate` with the fork's `_rna_info`, `BuildRNAInfo(keep_ui=)`) could
not run for 5.2: the fork's `_rna_info` needs the fork's Blender, and the 5.2 release binary ships its own. The
comparison covers the release's builtin stubs instead.

Known gaps and disagreements in the readers, besides the above:

- `RenderEngine.render` is both a registerable function and a pointer property in `rna_render.cc`. pyrna's
  getattr finds the property first, so the readers' attribute is what an instance returns, while builtin keeps the
  method subclasses implement.
- Operators whose identifiers are built from templates (node item operators) are missing.
- `Image.pixels`-style dynamic arrays: regex records only the `PROP_DYNAMIC` flag, which the renderer now reads as a
  dynamic array.

### 5.1 Nullable returns, classified from the C bodies (libclang)

RNA has no flag for whether a function's pointer return can be NULL, so the answer is in the C implementation.
`libclang/returns.py` reads it:

1. **Parse the runtime halves.** The C implementations sit behind `#ifdef RNA_RUNTIME`, which the define-time parse
   leaves out. They are parsed the way Blender compiles them: as the generated `rna_*_gen.cc` units (target
   `bf_rna`), each including `RNA_prototypes.hh`, then `rna_X.cc` and `rna_X_api.cc`. These exist after the
   build's code generation (`blender:build --target codegen`: makesrna, makesdna, the shader and data headers, no
   object files of Blender; 1,303 build steps). The build is the full configuration, so every `#ifdef WITH_*`
   branch matches a release build. Before, the `lite` configuration hid the real XR code behind `#else return
   nullptr;` stubs.
2. **Follow the callees.** Calls without a parsed body are looked up in a text index of definitions under
   `source/blender` (sources and headers, class bodies included), and their files are parsed, four rounds deep (156
   more units). Inline functions, function templates and class template methods in headers are
   lowered too.
3. **Walk each return.** A small path-sensitive walk over the lowered AST classifies every `return`. Calls are
   followed with each argument's nullness bound to the callee's parameter, so `get(ob) { if (!ob) return nullptr; ...
   }` called with the never-null `self` gives `never`.
   - `never`: an address, `new`, a `MEM_*` allocation, or a local known to be non-null. A local is non-null when it
     was checked (`if (!x) return ...`), sits in a loop condition (`for (x = first; x; ...)`), or was dereferenced
     (a NULL would crash there, not reach Python).
   - `null`: `nullptr`, `PointerRNA_NULL` or an empty `PointerRNA`, or a callee that can return NULL. pyrna gives
     `None` for a pointer return whose `data` is NULL (`pyrna_param_to_py`, `bpy_rna.cc`).
   - `raises`: NULL after a report of level `RPT_ERROR` or above on the same path. This includes a report inside a
     failed check (`if (!check(ob, reports)) return nullptr;`) and inside the callee that gave the NULL.
     `pyrna_func_call` turns such reports into a `RuntimeError` (`BPy_reports_to_error`), so the NULL never reaches
     Python.
   - `unknown`: a callee without a body, a call through a pointer, or a field read never checked.
4. **Remember conditions.** Each condition the path took is a fact (`supported(ob)` held, `ob->type == OB_MESH` did
   not), keyed by its canonical form, with locals standing for their initializer until assigned. A test the path
   already decided takes only its feasible side. Facts naming only a callee's arguments follow the call into it, and
   what holds on every true (false) return of a callee holds after the caller tests it. Loops forget what their body
   assigns.

With the codegen build, 1 of the 1,072 parsed units (define-time, runtime and the callees' units) has a clang error (a signedness warning `string_utf8.cc` turns
into an error itself), down from 69 of 1,097 on the partial `lite` build with a declaration shim. A cold run
parses for about 24 minutes, with 2 processes.

Results for 5.2 (1,389 RNA functions with a pointer return):

| Verdict | Functions | Stub | Examples |
|---|---|---|---|
| never | 102 | `X` | `BlendDataMeshes.new` (the ID is dereferenced right after allocation), `UILayout.row`, `CurveSplines.new` (`MEM_new`), `KeyMap.active` (falls back to `self`), `XrActionMaps.new`, `GreasePencilv3Layers.new` (a derived `Layer *` returned as its base) |
| raises | 42 | `X` | `ActionChannelbagFCurves.new` / `ensure`, `BlendDataObjects.new`, `Nodes.new`, `KeyMaps.new`, `Object.shape_key_add`, `Window.event_simulate` (the callee re-tests the flag the caller reported on) |
| null | 1,201 | `X \| None` | lookups (`FCurves.find`, `KeyMaps.find_match`, `Strip.strip_elem_from_frame`); `PaletteColors.new` (not editable, no report); `AssetTags.new` (only a warning); `NodeLinks.new` (sockets from another tree); `ID.copy`; 1,120 are `input_template` / `output_template` on every node type, which return an empty pointer past the last template |
| unknown | 44 | `X \| None` | 22 with no C function in the facts (Python callbacks such as `AssetShelf.get_active_asset`, and node socket item collections whose function name the define-time reader does not resolve), `GreasePencilLayer::frame_at`, `ID.evaluated_get` (reads a depsgraph field) |

Effect on the comparison: libclang's return nullability differs from builtin's on 1,233 members, down from
1,355. Its overall agreement with builtin rises to 81%, and its return differences with fake-bpy drop from 77 to 22.

Of the three fixes to the first version: parsing the runtime units as `bf_rna` does, keeping recovered calls and
lowering headers settled 12 functions. Nine of those were `unknown`; the other three were a wrong `never` (`ID.evaluated_get`,
where `return DEG_get_evaluated(depsgraph, id)` had been read as `return id`). Path facts settled one more
(`Window.event_simulate`). The define-time facts did not change. The codegen build settled ten more: eight XR
functions, and two returns the type guard against lost calls had distrusted (the guard now applies only to units
with clang errors and to templates, whose dependent calls clang leaves unresolved). It also adds what the full configuration compiles: 12 operators, 348 operator properties, 25
RNA properties and 22 Python module functions.
The remaining differences with builtin are almost all real NULL returns that builtin types as non-null.

Cross-checks (`libclang/crosscheck.py`, written to `crosscheck.md`), on the same generated units:

- **LLVM** (`clang -O1 -fno-inline -emit-llvm`): LLVM's attribute inference marks a raw pointer return `nonnull`
  only when it proves it within the unit, or marks the argument it returns `returned` (counted when that argument
  is never NULL). `-fno-inline` keeps the static RNA functions from being inlined into the generated wrappers,
  which would leave no definition to read. It marked 10 functions, all classified `never`. It cannot read a
  `PointerRNA` returned by value.
- **Clang Static Analyzer**: a probe calls each RNA function with its never-null arguments and dereferences the
  result; error reports end the path. It found a NULL path in 13 functions classified `null`, confirming them, and
  in 2 others, both false positives from defensive checks of values that cannot be NULL:
  - `AnnotationStrokes.new` tests the result of `MEM_new`, which aborts rather than return NULL;
  - `KeyMaps.new` tests `keymap &&` after `WM_keymap_ensure`, which always returns one.
- Five functions with overloaded names are not probed. Before the fixes above, the checks found 13 disagreements:
  11 came from the probe itself, because the analyzer never inlines the variadic `BKE_reportf`, so its reports are
  modelled as macros now. The 12th was `GreasePencilv3Layers.new`.

Only functions with a parsed C body are checked (the 22 `unknown` ones with no C function are not). Both tools see one unit, so callees elsewhere are opaque to them: they confirm or question a verdict, they do not
replace the walk.

Limits:

- **Invariants the code does not state.** `VertexGroups.new` checks `BKE_id_supports_vertex_groups(ob->data)`, then
  calls `BKE_object_defgroup_add_name`, which returns NULL unless `OB_TYPE_SUPPORT_VGROUP(ob->type)`. Both test the
  same thing only because an object's type always matches its data's ID type, which no line of code asserts.
  `BKE_attribute_new` ends in `(index == -1) ? nullptr : ...` right after `BM_data_layer_add_named` added that
  layer: the NULL is ruled out by what the callee did, not by a condition. Both stay `null`.
- **Fields are not invalidated by calls.** A fact about `ob->type` survives a call that could change it. RNA
  functions do not do this, but the walk would not notice one that did.
- **Missing C functions and bodies.** 22 functions have no C function in the define-time facts: registerable
  callbacks implemented in Python, and the node socket item `new` functions, whose name the reader does not resolve.
  About ten more end in a callee with no parsed body (`GreasePencilLayer::frame_at`, `RE_engine_begin_result`).
- **Configuration.** The codegen build turns off three windowing features whose system packages the build machine
  lacks (`WITH_X11_XINPUT`, `WITH_X11_XFIXES`, `WITH_GHOST_WAYLAND`). They touch no RNA, operator or Python API
  code.

## 6. Hand tables checked against the facts

`common/audit.py` checks `ENUM_RUNTIME_ITEMS` (`scripts/modules/_rna_info.py`). This is the fork's hand list of
enums whose static items are not the ones their item function gives.

- All 12 entries are confirmed: each has static items and an item function in makesrna's facts.
- 108 more enums have both. Each is a candidate: its item function may filter the static items, which a stub can
  keep as a `Literal`, or replace them, which needs `str`. Telling the two apart needs the function's body. That is
  the libclang reader's strength: it follows calls into bodies (30,296 of them) and could classify each item
  function by whether it only copies items from the static array.

Other hand tables a source reader could replace or check:

- `ID_DATA_OWNERS`: needs the `owner_id` passed where pointers are made, which is libclang territory.
- `POSITIONAL_ONLY_METHODS`: the readers already find these from `PyObject_CallMethod` formats and argument parsers.
- `BUFFER_CLASSES`: `tp_as_buffer` in the type tables, read by both regex and libclang.

## 7. Upstreamability

| | regex | libclang | makesrna |
|---|---|---|---|
| New dependency | none | `libclang` wheel (upstream tooling already uses it) | none |
| Needs a build | no | compile flags (or synthesized, with more errors) | yes, the `makesrna` target |
| Change to C/C++ | none | none | ~480-line patch to `makesrna.cc`, inert unless `RNA_JSON_DUMP` is set |
| Correctness risk | heuristics on unusual code (420 "defined twice" warnings from both-branch runs) | clang errors in 48 of 832 units, none fatal | none for RNA |
| Upkeep | follows code style changes | follows clang releases | follows makesrna's internals |
| Fit | a tool next to `rst_from_bmesh_opdefines.py` | `tools/check_source/` | `makesrna` itself, plus a Python consumer in `doc/python_api/` |

Verdict:

- **makesrna's dump is the upstreamable core for RNA.** It is small, exact and free at build time. It also gives
  the builtin generator facts it now takes from hand tables or lacks: never-null parameters, callback names, DNA
  fields.
- **The non-RNA areas fit a plain-Python reader.** This covers the Python C API tables, operators, node
  declarations, context callbacks and bmesh. The regex prototype shows this works without a build. It needs
  splitting into per-area readers and its heuristics narrowing before it is upstream quality.
- **libclang belongs in analysis tooling.** It suits one-off checks such as classifying item callbacks and owner
  IDs, not the docs build.

**Deviation from the plan.** The plan was to reuse `sphinx_stub_gen`'s back end as the renderer. The prototypes use
their own (`common/render.py`) instead, because that back end applies the fork's hand tables
(`ID_DATA_OWNERS`, `POSITIONAL_ONLY_METHODS`, `ENUM_RUNTIME_ITEMS`, ...). With them, the comparison could not tell
what the source gives from what the tables add. The renderer encodes only what the C code itself decides:
- `pyrna_math_object_from_array` for mathutils classes;
- the `PyTypeObject` slots for dunders;
- the socket declaration classes;
- the bmesh slot types.

Feeding the facts into `sphinx_stub_gen`'s data model is the next step for an upstream version.

## 8. Open questions

- Should RNA get a flag for never-null returns? The libclang classification (section 5.1) shows only 127 of 245
  distinct C functions are provably non-null to Python. A flag set where the C guarantees it would let every
  generator drop the guesswork.
- Is the 1-second makesrna dump worth adding to `stubs:generate` now, as a fact source for the builtin generator's
  never-null parameters and callback names?
- The 108 enum candidates: classify their item functions with libclang, then decide which stay `Literal`.
