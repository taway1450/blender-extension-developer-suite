# properties

**The checker must:** give an annotated property (`count: IntProperty()`) on a property host the type Blender
gives the attribute at runtime, and do the same for properties assigned to Blender's classes
(`bpy.types.Scene.count = IntProperty()`). The annotation is not a type to the checker; reading it as one is
what stock ty reports as `invalid-type-form`.

| Addon | Variant |
| --- | --- |
| `generated/props_scalar` | Int / Float / Bool / String with their options |
| `generated/props_vector` | every FloatVector subtype and size (see below), Int / Bool vectors, matrices |
| `generated/props_enum` | static items (`Literal`), `ENUM_FLAG` (`set[Literal]`), dynamic items (`str`) |
| `generated/props_pointer` | pointers to PropertyGroups and to every ID type, collections |
| `props_hosts` | the classes that take annotations, and those that silently ignore them |
| `props_styles` | plain annotations, `from __future__ import annotations`, inherited and mixin annotations, the old `x = IntProperty()` form (ignored by Blender), a `.pyi` the add-on ships (no rules there) |
| `props_callbacks` | `update` / `get` / `set` / `poll` / `items` callbacks: `self` is the declaring class |
| `props_defaults` | arguments Blender rejects at registration (fails to load on purpose) |
| `props_data_blocks` | the Property hosts that reject a pointer to a data-block, and two that accept one |
| `props_registered` | properties assigned to Blender's classes: which classes accept them |

**Runtime facts (Blender 5.4):**

| Property | Value type |
| --- | --- |
| FloatVector `COLOR` / `COLOR_GAMMA`, size 3 | `Color` (other sizes: array) |
| FloatVector `TRANSLATION` / `DIRECTION` / `VELOCITY` / `ACCELERATION` / `XYZ` / `XYZ_LENGTH` / `COORDINATES`, size 2-4 | `Vector` |
| FloatVector `MATRIX`, size (3, 3), (4, 4) or 16 | `Matrix` |
| FloatVector `EULER` size 3, `QUATERNION` size 4 | `Euler`, `Quaternion` (the size decides) |
| FloatVector other subtypes; other multi-dimensional sizes | `bpy_prop_array[float]`, nested arrays |
| `PointerProperty` to an ID type | `T \| None`; to a PropertyGroup: `T`, read-only |
| `CollectionProperty` | `bpy_prop_collection_idprop[T]` |

Hosts that take annotations: PropertyGroup, Operator, Macro, AddonPreferences, UIList, Node, NodeSocket,
NodeTree, NodeTreeInterfaceSocket, KeyConfigPreferences, Gizmo. Ignored on: Panel, Menu, Header, KeyingSetInfo, RenderEngine, FileHandler, AssetShelf.
Registered properties work on every ID type and on Bone, EditBone, PoseBone, Node, NodeSocket, ViewLayer, Strip;
not on Area, Modifier, Window, Preferences, SpaceView3D or Context. After registration an annotated property's
class attribute is gone (`AttributeError`), while a registered property's class attribute stays its property
declaration (`bpy.types.Scene.reg_int` is a `_PropertyDeferred`); the checker leaves class reads of both unresolved. When a class
and its base both register a name, the most-derived class wins on its instances, whichever was registered first.
`StringProperty(subtype="BYTE_STRING")` gives `bytes`, and `options={"READ_ONLY"}` or `get=` without `set=` makes any
property read-only. UIList does not take Registered properties: its class lacks the metaclass that registers them.

**Rules:** `blender-unsupported-property-host`, `blender-legacy-property`, `blender-invalid-property` (defaults that
do not fit, `set` without `get`, names starting with `_`, `size` outside 1-32 or with more than 3 dimensions, more
than 32 `ENUM_FLAG` items, a `str` default with function items, a data-block pointer on an Operator, Macro, Gizmo,
UIList, AddonPreferences or KeyConfigPreferences; checked at every `bpy.props` call, also in lambdas, comprehensions
and annotations outside a class body),
`blender-unsupported-property-target`. Wrong callback signatures and a `type=` of the wrong kind are
`invalid-argument-type` from the stubs.
