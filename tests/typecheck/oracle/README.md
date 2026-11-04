# Oracle baseline

Deltas merged into the bpy stubs of each generator before an addon's own reference stubs, in `mise run check:oracle`
(see `scripts/check_oracle.py`). They state what the typechecker assumes about the bpy stubs, so that the reference
stubs in `features/*/*/_expected/` can be the same for both generators. Each entry is something the stub generator
gets wrong or leaves out compared with Blender at runtime:

| Generator | Delta | Why |
| --- | --- | --- |
| builtin | `bpy_prop_collection_idprop` is generic, `add()` returns the item type | The runtime type of a `CollectionProperty` value; the item type is the `type=` PropertyGroup. |
| fake-bpy-module | `bpy_prop_array` is generic with typed `__getitem__`/`__iter__` | The stubs already write `bpy_prop_array[int]`, but the class takes no type parameter. |
