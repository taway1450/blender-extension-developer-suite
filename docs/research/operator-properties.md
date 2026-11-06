# How an idname string maps to an operator's properties type

Research note for [#24](https://github.com/taway1450/blender-extension-developer-suite/issues/24) (map:
[#21](https://github.com/taway1450/blender-extension-developer-suite/issues/21)), 2026-11-06. It builds on
[#23](https://github.com/taway1450/blender-extension-developer-suite/issues/23) (`operator_properties(class)`, the
synthesised protocol types, the `on_load` module arm; branch `research/operator-calls`),
[#22](https://github.com/taway1450/blender-extension-developer-suite/issues/22) (`addon_operators`, branch
`research/register-walk`), [#29](https://github.com/taway1450/blender-extension-developer-suite/issues/29) (the shared
`class_idname` query and findings through #27's per-file `addon_diagnostics`, branch `research/registration-checks`),
[#25](https://github.com/taway1450/blender-extension-developer-suite/issues/25) (value and write types of vector
properties) and [#26](https://github.com/taway1450/blender-extension-developer-suite/issues/26) (the Property
evaluator).

Conventions:

- Every fact has a source as `path:line`. `R/` is `ty-blender/ruff-blender/crates/ty_python_semantic/src/`, `I/` is
  `ty-blender/ruff-blender/crates/ty_ide/src/`, `BL/` is Blender's source at `.cache/blender-src/main/`, `T/` is
  `tests/typecheck/`, `SB/` and `SF/` are the builtin and fake-bpy-module stubs at `.cache/bpy-stubs-builtin/main/`
  and `.cache/bpy-stubs/main/`. `OP/` is `T/features/operator_properties/`.
- **Recommendation** marks my own proposals. Nothing was built or run: this note comes from reading code, stubs and
  the recorded results (`T/expected/*/main.txt`, `main.ide.md`).

---

## 1. Summary

**Recommendation:**

1. **Hooks.** One new one-line hook for every *call* sink: `blender::on_call` in `infer_call_expression_impl`, where
   ty has the call's bindings and return type (`R/types/infer/builder.rs:10142-10143`). It is table-driven by
   `(stub class, method, idname argument, result kind)`. The other sinks need no new hook: `Operator.properties` and
   the `.properties` of a key-map item or macro step go through the existing `on_load` / `on_store`
   (`R/types/dedicated/blender/member.rs:297-366`), `bl_keymap` through #27's per-file `addon_diagnostics`. The IDE
   needs two more one-line hooks (idname completion inside a string, hover on an idname string), section 8.
2. **Idname evaluation.** The idname argument's type as ty already inferred it: a string literal, or a union of
   dynamic types and one string literal (the #22 / #29 rule). ty folds constants and f-strings of literals itself
   (`R/../resources/mdtest/literal/f_string.md:5-15`). One syntactic addition: `X.bl_idname`, where `X` is (an
   instance of) an operator class, reads #29's `class_idname(X)`, because ty widens an undeclared class attribute
   to `str` (`R/../resources/mdtest/attributes.md:1289-1300`). Anything else keeps the stub type.
3. **Lookup.** Blender's own normalisation (`WM_operator_bl_idname`): a string with a `.` becomes
   `UPPER(prefix)_OT_rest`, any other string is used as is; then an exact match on the `_OT_` form
   (`BL/source/blender/windowmanager/intern/wm_operators.cc:161-179`,
   `BL/source/blender/windowmanager/intern/wm_operator_type.cc:78-100`). First the file's add-on (#22's
   `addon_operators`, isolation as in #23), then Blender's operators from the `bpy.ops` stubs.
4. **The properties type** is `OperatorProperties & P`: the stub's nominal `OperatorProperties` intersected with a
   synthesised read-only protocol `P` (#23's `Type::protocol_with_readonly_members`, `R/types/instance.rs:166-180`)
   that holds one member per property (its value type) plus a hidden identity member
   `__blender_operator__: Literal["<CATEGORY>_OT_<name>"]`. The nominal half keeps `is_property_set`,
   `property_unset`, `bl_rna` and assignability to `OperatorProperties`; `P` carries the operator. `on_load` reads
   `P`'s members first and otherwise only the nominal class's own members, never its `__getattr__`, so unknown
   attributes are errors on fake-bpy-module too. `on_store` gives writes the property's write type (#25) through the
   identity member.
5. **Containers.** `KeyMapItems.new(...)` returns `KeyMapItem & K`, `Macro.define(...)` returns `OperatorMacro & K`,
   with `K` a read-only protocol whose `properties` member is the properties type. A macro's own properties type has
   one member per step, named by the step's `_OT_` idname (#23's `DefineMacroStep`).
6. **Built-in operators** come from the `bpy.ops` stubs of both generators: the keyword-only parameters of
   `bpy.ops.<category>.<name>` (a function in builtin, `__new__` of a class in fake-bpy-module). The annotation minus
   `None` is the write type; the value type collapses `Vector | Sequence[float]` to the `mathutils` class. The data
   is good enough on both generators for the markers (section 6).
7. **`blender-unknown-operator`** is reported by `on_call` (and by the `bl_keymap` check) for a known idname string
   that neither the add-on nor Blender has, on the idname argument. Another add-on's operator is unknown. It is an
   absence rule: silent when the add-on's register walk is incomplete (#29) and in files that belong to no add-on.
8. **`blender-invalid-operator-property`** (declared in #23) is also reported by `on_call` for the property argument
   of `operator_enum` / `operator_menu_enum` that is not an enum property of the operator, and by the `bl_keymap`
   check for an unknown property name or a value not assignable to its write type.

---

## 2. What the tests require

| Add-on / file | What it pins down | Source |
| --- | --- | --- |
| `opprops_sinks` (`check_opprops_sinks.py`) | every call sink gives the properties, both idname forms; not `None`; wrong writes are `invalid-assignment`; `props.missing` and `bare.properties.amount` stay `unresolved-attribute` on **both** generators; `operator_enum` / `operator_menu_enum` property names are checked | `OP/opprops_sinks/check_opprops_sinks.py:12-83` |
| `opprops_sinks` (`__init__.py`) | `self.properties.amount += 1` in `execute`; `define(...).properties.amount = 2`; `item.properties.mode = "B"` on a key-map item made in `register()` | `OP/opprops_sinks/__init__.py:27`, `:52-56`, `:67`, `:71-73` |
| `opprops_sinks` (`check_opprops_sinks_tool.py`) | `bl_keymap` tuples: known idname in both forms; a bad value, a bad enum value and an unknown name are `blender-invalid-operator-property`; an unknown idname is `blender-unknown-operator` | `OP/opprops_sinks/check_opprops_sinks_tool.py:12-22` |
| `opprops_idnames` | literal (both forms), module constant, `Cls.bl_idname`, f-string of a constant; Blender's `object.select_all` / `OBJECT_OT_select_all`, `mesh.primitive_cube_add`; a `str` parameter keeps `OperatorProperties \| None`; an unknown idname and another add-on's idname are `blender-unknown-operator` | `OP/opprops_idnames/check_opprops_idnames.py:12-31` |
| `props_hosts` | `op.properties.value` is the operator's property (the map #1 exception) | `T/features/properties/props_hosts/check_props_hosts.py:18` |
| IDE | `^completion` of idnames inside the string of `layout.operator(...)` and `keymap_items.new(...)`; `^completion amount` on the properties; `^hover-contains "Literal"` on `.mode`; `^hover-contains "Step"` on the idname string | `OP/opprops_sinks/ide_opprops_sinks.py:12-25` |

The reference stubs spell the intended types as classes deriving `bpy_struct` with one attribute per property, and
the sinks as overloads per idname (`OP/opprops_sinks/_expected/stubs/bpy.types.pyi:5-53`,
`OP/opprops_idnames/_expected/stubs/bpy.types.pyi:5-21`).

Today all of them fail. On builtin, every property read is `unresolved-attribute` plus `type-assertion-failure`
(`T/expected/builtin/main.txt:398-511`, `:805-806`). On fake-bpy-module, `OperatorProperties.__getattr__`
(`SF/bpy-stubs/types/__init__.pyi:86110-86140`) turns reads into `Any`, so the `unresolved-attribute` lines vanish,
the asserts still fail, and `bare.properties.amount  # ty: ignore[unresolved-attribute]` is an
`unused-ignore-comment` (diff of the two `main.txt`). Every IDE marker fails (`T/expected/builtin/main.ide.md:105-135`).

Not this ticket: `register_class(OPPROPS_SINKS_OT_combo)` `invalid-argument-type` and `keyconfigs.addon`
`unresolved-attribute` (`T/expected/builtin/main.txt:431-436`) are stub / registration matters.

---

## 3. What Blender does

- **Lookup.** Every sink calls `WM_operatortype_find(idname)`, which first converts with `WM_operator_bl_idname`
  and then looks the `_OT_` form up in one map (`BL/.../wm_operator_type.cc:78-100`). The conversion upper-cases
  everything before the first `.` and replaces the `.` with `_OT_`; a string without `.` is used unchanged
  (`BL/.../wm_operators.cc:161-179`). So `"opprops_sinks.step"`, `"OPPROPS_SINKS_OT_step"` (and even
  `"Opprops_sinks.step"`) find the same operator, while `"OPPROPS_SINKS_OT_STEP"` does not.
- **Unknown operator.** `UILayout.operator`, `operator_menu_hold` and `operator_menu_enum` print a warning
  ("unknown operator") and return `None` (`BL/source/blender/makesrna/intern/rna_ui_api.cc:505-509`, `:547-552`,
  `:590-596`). So the stub's `OperatorProperties | None` is right for an unknown idname, and the `None` goes away for
  a known one.
- **`operator_enum`** warns and does nothing when the property is missing or not an enum
  (`BL/source/blender/editors/interface/interface_layout.cc:1772-1782`). Nothing raises, which is why a checker rule
  is the only place this error shows.
- **`bl_keymap`.** `register_tool` hands `bl_keymap` to the tool definition (`BL/scripts/modules/bpy/utils/__init__.py:1117`),
  which wraps a tuple into a key-map function (`BL/scripts/startup/bl_ui/space_toolsystem_common.py:42-49`, `:146-153`);
  `keymap_init_from_data` creates each item with `keymap_items.new(idname, **args)` and then `setattr`s each
  `(name, value)` of `"properties"`, recursing for a list value (a group pointer); an unknown name or a bad value
  only prints a warning (`BL/scripts/modules/bl_keymap_utils/io.py:233-260`).
- **The properties object** is an RNA struct named by the operator's `_OT_` idname, deriving `OperatorProperties`.
  Its properties are the operator's, in `get_type_hints` order, cut at the first refused data-block pointer (#23
  note, section 3.2).

---

## 4. The hooks

### 4.1 Call sinks: one hook

The stubs type every call sink with `operator: str` (or `idname: str`) and return `OperatorProperties`,
`OperatorProperties | None`, `KeyMapItem` or `OperatorMacro`: builtin `SB/bpy/types/__init__.pyi:11561`
(`Gizmo.target_set_operator`), `:13535` (`KeyMapItems.new`), `:14626` (`Macro.define`), `:26524-26527`
(`UILayout.operator*`), `:27730` (`WindowManager.operator_properties_last`), `:27921`
(`WorkSpaceTool.operator_properties`); fake-bpy-module `SF/bpy-stubs/types/__init__.pyi:9479`, `:57463`, `:68368`,
`:115558-115640`, `:121427`, `:121983`. They are ordinary stub methods, so neither `on_load` (it sees the attribute
`layout.operator`, not the call's arguments) nor type-expression inference can type their result.

`infer_call_expression_impl` ends with `let return_ty = bindings.return_type(db, env);`
(`R/types/infer/builder.rs:10142-10143`), after the arguments were inferred and checked against the stub signature
and after the existing special case for `range(...)` (`:10134-10140`), which is the same kind of refinement.

**Recommendation:** one line there:

```rust
let return_ty = crate::types::blender::on_call(&self.context, env, call_expression, callable_type, return_ty);
```

`on_call` lives in a new `blender/operator_properties.rs`. It reads argument types with the context's expression
types (all arguments are inferred by then). It:

1. returns `return_ty` unchanged unless `callable_type` (or, for a union callee such as `self.layout.operator` with
   `Panel.layout: UILayout | None`, `SB/bpy/types/__init__.pyi:19388`, each arm of it) is a bound method of a
   `bpy.types` stub method in the sink table. "A `bpy.types` stub method" is decided as `blender_function_name` does
   (`R/types/dedicated/blender/symbols.rs:17-39`), plus the enclosing class name, in a small tracked helper;
2. evaluates the idname argument (4.2), looks it up (5.1);
3. returns the refined type of the table's result kind, or `return_ty` unchanged when the idname is not known;
4. reports `blender-unknown-operator` / `blender-invalid-operator-property` through `context.report_lint`, as
   `check_property_write` already does (`member.rs:374-393`), so `# ty: ignore[...]` works per #6.

A call that fails to bind returns earlier (`builder.rs:10004-10009`) and keeps the stub type; that is wanted (a
wrong `text=` is ty's error, and the result is then unreliable anyway).

The sink table:

| Sink | Idname argument | Result |
| --- | --- | --- |
| `UILayout.operator`, `operator_menu_hold` | 1st / `operator=` | properties type (no `None`) |
| `UILayout.operator_menu_enum` | 1st / `operator=` | properties type; checks `property` (2nd) |
| `UILayout.operator_enum` | 1st / `operator=` | stub's `None`; checks `property` (2nd) |
| `UILayout.template_popup_confirm` | 1st / `operator=` | properties type (no `None`); not in the README, same shape (`SB/bpy/types/__init__.pyi:26621`) |
| `WindowManager.operator_properties_last` | 1st / `operator=` | properties type |
| `Gizmo.target_set_operator`, `WorkSpaceTool.operator_properties` | 1st / `operator=` | properties type |
| `KeyMapItems.new` | 1st / `idname=` | `KeyMapItem & K` (4.3) |
| `Macro.define` | 1st / `operator=` | `OperatorMacro & K` |
| `KeyMaps.find_item_from_operator`, `KeyMap.keymap_items.find_from_operator`, `Menu.path_menu(operator=)` | the idname parameter | stub type; `blender-unknown-operator` only (optional, no marker) |

So the answer to the ticket's question is **one hook for all call sinks**. One hook per sink would only repeat the
same lookup.

### 4.2 Evaluating the idname

**Recommendation:** a pure helper `idname_of(argument_type, argument_expr)`:

1. The argument type is a string literal, or a union of dynamic types and exactly one string literal: that string.
   This is #22 / #29's rule for `bl_idname` (register-walk note 5.3, registration-checks note 8.1), and it covers
   - `"opprops_sinks.step"` and `"OPPROPS_SINKS_OT_step"`;
   - `STEP_IDNAME`, a module constant: ty keeps a module global's literal type;
   - `f"{CATEGORY}.step"`: ty folds f-strings whose parts are literals (`f_string.md:5-15`).
2. Otherwise, when the expression is `<value>.bl_idname` and `<value>`'s type is a class literal, `type[...]` or an
   instance of a class whose MRO has `Operator` or `Macro`: #29's `class_idname(class)`. ty would give `str` here:
   it widens an undeclared class attribute's literal (`attributes.md:1289-1300`), and the stub base declares
   `bl_idname: str`. This covers `layout.operator(OPPROPS_IDNAMES_OT_step.bl_idname)` and `self.bl_idname`, the
   most common real-world spelling.
3. Otherwise (a `str` parameter, `os.environ.get(...)`): unknown, stub type kept, no diagnostic
   (`check_opprops_idnames.py:29`).

#26's evaluator is not needed: it follows names to `bpy.props` calls, not to strings, and ty already folds the
string forms.

### 4.3 `.properties` reads: `on_load`, no new hook

`on_load` is called for every attribute load with ty's own place, bound or not (`builder.rs:11246-11264`); today it
returns early for a bound place (`member.rs:305-307`). **Recommendation:** two arms before that early return:

- **Own properties.** Receiver an instance (or `Self`, a bounded type variable, a union arm, as
  `instance_value_type` already decomposes, `member.rs:156-200`) of an add-on class with `Operator` or `Macro` among
  its `bpy_types_bases`, attribute `properties`: the properties type of that class. This covers `self.properties`
  (`opprops_sinks/__init__.py:27`), `step.properties`, `bare.properties` and `op.properties.value` of
  `props_hosts`. A mixin is no operator, so `self.properties` inside a mixin keeps the stub type.
- **Refined receivers.** Receiver `C & X`, where `C` is a nominal instance of a `bpy.types` stub class and `X` a
  synthesised protocol (the properties type, or `K`): a name that `X` has gives `X`'s member type; a name `C`'s
  class defines gives that member (looked up on the class, so the stub's `__getattr__` is never consulted); any
  other name, and the identity member, is undefined, so ty reports `unresolved-attribute`. This makes
  `props.missing` and `bare.properties.amount` errors on both generators, and gives `item.properties` /
  `define(...).properties` the operator's properties type instead of `OperatorProperties | None`.

### 4.4 Writes: `on_store`, no new hook

`on_store` sees every attribute write with ty's requirement (`R/types/infer/builder/attribute_assignment.rs:44-50`,
`member.rs:331-366`). **Recommendation:** for a receiver `OperatorProperties & P` and a name of `P`: look the
operator up again by the identity member's idname (5.1, in the writing file's add-on, then Blender's), and return
`AssignableTo(write type)`: #25's write type for an add-on property (`Sequence | V` for vectors; enums, flags,
strings as their value type), the stub parameter annotation minus `None` for a Blender operator. A read-only
property (a collection, a `PropertyGroup` pointer, `options={"READ_ONLY"}`) keeps ty's own requirement, which
rejects the write. `props.amount = "2"`, `props.mode = "C"`, `item.properties.mode = "C"` and
`layout.operator("object.select_all").action = "NOPE"` are then `invalid-assignment`; `props.amount += 1` passes.

---

## 5. The properties type

### 5.1 Lookup

**Recommendation:** `find_operator(db, file, idname) -> Option<OperatorRef>`:

1. Normalise as Blender does (section 3).
2. The file's add-on: `addon_index_of(db, file)` (`R/types/dedicated/blender/index.rs:58-67`), then #22's
   `addon_operators`, keyed by the `_OT_` form. Only valid idnames are in it (#23 note 4.2). Isolation is #23's: a
   file in another add-on, or in no add-on, does not see these operators (`check_opprops_idnames.py:31`).
3. Blender's operators: `builtin_operator(program, category, name)` (6.1), with the category lower-cased from the
   `_OT_` form.

`OperatorRef` is `Addon(StaticClassLiteral)` or `Builtin { category: Name, name: Name }`. An add-on operator that
reuses a built-in idname wins: at runtime its registration replaces the built-in one. (#23 keeps the stub's
`bpy.ops` member in that case, because the stub binds the name; the difference is harmless and noted in section 10.)

### 5.2 Representation

The properties need: per-operator members; unknown names rejected on both generators; `bpy_struct` members kept
(`self.properties.is_property_set("filepath")` is common); assignability to `OperatorProperties` (user helpers and
`find_from_operator(..., properties=props)` take one); writes with write types.

| Option | Verdict |
| --- | --- |
| A synthesised protocol alone (#23's choice for `bpy.ops` objects) | loses `is_property_set` / `bl_rna` and is not assignable to `OperatorProperties` |
| A synthesised class (`DynamicClassLiteral`) as in the reference stubs | its anchor must be a `type(...)` call, `dynamic_class_header_range` panics otherwise (`R/types/class.rs:138-142`, #23 note 4.3); `self.properties` has no call at all |
| A protocol with read **and** write members | `ProtocolMemberData::property` and its parts are private to `protocol_class.rs` (`R/types/protocol_class.rs:1728-1765`, `:1049-1060`, `:1338`); needs upstream visibility edits |
| The operator class's own instance | would expose `execute`, `report`, `layout`, `bl_idname`... and hiding them is per class (`hides_instance_member`), not per use |
| **`OperatorProperties & P`** | assignable to `OperatorProperties`; `bpy_struct` members from the nominal half; per-operator members from `P`; `__getattr__` neutralised by `on_load`; built with existing constructors only |

**Recommendation:** `OperatorProperties & P`, with

- `OperatorProperties`: the stub class (`bpy_types_class(db, env, "OperatorProperties")`,
  `R/types/dedicated/blender/properties.rs:224-243`), as an instance;
- `P = Type::protocol_with_readonly_members(db, env, members)` (`R/types/instance.rs:166-180`), members:
  - `(name, value type)` for each property of `operator_properties(class)` (#23 note 5.2, the one place that answers
    "the properties of this operator"), value type from `PropertyDeclaration::value_type` (`properties.rs:126-186`,
    with #25's vector types); for a built-in operator, from 6.2;
  - for a macro, `(step _OT_ idname, properties type of the step)` per step (#23's `DefineMacroStep`);
  - `("__blender_operator__", Literal["<CATEGORY>_OT_<name>"])`, the identity.
- built by a tracked `operator_properties_type(AddonInProgram, OperatorRef)` (cycle-initial: the plain stub type).

Why the identity member:

- `on_store` needs the operator for write types and read-only-ness (4.4); the member types alone do not say it
  (a `READ_ONLY` int and a writable int look the same);
- it keeps `P` from being empty: an operator without properties would otherwise give an empty protocol, which every
  object satisfies, so the intersection could simplify to plain `OperatorProperties` and `bare.properties.amount`
  would be `Any` on fake-bpy-module again;
- it keeps `P` from being satisfied by fake-bpy-module's `OperatorProperties` through its `__getattr__`, which could
  equally let ty drop `P` from the intersection.

`on_load` hides the identity member (4.3) and `completions` leaves it out (section 8). Its cost is display: hover
shows `OperatorProperties & <Protocol with members '__blender_operator__', 'amount', ...>`. No marker records that
text (`^hover` only records, `T/README.md:156-163`).

### 5.3 Key-map items and macro steps

`KeyMapItem & K` and `OperatorMacro & K`, `K = protocol_with_readonly_members([("properties", properties type)])`.
`on_load`'s second arm (4.3) then gives `item.properties` the properties type, whatever the stub declares
(`properties: OperatorProperties | None` in builtin, `SB/bpy/types/__init__.pyi:13525`; a property in fake-bpy-module,
`SF/bpy-stubs/types/__init__.pyi:63720`). `kmi.properties` of `new(...)` is never `None` at runtime
(`OP/opprops_sinks/__init__.py:5-6`). `KeyMapItem`'s other members (`idname`, `active`, `type`) come from the
nominal half.

---

## 6. Blender's operators

### 6.1 Where the data is

Both generators describe every operator as a callable under `bpy.ops.<category>`, about 2,560 operators each:

- builtin: a module-level function with keyword-only parameters,
  `def select_all(*, action: Literal['TOGGLE', 'SELECT', 'DESELECT', 'INVERT']='TOGGLE') -> ...`
  (`SB/bpy/ops/object/__init__.pyi:174`); no positional context or undo;
- fake-bpy-module: a class deriving `_BPyOpsSubModOp` whose `__new__` takes `execution_context, undo, /, *` and then
  one keyword-only parameter per property, each `| None`
  (`SF/bpy-stubs/ops/object/__init__.pyi:4035-4044`, `SF/bpy-stubs/ops/mesh/__init__.pyi:2356-2376`).

**Recommendation:** a tracked `builtin_operator(program, category, name) -> Option<BuiltinOperator>`: resolve the
module `bpy.ops.<category>` (accepted only where `blender_module_name` accepts it, `symbols.rs:17-25`), take the
member `<name>` with `imported_symbol` as `bpy_types_class` does (`properties.rs:230-242`), and read the
**keyword-only parameters** of its signature: the function's own for builtin, `__new__`'s for a class. Positional
parameters (the context and undo of fake-bpy-module) are not properties.

### 6.2 Value and write types

| Stub annotation (both generators, `None` removed) | Write type | Value type |
| --- | --- | --- |
| `bool`, `int`, `float`, `str` | as is | as is |
| `Literal[...]`, an `rna_enum_*` alias, fake-bpy-module's `Literal[bpy.stub_internal.rna_enums.X]` | as is | as is (ty accepts `Literal[alias]`, `R/../resources/mdtest/annotations/literal.md:96-123`) |
| `set[Literal[...]]` (an `ENUM_FLAG`) | as is | as is |
| `Vector \| Sequence[float]`, `Euler \| ...`, `Matrix \| Sequence[Sequence[float]]` | as is | the `mathutils` arm |
| `Sequence[float]` / `Sequence[int]` / `Sequence[bool]` alone | as is | `bpy_prop_array[T]` |
| `Sequence[dict[str, Any]]` (a collection, e.g. `files`) | as is | `bpy_prop_collection` unspecialised (the item class is not in the stub) |
| `dict[str, Any]` named `<CAT>_OT_<name>` (a built-in macro's step, e.g. `TRANSFORM_OT_translate` in 38 operators) | as is | that step operator's properties type |
| other `dict[str, Any]` (a group pointer) | as is | `Unknown` |

The annotation is the argument the operator call accepts, which is exactly what a property write accepts, so the
write type needs no conversion beyond dropping `None`. The markers need only `Literal`, `float` and `bool`
(`check_opprops_idnames.py:21-25`), which both generators give exactly:
builtin `size: float=2.0, calc_uvs: bool=True` (`SB/bpy/ops/mesh/__init__.pyi:107`), fake-bpy-module
`size: float | None = 2.0, calc_uvs: bool | None = True` (`SF/bpy-stubs/ops/mesh/__init__.pyi:2363-2364`).

Data quality:

- **Both:** hidden properties are listed (`filemode: int=1` of `wm.append`, `SB/bpy/ops/wm/__init__.pyi:13`), which
  matches the runtime properties; dynamic enums are `str`, so `operator_enum` cannot tell a dynamic enum from a
  string property for a built-in operator and stays silent there; collection items and group pointers lose their
  class.
- **fake-bpy-module:** every parameter is `| None` (removed); the rest matches builtin.
- **builtin:** no positional context/undo (irrelevant here; it is #23's concern for `bpy.ops` calls on built-ins,
  which keep the stub's own signature).

A generator fix that would make this exact (a properties class per operator in the stubs) is not needed for the
markers and is not proposed.

---

## 7. Rules

### 7.1 `blender-unknown-operator`

**Recommendation:**

- Declared with `declare_lint!` in `R/types/dedicated/blender/lints.rs` beside #23's
  `blender-invalid-operator-property`, documented in `resources/lint_docs/`, registered by `register_lints`; default
  level `Warn` (Blender only prints a warning, section 3). `cargo dev generate-all` per #6.
- Reported by `on_call` on the idname argument when the idname is a known string (4.2) and `find_operator` finds
  nothing (`check_opprops_idnames.py:30-31`), and by the `bl_keymap` check (7.3) on the item's idname element.
- An **absence** rule as #29 defines it: silent when the add-on's register walk is incomplete (an operator may be
  registered by code the walk cannot follow), and in a file that belongs to no add-on (a shared library cannot know
  which add-on registers what). Another add-on's operator is reported; depending on another extension's operator is
  rare and can be suppressed.

### 7.2 `blender-invalid-operator-property` in `operator_enum` / `operator_menu_enum`

`on_call` evaluates the `property` argument (2nd positional or `property=`) as a string the same way as the idname.
It must name a property of `P` whose declaration is an `EnumProperty` (flag or not, `check_opprops_sinks.py:33`).
A missing name or another kind is reported on the argument (`:34-35`). For a built-in operator: a `Literal` or
`set[Literal]` member passes, a `bool` / `int` / `float` member is reported, a `str` member passes (it may be a
dynamic enum, 6.2).

### 7.3 `bl_keymap`

`bl_keymap` is a plain class attribute: nothing in the type system relates its tuples to an operator, and no stub
declares it (no match in either generator). **Recommendation:** a check in #27's per-file `addon_diagnostics` (the
query `check_types` merges, `R/types.rs:261`), next to #23's operator-property check:

- for each class of the file with `WorkSpaceTool` among `bpy_types_bases`, the own-body binding of `bl_keymap`
  whose value is a tuple literal. Blender turns only a `tuple` into key-map items and takes anything else as a
  key-map name or callback (`ToolDef.from_dict`, `BL/scripts/startup/bl_ui/space_toolsystem_common.py:146-153`),
  so anything else is skipped;
- each item a 3-tuple `(idname, args, data)`: the idname element's type (from the class body's inference,
  `definition_expression_type_in_scope` as `property_declaration` uses it, `properties.rs:340-343`) evaluated as in
  4.2 and looked up as in 5.1; unknown is `blender-unknown-operator` on the idname element
  (`check_opprops_sinks_tool.py:21`);
- for a dict literal `data` with a `"properties"` list or tuple of 2-tuples `(name, value)`: a name that is not a
  property, or a value whose inferred type is not assignable to the property's write type, is
  `blender-invalid-operator-property` on the pair (`:15-20`). A list value recurses into a group pointer's
  properties, as `_init_properties_from_data` does; anything not literal is skipped.

---

## 8. IDE

| Marker | Follows from the design? | What it needs |
| --- | --- | --- |
| `^hover-contains "Literal"` on `layout.operator(...).mode` | yes | the attribute's type from `on_load` |
| `^completion amount` on `layout.operator(...).am` | no: completion of a protocol lists its meta-type's members (#23 note, section 8, `R/types/list_members.rs:366-383`) | extend the existing `blender::completions` (`member.rs:395-419`, called at `R/semantic_model.rs:314`): for a receiver `C & P`, `P`'s names without the identity |
| `^completion opprops_sinks.step opprops_sinks.bare` inside `layout.operator("...")` and `keymap_items.new("...")` | no: string completion offers only the literals of the argument's expected type (`R/semantic_model.rs:654-720`, `:935-945`), which is the stub's `str` | **a one-line hook** in `SemanticModel::expected_string_literal_completions` appending Blender candidates: if the string is the idname argument of a sink (found from the covering node, which `semantic_model.rs` already uses), the add-on's operators in the dotted form, then Blender's (a tracked list of every `bpy.ops` category and member) |
| `^hover-contains "Step"` on the idname string | no: hover returns `None` for any literal expression (`I/hover.rs:59-63`) | **a one-line hook** before that return: for an idname string at a sink, show the operator class (or the `bpy.ops` stub callable) with its `bl_label` (read like `class_idname`) and docstring / `bl_description`; for a built-in, the stub docstring |

These two IDE hooks overlap the map's open item "IDE side of operators" (#21, "Not yet specified"); the idname half
can be built with this ticket, the `bpy.ops` half stays with #23's completion extension.

---

## 9. Files touched (for the build ticket)

| File | Change |
| --- | --- |
| `blender/operator_properties.rs` (new) | sink table, `on_call`, `idname_of`, `find_operator`, `operator_properties_type`, `builtin_operator` (6.1-6.2), idname completion and hover helpers |
| `blender/member.rs` | `on_load`: own-properties arm and refined-receiver arm (before the bound early return); `on_store`: properties writes; `completions`: `P`'s names |
| `blender/lints.rs` | `blender-unknown-operator`; the `bl_keymap` check in the per-file query |
| `R/types/infer/builder.rs` | one line: `on_call` after `bindings.return_type` (`:10143`) |
| `R/semantic_model.rs` | one line: Blender idname candidates in `expected_string_literal_completions` (IDE) |
| `I/hover.rs` | one line: idname hover before the literal early return (IDE) |
| `ty_blender` | Blender's idname normalisation (`WM_operator_bl_idname`) as a type-free function |

Reused, not rebuilt: #23's `operator_properties(class)` and `DefineMacroStep`, #22's `addon_operators`, #29's
`class_idname`, #25's value and write types, #27's per-file query.

---

## 10. Open points

- **To verify at build:**
  - ty does not simplify `OperatorProperties & P` to `OperatorProperties` on either generator (the identity member
    is there to prevent it; fake-bpy-module's `__getattr__` is the risk);
  - `on_load` overriding a *bound* place (fake-bpy-module's `__getattr__` result) with `Undefined` makes ty report
    `unresolved-attribute` (the lookup result is built from `on_load`'s place, `builder.rs:11265-11279`);
  - the union callee `self.layout.operator(...)` (`Panel.layout: UILayout | None`): which per-arm API of `Bindings`
    `on_call` uses to replace only the sink arm's return type;
  - an imported module constant (`from . import STEP_IDNAME`) keeps its literal type in the importing file (if ty
    widens it, `idname_of` follows the import to the constant's binding, as #22's `bl_idname` reading does).
- **Built-in vs add-on idname clash:** this design prefers the add-on's operator (it replaces the built-in at
  runtime); #23 keeps the stub's `bpy.ops` signature for such a name. Harmless, but the two disagree.
- **Write types for READ_ONLY operator properties** rely on the identity lookup; a properties value that flows into
  a file of another add-on (or of no add-on) loses the lookup and falls back to the value type for writes.
- **Language-server cost:** `on_call` runs on every `layout.operator(...)` in `draw` methods; `find_operator` and
  `operator_properties_type` are tracked per operator, `builtin_operator` per idname, the idname completion list
  once per program. To include in the map's measuring task.
