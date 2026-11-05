# How `bpy.ops.<category>.<name>` gets a call signature from a registered operator

Research note for [#23](https://github.com/taway1450/blender-extension-developer-suite/issues/23) (map:
[#21](https://github.com/taway1450/blender-extension-developer-suite/issues/21)), 2026-11-06. It builds on
[#22](https://github.com/taway1450/blender-extension-developer-suite/issues/22) (`register()` walk,
`addon_operators`, branch `research/register-walk`), [#25](https://github.com/taway1450/blender-extension-developer-suite/issues/25)
(vector value and write types, `research/vector-and-callback-properties`),
[#26](https://github.com/taway1450/blender-extension-developer-suite/issues/26) (Property evaluator,
`research/property-wrappers`), [#27](https://github.com/taway1450/blender-extension-developer-suite/issues/27)
(per-file lint query, `research/property-rules`) and
[#28](https://github.com/taway1450/blender-extension-developer-suite/issues/28) (bpy_extras mixins,
`research/bpy-symbols-leftovers`).

Conventions:

- Every fact has a source as `path:line`. `R/` is `ty-blender/ruff-blender/crates/ty_python_semantic/src/`,
  `BL/` is Blender's source at `.cache/blender-src/main/`, `T/` is `tests/typecheck/`, `SB/` and `SF/` are the
  builtin and fake-bpy-module stubs at `.cache/bpy-stubs-builtin/main/` and `.cache/bpy-stubs/main/`.
- **Recommendation** marks my own proposals. Nothing was built or run: this note comes from reading code, stubs and
  test results (`T/expected/*/main.txt`, `main.ide.md`).

---

## 1. Summary

**Recommendation:**

1. **Hook:** none new. The existing attribute-load hook `blender::on_load` (`R/types/infer/builder.rs:11257`,
   `R/types/dedicated/blender/member.rs:297-323`) already runs for every attribute ty cannot find, module
   receivers included. It gets a `Type::ModuleLiteral` arm: a missing attribute of the Blender module `bpy.ops`
   gives a **category** type; a missing attribute of a Blender module `bpy.ops.<category>` (an existing category such
   as `object`) gives an **operator** type. Both generators lay `bpy.ops` out as modules, so one rule fits both.
2. **Types:** the operator is a **synthesised protocol instance** (`Type::protocol_with_methods`,
   `R/types/instance.rs:182-193`) with `__call__`, `poll`, `idname`, `idname_py` and `get_rna_type`, each a
   `CallableType::function_like` with a leading `self`. A new category is a synthesised protocol with one read-only
   member per operator (`Type::protocol_with_readonly_members`, `R/types/instance.rs:166-180`). Dict arguments are
   synthesised `TypedDict`s (`TypedDictType::from_schema_items`, `R/types/typed_dict.rs:628-630`). These are ty's
   own synthesis facilities; nothing in upstream changes.
3. **Signature:** `(self, execution_context: Literal[<12 contexts>] = ..., undo: bool = ..., /, *, <property>: <argument
   type> = ...)` returning `set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]`.
4. **Properties** come in Blender's order, `typing.get_type_hints` over the reversed MRO, the most derived
   declaration winning but keeping its first position. The list stops at the first property Blender refuses on
   an operator (an ID pointer, or a pointer/collection to a group that contains one). A new
   `operator_properties(class)` query builds the list from the per-class property lookup in `member.rs`.
5. **Argument types** per property: the property's **write type** (#25), with two operator-specific
   additions: a float vector also accepts `mathutils.Vector` / `Matrix`, and a group pointer or collection becomes
   a `TypedDict` (all optional for a pointer, all required for collection items, `name` included).
6. **Macros:** the `register()` walk records `Macro.define(idname)` as a new event. The macro's call takes one
   `<CATEGORY>_OT_<name>` keyword per step, typed as the step's `TypedDict` (all optional).
7. **`blender-invalid-operator-property`** is declared beside the existing lints and reported by the per-file
   query of #27, on the annotated target name of the refused property.
8. **IDE:** hover, signature help and keyword completion follow from the synthesised callable. Attribute
   completion (`bpy.ops.opcall_basic.al`, `bpy.ops.object.<new>`, `bpy.ops.<new category>`) does not, and needs
   the existing `blender::completions` hook (`R/semantic_model.rs:314`).
9. **bpy_extras mixins (#28's question):** the operator signature needs a **property declaration** in the stub,
   not a plain `filepath: str`. Recommended stub form: `filepath: Annotated[str, StringProperty(...)]`, with
   `property_declaration` looking inside `Annotated` **only in files outside the first-party roots** (section 6.3).

---

## 2. What the tests require

| Add-on | What it pins down | Source |
| --- | --- | --- |
| `opcall_basic` | the twelve execution contexts and `undo`, positional-only; every property kind; wrong calls are `invalid-argument-type`, `unknown-argument`, `too-many-positional-arguments`, `positional-only-parameter-as-kwarg`; the ID pointer and every property after it dropped; `poll`, `idname` (`Literal["OPCALL_BASIC_OT_all"]`), `idname_py`, `get_rna_type` (`Struct`); unknown names stay `unresolved-attribute` | `T/features/operator_calls/opcall_basic/check_opcall_basic.py:13-95` |
| `opcall_category` | an operator added to the stubs' `object` category, built-in `object.select_all` kept, two operators in one new category | `opcall_category/check_opcall_category.py:12-23` |
| `opcall_idname_forms` | `bl_idname` from a constant, concatenation, f-string, another class plus `"_copy"`, a mixin; `os.environ.get(...)` gives nothing | `opcall_idname_forms/check_opcall_idname_forms.py:12-22` |
| `opcall_inherit` | base and mixin properties, a redeclared property takes the subclass type, a registered base keeps its own properties only | `opcall_inherit/check_opcall_inherit.py:12-21` |
| `opcall_macro` | one dict keyword per step, named by the step's `_OT_` idname; steps given in either idname form; no step property as a direct keyword | `opcall_macro/check_opcall_macro.py:14-20`, `opcall_macro/__init__.py:37-42` |
| `bpy_symbols/generated/sym_*`, `disc_register_factory` | `bpy.ops.<addon>.run(factor=...)` whatever the import form of `bpy.props` | `sym_*/check_sym_*.py:33-34`, `disc_register_factory/check_disc_register_factory.py:19-21` |
| `sym_bpy_extras` | `filepath`, `check_existing` from `ImportHelper` / `ExportHelper`; `axis_up` from `@orientation_helper` | `bpy_symbols/sym_bpy_extras/check_sym_bpy_extras.py:26-29` |
| `regchk_idname`, `regchk_isolation_a` | only valid idnames; another add-on's operator stays missing, a shared library's operator counts for the add-on that calls its `register_tool()` | `registration_checks/regchk_idname/check_regchk_idname.py:13`, `regchk_isolation_a/check_regchk_isolation_a.py:13-20` |
| IDE | `^signature`, `^completion all`, `^completion int_value=`, `^completion before=`, `^hover`, `^hover-contains "OPCALL_BASIC_OT_all"` on `.idname`; `^signature` on the macro | `opcall_basic/ide_opcall_basic.py:12-30`, `opcall_macro/ide_opcall_macro.py:12-14` |

The reference stubs spell out the intended signature (`opcall_basic/_expected/stubs/bpy.ops.opcall_basic.pyi`,
`opcall_macro/_expected/stubs/bpy.ops.opcall_macro.pyi`). Today every one of these lines fails the same way on both
generators: `unresolved-attribute` on the operator, then `type-assertion-failure` or `unused-ignore-comment`
(`T/expected/builtin/main.txt:275-397`; the fake-bpy-module list is identical). The IDE markers show
`(...) -> Unknown` and "not offered" (`T/expected/builtin/main.ide.md:53-103`).

---

## 3. What Blender does

### 3.1 The call

- Positional arguments: an execution context string, then an undo flag. A string after the flag, or a third
  argument, raises `ValueError` (`BL/source/blender/python/intern/bpy_operator_function.cc:115-149`). The undo flag
  accepts any `bool` or `int`, and may come alone (`op(True)` is valid at runtime).
- The context strings are `rna_enum_operator_context_items`: `INVOKE_DEFAULT`, `INVOKE_REGION_WIN`,
  `INVOKE_REGION_CHANNELS`, `INVOKE_REGION_PREVIEW`, `INVOKE_AREA`, `INVOKE_SCREEN` and the six `EXEC_*`
  (`BL/source/blender/makesrna/intern/rna_ui.cc:36-50`).
- The operator object has the methods `poll`, `get_rna_type`, `idname`, `idname_py` and a `bl_options` getter
  (`bpy_operator_function.cc:706-736`). `idname()` is the `CATEGORY_OT_name` form, `idname_py()` the dotted one
  (`:653-658`).

### 3.2 Which properties an operator has, in which order

- Blender collects a class's properties with `typing.get_type_hints(cls)` (`USE_POSTPONED_ANNOTATIONS` is defined,
  `BL/source/blender/python/intern/bpy_rna.cc:93`; `pyrna_deferred_register_class`, `:9656-9674`; the type-hints
  path, `:9540-9594`). `get_type_hints` walks `reversed(cls.__mro__)` and merges each class's `__annotations__`
  into one dict. So:
  - **every** class in the MRO counts, mixins and registered base operators alike (`opcall_inherit`);
  - the order is base-most first; a redeclared name keeps the position of its first declaration and takes the most
    derived value (`derived.mode` is a `StringProperty` in `mode`'s base position);
  - a value that is not a `_PropertyDeferred` is skipped without error (`deferred_register_prop`, `:9456-9459`),
    so a plain annotation `mode: int` in a subclass *removes* the inherited property.
- For each property in that order, `deferred_register_prop` refuses a `PointerProperty` or `CollectionProperty`
  whose `type=` "contains data-block properties" when the owner does not allow them, which is the case for
  operators (`bpy_rna.cc:9483-9500`). The loop stops at the first refusal (`:9571-9574`), so that property **and
  every one after it** are missing: the `opcall_basic.dropped` markers.
- "Contains data-block properties" is `STRUCT_ID` (an ID class) or `STRUCT_CONTAINS_DATABLOCK_IDPROPERTIES`
  (`BL/source/blender/makesrna/intern/rna_access.cc:808-811`). The second is set on a `PropertyGroup` when it gets
  a pointer or collection whose target contains data-blocks (`BL/source/blender/python/intern/bpy_props.cc:5549-5553`,
  `:5695-5699`), so it propagates through nested groups. No marker covers the nested case.

### 3.3 Macros

`Macro.define(idname)` adds a runtime pointer property to the macro, named by the step's `otsub->idname`, which is
the `_OT_` form whichever form was passed, and typed by the step's own properties
(`BL/source/blender/windowmanager/intern/wm_operator_type.cc:567-581`). So `combo(OPCALL_MACRO_OT_step={...})`.

---

## 4. The hook

### 4.1 Where `bpy.ops.<category>.<name>` is resolved

Both generators make `bpy.ops` a package of category modules: builtin `from bpy.ops import object as object`
(`SB/bpy/ops/__init__.pyi`), fake-bpy-module `from . import object as object` (`SF/bpy-stubs/ops/__init__.pyi:201-278`),
and `bpy` re-exports `ops` in both (`SB/bpy/__init__.pyi:13`, `SF/bpy-stubs/__init__.pyi:16`). Neither defines a
module `__getattr__`, so an unknown category or operator is a plain miss. An operator is a function in builtin
(`SB/bpy/ops/object/__init__.pyi:174`) and a class with `__new__` deriving `_BPyOpsSubModOp` in fake-bpy-module
(`SF/bpy-stubs/ops/object/__init__.pyi:4035-4044`, `SF/bpy-stubs/ops/__init__.pyi:280-308`).

Attribute loads go through `infer_attribute_load`, which calls `crate::types::blender::on_load(db, env, file,
attribute, value_type, member)` for **every** receiver before it reports `unresolved-attribute`
(`R/types/infer/builder.rs:11246-11277`). `on_load` returns ty's place untouched when it is bound
(`member.rs:305-307`), so it only ever adds names.

**Recommendation:** add a module arm to `on_load`, calling a new `blender/operators.rs`:

- receiver `Type::ModuleLiteral(m)` where `m`'s file is the Blender module `bpy.ops` (by `blender_module_name`,
  `R/types/dedicated/blender/symbols.rs:17-25`, which already rejects a first-party `bpy/`): the attribute is a
  category of the file's add-on that is not a stub module → the category type (4.3);
- receiver is the Blender module `bpy.ops.<c>`: the attribute is an operator `<c>.<name>` of the file's add-on →
  the operator type. Built-in operators are bound in the stub, so they are never replaced (`object.select_all`
  stays);
- anything else → ty's place.

This needs no upstream line: `on_load` and its call site exist. Typing `bpy.ops.opcall_basic.missing` and
`bpy.ops.object.opcall_category_missing` stays ty's own `unresolved-attribute`.

### 4.2 Isolation

The operators are those of the add-on of the file that does the lookup: `addon_index_of(db, file)`
(`R/types/dedicated/blender/index.rs:58-67`) gives the add-on, and #22's `addon_operators(AddonInProgram)` maps
`category -> name -> class`. A file in no add-on gets nothing. `regchk_isolation_b`'s operator is not in A's walk,
and the shared library's `regchk_shared.tool` is, because only A calls `register_tool()` (#22 note, section 5.2
"Isolation"). Nothing is stored on a stub class or module, so no per-class cache can leak one add-on's
operators into another (the rule `index.rs:13-15` already states).

`addon_operators` must keep only **valid** idnames: lower-case letters, digits and `_`, one `.`, both parts
non-empty, as `blender-invalid-idname` checks (`T/features/registration_checks/regchk_idname/__init__.py:1-4`).
#22 already says an invalid idname gets no attribute (#22 note, 5.3 item 3).

### 4.3 The category and operator types

**Recommendation:** synthesised protocol instances.

- **Operator:** `Type::protocol_with_methods(db, env, [("__call__", call), ("poll", poll), ("idname", idname),
  ("idname_py", idname_py), ("get_rna_type", get_rna_type)])` (`R/types/instance.rs:182-193`). Each method is a
  `CallableType::function_like` (`R/types/callable.rs:765`) whose first parameter is a positional-only `self`,
  as ty's own sequence-pattern protocols do (`R/types/match_pattern.rs:237-253`) and the `__contains__` protocol
  of narrowing (`R/types/narrow.rs:5605-5618`). Calling such an instance goes through its `__call__` member
  (`R/types.rs:7451-7474`), and `.idname` is a bound method.
  - `poll(self, execution_context: <contexts> = ..., /) -> bool`;
  - `idname(self) -> Literal["<CATEGORY>_OT_<name>"]`, `idname_py(self) -> Literal["<category>.<name>"]`;
  - `get_rna_type(self) -> bpy.types.Struct`, resolved like `bpy_types_class`
    (`R/types/dedicated/blender/properties.rs:224-243`).
  - `bl_options` is left out: it is a read-only attribute, and `protocol_with_methods` only takes methods. No
    marker needs it.
- **New category:** `Type::protocol_with_readonly_members(db, env, [(name, operator type), ...])`
  (`R/types/instance.rs:166-180`): `bpy.ops.opcall_basic.all` is then found by ty's own member lookup, and
  `.missing` is ty's `unresolved-attribute`.
- **Cache:** a tracked `operator_type(AddonInProgram, StaticClassLiteral)` and `category_type(AddonInProgram,
  Name)`, both with `cycle_initial` giving `None`. The add-on is in the key because a macro's steps come from that
  add-on's walk.

Why not a class: a synthesised class (`DynamicClassLiteral`) would display as a named class, but its anchor must
point at a `type(...)` call: `dynamic_class_header_range` panics on any other node
(`R/types/class.rs:138-142`), and it is called from diagnostics and class spans (`R/types/class.rs:898-999`).
There is no operator call to anchor to. A protocol has no anchor. Its cost is the display: hover shows a protocol
with members instead of a name (the `^hover` marker only records, `T/README.md:158-163`).

---

## 5. The signature

### 5.1 Parameters

```
__call__(
    self,
    execution_context: Literal["INVOKE_DEFAULT", ..., "EXEC_SCREEN"] = ...,
    undo: bool = ...,
    /,
    *,
    <one keyword-only parameter per property, in Blender's order> = ...,
) -> set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]
```

Built with `Parameter::positional_only`, `Parameter::keyword_only`, `with_annotated_type`, `with_default_type` and
`Signature::new` (`R/types/signatures.rs:5987`, `:6026`, `:6053`, `:6071`, `:949`). The defaults are only "has a
default"; their value can be `Any`. The context names and the result names are type-free facts: two constants in
`ty_blender`, cited to `rna_ui.cc:36-50` and the stubs' `rna_enum_operator_return_items`.

This gives the marked errors for free: `"NOPE"` is `invalid-argument-type`, a third positional is
`too-many-positional-arguments`, `execution_context=` is `positional-only-parameter-as-kwarg`, an unknown keyword
is `unknown-argument`. `op(True)` (undo alone) is valid at runtime but rejected here; no marker uses it. An overload
`(self, undo: bool, /, *, ...)` would cover it if it turns up.

### 5.2 Gathering the properties

**Recommendation:** a tracked `operator_properties(class) -> Box<[(Name, PropertyValue)]>`, next to
`instance_property` in `member.rs` (or in `operators.rs`, reading `member.rs`'s helpers):

1. Walk `class.iter_mro()` **reversed**, every static class, stub classes included.
2. For each, the annotated names of its own body in source order. `annotated_property(db, class, name)`
   (`member.rs:113-127`) gives the declaration (after #26, `property_value`). A name whose annotation is not a
   property is **removed** from the list (Blender's skip, 3.2); a later declaration replaces the value and keeps
   the position.
3. Add the decorator origin #28 proposes for `@orientation_helper` (`axis_forward`, `axis_up`) at the decorated
   class's position, after its body's annotations (the decorator writes into `__annotations__` after the body ran).
4. Truncate at the first property that Blender refuses (3.2): a pointer or collection whose target is an ID class,
   or a `PropertyGroup` that contains one, recursively, with a depth bound. `PropertyDeclaration::target_class`
   (`properties.rs:203-213`) already tells ID from group.

What `member.rs` gives: `annotated_property`, `body_binds` and the MRO walk. What it does not: `instance_property`
answers one name, by the **first** class in the MRO that binds it, and skips Ignored hosts (`member.rs:44-65`,
`:129-148`). That is the attribute rule. The operator list needs every name, in `get_type_hints` order, and only
annotations count (an `x = 5` in a subclass does not remove an inherited annotation). So the walk is new, the
pieces are shared. Registered properties never apply: they need a `bpy.types` owner (`index.rs:137-144`), and an
add-on's operator class is not one.

The same list serves #24 (operator properties by idname, `self.properties`, `layout.operator(...)`), so it should
be the one place that answers "the properties of this operator".

### 5.3 Argument type per property kind

**Recommendation:** `PropertyDeclaration::argument_type(db, env)`:

| Property | Argument type | Reason |
| --- | --- | --- |
| Bool, Int, String | `bool`, `int`, `str` (`bytes` for `BYTE_STRING`) | the value type (`properties.rs:126-133`) |
| Float | `int \| float` (`KnownUnion::Float`) | the value type; `float_value=1` passes |
| Enum | `Literal[...]`, `set[Literal[...]]` for `ENUM_FLAG`, `str` (or `set[str]`) for dynamic items | the value type (`properties.rs:134-150`); `["A"]` and `"A"` for a flag are rejected, `set()` passes |
| Bool/Int/Float vector | #25's write type `S \| V` (nested `Sequence[E]` plus the value type) | #25 note 2.3 |
| Float vector, additionally | `mathutils.Vector` for 1-D, `Matrix` for 2-D | see below |
| Pointer to a `PropertyGroup` | a `TypedDict`, `total=False`, of the group's argument types, `name: str` included | `_GroupValue`, `opcall_basic/_expected/stubs/bpy.ops.opcall_basic.pyi:12-14` |
| Collection of a `PropertyGroup` | `Sequence[TypedDict]`, every key required | `_GroupItem`, `:16-18`; `[{"count": 1}]` gives `missing-typed-dict-key` (`check_opcall_basic.py:83`) |
| Pointer/collection to an ID (or a group containing one) | not a parameter; the list stops there | 3.2 |
| Opaque (#26) or unknown option | `Any` | #26 note 4.1 |

- **Vectors:** #25's `V` is the value type, which is `bpy_prop_array[float]` for `FloatVectorProperty(size=3)`
  without subtype. A `Vector` must still pass (`check_opcall_basic.py:57`). It does on builtin, whose mathutils
  classes subclass `Sequence[float]`, but not on fake-bpy-module, whose classes subclass nothing (#25 note 2.3).
  At runtime any sequence is accepted (`bpy_rna_array.cc`, #25 note 2.1). So the float argument type adds
  `Vector` (1-D) or `Matrix` (2-D). **Recommendation:** put this in #25's `write_type` itself, so that
  `s.f_none_3 = Vector(...)` agrees with the operator call; then `argument_type` is `write_type` for vectors.
- **Dicts:** `TypedDictType::from_schema_items(db, schema)` (`R/types/typed_dict.rs:628-630`) with
  `TypedDictFieldBuilder::new(ty).required(..)` (`:3305-3313`) and a `TypedDictSchema` collected from
  `(Name, TypedDictField)` (`:3236`). Field types are the nested properties' argument types, so nested groups,
  enums and vectors recurse. `name: str` comes from `PropertyGroup.name` in the stubs (it is an RNA property, not
  an annotation). A group's own properties use the same gathering as 5.2 (groups are `get_type_hints`-collected
  too).
- Option-only differences (`HIDDEN`, `SKIP_SAVE`) do not change the argument (`hidden_value=1` passes).

### 5.4 Return value

`set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]`, built from the constant. It
matches the markers' `Result` alias on both generators whatever the stubs call the alias
(`SB/bpy/ops/object/__init__.pyi:174` `set[rna_enum_operator_return_items]`,
`SF/bpy-stubs/ops/object/__init__.pyi:4044`).

---

## 6. Special cases

### 6.1 Idnames

`addon_operators` (#22 note 5.3) reads `bl_idname` from the binding type of the first class in the MRO that
binds it, which covers the constant, concatenation, f-string and mixin forms, and yields nothing for
`os.environ.get(...)`. Still to verify at build, as #22 says: `OPCALL_IDNAME_FORMS_OT_fstring.bl_idname + "_copy"`.
`idname()` is the category upper-cased, `_OT_`, then the name: `object.opcall_category_scale` gives
`OBJECT_OT_opcall_category_scale` (`check_opcall_category.py:14`).

### 6.2 Macros

**Recommendation:**

- The walk (#22) gets an event `DefineMacroStep { macro: StaticClassLiteral, idname: Name, site: Site }` for a
  call `X.define(<string>)` whose receiver evaluates to a Class value that has `Macro` among its `bpy_types_bases`.
  The string is evaluated like `bl_idname` (literal or constant). `opcall_macro` defines its steps inside
  `register()`, after `register_class` (`opcall_macro/__init__.py:37-42`), which the walk reaches.
- `addon_operators` then holds, per macro, its steps in order. Each step's idname is normalised to the `_OT_`
  form (`opcall_macro.label` → `OPCALL_MACRO_OT_label`) and looked up among the add-on's operators in either form.
- The macro's `__call__` has one keyword-only parameter per step, named by the `_OT_` form and typed as a
  `TypedDict` (`total=False`) of that step's argument types. Its own annotations are not parameters
  (`combo(amount=2)` is `unknown-argument`).
- A step that names a **built-in** operator (`"TRANSFORM_OT_translate"`, common in real add-ons) has no add-on
  class. Recommendation for now: `dict[str, Any]`. Its keyword parameters could later be read from the stub's
  operator signature.
- On fallback (the walk is incomplete) no `define` is known, and a macro takes `**kwargs: Any`, so no false
  `unknown-argument`.

### 6.3 bpy_extras mixins (the question from #28)

The operator signature is built from **property declarations** (5.2). A plain `filepath: str` in the stub types
`imp.filepath` but declares no property, so `import_file(filepath=...)` and `export_file(check_existing=...)`
would be `unknown-argument` (`check_sym_bpy_extras.py:27-29`).

**Recommendation:** the generators write the mixins' properties as
`filepath: Annotated[str, StringProperty(subtype="FILE_PATH", ...)]` (`check_existing: Annotated[bool,
BoolProperty(...)]`). Stock tools read `str`, and ty-blender's `property_declaration` (`properties.rs:310-344`)
looks inside `Annotated` for a metadata element that is a `bpy.props` call, **only when the defining file is not
under a first-party root** (as `blender_module_name` decides, `symbols.rs:17-25`). In add-on code
`x: Annotated[str, StringProperty()]` creates no property at runtime: `get_type_hints` strips `Annotated` and
returns `str`, which is not a deferred, so Blender skips it (3.2). The checker must not accept it there. The
attribute's value type is then still `str` from the annotation; the argument type comes from the declaration.

`axis_forward` / `axis_up` come from #28's decorator origin, which 5.2 step 3 includes. A built-in table of
"extra properties per bpy_extras class" would also work, but it would need updating with Blender, and the
`Annotated` form covers any pure-Python Blender class the generators document.

### 6.4 Other import forms

`from bpy.ops import opcall_basic` and `import bpy.ops.opcall_basic` stay `unresolved-import`: ty resolves imports
to files, and there is no file. Real add-ons use the attribute form; no marker imports a category.

---

## 7. `blender-invalid-operator-property`

**Recommendation:**

- Declared with `declare_lint!` beside the existing two (`R/types/dedicated/blender/lints.rs:21-42`), documented in
  `resources/lint_docs/`, registered in `register_lints`. #24 reuses the same rule for the `operator_enum` /
  `bl_keymap` cases (`T/features/operator_properties/README.md`).
- Reported by #27's per-file query (the generalised `addon_diagnostics`, called from `R/types.rs:261`), in its
  class part: for each class of the file with `Operator` or `Macro` among `bpy_types_bases`
  (`symbols.rs:54-64`), each own-body property declaration that Blender would refuse (5.2 step 4) is reported on
  its annotated target name, as #27's host rule does. The `# ty: ignore` sits on that line
  (`opcall_basic/__init__.py:58`).
- A refused property inherited from a plain mixin is reported on the operator's class name: the mixin itself is
  not an operator, and may be used by a `PropertyGroup` where the pointer is fine.
- The properties after it get no diagnostic of their own; calling with them is `unknown-argument`.

---

## 8. IDE

| Marker | Follows from the type? | Source |
| --- | --- | --- |
| `^signature` (`bpy.ops.opcall_basic.all()`, macro) | yes: signature help upcasts the callee to a callable, which goes through `__call__` | `R/types/ide_support.rs:1142-1187` |
| `^completion int_value=`, `before=` | yes: keyword completions are the signature help's parameters (positional-only ones skipped) | `ty_ide/src/completion.rs:2166-2203` |
| `^hover` on `bpy.ops.opcall_basic.all` | yes (shows the protocol) | inferred type |
| `^hover-contains "OPCALL_BASIC_OT_all"` on `.idname` | yes: the bound method's return type is the literal | inferred type |
| `^completion all` on `bpy.ops.opcall_basic.al` | **no**: completion of a protocol instance lists its meta-type's members, not the interface | `R/types/list_members.rs:366-383` |
| `bpy.ops.object.<new op>`, `bpy.ops.<new category>` | **no**: the names exist only in the hook | |

**Recommendation:** extend `blender::completions` (`member.rs:395-419`; called from `R/semantic_model.rs:314`):
for the module `bpy.ops`, add the add-on's new categories; for a module `bpy.ops.<c>`, the add-on's operators in
`c`; for a receiver equal to one of the add-on's `category_type`s (interned, so equality identifies it), that
category's operators. No new hook.

---

## 9. Files touched (for the build ticket)

| File | Change |
| --- | --- |
| `blender/operators.rs` (new) | `category_type`, `operator_type`, signature and `TypedDict` construction, `module_attribute`, completion names |
| `blender/member.rs` | `on_load` module arm; `operator_properties` (or its helpers made `pub(super)`); `completions` additions |
| `blender/properties.rs` | `argument_type`; "contains data-blocks" test; `Annotated` look-through outside first-party roots |
| `blender/index.rs` / the walk (#22) | `DefineMacroStep`; `addon_operators` keeps valid idnames and macro steps |
| `blender/lints.rs` | `blender-invalid-operator-property` |
| `ty_blender` | the context and result name constants |
| upstream files | none |

---

## 10. Open points

- **To verify at build:**
  - a dict literal and a list of dict literals are checked against a *synthesised* `TypedDict` parameter
    (`invalid-argument-type`, `missing-typed-dict-key`) the way they are against a class-based one;
  - `.poll` / `.idname` on a synthesised protocol bind `self` and display well enough in hover;
  - `TypedDict` totality: the markers want collection items fully required. If Blender in fact fills missing keys
    with defaults, the marker (not the design) should change.
- **Nested data-block groups:** a group that contains an ID pointer is refused like an ID pointer (3.2). No marker
  covers it; the design includes it.
- **Built-in macro steps** take `dict[str, Any]` (6.2).
- **Undo alone** (`op(True)`) is rejected (5.1).
- **Shadowing:** an add-on operator whose idname equals a built-in one keeps the stub's signature (4.1).
- **Language-server cost:** building the signatures runs on the first `bpy.ops.<category>` access per add-on; the
  map's measuring task should include it.
