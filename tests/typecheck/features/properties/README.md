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
| `props_styles` | plain annotations, `from __future__ import annotations`, inherited and mixin annotations, the old `x = IntProperty()` form (ignored by Blender) |
| `props_callbacks` | `update` / `get` / `set` / `poll` / `items` callbacks: `self` is the declaring class |
| `props_defaults` | arguments Blender rejects at registration (fails to load on purpose) |
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
NodeTree, Gizmo. Ignored on: Panel, Menu, Header, KeyingSetInfo, RenderEngine, FileHandler, AssetShelf.
Registered properties work on every ID type and on Bone, EditBone, PoseBone, Node, NodeSocket, ViewLayer, Strip;
not on Area, Modifier, Window, Preferences, SpaceView3D or Context. After registration the class attribute is
gone (`AttributeError`).

**Rules:** `blender-unsupported-property-host`, `blender-legacy-property`, `blender-invalid-property` (defaults
that do not fit, `set` without `get`), `blender-unsupported-property-target`. Wrong callback signatures are
`invalid-argument-type`.
