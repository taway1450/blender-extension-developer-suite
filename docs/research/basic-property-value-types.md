# Basic property declarations: the value type each one gets

Research note, 2026-11-05, for [#7](https://github.com/taway1450/blender-extension-developer-suite/issues/7)
(map #1). Trimmed on 2026-11-18 to the rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings.

It answers what value type each basic property declaration (Int / Float / Bool / String, Enum, Pointer,
Collection) gets, and why. Vector subtypes and callbacks are in
[vector-and-callback-properties.md](vector-and-callback-properties.md); the `blender-*` property rules in
[property-rules.md](property-rules.md).

Conventions:

- Every fact has a `path:line` source. `blender/` is the Blender source (`main`, read on 2026-11-05).
- *Probed* means run on 2026-11-05 in Blender 5.4.0 Alpha (built 2026-11-02), in background mode with a
  throwaway script. *ty probe* means a stock ty build (`ty 0.0.97`) on a scratch file.

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
(`bpy_rna.cc:5182-5189`, probed). Section 4.2 explains it.

---

## 2. Int / Float / Bool / String

### 2.1 What Blender does

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

Assignment coercion, for the record (`bpy_rna.cc:1686-1900`, probed):

- `bool` accepts `True`/`False` or the ints `0`/`1` and rejects other ints (`:1720-1734`).
- `int` accepts anything `PyLong_AsLong` takes, which includes `bool`, and rejects `float` (`:1747-1767`).
- `float` accepts anything `PyFloat_AsDouble` takes: int, bool, float (`:1777-1789`).
- `str` rejects `None`, because runtime string properties get `PROP_NEVER_NULL` (`rna_define.cc:1281-1288`,
  `bpy_rna.cc:1806-1826`).

ty's `int` / `float` / `bool` / `str` types already model this, apart from `bool` accepting a literal `0`/`1`.

### 2.2 `options`

`options` takes members of `rna_enum_property_flag_items` (`rna_rna.cc:189-231`):

- `READ_ONLY`, `HIDDEN`, `SKIP_SAVE`, `SKIP_PRESET`, `ANIMATABLE`, `LIBRARY_EDITABLE`, `PROPORTIONAL`,
  `TEXTEDIT_UPDATE`, `OUTPUT_PATH`, `PATH_SUPPORTS_BLEND_RELATIVE`, `SUPPORTS_TEMPLATES`;
- plus `ENUM_FLAG`, for `EnumProperty` only (`rna_rna.cc:233-251`).

None of these changes the value type. One changes writability:

- **`READ_ONLY`** clears `PROP_EDITABLE`. `bpy_prop_assign_flag` inverts the bit (`bpy_props.cc:445-461`;
  comment at `rna_rna.cc:190-200`).
- Probed: `IntProperty(options={"READ_ONLY"})`, `PointerProperty(type=Object, options={"READ_ONLY"})` and an
  `ENUM_FLAG` enum with `READ_ONLY` all raise `AttributeError ... is read-only` on assignment. Reading still works.

So `READ_ONLY` is the only option with a type-visible effect, and it makes the attribute read-only the same
way as a PropertyGroup pointer (section 4.2).

(Also read-only: a `get=` callback without `set=` makes the property read-only. Probed: `IntProperty(get=...)`
raises on assignment.)

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

Two kinds of "dynamic" are mixed here:

- In Blender, only a `PyFunction` is dynamic. A comprehension is a static list built at import time.
- For the checker, anything whose identifiers it cannot read as string literals has to become `str`.

The checker's rule: the items are static if and only if the `items=` expression, after following a `Name` to
its assignment, is a list or tuple display whose every element is one of:

- a tuple display with 3 to 5 elements whose first element is a string literal;
- the literal `None`.

The value type is then `Literal[<first elements>]`, with `None` elements and `""` identifiers dropped. Anything
else gives `str`: a comprehension, a call, a `def` or `lambda`, a parameter, a display with any non-literal
identifier, or an empty display. The empty display is listed because `Literal[]` does not exist. At runtime the
value of an empty display is always `""`; `str` is the safe approximation.

Elements that fail at runtime (a list element, a tuple of the wrong length) make the items dynamic (`str`); the
error is left to `blender-invalid-property`.

### 3.3 The checker must read `items` from the AST, not from inferred types

ty probe (`reveal_type`):

| Expression | ty infers |
| --- | --- |
| `[("A", "A", ""), ("B", "B", "")]` | `list[tuple[str, str, str]]` |
| `(("A", "A", ""), ("B", "B", ""))` | `tuple[tuple[Literal["A"], Literal["A"], Literal[""]], ...]` |
| `ENUM_ITEMS` (module list constant) | `list[tuple[str, str, str]]` |
| `FINAL_ITEMS: Final = [...]` | `list[tuple[str, str, str]]` |
| `{"ENUM_FLAG"}`, or a constant holding it | `set[str]` |

ty promotes literals in list and set displays, so the inferred type of the most common forms (a list display,
a module constant, `options={...}`) has already lost the identifiers. Only tuple displays keep them. So
`items=` and `options=` are read from the AST of the call, and the inferred type is used only for `type=`
(section 4), where it handles aliases and forward references.

When `options=` is present but not readable (not a set display, and not a `Name` bound to one), the checker
cannot tell whether `ENUM_FLAG` is set. It gives `Unknown` rather than guess: a wrong guess would report false
`invalid-assignment`s.

---

## 4. `PointerProperty`

### 4.1 Targets

`BPy_PointerProperty` resolves `type` through `pointer_type_from_py`. It accepts only a struct that
`RNA_struct_is_a(ptype, RNA_PropertyGroup)` or `RNA_struct_is_ID(ptype)`; otherwise it raises `TypeError`
(`bpy_props.cc:5512-5521`). `RNA_struct_is_ID` holds for user-registered ID subclasses such as a custom
`NodeTree`, so those give `T | None` too.

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
collection, and a registered `Scene.p_values`. Even assigning the same value back is rejected.

---

## 5. `CollectionProperty`

- `type` must be a PropertyGroup subclass, or `TypeError` (`bpy_props.cc:5668-5673`).
- `RNA_def_collection_runtime` never sets `PROP_EDITABLE` (`rna_define.cc:4639-4653`), so the attribute is
  read-only.
- The value is a `pyrna_prop_CreatePyObject` (`bpy_rna.cc:1601-1602`).
- Probed:
  - the value's MRO is `bpy_prop_collection_idprop`, `bpy_prop_collection`, `bpy_prop`, `object`;
  - `.add()` returns `P_Item`;
  - assigning `[]` raises "is read-only".

---

## 6. Positional arguments: Blender rejects them

In C, the parsers declare `attr` positional plus `type` (Pointer, Collection) or `items` (Enum)
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
`:5564`) are misleading. The builtin stub generator copies them and accepts a positional `type` / `items`;
fake-bpy-module makes all three keyword-only, which matches the runtime.

The checker therefore reads keywords only, the same on both generators. When `type=` or `items=` is missing
(including when it was passed positionally), Pointer and Collection give `Unknown` and Enum gives `str` (or
`set[str]` with a readable `ENUM_FLAG`). The takeover (no `invalid-type-form`) stays either way; reporting the
positional form belongs to `blender-invalid-property`.
