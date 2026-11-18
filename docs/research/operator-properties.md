# How an idname string maps to an operator's properties type

Research note for [#24](https://github.com/taway1450/blender-extension-developer-suite/issues/24) (map
[#21](https://github.com/taway1450/blender-extension-developer-suite/issues/21)), 2026-11-06. Trimmed on 2026-11-18
to the rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings.
It builds on [#23](https://github.com/taway1450/blender-extension-developer-suite/issues/23)
([operator-calls.md](operator-calls.md)), [#22](https://github.com/taway1450/blender-extension-developer-suite/issues/22)
([register-walk.md](register-walk.md)) and [#29](https://github.com/taway1450/blender-extension-developer-suite/issues/29)
([registration-checks.md](registration-checks.md)).

Conventions:

- Every fact has a source as `path:line`. `R/` is `ty-blender/ruff-blender/crates/ty_python_semantic/src/`, `I/` is
  `ty-blender/ruff-blender/crates/ty_ide/src/`, `BL/` is Blender's source at `.cache/blender-src/main/`, `SB/` and
  `SF/` are the builtin and fake-bpy-module stubs at `.cache/bpy-stubs-builtin/main/` and `.cache/bpy-stubs/main/`.
  `OP/` is `tests/typecheck/features/operator_properties/`.
- **Recommendation** marks my own proposals.

What main does: `R/types/dedicated/blender/operator_properties.rs` (its module doc is the current description). It
follows this note. The idname clash this note raised with #23 was resolved in this note's favour: an add-on operator
that reuses a built-in idname replaces it, for `bpy.ops` calls too.

---

## 1. What Blender does

- **Lookup.** Every sink calls `WM_operatortype_find(idname)`, which first converts with `WM_operator_bl_idname`
  and then looks the `_OT_` form up in one map (`BL/source/blender/windowmanager/intern/wm_operator_type.cc:78-100`).
  The conversion upper-cases everything before the first `.` and replaces the `.` with `_OT_`; a string without `.`
  is used unchanged (`BL/source/blender/windowmanager/intern/wm_operators.cc:161-179`). So `"opprops_sinks.step"`,
  `"OPPROPS_SINKS_OT_step"` (and even `"Opprops_sinks.step"`) find the same operator, while
  `"OPPROPS_SINKS_OT_STEP"` does not.
- **Unknown operator.** `UILayout.operator`, `operator_menu_hold` and `operator_menu_enum` print a warning
  ("unknown operator") and return `None` (`BL/source/blender/makesrna/intern/rna_ui_api.cc:505-509`, `:547-552`,
  `:590-596`). So the stub's `OperatorProperties | None` is right for an unknown idname, and the `None` goes away for
  a known one. Because Blender only warns, `blender-unknown-operator` is a warning.
- **`operator_enum`** warns and does nothing when the property is missing or not an enum
  (`BL/source/blender/editors/interface/interface_layout.cc:1772-1782`). Nothing raises, which is why a checker rule
  is the only place this error shows.
- **`bl_keymap`.** `register_tool` hands `bl_keymap` to the tool definition (`BL/scripts/modules/bpy/utils/__init__.py:1117`),
  which wraps a tuple into a key-map function (`BL/scripts/startup/bl_ui/space_toolsystem_common.py:42-49`, `:146-153`);
  anything other than a `tuple` is taken as a key-map name or callback. `keymap_init_from_data` creates each item
  with `keymap_items.new(idname, **args)` and then `setattr`s each `(name, value)` of `"properties"`, recursing for
  a list value (a group pointer); an unknown name or a bad value only prints a warning
  (`BL/scripts/modules/bl_keymap_utils/io.py:233-260`).
- **The properties object** is an RNA struct named by the operator's `_OT_` idname, deriving `OperatorProperties`.
  Its properties are the operator's, in `get_type_hints` order, cut at the first refused data-block pointer
  ([operator-calls.md](operator-calls.md) section 1.2).
- `kmi.properties` of `keymap_items.new(...)` is never `None` at runtime (`OP/opprops_sinks/__init__.py:5-6`).

---

## 2. Why one call hook

The stubs type every call sink with `operator: str` (or `idname: str`) and return `OperatorProperties`,
`OperatorProperties | None`, `KeyMapItem` or `OperatorMacro`. They are ordinary stub methods, so neither the
attribute-load hook (it sees the attribute `layout.operator`, not the call's arguments) nor type-expression
inference can type their result. One hook where ty has the call's bindings and return type serves every sink; one
hook per sink would only repeat the same lookup. A call that fails to bind keeps the stub type: a wrong `text=` is
ty's error, and the result is then unreliable anyway.

### 2.1 Evaluating the idname

The idname argument's type as ty already inferred it: a string literal, or a union of dynamic types and one string
literal. ty keeps a module global's literal type, and folds f-strings whose parts are literals
(`R/../resources/mdtest/literal/f_string.md:5-15`). The one syntactic addition is `X.bl_idname`, where `X` is (an
instance of) an operator class: ty widens an undeclared class attribute's literal
(`R/../resources/mdtest/attributes.md:1289-1300`), and the stub base declares `bl_idname: str`. That form
(`self.bl_idname`, `MY_OT_op.bl_idname`) is the most common real-world spelling. Anything else (a `str` parameter,
`os.environ.get(...)`) keeps the stub type, with no diagnostic.

---

## 3. The properties type

### 3.1 Representation

The properties need: per-operator members; unknown names rejected on both generators; `bpy_struct` members kept
(`self.properties.is_property_set("filepath")` is common); assignability to `OperatorProperties` (user helpers and
`find_from_operator(..., properties=props)` take one); writes with write types.

| Option | Verdict |
| --- | --- |
| A synthesised protocol alone (#23's choice for `bpy.ops` objects) | loses `is_property_set` / `bl_rna` and is not assignable to `OperatorProperties` |
| A synthesised class (`DynamicClassLiteral`) as in the reference stubs | its anchor must be a `type(...)` call, `dynamic_class_header_range` panics otherwise (`R/types/class.rs:138-142`); `self.properties` has no call at all |
| A protocol with read **and** write members | `ProtocolMemberData::property` and its parts are private to `protocol_class.rs` (`R/types/protocol_class.rs:1728-1765`, `:1049-1060`, `:1338`); needs upstream visibility edits |
| The operator class's own instance | would expose `execute`, `report`, `layout`, `bl_idname`... and hiding them is per class, not per use |
| **`OperatorProperties & P`** | assignable to `OperatorProperties`; `bpy_struct` members from the nominal half; per-operator members from `P`; `__getattr__` neutralised by the attribute-load hook; built with existing constructors only |

`P` is a synthesised read-only protocol (`Type::protocol_with_readonly_members`, `R/types/instance.rs:166-180`) with
one member per property (its value type) and the identity member
`__blender_operator__: Literal["<CATEGORY>_OT_<name>"]`.

Why the identity member:

- writes need the operator for write types and read-only-ness; the member types alone do not say it
  (a `READ_ONLY` int and a writable int look the same);
- it keeps `P` from being empty: an operator without properties would otherwise give an empty protocol, which every
  object satisfies, so the intersection could simplify to plain `OperatorProperties` and `bare.properties.amount`
  would be `Any` on fake-bpy-module again;
- it keeps `P` from being satisfied by fake-bpy-module's `OperatorProperties` through its `__getattr__`
  (`SF/bpy-stubs/types/__init__.pyi:86110-86140`), which could equally let ty drop `P` from the intersection.

Its cost is display: hover shows `OperatorProperties & <Protocol with members '__blender_operator__', 'amount', ...>`.

Reads take `P`'s members, else the nominal class's own members, never its `__getattr__`, so unknown names are
`unresolved-attribute` on fake-bpy-module too. A mixin is no operator, so `self.properties` inside a mixin keeps the
stub type. Key-map items and macro steps are `KeyMapItem & K` and `OperatorMacro & K`, with `K` a read-only protocol
whose `properties` member is the properties type.

A properties value that flows into a file of another add-on (or of no add-on) loses the identity lookup and falls
back to the value type for writes.

---

## 4. Blender's operators in the stubs

Both generators describe every operator as a callable under `bpy.ops.<category>`:

- builtin: a module-level function with keyword-only parameters,
  `def select_all(*, action: Literal['TOGGLE', 'SELECT', 'DESELECT', 'INVERT']='TOGGLE') -> ...`
  (`SB/bpy/ops/object/__init__.pyi:174`); no positional context or undo;
- fake-bpy-module: a class deriving `_BPyOpsSubModOp` whose `__new__` takes `execution_context, undo, /, *` and then
  one keyword-only parameter per property, each `| None`
  (`SF/bpy-stubs/ops/object/__init__.pyi:4035-4044`, `SF/bpy-stubs/ops/mesh/__init__.pyi:2356-2376`).

The keyword-only parameters are the properties; positional ones (fake-bpy-module's context and undo) are not.

| Stub annotation (both generators, `None` removed) | Write type | Value type |
| --- | --- | --- |
| `bool`, `int`, `float`, `str` | as is | as is |
| `Literal[...]`, an `rna_enum_*` alias, fake-bpy-module's `Literal[bpy.stub_internal.rna_enums.X]` | as is | as is (ty accepts `Literal[alias]`, `R/../resources/mdtest/annotations/literal.md:96-123`) |
| `set[Literal[...]]` (an `ENUM_FLAG`) | as is | as is |
| `Vector \| Sequence[float]`, `Euler \| ...`, `Matrix \| Sequence[Sequence[float]]` | as is | the `mathutils` arm |
| `Sequence[float]` / `Sequence[int]` / `Sequence[bool]` alone | as is | `bpy_prop_array[T]` |
| `Sequence[dict[str, Any]]` (a collection, e.g. `files`) | as is | `bpy_prop_collection` unspecialised (the item class is not in the stub) |
| `dict[str, Any]` named `<CAT>_OT_<name>` (a built-in macro's step, e.g. `TRANSFORM_OT_translate`) | as is | that step operator's properties type |
| other `dict[str, Any]` (a group pointer) | as is | `Unknown` |

The annotation is the argument the operator call accepts, which is exactly what a property write accepts, so the
write type needs no conversion beyond dropping `None`.

Data quality:

- **Both:** hidden properties are listed (`filemode: int=1` of `wm.append`, `SB/bpy/ops/wm/__init__.pyi:13`), which
  matches the runtime properties; dynamic enums are `str`, so `operator_enum` cannot tell a dynamic enum from a
  string property for a built-in operator and stays silent there; collection items and group pointers lose their
  class.
- **fake-bpy-module:** every parameter is `| None` (removed); the rest matches builtin.

A generator fix that would make this exact (a properties class per operator in the stubs) was not needed.

---

## 5. Rules

- **`blender-unknown-operator`** is an absence rule ([registration-checks.md](registration-checks.md) section 1):
  silent when the add-on's register walk is incomplete (an operator may be registered by code the walk cannot
  follow), and in a file that belongs to no add-on (a shared library cannot know which add-on registers what).
  Another add-on's operator is reported; depending on another extension's operator is rare and can be suppressed.
- **`operator_enum` / `operator_menu_enum`:** the `property` argument must name an `EnumProperty` (flag or not) of
  the operator. For a built-in operator a `str` member passes: it may be a dynamic enum.
- **`bl_keymap`** is a plain class attribute: nothing in the type system relates its tuples to an operator, and no
  stub declares it. So it is checked from the class body: only a tuple value, each item `(idname, args, data)`, with
  the `"properties"` pairs checked against the operator's write types; anything not literal is skipped.

---

## 6. IDE: what does not follow from the type

- Completion of a protocol lists its meta-type's members (`R/types/list_members.rs:366-383`), so completion of the
  properties needs ty-blender's completion hook.
- String completion offers only the literals of the argument's expected type (`R/semantic_model.rs:654-720`,
  `:935-945`), which is the stub's `str`. Idname completion inside `layout.operator("...")` needs a hook.
- Hover returns `None` for any literal expression (`I/hover.rs:59-63`). Hover on an idname string needs a hook.
