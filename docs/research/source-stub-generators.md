# Stubs from Blender's source: three readers compared

Research note, 2026-11-20.

**Question.** How many `bpy` stubs and facts can be read straight from Blender's source code, with no running
Blender and no API docs? What can only a source reader find? Which tool should do the reading: plain Python,
libclang or makesrna? Could upstream adopt it?

**Method.** Three prototypes were built in `prototypes/source_stubs/` (see its README), one per tool. They share a
JSON model of facts (`common/model.py`), an `ast` reader for the Python side (`common/pysource.py`) and one renderer
(`common/render.py`). Each was run on the Blender 5.2.0 source (`v5.2.0`, `fbe6228777e7`, worktree
`.cache/blender-src/5.2-src`). Their stubs were compared with Blender's builtin 5.2 stubs
(`.cache/bpy-stubs-builtin/5.2`), fake-bpy-module 5.2 (`.cache/bpy-stubs/5.2`) and each other
(`common/compare.py`). The outputs are in `.cache/source-stubs/5.2/`: `<tool>/facts.json`, `<tool>/stubs/`,
`<tool>/coverage.md`, `comparison.md` and `audit.md`.

## 1. Answer

1. **Most of the API can be read from source, by all three tools.**
   - The readers agree with the builtin stubs on about 80% of the members both have (regex 80%, libclang 78%,
     makesrna 81%). Builtin and fake-bpy agree with each other on only 64%.
   - With one exception, the readers find every RNA struct and every C operator the builtin stubs have. The
     exception is the 55 classes registered from Python (`*_UL_*`, `*_AST_*`, `*_FH_*`).
   - The disagreements left are mostly facts the readers have right and the builtin stubs miss (section 4), or
     conventions (enum alias vs inline `Literal`).
2. **On RNA, the plain-Python reader matches makesrna.**
   - regex and makesrna agree on 100% of the members both have (13,035 same, 44 different).
   - regex reads 95% of makesrna's properties: 10,103 of 10,634.
   - makesrna is exact by construction, because it runs the definitions. The regex reader interprets the same
     `RNA_def_*` call sequences with a small C tokenizer, `#define` expansion and an interpreter that runs both
     branches of a condition it cannot decide.
3. **Only regex and libclang reach beyond RNA.** makesrna knows RNA only. Operators, the Python C API, context
   members, node declarations and bmesh operators are not RNA definitions.
   - regex and libclang read all six areas.
   - They agree with each other on 99% of shared members (37,136 same, 519 different).
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
     semantics: classifying item callbacks, following function pointers, resolving types of locals. It is the
     wrong one for generating stubs on every build: 17 minutes cold, a pinned wheel, and the build's
     `compile_commands.json`.

## 2. The three tools

| | regex (plain Python) | libclang | makesrna |
|---|---|---|---|
| Reads | C/C++ as text: tokenizer, `#define` expansion, call interpreter, table readers | clang's AST (`libclang==18.1.1` from PyPI), flags from `compile_commands.json` | RNA definitions as makesrna runs them, dumped by `makesrna-json-dump.patch` |
| Needs | Python 3, the source tree | the wheel, a configured build for compile flags (`--synthesize-flags` works without one, with more errors) | a configured build with the patch and the `makesrna` target built |
| Areas | RNA, operators, nodes, Python C API, context, bmesh | the same | RNA only |
| Time (5.2) | 55 s extract + 5 s Python | ~17 min cold (833 units, 2 processes), 11 s warm | 1 s extract + 6 s Python |
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
| Context members (typed) | 104 (99) | 104 (60) | - |
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
| regex | 80% | 76% | | 99% | 100% |
| libclang | 78% | 74% | 99% | | 99% |
| makesrna | 81% | 84% | 100% | 99% | |
| builtin | | 64% | | | |

Per area against builtin, for regex: `bpy.types` 82%, `bpy.ops` 84%, `mathutils` 85%, `gpu` 34%, `bmesh` 32%,
other C modules 46%. The low figures for `gpu`, `bmesh` and the C modules are mostly parameter names and kinds:
the readers take positional-only from the argument parser and keyword-only from bmesh slots, and builtin has
neither.

Kinds of disagreement with builtin, for makesrna (the cleanest case, RNA only):

| Kind | Count | Who is right |
|---|---|---|
| Return `X \| None` vs `X` | 1,226 | Open. RNA return pointers have no never-null flag; builtin assumes non-null. |
| Parameter `X` vs `X \| None` | 468 | makesrna: the parameters are `PROP_NEVER_NULL` (e.g. `AOVs.remove(aov)`), and `None` raises. |
| Enum `Literal` vs alias | 321 + 186 | Equal: alias spelling the comparison does not resolve. |
| Parameter types | 222 | Mixed: mostly Python-script functions the `ast` reader leaves untyped. |
| Positional-only / keyword-only | 168 | Convention: RNA functions take any parameter by position; builtin makes optional ones keyword-only. |
| `Literal` vs `str` (dynamic enum) | 133 | Builtin keeps the static items of enums with an item function; the readers say `str` (section 5). |

## 3. Upstream tools that already exist

- **makesrna** (`source/blender/makesrna/intern/makesrna.cc`). In define mode it keeps every callback as the name
  of its C function (`refine`, `itemf`, `typef`, `poll`, `editable`, get/set), each property's DNA field and each
  struct's file. It throws these away when it writes C. The patch dumps them as JSON when `RNA_JSON_DUMP` is set
  and changes nothing otherwise. It is recorded as the local branch `source-facts-makesrna` in
  `.cache/blender-src/5.2-src` (not pushed).
- **`doc/python_api/rst_from_bmesh_opdefines.py`**. A regex reader of `bmesh_opdefines.cc` that writes the bmesh
  ops rst. Its header says it "makes assumptions about formatting" and should be rewritten "using a real parser or
  add introspection into `bmesh.ops`". The regex prototype's bmesh reader is that rewrite: tokenized, with enum
  items and slot docs. It finds 83 of 83 ops.
- **`tools/check_source/static_check_clang.py` + `project_source_info.py`**. Upstream already runs libclang over the
  build's compile commands for source checks (struct comments, and so on). The libclang prototype uses the same
  approach, so upstream has the dependency in its tooling, but not in the build.
- **`doc/python_api/sphinx_doc_gen.py` / `sphinx_stub_gen.py`**. The builtin generator introspects a running
  Blender. A source reader can feed its data model (section 6) or check its hand tables (section 5).

## 4. Facts only a source reader has

Each was found by at least one prototype and is missing or wrong in the builtin 5.2 stubs.

1. **Never-null parameters.** 468 RNA function parameters are `PROP_NEVER_NULL` and required
   (`AOVs.remove(aov)`, `Action.flip_with_pose(object)`). Builtin types them `X | None`.
2. **Positional-only C functions.** The argument parsers say which parameters have no keyword:
   - `METH_VARARGS` functions;
   - empty `_keywords[]` entries, 488 parameters;
   - `bl_math.clamp`, `lerp` and `smoothstep`.

   Builtin allows keywords for all of them.
3. **bmesh operators.** `bm` is positional-only, every slot is keyword-only, and enum slots are `Literal`s
   (`beautify_fill(method: Literal['AREA', 'ANGLE'])`). Builtin has `int` and neither marker.
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
   These are what a stub generator needs to decide whether static items are real (section 5) or a pointer's type
   is narrower than declared.
7. **DNA mapping.** Each property's DNA struct and field and each struct's DNA name (1,635 by libclang). The
   runtime has no such link.
8. **Operator property flags**, e.g. `MESH_OT_primitive_cube_add_gizmo.matrix` is hidden and skip-save.
9. **A source location for every fact**, so a wrong stub points at the line that defines it.

Facts no source reader can get, so they still need the runtime or the docs:

- DNA defaults: makesrna applies `DNA_*_defaults.h` at build time, and the readers see only `RNA_def_*` defaults.
- Items an item function builds at runtime.
- Sockets whose type depends on node storage: zones, bundles, menus, 133 sockets.
- Identifiers built at runtime.
- `#ifdef` branches the build disabled, as seen by libclang. regex runs both and makesrna sees the build's.
- Everything registered from Python by add-ons that are not in the scanned roots.

## 5. Hand tables checked against the facts

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

## 6. Upstreamability

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

## 7. Open questions

- Should a return pointer of an RNA function be `X | None`? RNA has no flag for it. Most `new()` functions raise
  instead of returning NULL, but some lookups return NULL.
- Is the 1-second makesrna dump worth adding to `stubs:generate` now, as a fact source for the builtin generator's
  never-null parameters and callback names?
- The 108 enum candidates: classify their item functions with libclang, then decide which stay `Literal`.
