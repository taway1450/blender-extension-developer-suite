# How `bpy.ops.<category>.<name>` gets a call signature from a registered operator

Research note for [#23](https://github.com/taway1450/blender-extension-developer-suite/issues/23) (map
[#21](https://github.com/taway1450/blender-extension-developer-suite/issues/21)), 2026-11-06. Trimmed on 2026-11-18
to the rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings.
It builds on [#22](https://github.com/taway1450/blender-extension-developer-suite/issues/22)
([register-walk.md](register-walk.md)), [#25](https://github.com/taway1450/blender-extension-developer-suite/issues/25)
([vector-and-callback-properties.md](vector-and-callback-properties.md)),
[#26](https://github.com/taway1450/blender-extension-developer-suite/issues/26)
([property-wrappers.md](property-wrappers.md)) and
[#28](https://github.com/taway1450/blender-extension-developer-suite/issues/28)
([bpy-symbols-leftovers.md](bpy-symbols-leftovers.md)).

Conventions:

- Every fact has a source as `path:line`. `R/` is `ty-blender/ruff-blender/crates/ty_python_semantic/src/`,
  `BL/` is Blender's source at `.cache/blender-src/main/`, `T/` is `tests/typecheck/`, `SB/` and `SF/` are the
  builtin and fake-bpy-module stubs at `.cache/bpy-stubs-builtin/main/` and `.cache/bpy-stubs/main/`.
- **Recommendation** marks my own proposals.

What main does: `R/types/dedicated/blender/operators.rs` (its module doc is the current description) and
`T/features/operator_calls/README.md`. Three points differ from this note's original proposal:

- The undo flag alone (`op(True)`) is accepted, through a second overload of `__call__`. Wrong calls are therefore
  ty's `no-matching-overload`, or `invalid-argument-type` when only one overload fits the positional arguments.
- An add-on operator whose idname equals a built-in one replaces the built-in operator, as it does at runtime.
- Built-in operators get the same protocol, with the keywords of their stub, in any file.

---

## 1. What Blender does

### 1.1 The call

- Positional arguments: an execution context string, then an undo flag. A string after the flag, or a third
  argument, raises `ValueError` (`BL/source/blender/python/intern/bpy_operator_function.cc:115-149`). The undo flag
  accepts any `bool` or `int`, and may come alone (`op(True)` is valid at runtime).
- The context strings are `rna_enum_operator_context_items`: `INVOKE_DEFAULT`, `INVOKE_REGION_WIN`,
  `INVOKE_REGION_CHANNELS`, `INVOKE_REGION_PREVIEW`, `INVOKE_AREA`, `INVOKE_SCREEN` and the six `EXEC_*`
  (`BL/source/blender/makesrna/intern/rna_ui.cc:36-50`).
- The operator object has the methods `poll`, `get_rna_type`, `idname`, `idname_py` and a `bl_options` getter
  (`bpy_operator_function.cc:706-736`). `idname()` is the `CATEGORY_OT_name` form, `idname_py()` the dotted one
  (`:653-658`).

### 1.2 Which properties an operator has, in which order

- Blender collects a class's properties with `typing.get_type_hints(cls)` (`USE_POSTPONED_ANNOTATIONS` is defined,
  `BL/source/blender/python/intern/bpy_rna.cc:93`; `pyrna_deferred_register_class`, `:9656-9674`; the type-hints
  path, `:9540-9594`). `get_type_hints` walks `reversed(cls.__mro__)` and merges each class's `__annotations__`
  into one dict. So:
  - **every** class in the MRO counts, mixins and registered base operators alike;
  - the order is base-most first; a redeclared name keeps the position of its first declaration and takes the most
    derived value;
  - a value that is not a `_PropertyDeferred` is skipped without error (`deferred_register_prop`, `:9456-9459`),
    so a plain annotation `mode: int` in a subclass *removes* the inherited property.
- For each property in that order, `deferred_register_prop` refuses a `PointerProperty` or `CollectionProperty`
  whose `type=` "contains data-block properties" when the owner does not allow them, which is the case for
  operators (`bpy_rna.cc:9483-9500`). The loop stops at the first refusal (`:9571-9574`), so that property **and
  every one after it** are missing.
- "Contains data-block properties" is `STRUCT_ID` (an ID class) or `STRUCT_CONTAINS_DATABLOCK_IDPROPERTIES`
  (`BL/source/blender/makesrna/intern/rna_access.cc:808-811`). The second is set on a `PropertyGroup` when it gets
  a pointer or collection whose target contains data-blocks (`BL/source/blender/python/intern/bpy_props.cc:5549-5553`,
  `:5695-5699`), so it propagates through nested groups.
- Registered properties never apply to an operator: they need a `bpy.types` owner, and an add-on's operator class
  is not one.

### 1.3 Macros

`Macro.define(idname)` adds a runtime pointer property to the macro, named by the step's `otsub->idname`, which is
the `_OT_` form whichever form was passed, and typed by the step's own properties
(`BL/source/blender/windowmanager/intern/wm_operator_type.cc:567-581`). So `combo(OPCALL_MACRO_OT_step={...})`.
The macro's own annotations are not call parameters.

### 1.4 How the stubs lay out `bpy.ops`

Both generators make `bpy.ops` a package of category modules: builtin `from bpy.ops import object as object`
(`SB/bpy/ops/__init__.pyi`), fake-bpy-module `from . import object as object` (`SF/bpy-stubs/ops/__init__.pyi:201-278`).
Neither defines a module `__getattr__`, so an unknown category or operator is a plain miss. An operator is a
function in builtin (`SB/bpy/ops/object/__init__.pyi:174`) and a class with `__new__` deriving `_BPyOpsSubModOp` in
fake-bpy-module (`SF/bpy-stubs/ops/object/__init__.pyi:4035-4044`, `SF/bpy-stubs/ops/__init__.pyi:280-308`).

`from bpy.ops import opcall_basic` and `import bpy.ops.opcall_basic` stay `unresolved-import`: ty resolves imports
to files, and there is no file. Real add-ons use the attribute form.

---

## 2. Why a protocol, not a class

The operator is a synthesised protocol instance (`Type::protocol_with_methods`, `R/types/instance.rs:182-193`), and
a new category a protocol with one read-only member per operator (`Type::protocol_with_readonly_members`,
`R/types/instance.rs:166-180`). Each method is a `CallableType::function_like` (`R/types/callable.rs:765`) whose
first parameter is a positional-only `self`, as ty's own sequence-pattern protocols do
(`R/types/match_pattern.rs:237-253`). Calling such an instance goes through its `__call__` member
(`R/types.rs:7451-7474`). Dict arguments are synthesised `TypedDict`s (`TypedDictType::from_schema_items`,
`R/types/typed_dict.rs:628-630`). These are ty's own synthesis facilities; nothing in upstream changes.

Why not a class: a synthesised class (`DynamicClassLiteral`) would display as a named class, but its anchor must
point at a `type(...)` call: `dynamic_class_header_range` panics on any other node
(`R/types/class.rs:138-142`), and it is called from diagnostics and class spans (`R/types/class.rs:898-999`).
There is no operator call to anchor to. A protocol has no anchor. Its cost is the display: hover shows a protocol
with members instead of a name.

Isolation: the operators are those of the add-on of the file that does the lookup. Nothing is stored on a stub
class or module, so no per-class cache can leak one add-on's operators into another.

---

## 3. bpy_extras mixins (the question from #28)

The operator signature is built from **property declarations**. A plain `filepath: str` in the stub types
`imp.filepath` but declares no property, so `import_file(filepath=...)` and `export_file(check_existing=...)`
would be `unknown-argument`.

**Recommendation:** the generators write the mixins' properties as
`filepath: Annotated[str, StringProperty(subtype="FILE_PATH", ...)]` (`check_existing: Annotated[bool,
BoolProperty(...)]`). Stock tools read `str`, and ty-blender looks inside `Annotated` for a metadata element that
is a `bpy.props` call, **only when the defining file is not under a first-party root**. In add-on code
`x: Annotated[str, StringProperty()]` creates no property at runtime: `get_type_hints` strips `Annotated` and
returns `str`, which is not a deferred, so Blender skips it (1.2). The checker must not accept it there. The
attribute's value type is then still `str` from the annotation; the argument type comes from the declaration.

`axis_forward` / `axis_up` come from `@orientation_helper` ([bpy-symbols-leftovers.md](bpy-symbols-leftovers.md)).
A built-in table of "extra properties per bpy_extras class" would also work, but it would need updating with
Blender, and the `Annotated` form covers any pure-Python Blender class the generators document.

---

## 4. IDE: what follows from the type

| Feature | Follows from the type? | Source |
| --- | --- | --- |
| signature help on an operator or macro call | yes: signature help upcasts the callee to a callable, which goes through `__call__` | `R/types/ide_support.rs:1142-1187` |
| keyword completion (`int_value=`) | yes: keyword completions are the signature help's parameters (positional-only ones skipped) | `ty_ide/src/completion.rs:2166-2203` |
| hover on the operator | yes (shows the protocol) | inferred type |
| hover on `.idname` | yes: the bound method's return type is the literal | inferred type |
| attribute completion on `bpy.ops.opcall_basic.al` | **no**: completion of a protocol instance lists its meta-type's members, not the interface | `R/types/list_members.rs:366-383` |
| `bpy.ops.object.<new op>`, `bpy.ops.<new category>` | **no**: the names exist only in the hook | |

So attribute completion of categories and operators needs ty-blender's completion hook.
