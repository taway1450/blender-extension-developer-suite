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
- **A DNA pointer can be None:** `ToolSettings.sculpt` (allocated on first use), `Object.pose` (armatures only),
  every `animation_data` (until `animation_data_create()`). They stay `| None`.
- **Blender always passes a context** to `Menu.poll` / `draw`, `Header.draw`, `UIList.draw_item` / `draw_filter` /
  `filter_items`, `AssetShelf.poll` / `draw_context_menu`, `FileHandler.poll_drop`, `KeyingSetInfo.poll` /
  `iterator` / `generate` and `RenderEngine.draw` / `view_update` / `view_pause` / `view_resume`: the C caller
  passes the live `bContext`. `RenderEngine.view_draw` gets None when a viewport is drawn off-screen (Viewport
  Render, `GPUOffScreen.draw_view3d`), so it stays `Context | None`.
- **A struct is refined to the subclass its Type tag names** (`rna_Modifier_refine`, `rna_Space_refine`, ... in C,
  which introspection cannot read): a modifier of type `'SUBSURF'` is a `SubsurfModifier`, a space of type
  `'VIEW_3D'` a `SpaceView3D`. Blender's fork probes them when it writes the API docs (`sphinx_doc_gen_type_tags.py`
  makes an instance of each tag value) and each subclass declares its tag: `SubsurfModifier.type:
  Literal['SUBSURF']` (modifiers, shader effects, constraints, F-Curve modifiers, lights, light probes, textures,
  attributes by `data_type`, strips and their modifiers, spaces, RNA properties); built-in node trees, nodes and
  sockets declare their `bl_idname`, sockets their `type` (many socket classes share `'VALUE'`).
- **Some tags decide another attribute's type** without a refined struct: an object of type `'MESH'` has a `Mesh`
  as its data (`'FONT'` a `TextCurve`, `'SURFACE'` a `SurfaceCurve`, `'EMPTY'` no data or the `Image` it
  displays), a fluid modifier of type `'DOMAIN'` has domain settings and no flow or effector settings. The stubs
  declare a private tag view per value, `_Object_MESH(Object)` with `type: Literal['MESH']` and `data: Mesh`, and
  `_FluidModifier_DOMAIN` etc.
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
- **A math or array property takes any sequence** of the right length (`pyrna_py_to_array`): `ob.location = (1, 1,
  1)`, `ob.matrix_world = rows`, `ob.lock_location = (True, False, True)`, and an array's slice any iterable of its
  elements (`image.pixels[:] = buffer`). Reading it still gives the `Vector` / `Color` / `Euler` / `Quaternion` /
  `Matrix` or the `bpy_prop_array`, and an element of the wrong type raises `TypeError`. The stubs write a writable one
  as a property whose setter takes `Sequence[float]` (`Sequence[Sequence[float]]` for a `Matrix`, `Sequence[T]` for a
  `bpy_prop_array[T]`); a `bpy_prop_array` is itself a `Sequence`.

| Addon | Variant |
| --- | --- |
| `api_never_none` | embedded and DNA pointers; unannotated callback overrides of `Menu`, `Header`, `UIList` and `RenderEngine`, and their callers |
| `api_type_tags` | the Type tag of refined subclasses (value form), the tag views of `Object` and `FluidModifier` (sibling form), action strips |
| `api_stub_gaps` | class bases and Python `__init__`, iteration and context-manager protocols, version tuples, `bl_rna`, module members, `Operator.description` returning None |
| `api_setters` | sequences assigned to math and array properties and to an array slice, the read types (also in the editor's hover), wrong element types |

Only the stubs of Blender main built from the fork state these facts (both generators read the RNA flag and the
declared tags); 5.2's stubs fail these markers, and fake-bpy-module leaves out the private tag views (named exceptions
in spec #75). The pointer, caller, Type tag, `api_stub_gaps` and `api_setters` markers are guards (`bare-ok`): they
hold without the checker. The callback overrides (and `api_stub_gaps`' unannotated `description`) need the checker's
inheritance typing.
