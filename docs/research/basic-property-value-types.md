# Basic property declarations: the value type each one gets

Research note, 2026-11-05, for [#7](https://github.com/taway1450/blender-extension-developer-suite/issues/7)
on the map [#1](https://github.com/taway1450/blender-extension-developer-suite/issues/1). It answers what value type
ty-blender should give each basic property declaration (Int / Float / Bool / String, Enum, Pointer, Collection) on
both stub generators. It also covers which arguments the glue must read, and which markers a stub bug blocks.

Out of scope, as settled in [#2](https://github.com/taway1450/blender-extension-developer-suite/issues/2): vector
subtypes and sizes, callbacks, inherited and mixin annotations, and the `blender-*` property rules.

Conventions:

- Every fact has a `path:line` source. Paths are relative to the main repo root:
  - `blender/` is the Blender source (`main`);
  - `B/` is `.cache/bpy-stubs-builtin/main/` (the builtin generator);
  - `F/` is `.cache/bpy-stubs/main/` (fake-bpy-module);
  - `gen` is `scripts/feature_generators/properties.py`;
  - `props/` is `tests/typecheck/features/properties/`.
- My own recommendations are marked **Recommendation**.
- *Probed* means I ran it on 2026-11-05 in `.cache/blender-bin/main/blender.exe` (Blender 5.4.0 Alpha, built
  2026-11-02), in background mode with a throwaway script. *ty probe* means
  `ty-blender/ruff-blender/target/release/ty.exe` (`ty 0.0.97 (368c78c30)`) on a scratch file.

---

## 1. The table

| Declaration | Value type | Writable? | Source |
| --- | --- | --- | --- |
| `BoolProperty(...)` | `bool` | yes | `blender/source/blender/python/intern/bpy_rna.cc:1546-1548` |
| `IntProperty(...)`, any `subtype` | `int` | yes | `bpy_rna.cc:1549-1551` |
| `FloatProperty(...)`, any `subtype` / `unit` | `float` | yes | `bpy_rna.cc:1552-1554` |
| `StringProperty(...)`, `subtype` other than `BYTE_STRING` | `str` | yes | `bpy_rna.cc:1555-1584` |
| `StringProperty(subtype="BYTE_STRING")` | **`bytes`** | yes | `bpy_rna.cc:1564-1566`; probed |
| `EnumProperty(items=<static items>)` | `Literal["A", "B", ...]` | yes | `bpy_rna.cc:1475-1478` |
| `EnumProperty(items=<dynamic items>)` | `str` | yes | as above |
| `EnumProperty(items=<static>, options={"ENUM_FLAG", ...})` | `set[Literal["A", "B", ...]]` | yes | `bpy_rna.cc:1460-1474` |
| `EnumProperty(items=<dynamic>, options={"ENUM_FLAG", ...})` | `set[str]` | yes | as above |
| `PointerProperty(type=<ID subclass>)` | `T \| None` | yes | `bpy_rna.cc:1588-1599`; `blender/source/blender/makesrna/intern/rna_define.cc:4613-4615` |
| `PointerProperty(type=<PropertyGroup subclass>)` | `T` | **no** | `rna_access.cc:4656-4665`; `rna_define.cc:4611-4615` |
| `CollectionProperty(type=<PropertyGroup subclass>)` | `bpy_prop_collection_idprop[T]` | **no** | `bpy_rna.cc:1601-1602`; `rna_define.cc:4639-4653` |
| any of the above with `options={"READ_ONLY", ...}` | unchanged | **no** | `blender/source/blender/makesrna/intern/rna_rna.cc:189-201`; `bpy_props.cc:445-461`; probed |

"Writable: no" means that assignment raises `AttributeError: bpy_struct: attribute "x" from "Y" is read-only`
(`bpy_rna.cc:5182-5189`, probed). Section 5 explains it.

The markers agree with this table everywhere except one: `BYTE_STRING` (section 2.2).

---

## 2. Int / Float / Bool / String

### 2.1 What the markers say

`gen:91-120` generates one field for each of these:

- Bool, Int, Float and String, plain and with `default` / `min` / `max` / `soft_*` / `step` / `precision` / `maxlen`;
- every `subtype` of Int and Float (15 values, `gen:53-69`);
- every Float `unit` (16 values, `gen:70-87`);
- every String `subtype` (6 values, `gen:88`).

The marker type is `bool` / `int` / `float` / `str` throughout (`gen:93-119`). Assignment markers:

- `bool` rejects `"yes"`;
- `int` rejects `"3"` and `1.5`;
- `float` accepts `1` and rejects `"1.5"`;
- `str` rejects `1` and `None`.

They are in `props/generated/props_scalar/check_props_scalar.py:79-91`.

### 2.2 What Blender does

`pyrna_prop_to_py` picks the Python type from the RNA property type alone (`bpy_rna.cc:1531-1612`):

- `PROP_BOOLEAN` gives `bool` (`:1546-1548`);
- `PROP_INT` gives `int` (`:1549-1551`);
- `PROP_FLOAT` gives `float` (`:1552-1554`).

`subtype` and `unit` play no part for these three.

**`PROP_STRING` is the exception.** With subtype `PROP_BYTESTRING` it returns `PyBytes_FromStringAndSize`
(`bpy_rna.cc:1564-1566`, and the same in the non-coerce branch `:1574-1576`). The setter then requires `bytes`
and rejects `str` with "expected a bytes type" (`bpy_rna.cc:1829-1856`). `BYTE_STRING` is a valid
`StringProperty` subtype (`rna_rna.cc:64`).

Probed: `StringProperty(subtype="BYTE_STRING")` reads as `('bytes', b'')`, and after `s.s = b"x"` it reads
`b'x'`. `FILE_PATH` reads as `str`.

> **Marker bug.** `gen:119` generates `s_byte_string` with type `str`. As a result:
> - `props/generated/props_scalar/check_props_scalar.py:74` asserts `str`;
> - `props/generated/props_scalar/_expected/addon/__init__.pyi:72` says `s_byte_string: str`.
>
> At runtime the value is `bytes`. The oracle cannot catch this: it only checks that the markers and the
> reference stubs agree, and both are wrong. **Recommendation:** in `gen:119`, map `BYTE_STRING` to `bytes`.
> Optionally add a `bad=['"text"']` assignment marker for it.

Assignment coercion, for the record (`bpy_rna.cc:1686-1900`, probed):

- `bool` accepts `True`/`False` or the ints `0`/`1` and rejects other ints (`:1720-1734`).
- `int` accepts anything `PyLong_AsLong` takes, which includes `bool`, and rejects `float` (`:1747-1767`).
- `float` accepts anything `PyFloat_AsDouble` takes: int, bool, float (`:1777-1789`).
- `str` rejects `None`, because runtime string properties get `PROP_NEVER_NULL` (`rna_define.cc:1281-1288`,
  `bpy_rna.cc:1806-1826`).

ty's `int` / `float` / `bool` / `str` types already model this, apart from `bool` accepting a literal `0`/`1`. No
marker covers that case.

### 2.3 `options`

`options` takes members of `rna_enum_property_flag_items` (`rna_rna.cc:189-231`):

- `READ_ONLY`, `HIDDEN`, `SKIP_SAVE`, `SKIP_PRESET`, `ANIMATABLE`, `LIBRARY_EDITABLE`, `PROPORTIONAL`,
  `TEXTEDIT_UPDATE`, `OUTPUT_PATH`, `PATH_SUPPORTS_BLEND_RELATIVE`, `SUPPORTS_TEMPLATES`;
- plus `ENUM_FLAG`, for `EnumProperty` only (`rna_rna.cc:233-251`).

None of these changes the value type. One changes writability:

- **`READ_ONLY`** clears `PROP_EDITABLE`. `bpy_prop_assign_flag` inverts the bit (`bpy_props.cc:445-461`;
  comment at `rna_rna.cc:190-200`).
- Probed: `IntProperty(options={"READ_ONLY"})`, `PointerProperty(type=Object, options={"READ_ONLY"})` and an
  `ENUM_FLAG` enum with `READ_ONLY` all raise `AttributeError ... is read-only` on assignment. Reading still works.

No marker covers `READ_ONLY` today. **Recommendation:** make `READ_ONLY` a read-only attribute, the same way as a
PropertyGroup pointer (section 5). Add a generated field such as `i_readonly` with a `bad=["1"]` marker. The issue
lists `options` as in scope, and this is the only option with a type-visible effect.

(Also read-only, but out of scope: a `get=` callback without `set=` makes the property read-only. Probed:
`IntProperty(get=...)` raises on assignment. That belongs to the callbacks work.)

---

## 3. `EnumProperty`

### 3.1 How Blender reads `items`

`BPy_EnumProperty` (`bpy_props.cc:5159-5360`):

- **Function.** If `PyFunction_Check(items)`, the items are dynamic (`is_itemf = true`, `:5285-5305`). This covers
  a `def` and a `lambda`, which must take exactly 2 arguments (`:5287-5292`). Any other callable is not a
  `PyFunction`: a bound method, `functools.partial` or a builtin falls through to the sequence branch and fails
  there.
- **Sequence.** Anything else goes through `PySequence_Fast(items, ...)` (`:5309-5313`), which accepts any iterable
  (probed: a generator expression registers). `enum_items_from_py` then walks it (`bpy_props.cc:2475-2595`):
  - Each element must be **exactly a `tuple`** (`PyTuple_CheckExact`) of 3, 4 or 5 items:
    - `(identifier, name, description)`;
    - `(..., number)`;
    - `(..., icon, number)`, where `icon` is a `str` name or an `int` (`:2537-2548`).
  - `None` is a separator and adds no identifier (`:2584-2587`).
  - Anything else, including a list `["A", "A", ""]`, raises `TypeError: EnumProperty(...): expected a tuple
    containing (identifier, name, description) ...` (`:2588-2595`). Probed: a list of lists fails to register.
- **Value.** On read, a non-flag enum returns the current item's identifier as `str` (`bpy_rna.cc:1475-1478`). If
  no item matches, it returns `""` with a warning (`:1479-1520`). Probed:
  - `EnumProperty(items=[])` reads `''`;
  - an item with identifier `""` reads `''`.
- **`ENUM_FLAG`.** Returns a `set` of identifiers (`bpy_rna.cc:1460-1474`), with at most
  `RNA_ENUM_BITFLAG_SIZE` = 32 items (`bpy_props.cc:2493-2498`, `blender/source/blender/makesrna/RNA_types.hh:270`).
  Assigning a `list` or a `str` to it raises `TypeError ... expected a set` (`bpy_rna.cc:1423`, probed).
- **Assignment.** Assigning an identifier that is not in the items raises `TypeError: ... enum "ZZZ" not found in
  ('X')`, also for dynamic items (probed). An `int` is rejected (`bpy_rna.cc:1392`, probed).

### 3.2 Static and dynamic, for the checker

The markers are in `gen:282-346` and `props/generated/props_enum/check_props_enum.py:16-33`.

| `items=` form | Marker | Static? |
| --- | --- | --- |
| list literal of tuple literals `[("A","A",""), ...]` | `Literal["A","B"]` (`e_list`) | static |
| tuple literal of tuple literals | `Literal["A","B"]` (`e_tuple`) | static |
| 4-tuples with numbers | `Literal["A","B"]` (`e_numbers`) | static |
| 5-tuples with icon and number | `Literal["A","B"]` (`e_icons`) | static |
| `None` separators among the tuples | `Literal["A","B"]` (`e_separator`) | static, `None` skipped |
| one item | `Literal["ONLY"]` (`e_single`) | static |
| `default="B"` / `default=5` | unchanged (`e_default`, `e_default_number`) | `default` does not affect the type |
| module-level constant, list or tuple (`ENUM_ITEMS`, `ENUM_ITEMS_TUPLE`) | `Literal["RED","GREEN"]`, `Literal["ONE","TWO"]` | static |
| list comprehension | `str` (`e_comprehension`) | dynamic for the checker |
| `def` callback | `str` (`e_callback`) | dynamic |
| `lambda` | `str` (`e_lambda`) | dynamic |
| `ENUM_FLAG` + static | `set[Literal["A","B"]]` (`e_flag`, `e_flag_default`, `e_flag_constant`) | |
| `ENUM_FLAG` + callback | `set[str]` (`e_flag_callback`) | |
| `options={"HIDDEN","SKIP_SAVE"}` | `Literal["A","B"]` (`e_other_options`) | other options do not change the type |

Two kinds of "dynamic" are mixed here:

- In Blender, only a `PyFunction` is dynamic. A comprehension is a static list built at import time.
- For the checker, anything whose identifiers it cannot read as string literals has to become `str`.

**Recommendation: the checker's rule.** The items are static if and only if the `items=` expression, after
following at most one `Name` to a module- or class-level assignment, is a list or tuple display whose every
element is one of:

- a tuple display with 3 to 5 elements whose first element is a string literal;
- the literal `None`.

The value type is then `Literal[<first elements>]`, with `None` elements and `""` identifiers dropped. Anything
else gives `str`:

- a comprehension, a call, a `def` or `lambda`, or a parameter;
- a constant that is reassigned, or one imported from another module, unless that is cheap to follow;
- a display with any non-literal identifier;
- an empty display.

The empty display is listed because `Literal[]` does not exist. At runtime the value of an empty display is
always `""`; `str` is the safe approximation.

**Recommendation: elements that fail at runtime.** A list element, or a tuple of the wrong length, fails when the
module is imported. Treat the items as dynamic (`str`) and leave the error to `blender-invalid-property` later.

### 3.3 The checker must read `items` from the AST, not from inferred types

ty probe (`reveal_type`):

| Expression | ty infers |
| --- | --- |
| `[("A", "A", ""), ("B", "B", "")]` | `list[tuple[str, str, str]]` |
| `(("A", "A", ""), ("B", "B", ""))` | `tuple[tuple[Literal["A"], Literal["A"], Literal[""]], ...]` |
| `ENUM_ITEMS` (module list constant) | `list[tuple[str, str, str]]` |
| `FINAL_ITEMS: Final = [...]` | `list[tuple[str, str, str]]` |
| `{"ENUM_FLAG"}`, or a constant holding it | `set[str]` |

ty promotes literals in list and set displays, so the inferred type of the most common forms (`e_list`,
`e_constant`, `options={...}`) has already lost the identifiers. Only tuple displays keep them.

**Recommendation:** read `items=` and `options=` from the AST of the call. For a `Name`, go to its definition's
assigned expression, and use the inferred type only for `type=` (section 4). Django reads keyword values through
`call.arguments.find_keyword(...)` plus `definition_expression_type`
(`ty-blender/ruff-blender/crates/ty_python_semantic/src/types/dedicated/django.rs:71-99`). The keyword lookup
transfers. For `items` and `options`, the expression has to be inspected structurally, not through its type.

**Recommendation: unreadable `options`.** When `options=` is present but not readable (not a set display, and not
a `Name` bound to one), the checker cannot tell whether `ENUM_FLAG` is set. Give `Unknown` rather than guess: a
wrong guess would report false `invalid-assignment`s. No marker covers this case.

---

## 4. `PointerProperty`

### 4.1 Targets

- `BPy_PointerProperty` resolves `type` through `pointer_type_from_py`. It accepts only a struct that
  `RNA_struct_is_a(ptype, RNA_PropertyGroup)` or `RNA_struct_is_ID(ptype)`; otherwise it raises `TypeError`
  (`bpy_props.cc:5512-5521`).
- The documented type is `type[PropertyGroup | ID]` (`bpy_props.cc:3516-3518`).
- Both stubs say the same: `B/bpy/props/__init__.pyi:24`; `F/bpy-stubs/props/__init__.pyi:773` (which adds
  `| None`).

The markers (`gen:351-409`, `props/generated/props_pointer/check_props_pointer.py:71-87`):

- `type=bpy.types.<ID>` for Object, Material, Image, Collection, Mesh, NodeTree, Text, World, Camera, Action and
  Scene gives `<ID> | None`. A narrowed `s.p_object.name` is a `str`.
- `type=Obj`, an import alias of `bpy.types.Object`, gives `Object | None`. This shows that `type=` must be read
  as a resolved class, not as a name.
- `type=<PropertyGroup subclass in the add-on>` gives `T`, and member access chains through it
  (`s.p_group.inner.value`).
- In `props/props_styles/future_annotations.py:11` (`from __future__ import annotations`), `type=` names a class
  defined further down. The marker `assert_type(f.later, PROPS_STYLES_Later)` is at
  `props/props_styles/check_props_styles.py:19`.

### 4.2 Why ID pointers can be `None` and PropertyGroup pointers cannot

- `property_pointer_get` (`blender/source/blender/makesrna/intern/rna_access.cc:4630-4667`):
  - For an ID target it returns the stored ID pointer, which may be null (`:4644-4647`).
  - For a PropertyGroup it returns the group IDProperty itself (`:4649-4650`). If none exists yet, it creates one
    (`PROP_IDPROPERTY && do_create`, `:4656-4665`).
- `pyrna_prop_to_py` turns a null pointer into `None` (`bpy_rna.cc:1588-1599`).

So a PropertyGroup pointer never reads as `None`. Probed: it reads as `P_Item` on a fresh scene, and an ID
pointer reads as `None`.

### 4.3 Read-only behaviour

- `RNA_def_property` gives `PROP_EDITABLE` to every type except `PROP_POINTER` and `PROP_COLLECTION`
  (`rna_define.cc:1319-1321`).
- `RNA_def_pointer_runtime` adds `PROP_EDITABLE` back only when the target is an ID (`rna_define.cc:4613-4615`).
- `bpy_prop_assign_flag` never sets `PROP_EDITABLE` from `options`; it can only clear it (`bpy_props.cc:445-461`).

So a PropertyGroup pointer stays read-only whatever `options` says. Probed: `PointerProperty(type=Item,
options={"HIDDEN"})` raises on assignment.

On `setattr`, `pyrna_struct_setattro` checks `RNA_property_editable_flag` and raises `AttributeError: bpy_struct:
attribute "grp" from "P_Values" is read-only` (`bpy_rna.cc:5182-5189`). Probed for the group pointer, the
collection, and a registered `Scene.p_values`.

The markers expect `invalid-assignment` for these:

- `s.p_group = None`, and `s.p_group = s.p_group`, so even the same value is rejected
  (`check_props_pointer.py:106-107`);
- `scene.<addon> = None` for each registered pointer (`gen:536`).

In the reference stubs, a read-only property is a getter-only `@property` (`gen:541-543`), and the oracle passes
with that on both generators (`.cache/typecheck-results/main/{builtin,fake-bpy-module}/oracle.md`: props_pointer
29 markers checked, 0 failures).

**Recommendation:** synthesise read-only attributes (PropertyGroup pointers, collections, `READ_ONLY`) as
getter-only properties, so that ty's normal property-assignment check reports `invalid-assignment`. Synthesise
the others as plain instance attributes of the value type.

### 4.4 Which `type=` values give which result

**Recommendation.** Use the inferred type of the `type=` expression (`definition_expression_type`), which handles
aliases and forward references:

- a class literal or `type[C]` where `C` is a subclass of `bpy.types.ID` gives `C | None`. This includes
  user-registered ID subclasses such as a custom `NodeTree`, because `RNA_struct_is_ID` holds for them;
- a class literal or `type[C]` where `C` is a subclass of `bpy.types.PropertyGroup` gives `C`, read-only;
- anything else (another `bpy_struct`, a union, an unknown) gives `Unknown`. A non-ID, non-PropertyGroup target is
  a runtime `TypeError`, left to `blender-unsupported-property-target` later.

---

## 5. `CollectionProperty`

### 5.1 What Blender does

- `type` must be a PropertyGroup subclass, or `TypeError` (`bpy_props.cc:5668-5673`).
- `RNA_def_collection_runtime` never sets `PROP_EDITABLE` (`rna_define.cc:4639-4653`), so the attribute is
  read-only.
- The value is a `pyrna_prop_CreatePyObject` (`bpy_rna.cc:1601-1602`).
- Probed:
  - the value's MRO is `bpy_prop_collection_idprop`, `bpy_prop_collection`, `bpy_prop`, `object`;
  - `.add()` returns `P_Item`;
  - assigning `[]` raises "is read-only".

The markers (`check_props_pointer.py:88-99`):

- `s.c_items` is `bpy_prop_collection_idprop[Item]`;
- `.add()`, `[0]`, `["name"]` and iteration give `Item`;
- `remove`, `move` and `clear` exist;
- `bpy_prop_collection[Item]` accepts the value;
- `s.c_items = []` is `invalid-assignment`.

### 5.2 What each generator's stubs can express

| | builtin (`B/bpy/types/__init__.pyi`) | fake-bpy-module (`F/bpy-stubs/types/__init__.pyi`) |
| --- | --- | --- |
| `bpy_prop_collection` | `Generic[_T]`, typed `__getitem__`/`__iter__` (`:148`, `:160-165`) | `bpy_prop_collection[_GenericType1]` (`:3673`) |
| `bpy_prop_collection_idprop` | **not generic**: `class bpy_prop_collection_idprop(bpy_prop_collection)`, `add() -> Any` (`:2463-2467`) | generic `bpy_prop_collection_idprop[_GenericType1](bpy_prop_collection)`, `add() -> _GenericType1`, own typed `__getitem__`, `__iter__`, `get`, `values` (`:3817-3920`) |

fake-bpy-module's class subclasses the bare `bpy_prop_collection`, so it inherits `bpy_prop_collection[Unknown]`.
Every member the markers use is redefined on the subclass, so this does not matter for them. The assignment to
`bpy_prop_collection[Item]` passes through the `Unknown` base.

The oracle baseline patches only the builtin gap. It makes the class
`bpy_prop_collection_idprop(bpy_prop_collection[_T], Generic[_T])` with `add() -> _T`
(`tests/typecheck/oracle/builtin/bpy.types.pyi:5-9`; reason in `tests/typecheck/oracle/README.md`). The map puts
fixing this in the stub generator, not the checker (#1, "Out of scope").

**Recommendation.** Build the value as the stub's `bpy_prop_collection_idprop` specialised with `T` when the class
is generic, and as the bare class when it is not. Do not substitute `bpy_prop_collection[T]` on builtin: it would
lose `add`/`remove`/`move`/`clear`, and it would turn the stub bug into a checker workaround that has to be
removed later.

---

## 6. Inputs the glue must read

### 6.1 Keywords that affect the value type

| Function | Keywords that matter | Ignored for the type |
| --- | --- | --- |
| `BoolProperty`, `IntProperty`, `FloatProperty` | `options` (`READ_ONLY`) | `name`, `description`, `translation_context`, `default`, `min`/`max`/`soft_*`, `step`, `precision`, `subtype`, `unit`, `override`, `tags`, callbacks |
| `StringProperty` | `subtype` (`BYTE_STRING`), `options` (`READ_ONLY`) | `default`, `maxlen`, `search`, `search_options`, the rest |
| `EnumProperty` | `items`, `options` (`ENUM_FLAG`, `READ_ONLY`) | `default`, the rest |
| `PointerProperty` | `type`, `options` (`READ_ONLY`) | `poll`, `update`, the rest |
| `CollectionProperty` | `type` | `options` (cannot make it writable), the rest |

The keyword lists come from the `_keywords[]` arrays: Bool `bpy_props.cc:3632-3648`, Enum `:5199-5215`, Pointer
`:5462-5474`, Collection `:5620-5630`, and the same pattern for Int, Float and String at `:4050`, `:4485`,
`:4939`.

### 6.2 Positional arguments: the stubs disagree, and Blender rejects both forms

**Blender.** In C, the parsers declare `attr` positional plus `type` (Pointer, Collection) or `items` (Enum)
positional-or-keyword, and everything else keyword-only (`"O&" "O" "|$"`, `bpy_props.cc:5216-5231`,
`:5475-5487`, `:5631-5641`). But a user never calls that signature. In the class-body form,
`bpy_prop_deferred_data_or_srna` runs first (`bpy_props.cc:3235-3283`):

- **One positional argument** is taken as `self`, the class to define the property on (`:3248-3258`):
  - `PointerProperty(Item)` and `CollectionProperty(Item)` raise `TypeError: ... missing required argument
    'attr'`.
  - `EnumProperty([...])` returns a `_PropertyDeferred` with **empty keywords**: the list is not a type, so
    `srna_from_self` returns null without an error (`bpy_rna.cc:9431-9446`). Registration then fails with
    `EnumProperty() missing required argument 'items'`.
  - All three probed.
- **Two or more positional arguments** raise `ValueError: <fn>: all args must be keywords` (`:3261-3266`,
  probed).

So **`type=` and `items=` work only as keywords**. The docstrings `PointerProperty(type, *, ...)`,
`EnumProperty(items, *, ...)` and `CollectionProperty(type, *, ...)` (`bpy_props.cc:5073-5075`, `:5396-5398`,
`:5564`) are misleading.

**Stubs:**

- builtin copies the docstrings: `CollectionProperty(type: ..., *, ...)`, `EnumProperty(items: ..., *, ...)`,
  `PointerProperty(type: ..., *, ...)` (`B/bpy/props/__init__.pyi:18`, `:19`, `:24`). Stock ty accepts a
  positional `type` / `items` there.
- fake-bpy-module makes all three keyword-only: `def CollectionProperty(*, type: ...)`, `def EnumProperty(*,
  items: ...)`, `def PointerProperty(*, type: ...)` (`F/bpy-stubs/props/__init__.pyi:300-302`, `:324-326`,
  `:771-773`). Stock ty reports a positional argument as a call error. fake-bpy-module matches the runtime.
- All the other property functions are keyword-only in both (`B/bpy/props/__init__.pyi:16-26`;
  `F/bpy-stubs/props/__init__.pyi:161-162`, `:443-444`, `:612-613`, `:810-811`).

**Recommendation.** Read only keywords (`call.arguments.find_keyword("type" | "items" | "options" | "subtype")`),
the same on both generators. When `type=` or `items=` is missing (including when it was passed positionally):

- Pointer and Collection give `Unknown`;
- Enum gives `str`, or `set[str]` with a readable `ENUM_FLAG`.

Keep the takeover (no `invalid-type-form`) either way. The positional form is a runtime error, but reporting it
belongs to `blender-invalid-property`. No marker uses a positional argument.

### 6.3 Arguments that are not literals

| Argument | Read from | If not readable |
| --- | --- | --- |
| `type=` | inferred type (`type[C]` / class literal); aliases, `bpy.types.X` attribute access and `__future__` forward references all resolve | `Unknown` |
| `items=` | AST: list/tuple display, or one `Name` hop to such a display (section 3.3) | `str` (`set[str]` with `ENUM_FLAG`) |
| `options=` | AST: set display of string literals, or one `Name` hop | Enum: `Unknown` (flag unknown). Others: assume writable |
| `subtype=` (String only) | inferred type; a string literal reads as `Literal["BYTE_STRING"]` (ty probe) | `str` |

These are all recommendations. The markers only cover literal arguments, a module constant for `items`, and an
import alias for `type`.

---

## 7. Markers a stub bug blocks

These follow from section 5.2 and from the recorded results (`tests/typecheck/expected/builtin/main.txt:1033`,
`:1038` already record `not-subscriptable` on the two `bpy_prop_collection_idprop[...]` lines).

**builtin: 7 markers cannot pass** while `bpy_prop_collection_idprop` is not generic. All are in
`props/generated/props_pointer/check_props_pointer.py`:

| Line | Marker | Why |
| --- | --- | --- |
| 88 | `assert_type(s.c_items, bpy_prop_collection_idprop[PROPS_POINTER_Item])` | `not-subscriptable` on the marker line; the asserted type is Unknown |
| 89 | `assert_type(s.c_items.add(), PROPS_POINTER_Item)` | `add() -> Any` |
| 90 | `assert_type(s.c_items[0], PROPS_POINTER_Item)` | base `bpy_prop_collection` unspecialised, so `_T` is Unknown |
| 91 | `assert_type(s.c_items["name"], PROPS_POINTER_Item)` | same |
| 93 | `assert_type(entry, PROPS_POINTER_Item)` (in the `for`) | same, via `__iter__` |
| 98 | `assert_type(s.c_inner, bpy_prop_collection_idprop[PROPS_POINTER_Inner])` | `not-subscriptable` |
| 99 | `assert_type(s.c_inner.add().value, int)` | `add() -> Any` |

On builtin, lines 94-97 (`remove`, `move`, `clear`, and the `bpy_prop_collection[...]` annotation) and the
read-only marker at 108 (`s.c_items = []`) can pass.

**fake-bpy-module: none** in the basic-property add-ons (`props_scalar`, `props_enum`, `props_pointer`,
`props_hosts`, `props_styles`). Its known stub bug, the non-generic `bpy_prop_array`
(`F/bpy-stubs/types/__init__.pyi:3658`; patched in `tests/typecheck/oracle/fake-bpy-module/bpy.types.pyi:3-14`),
affects only `props_vector`, which is out of scope here.

**Not a stub bug, but expected to fail until it is fixed in the generator:**
`props/generated/props_scalar/check_props_scalar.py:74` (`assert_type(s.s_byte_string, str)`), on both
generators. If the checker gives the runtime-correct `bytes`, this marker fails, and so does the matching
reference stub. Fix `gen:119` (section 2.2) before or with the build ticket.

**Next to this ticket (property hosts, not value types):** `assert_type(op.properties.value, int)`
(`props/props_hosts/check_props_hosts.py:18`) needs the checker to type `Operator.properties` as the operator's
own properties:

- builtin's `OperatorProperties` has no `__getattr__` (`B/bpy/types/__init__.pyi:19276-19281`), so the line also
  records `unresolved-attribute` (`tests/typecheck/expected/builtin/main.txt:1670`);
- fake-bpy-module's has `__getattr__ -> Any` (`F/bpy-stubs/types/__init__.pyi:86150`), so the
  marker fails as a plain `type-assertion-failure` (`tests/typecheck/expected/fake-bpy-module/main.txt:1645`).

This is not a stub bug: neither stub can know the add-on's properties.

---

## 8. Summary of recommendations

1. Value types as in section 1, with `StringProperty(subtype="BYTE_STRING")` giving `bytes`. Fix `gen:119` and
   its reference stub to match.
2. Make these read-only (getter-only synthesised property, so that assignment is `invalid-assignment`):
   PropertyGroup pointers, collections, and anything with `options={"READ_ONLY"}`. Add a `READ_ONLY` marker.
3. Static enum items: a list/tuple display (or one `Name` hop to one) of tuple displays with string-literal
   identifiers, plus `None` separators. Everything else gives `str`. Read `items` and `options` from the AST,
   because ty's inferred types promote list and set literals to `str`.
4. `type=` comes from the inferred type: an ID subclass gives `T | None`, a PropertyGroup subclass gives `T`
   (read-only), anything else gives `Unknown`.
5. Read keywords only, on both generators. A positional `type`/`items` is a runtime error (builtin's stub wrongly
   accepts it); fall back to `Unknown` / `str`, and leave reporting to the later rules.
6. Specialise the stub's own `bpy_prop_collection_idprop` when it is generic. On builtin, expect the 7 failures in
   section 7 until the generator is fixed.
