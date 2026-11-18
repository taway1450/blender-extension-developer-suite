# api_types

**The stubs must state:** which pointers and callback parameters Blender never sets to None, the Type tag of each
refined subclass, and the facts introspection misses (class bases, protocols, module members, ...). These are runtime
facts of the Blender API, not something the checker adds: the fix belongs in the stubs (Blender's RNA definitions, which
the stub generator reads), and the markers guard that the stubs keep saying so.

## What Blender does

- **A pointer to a struct embedded by value is never None.** When the DNA member is a struct, not a pointer to one,
  RNA's getter returns the member's address (`Camera.dof`, `Scene.view_settings`, `Scene.eevee`,
  `RenderSettings.ffmpeg`, `ToolSettings.image_paint`, ...: 62 properties, all read-only). Blender's fork flags them
  `PROP_NEVER_NULL` in makesrna, so `is_never_none` is true and the stubs drop `| None`.
- **Some pointers and function results Blender always sets** (each probed in #109, `mise run probe:never-none`):
  `XrSessionState.viewfinder` (null only when `WindowManager.xr_session_state` is None too), the four
  `KeyConfigurations` pointers, `NodeLink` and `NodeInternalLink` ends, `EditBone.color`,
  `MovieTracking.reconstruction` / `MovieTrackingObject.reconstruction`, `MovieTrackingObjects.active` (Blender's fork
  clamps `MovieTracking.active_object_index` to the objects), `SpaceView3D.region_3d`, `AssetRepresentation.metadata`,
  `Depsgraph.scene` / `scene_eval` / `view_layer` / `view_layer_eval`, `DepsgraphObjectInstance.object`,
  `DepsgraphUpdate.id`, and `Material.node_tree` / `World.node_tree` (every material and world has one since 5.0).
  `bpy.data.node_groups.new()` raises for an unknown type and `AssetLibraryCollection.new()` for an error report
  instead of returning None, and `id_properties_ui()` raises for every failure. Blender's fork flags them
  `PROP_NEVER_NULL` (`id_properties_ui` by its docstring). `XrSessionState` itself and
  `DepsgraphObjectInstance.instance_object` / `.parent` (None unless the object is an instance) stay `| None`.
- **A DNA pointer can be None:** `ToolSettings.sculpt` (allocated on first use), `Object.pose` (armatures only),
  every `animation_data` (until `animation_data_create()`). They stay `| None`.
- **Blender always passes a context** to `Menu.poll` / `draw`, `Header.draw`, `UIList.draw_item` / `draw_filter` /
  `filter_items`, `AssetShelf.poll` / `draw_context_menu`, `FileHandler.poll_drop`, `KeyingSetInfo.poll` /
  `iterator` / `generate` and `RenderEngine.draw` / `view_update` / `view_pause` / `view_resume`: the C caller
  passes the live `bContext`. `RenderEngine.view_draw` gets None when a viewport is drawn off-screen (Viewport
  Render, `GPUOffScreen.draw_view3d`), so it stays `Context | None`.
- **The context's preferences and window manager are never None:** `Context.preferences` is the global `U` and
  `Context.window_manager` the window manager, which exists whenever Python runs. Blender's fork flags both
  `PROP_NEVER_NULL` (both are read-only). `Context.blend_data` is left as it is.
- **Blender always fills some other callback parameters:** `UIList.draw_item` / `filter_items`' `data` (the struct
  holding the collection), `KeyingSetInfo.iterator` / `generate`'s `ks` (`validate_keyingset` returns early without
  a keying set), `AssetShelf.asset_poll` / `draw_context_menu`'s `asset` and `draw_context_menu`'s `layout`, and
  the `depsgraph` of `RenderEngine.update` / `render` / `bake` / `view_update` / `view_draw`. Blender's fork flags
  them `PROP_NEVER_NULL`; `RenderEngine.update` also takes its `data` and `depsgraph` positionally, as Blender calls
  it. `UIList.draw_item`'s `item` (an empty slot of an ID-pointer array is None) and `active_data` stay `| None` in
  the stubs (the checker takes an unannotated `item` as not None, an Assumption: features/assumptions), and
  so does `ObjectModifiers.new()`'s result: a modifier that cannot be added (a second one of a unique type, an object
  type without modifiers) is only a warning report, so it returns None instead of raising.
- **A struct is refined to the subclass its Type tag names** (`rna_Modifier_refine`, `rna_Space_refine`, ... in C,
  which introspection cannot read): a modifier of type `'SUBSURF'` is a `SubsurfModifier`, a space of type
  `'VIEW_3D'` a `SpaceView3D`. Blender's fork probes them when it writes the API docs (`sphinx_doc_gen_type_tags.py`
  makes an instance of each tag value) and each subclass declares its tag: `SubsurfModifier.type:
  Literal['SUBSURF']` (modifiers, shader effects, constraints, F-Curve modifiers, lights, light probes, textures,
  attributes by `data_type`, strips and their modifiers, spaces, RNA properties, node tree interface items by
  `item_type`, boid rules, line style modifiers, viewer path elements, project variables); built-in node trees, nodes
  and sockets declare their `bl_idname`, nodes their legacy `type` (`ShaderNodeMath` and `TextureNodeMath` share
  `'MATH'`), sockets their `type` (many socket classes share `'VALUE'`). A value every subclass below an
  intermediate class shares is declared there (`NodeTreeInterfaceSocket.item_type: Literal['SOCKET']`), and a tag
  each subclass defines itself is declared on the base too (`LineStyleColorModifier.type`). Only the startup file's
  spreadsheet gives viewer path elements, so only `IDViewerPathElem` declares its `type`.
- **A refined base without a tag is one of its subclasses:** a `GreasePencilTreeNode` is a `GreasePencilLayer` or a
  `GreasePencilLayerGroup` (`rna_GreasePencilTreeNode_refine`), so `root_nodes`, `children`, `next_node` and
  `prev_node` give the union. `Curve` has no tag either: only `curves.new()`'s `type` names its subclass, so the
  stubs give `BlendDataCurves.new` an overload per curve type (`'FONT'` → `TextCurve`, `'SURFACE'` →
  `SurfaceCurve`, `'CURVE'` → `Curve`).
- **Some tags decide another attribute's type** without a refined struct: an object of type `'MESH'` has a `Mesh`
  as its data (`'FONT'` a `TextCurve`, `'SURFACE'` a `SurfaceCurve`, `'EMPTY'` no data or the `Image` it
  displays; `'ARMATURE'` a pose or None until the depsgraph builds it, every other type no pose), a fluid modifier of type `'DOMAIN'` has domain settings and no flow or effector settings. The stubs
  declare a private tag view per value, `_Object_MESH(Object)` with `type: Literal['MESH']` and `data: Mesh`, and
  `_FluidModifier_DOMAIN` etc.
- **The only spreadsheet table ID is a geometry table ID:** `SpreadsheetTableID.type` has the one value
  `'GEOMETRY'`, so `SpreadsheetTable.id` is a `SpreadsheetTableIDGeometry`.
- **The only action strip is a keyframe strip:** `ActionStrip.type` has the one value `'KEYFRAME'`, so the items of
  `ActionLayer.strips` and `ActionStrips.new()` are `ActionKeyframeStrip`.
- **Introspection misses some facts** (Blender's fork adds them in `sphinx_doc_gen.py`):
  - module classes have bases: Freestyle's C classes (`ViewEdge` is an `Interface1D`, `QuantitativeInvisibilityUP1D`
    a `UnaryPredicate1D`) and its Python classes (`pyDensityAnisotropyF1D(UnaryFunction1DDouble)`), and a pure
    Python class has its Python `__init__` (a dataclass such as `bpy_extras.anim_utils.BakeOptions` included);
  - BMesh sequences (`bm.verts`, `bm.select_history`, ...) iterate over their elements, entering an ImBuf buffer
    (`ibuf.with_buffer()`) gives a `memoryview`, and an item of `Matrix.row` / `Matrix.col` is a `Vector`;
  - `BlendData.version`, `Library.version` and `Preferences.version` are `PROP_THICK_WRAP` int arrays, which read as
    a `tuple`, so they compare with tuples;
  - every struct has `bl_rna` (set on each class, so it is not in `bpy_struct.__dict__`);
  - `bpy.utils.system_resource` and `is_path_builtin` are public though not in `__all__`; `bpy.path.extensions_*`
    are frozensets and `imbuf.file_types` is a read-only dictionary;
  - `Operator.description` may return None (its `result` string is not never-None), and Blender then shows the
    operator's own description. There is no probe: Blender calls it only for a tooltip.
- **Stub-generator gaps** (Blender's fork fixes them in `sphinx_stub_gen.py` / `sphinx_doc_gen.py` and the docstrings):
  - `BMElemSeq` is one C type for every element link (`BMFace.loops`, `BMVert.link_faces`, `BMLoop.link_loops`,
    ...), each attribute holding one element type: it is generic and the attributes say which
    (`loops: BMElemSeq[BMLoop]`), so `face.loops[0].vert` is a `BMVert`;
  - a `bpy.data` collection looks an item up by a `(name, library_filepath)` key too, the library None for local data
    (`bpy.data.objects[name, None]`);
  - Blender's UI sets context store members that RNA does not list (`context.constraint`, `keymap`, `animated_id`,
    `freestyle_module`, `tool`, `asset_shelf`): each is `X | None`, set only inside the layouts that store it;
  - `bpy.data.libraries.load()` and `bpy.data.temp_data()` return context managers (the input and output libraries,
    a temporary `BlendData`);
  - Freestyle calls an overridable `__call__` (predicates), `traverse` and `shade` with positional arguments, and
    Blender a render engine's `update_script_node` / `update_render_passes` / `update_custom_camera` with all their
    arguments positionally: the parameters are positional-only or required, so an override may rename them or drop
    their defaults;
  - Freestyle's undocumented members reach the stubs once documented: the `UnaryFunction0D*` / `UnaryFunction1D*`
    bases' `__call__` (so a Python function such as `pyDensityAnisotropyF1D` is callable), `Noise.rand` /
    `turbulence_smooth` and `BoundingBox`'s attributes (`corners`); the `freestyle.utils` generators say what they
    yield (the stub generator writes `-> None` without an `:rtype:`), and `Operators.create` takes a list of any
    shader types (`list[_StrokeShaderT]`, bound to `StrokeShader`: the C code requires a `list`, which is invariant);
  - a dynamic enum whose items come from a callback (`NodeTreeInterface.new_socket(socket_type=...)`,
    `GREASE_PENCIL_OT_set_material.slot`) lists only the `'DEFAULT'` placeholder, so it is a `str`;
  - `bpy.utils.keyconfig_set` returns whether it loaded the key configuration, and `Gizmo.target_set_value` takes a
    documented `value`.
- **A math or array property takes any sequence** of the right length (`pyrna_py_to_array`): `ob.location = (1, 1,
  1)`, `ob.matrix_world = rows`, `ob.lock_location = (True, False, True)`, and an array's slice any iterable of its
  elements (`image.pixels[:] = buffer`). Reading it still gives the `Vector` / `Color` / `Euler` / `Quaternion` /
  `Matrix` or the `bpy_prop_array`, and an element of the wrong type raises `TypeError`. The stubs write a writable one
  as a property whose setter takes `Sequence[float]` (`Sequence[Sequence[float]]` for a `Matrix`, `Sequence[T]` for a
  `bpy_prop_array[T]`); a `bpy_prop_array` is itself a `Sequence`.
- **Blender's private C modules import:** `_cycles` (the Cycles add-on), `_bpy` (behind `bpy` itself), `_bpy_hydra`
  (behind `HydraRenderEngine`) and `_freestyle` (Freestyle's C classes and functions). They have no API docs, so
  Blender's fork writes their stubs by hand (`doc/python_api/stubs_handwritten/`): the first three are partial, every
  member is `Any`; `_freestyle` re-exports its members from the documented `freestyle.*` modules, which re-export the
  very same objects, so a `_freestyle.ViewEdge` is a `freestyle.types.ViewEdge`. Its few undocumented members
  (`blendRamp`, `evaluateColorRamp`, `evaluateCurveMappingF`, `Integrator`) are `Any`.

| Addon | Variant |
| --- | --- |
| `api_never_none` | embedded and DNA pointers, pointers and function results Blender always sets, the context's preferences and window manager; unannotated callback overrides of `Menu`, `Header`, `UIList`, `RenderEngine`, `KeyingSetInfo` and `AssetShelf`, and their callers |
| `api_type_tags` | the Type tag of refined subclasses (value form): `Node.type`, interface `item_type`, boid rules, line style modifiers (the tag on the base), spreadsheet table IDs, viewer path elements, project variables; the tag views of `Object` (`data`, `pose`) and `FluidModifier` (sibling form); a Grease Pencil layer tree node as a layer or a layer group; the `BlendDataCurves.new` overloads; action strips |
| `api_stub_gaps` | class bases and Python `__init__`, iteration and context-manager protocols, version tuples, `bl_rna`, module members, `Operator.description` returning None; the stub-generator gaps: `BMElemSeq[T]`, `bpy.data[name, lib]`, context store members, `libraries.load` / `temp_data`, positional Freestyle and render engine callbacks (overrides in `__init__.py`), dynamic enums, `keyconfig_set` / `target_set_value`; Freestyle's unary function `__call__`, `Noise`, `BoundingBox`, generators and `Operators.create` |
| `api_setters` | sequences assigned to math and array properties and to an array slice, the read types (also in the editor's hover), wrong element types |
| `api_c_modules` | the private C modules import, partially typed; `_freestyle`'s classes and functions are the `freestyle` ones |

Only the stubs of Blender main built from the fork state these facts (both generators read the RNA flag and the declared
tags); 5.2's stubs fail these markers, and fake-bpy-module leaves out the private tag views and the C modules (named
exceptions in spec #75). fake-bpy-module also misses the stub-generator gaps it does not read from the docstrings
(`BMElemSeq` attributes, the `(name, None)` key, the two context managers, the positional Freestyle methods; named
exceptions in spec #95). fake-bpy-module keeps `| None` on a writable never-None pointer (`KeyConfigurations.active`,
`MovieTrackingObjects.active`), and its own mod file retypes `Material.node_tree` / `World.node_tree` as
`ShaderNodeTree | None` (named exceptions in spec #132). The Freestyle gaps fail on 5.2 and on fake-bpy-module,
which gives Freestyle's classes no bases (`TrueUP1D` is no `UnaryPredicate1D`, so `pyDensityAnisotropyF1D` has no
`__call__`; a named exception in spec #132). The pointer, caller, Type tag, `api_stub_gaps`, `api_setters` and `api_c_modules` markers are
guards (`bare-ok`): they hold without the checker. The callback overrides (and `api_stub_gaps`' unannotated
`description`) need the checker's inheritance typing.
