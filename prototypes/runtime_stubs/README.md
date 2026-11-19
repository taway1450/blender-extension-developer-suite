# PROTOTYPE: stubs from a running Blender (throwaway)

Throwaway code that answers one question from `docs/research/runtime-stub-generator.md`: can a third stub generator
open Blender and turn everything it holds at runtime into stubs, competing with fake-bpy-module and the builtin
stubs? And can it do the same for a user's add-on, including the content of the add-on's `.blend` files? Nothing
here is production code, and nothing else in the repo depends on it.

`runtime_stub_gen.py` runs inside Blender and fills the data model of Blender's own stub generator
(`doc/python_api/sphinx_stub_gen.py`: `ModuleInfo`, `ClassInfo`, ...) straight from introspection. No rst is
written or parsed. It renders the model with that generator's back end, so the stubs keep the shapes ty-blender reads.
Blender's Python has no docutils, which only the rst front end uses, so a stand-in module lets `sphinx_stub_gen`
import (the research note's R0 seam).

| Area | Where it comes from |
|---|---|
| `bpy.types` | `_rna_info.BuildRNAInfo` with `get_type_description` strings; the fork's Type-tag probe in the same process (refined pointers, tag values such as `SubsurfModifier.type`); the context member table of `sphinx_doc_gen`, checked against `_bpy.context_members()` |
| `bpy.ops` | the same RNA info: one function per operator, keyword arguments typed as `sphinx_doc_gen` types them |
| C modules (`mathutils`, `gpu`, `bmesh`, `aud`, `bpy.app`, `_freestyle`, ...) | their live members (`dir()`, `__bases__`, slots), typed by the rst field lists in their `__doc__` (Blender's C functions have no `__text_signature__`), with the `\|X\|` substitutions their module docstring defines |
| Python modules (`bpy.utils`, `bpy_extras`, `bl_ui`, `freestyle`, ...) | copied as source, as the note recommends; a class a startup script registers in `bpy.types` is re-exported there from its module, with all its members |
| Default add-ons' registrations (`Scene.cycles`, `CYCLES_*` panels) | left out with their provenance (`facts.json`): the user may disable those add-ons |

Add-on mode (`--addon <folder>`) enables the add-on as a legacy add-on after a first snapshot of RNA and
`bpy.ops`. It then writes:

- `delta.json`: the new structs, the new properties on existing structs, the new operators and the add-on's modules;
- `stubs/`: a merged package, the general stubs plus the add-on's registrations (`Scene.reg_group:
  PROPS_REGISTERED_Item | None`, `bpy.ops.opcall_basic.all(...)`), for stock type checkers;
- `blend/<file>.json`: for every `.blend` under the add-on, opened with `-Y` (no auto-run), every local ID by class
  and name, walked to depth 4 through RNA: named collections (`modifiers`, `material_slots`, `nodes`, sockets by
  identifier) by refined class, and ID pointers as references.

Run it with the builtin and fake-bpy-module stubs of the version already generated:

```bash
mise run probe:runtime-stubs main
```

## Findings on `main` (Blender 5.4 alpha, 66f10cc53b)

- **Speed.** General mode takes about 2.7 s inside Blender: 1 s of that is `BuildRNAInfo` plus the Type-tag probe.
  The builtin generator writes and parses 49 MB of rst instead. Add-on mode is 3.2 s per add-on, and a `.blend`
  takes about 10 ms to open and walk.
- **Factory startup enables the default add-ons** in background mode (`bl_pkg`, `cycles`, `io_anim_bvh`,
  `io_curve_svg`, `io_mesh_uv_layout`, `io_scene_fbx`, `io_scene_gltf2`, `pose_library`). This answers the note's
  first open question: no explicit `addon_utils.enable` is needed. 135 of their classes and 16 of their properties
  on built-in structs are left out of the general stubs.
- **Against builtin (same build):**
  - The runtime package has 366 modules (builtin 147), because it ships the Python source of the script folders.
    Only `bpy.app.translations`, `bpy.utils.units` and `freestyle.utils.ContextFunctions` are missing: they are
    module-like C objects or attributes the walk does not reach yet.
  - Members of shared classes: 22,655 the same, 579 typed differently, 299 untyped (copied source without
    annotations, where builtin has docstring types), 694 only in runtime and 1,625 only in builtin.
  - The 1,924 startup classes the builtin stubs declare bare (`class VIEW3D_PT_x(Panel): ...`) are re-exported from
    `bl_ui` / `bl_operators` with all their members. This is the S10 gap of `docs/reports/remaining-causes.md`.
- **What the runtime alone does not give** (the classes and members only in builtin, and the typed differences):
  - the node-socket probe's socket views (`_ShaderNodeBsdfPrincipled_inputs`, 1,173 classes, plus the
    `inputs`/`outputs` they type). The probe runs in-process like the Type-tag one, but rendering its views needs
    `sphinx_doc_gen`'s `write_struct` logic;
  - `bmesh.ops` argument types (87 functions): the runtime `__doc__` has only names and defaults, and the types
    come from `bmesh_opdefines.cc`;
  - the operand types of C slots (`Vector.__add__`, `BMEdgeSeq.__iter__`): CPython's slot docstrings are generic,
    so operators return `Any` (52 in `mathutils`, 27 in `bmesh.types`), where builtin uses its tables;
  - the hand tables of `sphinx_doc_gen` that the prototype does not apply yet: `RNA_PROPERTY_TYPES`
    (`Library.version` is a tuple), keyword-only optional RNA parameters, `RNA_SELF_RETURNS`
    (`animation_data_create`), and the C-API internals (`ContextTempOverride`, `BlendDataPathMeta`,
    `InlineShaderNodes`, `GeometrySet`, still unresolved references);
  - docstring types of documented Python modules (`bpy.path`, `bpy_extras`): the copied source has none where it
    is unannotated.
- **Against fake-bpy-module:** 14,672 members the same and 10,683 typed differently (nullability, collections,
  enum spelling: the shapes the two generators already disagree on). The runtime stubs follow builtin's shapes,
  because they share its back end.
- **Add-on mode** sees what source analysis cannot, and what the checker must otherwise assume:
  - `opcall_basic`: Blender registers `OPCALL_BASIC_OT_dropped` and `OPCALL_BASIC_OT_dropped_group` even though
    their ID pointer properties fail. The add-on logs the error and keeps the operators, without those properties.
  - `props_registered`: 27 properties on 17 built-in structs, among them those registered through an alias or
    `setattr`.
  - The `.blend` walk records the loaded state, after versioning: refined socket classes (`NodeSocketFloatFactor`),
    modifiers by name, material slots, and node groups with their nodes.

## Verdict

Introspection is a viable front end, and a fast one, for everything RNA and the startup scripts define. It is the
only route to registrations and `.blend` content as Blender sees them. It cannot replace the doc pipeline's tables
and source-derived facts (socket views, `bmesh.ops`, slot operand types, the RNA tables above). Those stay shared
with builtin, as the note expected. The cheapest product path is still the note's R1–R3: move the docutils imports
out of `sphinx_stub_gen`, let the runtime front end call the same table and probe helpers `write_struct` uses, and
add `--generator runtime` to `generate_stubs.py`, so that `check:features` and `check:blender` can measure it like
the other two.
