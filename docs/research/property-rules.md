# Detecting and reporting the four property rules

Research note, 2026-11-06, for [issue #27](https://github.com/taway1450/blender-extension-developer-suite/issues/27)
under the map [#21](https://github.com/taway1450/blender-extension-developer-suite/issues/21). Binding earlier
decisions: [#6](https://github.com/taway1450/blender-extension-developer-suite/issues/6) (add-on lints reported
through `InferContext::report_lint` from a query merged in `check_types`), [#7](https://github.com/taway1450/blender-extension-developer-suite/issues/7)
(`items=` / `options=` read from syntax, keywords only), [#10](https://github.com/taway1450/blender-extension-developer-suite/issues/10)
(`property_declaration(definition)`, the off-host rule) and [#25](https://github.com/taway1450/blender-extension-developer-suite/issues/25)
(it hands reporting of bad `size=` / `subtype=` to this ticket and names `blender-legacy-property` as the
`props_styles` leftover).

The question: for `blender-unsupported-property-host`, `blender-legacy-property`, `blender-invalid-property` and
`blender-unsupported-property-target`, which data decides each, where it is reported, and which line carries
it. Which "default does not fit" cases exist, and which can the checker decide from literals?

Conventions:

- `ruff-blender/` is `ty-blender/ruff-blender/` (branch `blender`); `glue/` is
  `ruff-blender/crates/ty_python_semantic/src/types/dedicated/blender/`. `blender/` is Blender's source at
  `.cache/blender-src/main`. Test paths are relative to this repo.
- **Runtime-checked** facts come from one probe script run in the cached Blender main build (5.4.0 Alpha,
  `9273a5a99cb0`, built 2026-11-02) in background mode: it registers one class or assignment per case and
  records the exception. Everything else comes from reading the source.
- My own recommendations are marked **Recommendation**. Nothing was built.

---

## 1. Answer in brief

| Rule | Decided by | Reported from | Anchor |
| --- | --- | --- | --- |
| `blender-unsupported-property-host` | `property_declaration` of a member in the class's own body + `is_ignored_host(class)` (`member.rs:129-148`) | the per-file query | the annotated target name (`value`) |
| `blender-legacy-property` | a plain class-body assignment `x = <bpy.props call>` on a class with a `bpy.types` base; callee from the class scope's inference | the per-file query | the assignment target (`legacy`) |
| `blender-invalid-property` | a new `property_problems(call)` over the declaration's syntax and argument types, for both origins | the per-file query | the offending keyword argument (`default=...`, `set=...`, `size=...`) |
| `blender-unsupported-property-target` | the Add-on index's `RegisteredProperty`, with a new `accepted` bit from an allowlist of `bpy.types` roots | the per-file query | the owner expression (`bpy.types.Area`) |

1. **One reporting site.** **Recommendation:** generalise the existing `addon_diagnostics` query
   (`glue/lints.rs:73-97`, merged by the existing hook at `types.rs:261`, before `check_suppressions`) into a
   per-file query that also runs the four property rules on every first-party file. That adds **no line to an
   upstream file**: the merge hook, `register_lints` (`diagnostic.rs:212`) and the suppression path are all in
   place. Every rule is about a declaration that sits in that same file, so `# ty: ignore[...]` on the line works
   as #6 describes.
2. **Not the annotation takeover.** Reporting `blender-invalid-property` from `type_expression/blender.rs` would be
   fork-only too, but it fires while the class body is inferred (it cannot ask whether the class is an Ignored host
   without a cycle), and it never sees Registered properties. The per-file pass sees both origins and decides
   once, which is the principle of `member.rs`.
3. **min / max are not a rule.** Blender accepts `min > max`, a default outside `min`/`max` and soft limits
   outside hard ones (runtime-checked). The only `min > max` check is `#ifndef NDEBUG` in `rna_define.cc:1757-1762`.
4. **What Blender rejects at registration** (all runtime-checked, all decidable from literals): enum defaults not
   among the items or numbers, wrong default kind for `ENUM_FLAG`, a `str` default with function `items`, vector
   defaults of the wrong length or shape, `size` outside 1-32 or with more than 3 dimensions, `set=` without
   `get=` (all eight kinds), a name starting with `_`, `PointerProperty` / `CollectionProperty` with a `type=` of
   the wrong kind, an ID pointer on a struct that forbids data-block properties (e.g. `AddonPreferences`), and
   unknown `subtype=` / `unit=` / `options=` identifiers. Section 4 lists them with their sources.
5. **Unsupported targets are silent at runtime.** `bpy.types.Area.x = IntProperty()` stores the
   `_PropertyDeferred` as a plain class attribute (`bpy_rna.cc:5118-5131`, metaclass choice at
   `bpy_rna.cc:8708-8716`). Today the index still treats `area.x` as an `int`; it should not (section 5.4).

---

## 2. The runtime model (facts)

### 2.1 When Blender validates a declaration

- `IntProperty(...)` in a class body only stores its keywords: with no struct to define on, the function returns
  a `_PropertyDeferred` (`bpy_props.cc:3240-3275`). Nothing is checked there.
- **Annotated:** `register_class` reads the class's `__annotations__` through `typing.get_type_hints`
  (`bpy_rna.cc:9540-9594`) and calls each deferred function with the struct (`deferred_register_prop`,
  `bpy_rna.cc:9454-9535`). Any error becomes `ValueError: bpy_struct "X" registration error: 'name' IntProperty
  could not register (see previous error)` (`bpy_rna.cc:9519-9532`), so `register()` fails.
- Hosts: `pyrna_deferred_register_class` returns at once when the struct cannot hold ID properties
  (`RNA_struct_system_idprops_register_check`, `bpy_rna.cc:9658-9662`, `rna_access.cc:813-816`). That is why a
  Panel's annotations are ignored without an error, and why a bad default on a Panel raises nothing either.
- **Registered:** `bpy.types.Scene.x = IntProperty(...)` goes through the metaclass's `__setattr__`
  (`pyrna_struct_meta_idprop_setattro`, `bpy_rna.cc:5101-5163`), which calls `deferred_register_prop` right away.
  So a bad registered declaration raises **at the assignment line** (runtime-checked: an enum default `"C"` on
  `Scene` raises the same `ValueError`).
- **Legacy:** only `__annotations__` is read; a class-body `legacy = IntProperty()` is never looked at. It stays a
  class attribute holding the `_PropertyDeferred`, no RNA property is made, and no warning is printed
  (runtime-checked: `"legacy" in cls.bl_rna.properties` is `False`).

### 2.2 Which classes accept a Registered property

- Only classes created with the metaclass `bpy_struct_meta_idprop` (or a subclass of it, such as `_bpy_types`'s
  `_RNAMetaPropGroup`) route `setattr` to `deferred_register_prop`. The metaclass is chosen when the Python class
  is made, from `RNA_struct_system_idprops_check(srna)` (`bpy_rna.cc:8708-8716`). Any other class takes a plain
  `type.__setattr__`: no error, no property.
- Runtime-checked: `bpy.types` has 105 classes with that exact metaclass, 59 of them ID types. The 46 others are
  `Bone`, `EditBone`, `PoseBone`, `BoneCollection`, `ViewLayer`, `Strip` and its 27 subclasses, `TimelineMarker`,
  `View3DShading`, `IDPropertyWrapPtr`, `OperatorProperties`, `GizmoProperties`, `GizmoGroupProperties`,
  `KeyConfigPreferences`, and the `Nodes/SceneCompositor/SequencerCompositor*Properties[Empty]` structs.
  `_bpy_types.py:1160, 1503-1558` gives `_RNAMetaPropGroup` to `PropertyGroup`, `NodeTree`, `Node`,
  `NodeSocket` and `NodeTreeInterfaceSocket`.
- Runtime-checked "silent plain attribute": `Area`, `Modifier`, `Window`, `Preferences`, `SpaceView3D`,
  `Context` (the `props_registered` markers), and also `Operator`, `Panel` and `AddonPreferences`.
- The RNA side lists the same roots: `RNA_def_struct_system_idprops_func` is called for `PropertyGroup`, `ID`,
  `IDPropertyWrapPtr`, `Bone`, `EditBone`, `BoneCollection`, `ViewLayer`, the nodes-modifier properties,
  `NodeSocket`, `NodeTreeInterfaceSocket`, `Node`, `PoseBone`, the compositor effect / modifier properties,
  `Strip`, `View3DShading`, `TimelineMarker`, `UIList`, `AddonPreferences`, `OperatorProperties`,
  `KeyConfigPreferences`, `GizmoProperties` and `GizmoGroupProperties` (`makesrna/intern/*.cc`, grep). `UIList`
  and `AddonPreferences` have ID properties for their annotations, but their Python classes do not get the
  metaclass (AddonPreferences runtime-checked; **UIList not checked**).

### 2.3 Data-block pointers

- `deferred_register_prop` rejects a `PointerProperty` / `CollectionProperty` whose type can hold data-blocks when
  the owner forbids data-block ID properties (`bpy_rna.cc:9483-9503`, `RNA_struct_idprops_datablock_allowed`,
  `rna_access.cc:803-806`).
- Runtime-checked: `p: PointerProperty(type=Object)` **fails on `AddonPreferences`** and works on `PropertyGroup`
  and on `Operator`. Registered on `OperatorProperties`, `GizmoProperties`, `GizmoGroupProperties`,
  `KeyConfigPreferences` and `IDPropertyWrapPtr`, it fails; on every other accepting struct it works.

---

## 3. The data the glue already has

- `PropertyDeclaration` (`glue/properties.rs:296-309`) keeps the kind, static enum identifiers, `ENUM_FLAG`,
  `READ_ONLY`, `BYTE_STRING` and the `type=` target. It keeps no ranges and no other arguments.
- `property_declaration(definition)` (`properties.rs:532-566`) finds the call of an annotated class member (also
  quoted) and reads the callee and argument types from the definition's own inference.
- `annotated_property(class, name)` and `is_ignored_host(class)` (`member.rs:113-148`) decide host-ness by the
  `bpy.types` bases, with plain mixins kept (the off-host rule of #10).
- `file_facts(file)` (`index.rs:118-166`) finds `owner.name = call` and `setattr(owner, "name", call)` anywhere
  in a file, resolves owner and callee without inference, and keeps `RegisteredProperty { owner, name,
  declaration }`, for **any** `bpy.types` owner (`is_bpy_types_class`, `index.rs:142-144`).
- `static_enum_items` (`properties.rs:585-631`) keeps only identifiers, not item numbers, and returns `None` both
  for function items and for unreadable constants.

---

## 4. "Default does not fit" and the other registration errors

All rows raise at registration (Annotated) or at the assignment (Registered). "Literal" means the checker reads it
from syntax (string / number literals, set, tuple and list displays, the existing one-constant hop for `items=`),
or from an inferred literal or fixed-length tuple type. Anything else stays silent.

| Case | Blender's check | Runtime-checked | From literals |
| --- | --- | --- | --- |
| Enum default `str` not an identifier | `bpy_props.cc:2563-2570, 2610-2617` | yes (`props_defaults`) | yes, with static items |
| Enum default `int` not an item number | same, `:2618-2621`; a 3-tuple's number is its **index, counting `None` separators** (`:2559-2561`) | yes: `[A, None, B]` takes `default=2`, rejects `1` | yes, needs numbers kept |
| Enum default a `set` without `ENUM_FLAG` | must be `str` or `int`, `:2508-2518` | yes (`props_defaults`) | yes, set display |
| `ENUM_FLAG` default not a `set` | `:2499-2505` | yes | yes |
| `ENUM_FLAG` default with unknown members | `:2553-2556, 2600-2607` | yes | yes, set display of strings |
| `ENUM_FLAG` with more than 32 items | `:2493-2498` | yes | yes |
| Enum default `str` with function `items` | `:5296-5301` | yes; an `int` default is accepted | yes when `items=` is a lambda or a `def` |
| Enum default with empty static items | not found, `:2610` | yes | yes |
| Malformed static enum item (not a 3-5 tuple of strings) | `:2588-2595` | yes | yes |
| Vector default length differs from `size` (default `size` is 3) | `PyC_AsArray_FAST`, `py_capi_utils.cc:54-60` | yes (`props_defaults`, and `default=(1.0, 2.0)` with no `size`) | yes |
| Matrix default shape differs from `size=(r, c)` | `PyC_AsArray_Multi_FAST_impl`, `py_capi_utils.cc:220-228` | yes (`matrix_shape`) | yes, nested displays |
| Scalar default for a vector | not a sequence | yes | yes |
| `size` outside 1-32, or more than 3 dimensions | `bpy_props.cc:536-590` | yes (`33`, `0`, `(2, 2, 2, 2)`) | yes, int or tuple literal |
| `set=` without `get=` | `bpy_props.cc:2800-2806` and the 7 other kinds (`:2855-3181`); only Bool returns at once, the others leave the error set and fail with `SystemError` | yes, all eight kinds | yes: `set=` present and not `None`, `get=` missing or `None` |
| Name starts with `_` | `bpy_rna.cc:9473-9481` | yes | yes (annotation target, attribute or `setattr` string) |
| `PointerProperty` `type=` not an ID / PropertyGroup; `CollectionProperty` `type=` not a PropertyGroup | `bpy_props.cc:5517-5520, 5670-5672` | yes (`type=Operator`; `CollectionProperty(type=Object)`) | yes, from the inferred `type=` (existing `target_class`) |
| ID pointer on a struct without data-block ID properties | `bpy_rna.cc:9486-9501` | yes (`AddonPreferences`; registered on `OperatorProperties` etc.) | yes, needs the owner's list |
| Unknown `subtype=` / `unit=` / `options=` identifier | `pyrna_enum_value_parse_string` | yes (`"BOGUS"`, ValueError) | yes, string literals |

Accepted, so **not** a rule (runtime-checked): `min > max`, `default` outside `min`/`max`, soft limits outside
hard limits, a `StringProperty` default longer than `maxlen`, explicit `ENUM_FLAG` numbers that are not powers of
two, and an empty set as an `ENUM_FLAG` default.

Overlap with the stubs:

- `IntProperty(default=1.5)` and wrong callback arities are already `invalid-argument-type` from both stubs, and
  `props_defaults` marks them so. The glue must not report them again.
- `subtype=` / `unit=` / `options=`: fake-bpy-module types them as `Literal` enums
  (`rna_enums.PropertySubtypeNumberArrayItems`, `set[...PropertyFlagItems]`), so an unknown literal is already
  `invalid-argument-type` there; builtin types them as `str` / `set[str]`. **Recommendation:** fix the builtin
  generator to emit the same `Literal` types, and let `invalid-argument-type` carry these on both generators.
  If the glue reported them as well, fake-bpy-module would get two rules on one line.
- `size=` is `int | Sequence[int]` in both stubs, which cannot express 1-32. The glue reports it (the part #25
  handed over). An unreadable `size=` (a name, a call) is not a Blender error: silent, and #25's `Any` value type.
- The existing failure `props_defaults/__init__.py | invalid-argument-type | matrix: FloatVectorProperty(size=(2, 2),
  default=((1.0, 0.0), (0.0, 1.0)))` (both generators) is a stub bug: both type `default` as `Sequence[float]`.
  **Recommendation:** the generators type vector defaults as `Sequence[float] | Sequence[Sequence[float]]` (and
  int / bool alike), and the glue decides the shape. A rewritten callee in the takeover (#25) would cover only
  Annotated properties.

---

## 5. Recommended design

### 5.1 Lints

- Four `declare_lint!`s next to the existing two in `glue/lints.rs`, docs in `resources/lint_docs/blender-*.md`,
  registered in the existing `blender::register_lints`. Run `cargo dev generate-all` and commit `rules.md` and
  `ty.schema.json` (#6).
- **Recommendation for levels:** `blender-invalid-property` is `Error` (registration fails).
  `blender-unsupported-property-host`, `blender-legacy-property` and `blender-unsupported-property-target` are
  `Warning`: the code runs, the property is silently missing, and a later read is already `unresolved-attribute`.
  The feature tests do not depend on the level.

### 5.2 Where: one per-file query

- Generalise `addon_diagnostics(file)` (e.g. to `blender_diagnostics(file)`): the add-on-level part keeps its
  root-module guard; a new part runs on every first-party file. Both report through the same `InferContext` on the
  file's global scope. The existing line `diagnostics.extend(blender::addon_diagnostics(db, file))`
  (`types.rs:261`) needs at most a rename. **No new upstream hook.**
- The class rules need no add-on: they apply to any class with a `bpy.types` base (Blender's own `scripts/`
  included). Registered rules read `file_facts(file)`, which is per file and already computed for the index.
- Cost: the class part only visits class scopes of the file, and `property_declaration` and MROs are cached
  queries that member lookups compute anyway. A tracked query keeps a manifest or sibling-file edit from
  re-running it. Not measured.
- Rejected alternatives:
  - a post-inference hook after `check_static_class_definitions` (`infer/builder.rs:1255`): it works, but costs
    one new upstream line for nothing the per-file query lacks;
  - the annotation takeover: see section 1, item 2;
  - `check_property_write` in `validate_attribute_assignment` (`attribute_assignment.rs:63`): it sees only
    `owner.x = ...`, not `setattr(...)`, and gets no `value`.

### 5.3 What each rule reads

- **Host:** for each class `C` of the file with `is_ignored_host(C)`, each member of `C`'s own body with
  `property_declaration(definition)` is reported on its target name. Mixins are not reported: an annotation on a
  plain class is right for a host and only wasted on a Panel, and the Panel's subclass does not spell it.
  `invalid-property` is skipped on Ignored hosts (Blender never evaluates the declaration there).
- **Legacy:** for each class `C` with a `bpy.types` base (host or not), each class-body `Assign` whose value is a
  call that `PropertyKind::of_callee` accepts. The callee type comes from the class scope's inference of that
  expression (as `property_declaration` does with `definition_expression_type_in_scope`). Reported on the target.
  Plain classes are skipped: a holder class of deferred properties is legitimate there (e.g. for
  `setattr(Scene, name, Holder.x)`), and a false positive costs more than a miss.
- **Invalid:** a new `glue/property_rules.rs` exposes `property_problems(db, scope, owner_kind, call,
  argument_type) -> Vec<(TextRange, Problem)>`, the checks of section 4. Inputs:
  - the call, from `property_declaration`'s parsing (factor out a `declaration_call(definition)`), or from the
    `file_facts` candidate (store the call's range in `RegisteredProperty` and re-find the node in the cached
    parsed module);
  - static enum items **with their numbers**: extend `static_enum_items` to `(identifier, number)` with the
    `None`-counting index, and tell function `items` (lambda / `def` / function type) from unreadable ones;
  - `default=` / `size=` read from syntax first (sets are widened by inference, #7), then from literal or
    fixed-length tuple types;
  - the owner, for the data-block check: Annotated → the class's host kind (`AddonPreferences` forbids ID
    pointers); Registered → the owner's root (section 2.2).
  Reported on the offending keyword (`default=...`, `set=...`, `size=...`, `type=...`) or on the name for `_x`.
  In a quoted annotation, anchor on the string literal, since the parsed string's ranges are not file ranges.
- **Target:** `file_facts` keeps every `bpy.types` owner as today, plus `accepted: bool` and the owner
  expression's range. `accepted` comes from an allowlist of roots checked with `bpy_types_bases`: `ID`,
  `PropertyGroup`, `Node`, `NodeSocket`, `NodeTreeInterfaceSocket`, `Bone`, `EditBone`, `PoseBone`,
  `BoneCollection`, `ViewLayer`, `Strip`, `TimelineMarker`, `View3DShading`, `IDPropertyWrapPtr`,
  `OperatorProperties`, `GizmoProperties`, `GizmoGroupProperties`, `KeyConfigPreferences` and the four
  `*Properties` / `*PropertiesEmpty` families (2.2). An allowlist errs towards a missed warning when a Blender
  version adds a struct; a denylist would err towards false positives.

### 5.4 Effects on typing

- An unaccepted Registered property must not type `area.reg_area`: `instance_property` (`member.rs:44-65`) and
  `completions` skip registrations with `accepted == false`. The class write itself stays `Unconstrained`
  (`is_registered_on_class` keeps them), so `bpy.types.Area.reg_area = IntProperty()` gets exactly one
  diagnostic, the one its marker expects. No marker covers the instance read yet; propose
  `area.reg_area  # ty: ignore[unresolved-attribute]` in `check_props_registered.py`. (At runtime the read returns
  the `_PropertyDeferred` class attribute; leaving it unresolved matches how class reads are treated.)
- Nothing else changes: the host rule already hides the member (`hides_instance_member`), and the legacy form
  stays a `_PropertyDeferred` class attribute.

### 5.5 Expected test effect

On both generators, the 7 + 1 + 9 + 6 `ignore-comment-unknown-rule` lines of `props_hosts`, `props_styles`,
`props_defaults` and `props_registered` (`tests/typecheck/expected/*/main.txt`) become matched markers. The
`matrix` false positive needs the generator fix of section 4. The remaining lines there belong to other tickets
(`register_class(cls)` in `props_hosts`; `op.properties.value`; the non-generic `bpy_prop_collection_idprop` on
builtin).

---

## 6. Open points

- **New error cases without markers:** `_`-prefixed names, a wrong `type=` kind, ID pointers on
  `AddonPreferences`, function `items` with a `str` default, `ENUM_FLAG` over 32 items, `size` out of range,
  `set=` without `get=` on kinds other than Int. `props_defaults` should gain one marker each; `check:load` keeps
  confirming the add-on fails.
- **Should `blender-invalid-property` cover the data-block pointer on `AddonPreferences`?** It is a
  registration `ValueError` like the others, so this note says yes; it is also an `addon_preferences` concern.
- **UIList** as a Registered target was not probed.
- The Registered-target allowlist is tied to Blender's version. A `check:load` probe that compares it with the
  metaclasses (2.2) would keep it honest.
