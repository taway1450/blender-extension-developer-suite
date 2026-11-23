# Where type tags get their data

Research note, 2026-11-17, for issue #112. Trimmed on 2026-11-18 to the rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings.

**Question.** Where can the facts behind Type tags come from, and how reliable is each source: RNA's refine functions, the stub generator, or a table written by hand in `crates/ty_blender`? How could fake-bpy-module carry the same facts?

Conventions: `src/` means `.cache/blender-src/main/` (the Blender fork, commit `9a7af0b847`). `ty/` means `ty-blender/ruff-blender/crates/`.

Main now: every gap this note listed is closed. The probe records `Node.type`, `NodeTreeInterfaceItem.item_type`, boid rules, line style modifiers, viewer path elements, project variables and `pose` in the `Object.type` view; constructor narrowing reads the existing table, and `BlendDataCurves.new` has an overload per curve type. fake-bpy-module now carries the tag views. See `tests/typecheck/features/api_types/README.md` and `tests/typecheck/features/type_narrowing/README.md`, and [type-tags.md](type-tags.md) for the narrowing itself.

## 1. Answer

1. **The source is the stub generator.** The Blender fork's `doc/python_api/sphinx_doc_gen_type_tags.py` runs inside Blender while the API docs are generated. It makes one instance for each tag value and reads which subclass Blender returns. `sphinx_doc_gen.py` then writes the result into the RST in two forms: a value-form literal on each refined subclass (`type: Literal['SUBSURF']`), and a private tag view for each tag value with consequences for other members (`_Object_MESH`, `_FluidModifier_DOMAIN`). ty reads only the stubs.
2. **RNA cannot be read for this.** `RNA_def_struct_refine_func` stores only the name of a C function. Introspection cannot see that function, and its C body switches on DNA constants (`LA_LOCAL`), on registries (`typeinfo->rna_ext.srna`, `ModifierTypeInfo::srna`), on values RNA does not expose (`Curve::ob_type`) or on flag bits.
3. **A hand table in `ty_blender` is the least reliable source.** It goes stale with every Blender change, and the stubs already state the same facts. Only facts that hold in every Blender version belong there: `ty/ty_blender/src/type_tags.rs` keeps `ADDON_TYPE_TAG = "CUSTOM"` (a test of it narrows nothing) and `excludes_on_mismatch` (a failed `bl_idname` test rules nothing out). Its module doc states the rule: "Which value names which class depends on the Blender version and is read from the stubs; what holds for every version is here."
4. **Some sub-pointers look like tags but are not.** `Material.node_tree` / `World.node_tree` follow nothing: `use_nodes` is deprecated and always `True` (`rna_material.cc:271`, `rna_world.cc:94`), so they are a never-None fact. Grease Pencil brush settings follow the brush's mode (`BKE_brush_init_gpencil_settings`, `brush.cc:703-710`), and `tool_settings.sculpt` etc. exist once that mode has been entered: session state, reached by implied narrowing by mode. `MaterialGPencilStyle` follows `Material.is_grease_pencil`, whose getter is `gp_style != nullptr` (`rna_material.cc:414`). Sites that read `constraints[0]`, `inputs["Color"]` or `bpy.data.objects["Cube"].data` never state the subclass, so no tag source reaches them.

## 2. The candidate sources

### 2.1 RNA (`RNA_def_struct_refine_func`, `rna_*_refine`)

**What it is.** `RNA_def_struct_refine_func(srna, "rna_Light_refine")` stores a function name (`src/source/blender/makesrna/intern/rna_define.cc:1047`). makesrna turns it into a function pointer.

**What it covers.** In principle, every refined base. In practice the bodies fall into four kinds:

| Kind | Examples | What the body reads |
| --- | --- | --- |
| switch on a DNA enum | `rna_Light_refine` (`rna_light.cc:46`), `rna_ConstraintType_refine` (`rna_constraint.cc:341`), `rna_Texture_refine`, `rna_Space_refine`, `rna_BoidRule_refine`, the four `rna_LineStyle_*_modifier_refine`, `rna_GreasePencilTreeNode_refine`, `rna_viewer_path_elem_refine`, `rna_ProjectVariable_refine` | `la->type` against `LA_LOCAL`, ... The RNA identifier (`'POINT'`) appears only in a separate enum table (`rna_enum_light_type_items`, `rna_light.cc:126`). |
| type-info registry | `rna_Modifier_refine` (`rna_modifier.cc:906`: `BKE_modifier_get_info(md->type)->srna`), `rna_Node_refine` (`rna_nodetree.cc:1447`), `rna_NodeSocket_refine` (`rna_node_socket.cc:248`), `rna_NodeTree_refine`, `rna_NodeTreeInterfaceItem_refine` | A pointer set elsewhere: `MOD_*.cc` for modifiers, node registration for nodes. |
| a value RNA does not expose | `rna_Curve_refine` (`rna_curve.cc:249`, `cu->ob_type`), `rna_UserAssetLibrary_refine` (`rna_userdef.cc:457`, a flag bit), `rna_ID_refine` (`GS(id->name)`), `rna_IKParam_refine` (`rna_pose.cc:330`, the solver, an attribute of the owning `Pose`) | There is no tag attribute on the struct to test. |
| Python registration | `rna_Operator_refine`, `rna_Panel_refine`, `rna_Menu_refine`, `rna_UIList_refine`, `rna_Gizmo_refine`, `rna_PropertyGroup_refine`, `rna_AddonPref_refine`, ... | The add-on's own class. These are not tags. |

**Does it stay correct as Blender changes?** The source itself is correct by definition, but reading it is not. Nothing in RNA's data links a refine function to a property. `bl_rna` does not expose the function, so Python introspection cannot reach it. A static reader would have to parse C++ switch statements, map each DNA constant to its RNA identifier through the matching `EnumPropertyItem` table, find which RNA property reads that DNA field (`RNA_def_property_enum_sdna`), and follow registries into other directories. Every refactor of a refine body (Modifier moved to `ModifierTypeInfo`; Node and NodeSocket go through `typeinfo`) breaks such a reader without warning.

**What it says about sub-pointers.** Nothing. `Object.pose` is a plain `RNA_def_property_pointer_sdna(prop, nullptr, "pose")` (`rna_object.cc:3721`). Whether it is set depends on BKE code (`BKE_pose_rebuild`), and RNA does not record that.

### 2.2 The stub generator (the fork's `doc/python_api/`)

**What it is.** `sphinx_doc_gen_type_tags.py`, in the fork (Blender 5.2's tree does not have it). It runs inside Blender, as part of `sphinx_doc_gen.py` when `USE_STUB_GEN` is on:

- **Families.** For each value of `base.attr`'s enum, it makes an instance with the real constructor and records `type(instance).bl_rna.identifier` → value.
- **Single-subclass bases.** A base whose tag enum has one value is always that one subclass (`ActionStrip` → `ActionKeyframeStrip`), and every pointer to it is rewritten.
- **Tag views.** For each value, it makes instances and reads the named members (`Object.type` → `data`; `FluidModifier.fluid_type` → its three settings pointers). A member that is always None becomes `None`. Several variants give their nearest common base, so a light object's data is a `Light`.
- **Missing values** are printed as `Type tag not probed: ...` (for example `Strip.type 'SOUND'` without Audaspace).

The output is RST, which the built-in stub generator turns into `Literal` declarations and the view classes.

**Does it stay correct as Blender changes?** It is the most reliable source of the three. It asks the running Blender, so a new modifier, a renamed node or a changed refine function shows up the next time the stubs are generated. Nothing has to be edited. Its limits:

- It covers only the families someone listed. A base that is not listed has no tags, and each new family needs a constructor recipe in the probe.
- `Node.type` is a legacy string, not an enum (`rna_nodetree.cc:4140`: "Legacy unique node type identifier, redundant with bl_idname"). Several classes share a value (`'MATH'`), which the table handles by mapping one literal to every class that declares it.
- It records what a **fresh** instance shows. That holds for refined subclasses. For views it can differ from the steady state. For example, `Object.pose` of a new armature object is null until the object is evaluated or a file is read (`src/source/blender/blenkernel/intern/object.cc:4293`, `BKE_pose_rebuild` under `recalc_data`).
- `Curve` has no tag attribute: its subclass follows `Curve::ob_type`, which no RNA property exposes. Only the probe can record "`curves.new(type='FONT')` gives a `TextCurve`", as a constructor fact rather than a tag.
- It needs a Blender build, and the fork's generator. The 5.2 stubs come from 5.2's tree, so they have no tags.

**Side file or stubs?** The probe could also write a JSON table next to the stubs. Writing the tags into the stubs is better on every count: one artifact carries the facts, both stub sets get them through the RST, hover and an IDE without ty see them, and the views work through ordinary member lookup. A side file would bind ty to a format only the built-in stubs ship.

### 2.3 A hand-written table in `crates/ty_blender`

**What it would cover.** Whatever someone types in, including facts no probe can reach, such as "the node created by `nodes.new('ShaderNodeMath')` is a `ShaderNodeMath`".

**Does it stay correct?** No. It holds one Blender version's facts inside the type checker. Values go stale silently (5.x renamed nodes and removed `use_nodes`). It has to be keyed by version, and it duplicates what the stubs already state. It also runs against the crate's own rule (section 1). It only fits facts that hold in every version, which is what `ADDON_TYPE_TAG` and `excludes_on_mismatch` already are.

So the stub generator is the only source of per-version tag facts, its gaps are closed in the probe, and `ty_blender` keeps the version-free rules.

## 3. fake-bpy-module

- fake-bpy-module builds its stubs from the same RST (`fake-bpy-module/src/gen.py` reads every `*.rst` under the input directory), and `scripts/generate_stubs.py` hands it `.cache/bpy-rst/<version>/sphinx-in`. So it gets the value form for free, written as `@property def type(self) -> typing.Literal["SUBSURF"]` with the docstring "The type of every `SubsurfModifier`". ty's table reads the property form too.
- The tag views were missing at the time: the RST held the view pages, but fake-bpy-module's output had no `_Object_` or `_FluidModifier_` class, and it typed `Object.data` as the union of every data type. Ways to carry the views: (a) fix whatever drops the orphan class pages, so they pass through unchanged (the best option, since nothing else changes); (b) a `mods/*.mod.rst` file that declares them (fake-bpy-module's patch mechanism). That one is hand-written, so it would go stale as in 2.3.
- In the built-in stubs the constructor parameter and the tag share the enum alias (`ObjectConstraints.new(self, type: rna_enum_constraint_type_items)` and `Constraint.type: rna_enum_constraint_type_items`). fake-bpy-module expands the enum to literals, so a constructor rule there needs the method → tag pairing stated some other way.
