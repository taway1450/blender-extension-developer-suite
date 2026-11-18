# Detecting and reporting the property rules

Research note, 2026-11-06, for [issue #27](https://github.com/taway1450/blender-extension-developer-suite/issues/27)
(map #21). Trimmed on 2026-11-18 to the rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings.

The question: for `blender-unsupported-property-host`, `blender-legacy-property`, `blender-invalid-property` and
`blender-unsupported-property-target`, which data decides each and where it is reported. Which "default does not
fit" cases exist, and which can the checker decide from literals?

Conventions:

- `blender/` is Blender's source (`main`, read on 2026-11-06).
- **Runtime-checked** facts come from one probe script run in Blender main (5.4.0 Alpha, `9273a5a99cb0`, built
  2026-11-02) in background mode: it registers one class or assignment per case and records the exception.
  Everything else comes from reading the source.

What main does differently from the original: `blender-invalid-property` runs at every `bpy.props` call where it is
written (module constants and wrappers included), so a broken shared declaration is reported once, where it is
defined; only the data-block check needs the owner. A data-block pointer on an Operator or Macro is its own rule,
`blender-invalid-operator-property` (section 1.3). See the module doc of `rules.rs` in
`ty-blender/ruff-blender/crates/ty_python_semantic/src/types/dedicated/blender/`.

---

## 1. The runtime model (facts)

### 1.1 When Blender validates a declaration

- `IntProperty(...)` in a class body only stores its keywords: with no struct to define on, the function returns
  a `_PropertyDeferred` (`bpy_props.cc:3240-3275`). Nothing is checked there.
- **Annotated:** `register_class` reads the class's `__annotations__` through `typing.get_type_hints`
  (`bpy_rna.cc:9540-9594`) and calls each deferred function with the struct (`deferred_register_prop`,
  `bpy_rna.cc:9454-9535`). Any error becomes `ValueError: bpy_struct "X" registration error: 'name' IntProperty
  could not register (see previous error)` (`bpy_rna.cc:9519-9532`), so `register()` fails.
- Hosts: `pyrna_deferred_register_class` returns at once when the struct cannot hold ID properties
  (`RNA_struct_system_idprops_register_check`, `bpy_rna.cc:9658-9662`, `rna_access.cc:813-816`). That is why a
  Panel's annotations are ignored without an error, and why a bad default on a Panel raises nothing either. So
  `blender-invalid-property` is skipped on Ignored hosts: Blender never evaluates the declaration there.
- **Registered:** `bpy.types.Scene.x = IntProperty(...)` goes through the metaclass's `__setattr__`
  (`pyrna_struct_meta_idprop_setattro`, `bpy_rna.cc:5101-5163`), which calls `deferred_register_prop` right away.
  So a bad registered declaration raises **at the assignment line** (runtime-checked: an enum default `"C"` on
  `Scene` raises the same `ValueError`).
- **Legacy:** only `__annotations__` is read; a class-body `legacy = IntProperty()` is never looked at. It stays a
  class attribute holding the `_PropertyDeferred`, no RNA property is made, and no warning is printed
  (runtime-checked: `"legacy" in cls.bl_rna.properties` is `False`).

### 1.2 Which classes accept a Registered property

- Only classes created with the metaclass `bpy_struct_meta_idprop` (or a subclass of it, such as `_bpy_types`'s
  `_RNAMetaPropGroup`) route `setattr` to `deferred_register_prop`. The metaclass is chosen when the Python class
  is made, from `RNA_struct_system_idprops_check(srna)` (`bpy_rna.cc:8708-8716`). Any other class takes a plain
  `type.__setattr__`: no error, no property. `bpy.types.Area.x = IntProperty()` stores the `_PropertyDeferred` as
  a plain class attribute (`bpy_rna.cc:5118-5131`).
- Runtime-checked: besides the ID types, the classes with that metaclass are `Bone`, `EditBone`, `PoseBone`,
  `BoneCollection`, `ViewLayer`, `Strip` and its subclasses, `TimelineMarker`, `View3DShading`,
  `IDPropertyWrapPtr`, `OperatorProperties`, `GizmoProperties`, `GizmoGroupProperties`, `KeyConfigPreferences`,
  and the `Nodes/SceneCompositor/SequencerCompositor*Properties[Empty]` structs. `_bpy_types.py:1160, 1503-1558`
  gives `_RNAMetaPropGroup` to `PropertyGroup`, `NodeTree`, `Node`, `NodeSocket` and `NodeTreeInterfaceSocket`.
- Runtime-checked "silent plain attribute": `Area`, `Modifier`, `Window`, `Preferences`, `SpaceView3D`,
  `Context`, and also `Operator`, `Panel` and `AddonPreferences`.
- The RNA side lists the same roots: `RNA_def_struct_system_idprops_func` is called for `PropertyGroup`, `ID`,
  `IDPropertyWrapPtr`, `Bone`, `EditBone`, `BoneCollection`, `ViewLayer`, the nodes-modifier properties,
  `NodeSocket`, `NodeTreeInterfaceSocket`, `Node`, `PoseBone`, the compositor effect / modifier properties,
  `Strip`, `View3DShading`, `TimelineMarker`, `UIList`, `AddonPreferences`, `OperatorProperties`,
  `KeyConfigPreferences`, `GizmoProperties` and `GizmoGroupProperties` (`makesrna/intern/*.cc`, grep). `UIList`
  and `AddonPreferences` have ID properties for their annotations, but their Python classes do not get the
  metaclass, so neither accepts a Registered property.

### 1.3 Data-block pointers

- `deferred_register_prop` rejects a `PointerProperty` / `CollectionProperty` whose type can hold data-blocks when
  the owner forbids data-block ID properties (`bpy_rna.cc:9483-9503`, `RNA_struct_idprops_datablock_allowed`,
  `rna_access.cc:803-806`).
- Runtime-checked: `p: PointerProperty(type=Object)` **fails on `AddonPreferences`** and registers on
  `PropertyGroup`. Registered on `OperatorProperties`, `GizmoProperties`, `GizmoGroupProperties`,
  `KeyConfigPreferences` and `IDPropertyWrapPtr`, it fails; on every other accepting struct it works.
- On an Operator the original probe saw it register. Main treats it as refused
  (`blender-invalid-operator-property`): Blender drops that property and every property after it.

---

## 2. "Default does not fit" and the other registration errors

All rows raise at registration (Annotated) or at the assignment (Registered). "Literal" means the checker reads it
from syntax (string / number literals, set, tuple and list displays, a constant hop for `items=`), or from an
inferred literal or fixed-length tuple type. Anything else stays silent.

| Case | Blender's check | Runtime-checked | From literals |
| --- | --- | --- | --- |
| Enum default `str` not an identifier | `bpy_props.cc:2563-2570, 2610-2617` | yes | yes, with static items |
| Enum default `int` not an item number | same, `:2618-2621`; a 3-tuple's number is its **index, counting `None` separators** (`:2559-2561`) | yes: `[A, None, B]` takes `default=2`, rejects `1` | yes, needs numbers kept |
| Enum default a `set` without `ENUM_FLAG` | must be `str` or `int`, `:2508-2518` | yes | yes, set display |
| `ENUM_FLAG` default not a `set` | `:2499-2505` | yes | yes |
| `ENUM_FLAG` default with unknown members | `:2553-2556, 2600-2607` | yes | yes, set display of strings |
| `ENUM_FLAG` with more than 32 items | `:2493-2498` | yes | yes |
| Enum default `str` with function `items` | `:5296-5301` | yes; an `int` default is accepted | yes when `items=` is a lambda or a `def` |
| Enum default with empty static items | not found, `:2610` | yes | yes |
| Malformed static enum item (not a 3-5 tuple of strings) | `:2588-2595` | yes | yes |
| Vector default length differs from `size` (default `size` is 3) | `PyC_AsArray_FAST`, `py_capi_utils.cc:54-60` | yes (also `default=(1.0, 2.0)` with no `size`) | yes |
| Matrix default shape differs from `size=(r, c)` | `PyC_AsArray_Multi_FAST_impl`, `py_capi_utils.cc:220-228` | yes | yes, nested displays |
| Scalar default for a vector | not a sequence | yes | yes |
| `size` outside 1-32, or more than 3 dimensions | `bpy_props.cc:536-590` | yes (`33`, `0`, `(2, 2, 2, 2)`) | yes, int or tuple literal |
| `set=` without `get=` | `bpy_props.cc:2800-2806` and the 7 other kinds (`:2855-3181`); only Bool returns at once, the others leave the error set and fail with `SystemError` | yes, all eight kinds | yes: `set=` present and not `None`, `get=` missing or `None` |
| Name starts with `_` | `bpy_rna.cc:9473-9481` | yes | yes (annotation target, attribute or `setattr` string) |
| `PointerProperty` `type=` not an ID / PropertyGroup; `CollectionProperty` `type=` not a PropertyGroup | `bpy_props.cc:5517-5520, 5670-5672` | yes (`type=Operator`; `CollectionProperty(type=Object)`) | yes, from the inferred `type=` |
| ID pointer on a struct without data-block ID properties | `bpy_rna.cc:9486-9501` | yes (`AddonPreferences`; registered on `OperatorProperties` etc.) | yes, needs the owner's list |
| Unknown `subtype=` / `unit=` / `options=` identifier | `pyrna_enum_value_parse_string` | yes (`"BOGUS"`, ValueError) | yes, string literals |

Accepted, so **not** a rule (runtime-checked): `min > max`, `default` outside `min`/`max`, soft limits outside
hard limits, a `StringProperty` default longer than `maxlen`, explicit `ENUM_FLAG` numbers that are not powers of
two, and an empty set as an `ENUM_FLAG` default. The only `min > max` check is `#ifndef NDEBUG` in
`rna_define.cc:1757-1762`.

Overlap with the stubs: what a stub already rejects as `invalid-argument-type` (`IntProperty(default=1.5)`, wrong
callback arities, an unknown `subtype=` literal on fake-bpy-module) is left to it, so one line does not get two
rules. `size=` is `int | Sequence[int]` in both stubs, which cannot express 1-32, so the checker reports it. An
unreadable `size=` (a name, a call) is not a Blender error: silent.

---

## 3. Design rationale

### 3.1 Not the annotation takeover

Reporting `blender-invalid-property` from the annotation takeover would fire while the class body is inferred (it
cannot ask whether the class is an Ignored host without a cycle), and it never sees Registered properties. A
per-file pass sees both origins and decides once. A post-inference hook after `check_static_class_definitions`
would also work, but costs a new upstream line for nothing the per-file pass lacks; the attribute-write check sees
only `owner.x = ...`, not `setattr(...)`.

### 3.2 What each rule reads

- **Host:** each member of an Ignored host's own body that is a property declaration is reported on its target
  name. Mixins are not reported: an annotation on a plain class is right for a host and only wasted on a Panel,
  and the Panel's subclass does not spell it.
- **Legacy:** each class-body `x = <bpy.props call>` in a class with a `bpy.types` base (host or not). Plain
  classes are skipped: a holder class of deferred properties is legitimate there (e.g. for
  `setattr(Scene, name, Holder.x)`), and a false positive costs more than a miss.
- **Target:** a Registered property is accepted when its owner derives from an allowlist of roots (section 1.2). An
  allowlist errs towards a missed warning when a Blender version adds a struct; a denylist would err towards false
  positives. An unaccepted Registered property does not type the instance read (`area.reg_area`): at runtime the
  read returns the `_PropertyDeferred` class attribute.
- **Each line gets one rule:** a declaration that Blender never evaluates (on an Ignored host, in the legacy form,
  or on an unsupported target) is not checked for `blender-invalid-property`.

### 3.3 Levels

`blender-invalid-property` is an error (registration fails). The host, legacy and target rules are warnings: the
code runs, the property is silently missing, and a later read is already `unresolved-attribute`.
