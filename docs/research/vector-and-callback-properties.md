# Vector properties and callback `self`: where their types come from

Research note, 2026-11-06, for [#25](https://github.com/taway1450/blender-extension-developer-suite/issues/25)
(map #21). Trimmed on 2026-11-18 to the rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings.

It answers what value type a `FloatVectorProperty` / `IntVectorProperty` / `BoolVectorProperty` gets from its
`subtype=` and `size=`, what a write to such a property accepts, and how a callback (`update`, `get`, `set`,
`poll`, `items`, ...) learns that its `self` is the declaring class. It builds on
[basic-property-value-types.md](basic-property-value-types.md) (#7) and
[property-annotation-takeover.md](property-annotation-takeover.md) (#4).

Conventions:

- Paths are relative to the main repo root. `blender/` is the Blender source (`main`, read on 2026-11-06);
  `ty/` is `ty-blender/ruff-blender/crates/ty_python_semantic/src/types/` (read at the fork commit of that day).
- Every fact below is read from source. Nothing was probed in Blender or ty for this note; the places where a
  probe would settle a doubt are marked **Unverified**.

---

## 1. The vector value table

### 1.1 What Blender does

Reading an array property goes `pyrna_prop_to_py` → `pyrna_py_from_array` → `pyrna_math_object_from_array`
(`blender/source/blender/python/intern/bpy_rna.cc:1540-1541`, `bpy_rna_array.cc:977-988`). The mathutils wrapping
is decided at `bpy_rna.cc:827-971`:

- Only `PROP_FLOAT` arrays are wrapped. An int array is wrapped only when `PROP_THICK_WRAP`, and a bool array never
  (`:843-856`). Python-defined properties are never thick: `RNA_def_property` sets `PROP_THICK_WRAP` only on pointers
  (`blender/source/blender/makesrna/intern/rna_define.cc:1290-1293`), and they are never `PROP_DYNAMIC` (`:838-840`).
  So **Int and Bool vectors are always `bpy_prop_array`**, whatever their subtype.
- A float array is considered when `totdim == 1`, or `totdim == 2` with subtype `MATRIX` (`:861`). Then, by subtype,
  where `len` is the *total* length (`RNA_property_array_length`, `:842`):

| Subtype | Condition | Value |
| --- | --- | --- |
| `COORDINATES`, `TRANSLATION`, `DIRECTION`, `VELOCITY`, `ACCELERATION`, `XYZ`, `XYZ_LENGTH` (`PROP_ALL_VECTOR_SUBTYPES`, `:817-823`) | `2 <= len <= 4` | `Vector` (`:868-880`) |
| `MATRIX` | `len == 16` | `Matrix` 4×4 (`:882-893`) |
| `MATRIX` | `len == 9` | `Matrix` 3×3 (`:895-906`) |
| `EULER` or `QUATERNION` | `len == 3` | `Euler` (`:910-929`) |
| `EULER` or `QUATERNION` | `len == 4` | `Quaternion` (`:930-942`) |
| `COLOR`, `COLOR_GAMMA` | `len == 3` | `Color` (`:945-958`) |
| anything else (`NONE`, `AXISANGLE`, `LAYER`, `LAYER_MEMBER`, other lengths, other dimensions) | | `bpy_prop_array` (`:965-974`) |

The comment above the macro says `PROP_NONE` counts as a vector subtype (`:813-815`), but the macro does not list it:
`subtype="NONE"` gives an array.

A multi-dimensional array is a `bpy_prop_array` whose items are `bpy_prop_array`s one dimension down, down to the
scalars (`bpy_rna_array.cc:928-970`). The inner arrays are never mathutils objects.

Quirks that follow from "`len` is the total length":

- `MATRIX, size=9` reads as a 3×3 `Matrix`.
- Any 2-D `MATRIX` with 9 or 16 items is a `Matrix`, so `size=(2, 8)` reads as a 4×4 `Matrix` and `size=(1, 9)` as a
  3×3 one. `size=(2, 2)` (4 items) is a nested array.
- `size=(4,)` is one-dimensional, the same as `size=4`.

### 1.2 What `size=` and `subtype=` accept

- `size=` (`bpy_props.cc:531-591`): an exact `int` in `[1, 32]`, or any sequence of 1 to 3 ints, each in `[1, 32]`
  (`RNA_STACK_ARRAY` = 32, `blender/source/blender/makesrna/RNA_types.hh:274`; `RNA_MAX_ARRAY_DIMENSION` = 3,
  `RNA_define.hh:29`). Anything else is a `TypeError` at registration.
- The default size is 3 (`bpy_props.cc:4674`). `default=` never sets the size: a default of another length is an
  error (`bpy_prop_array_from_py_with_dims`, `:600-613`).
- `subtype=` takes the names of `rna_enum_property_subtype_number_array_items` (`rna_rna.cc:88-104`, `:122-127`),
  with `NONE` as the default (`bpy_props.cc:4689-4691`). `COORDINATES` is `PROP_COORDS`.

An unreadable or out-of-range `size=` / `subtype=` gives `Any`: for Int and Bool an unknown size decides the
nesting too. The element `float` is what the annotation `float` means (`int | float`), so `bpy_prop_array[float]`
in user code matches it.

## 2. What a write accepts

### 2.1 What Blender does

Assignment goes through `pyrna_py_to_array` → `validate_array` (`bpy_rna_array.cc:320-393`):

- A mathutils `Matrix` is accepted only by a 2-D float property whose dimensions match (`:330-373`). A `Matrix`
  assigned to a 1-D `size=16` `MATRIX` property raises `ValueError: ... matrix assign array with 1 dimensions`, even
  though that property *reads* as a `Matrix`. **Unverified:** a probe would confirm it.
- Anything else must be a sequence, nested once per dimension, with exactly the declared length at every level
  (`validate_array_type`, `:76-176`). The top level goes through `PySequence_Fast`, so any iterable works there; inner
  levels need `PySequence_Size`. A `Vector`, `Color`, `Euler`, `Quaternion` or `bpy_prop_array` is a sequence at
  runtime, so it can be assigned.
- A `str` is a sequence of `str`, and is rejected on the item type. A scalar is rejected.

### 2.2 Why the write type differs from the value type

The value type cannot be the write type: `s.f_translation_3 = (1.0, 1.0, 1.0)` must pass while the attribute reads
as `Vector`. So a vector's write type is `Sequence[E]` nested once per dimension, plus the value type itself except
a `Matrix` on a 1-D property. The value type is needed because neither stub makes all of these values a
`Sequence`: builtin's mathutils classes subclass `Sequence[float]`, but its `bpy_prop_array` does not, and
fake-bpy-module's mathutils classes subclass nothing.

Using `Sequence` rather than `Iterable` at the top level rejects a generator expression, which Blender accepts. That
is accepted, because it keeps the nested and the flat case the same shape.

## 3. Callback `self`

### 3.1 What Blender does

- Every Python callback of a property gets `self = pyrna_struct_as_instance(ptr)` (`bpy_props.cc:421-443`, used at
  `:731`, `:780`, ... for update, get, set, the transforms, poll and items). `ptr` is the struct that owns the
  property, so `self` is an instance of the class that holds it:
  - the PropertyGroup subclass;
  - the operator, through the instance that `rna_Operator_instance` keeps (`blender/source/blender/makesrna/intern/rna_wm.cc:1971-1974`);
  - the ID type, for a Registered property.
  For a mixin, it is the concrete class that inherited the annotation, which is a subtype of the declaring class.
  So **the declaring class is a sound type for `self`**.
- `poll(self, candidate)`: the candidate is `pyrna_struct_as_instance(&candidate)` (`bpy_props.cc:2216-2235`), an
  instance of the `type=` class (never `None`). `poll` is allowed for ID and PropertyGroup targets alike
  (`bpy_props.cc:5516-5555`: the target check, then `bpy_prop_callback_check(poll_fn, "poll", 2)`, with no ID-only condition).
- What the other parameters and return values are (int for Enum `get`/`set`, nested tuples for vector `set`,
  `Context | None` for `items`, ...) is in the conversions at `bpy_props.cc:712-2420`. Both stubs encode these
  already, so the checker does not need its own copy of them (3.3).
- **`get=` without `set=` makes the property read-only.** `RNA_def_property_*_funcs_runtime` clears `PROP_EDITABLE`
  when there is a getter and no setter (`rna_define.cc:3133-3146`, and the same for the other types at `:3166-3177`,
  `:3241-3255`, `:3277-3291`, `:3357-3371`).

### 3.2 What the stubs and ty do

- **builtin** types every callback's first parameter as `bpy_struct`, and the `poll` candidate as `ID`. A callback
  annotated `self: Settings` is not assignable, because of parameter contravariance.
- **fake-bpy-module** makes each function generic in the self type (`def IntProperty[_GenericType1: bpy_struct](...,
  update: Callable[[_GenericType1, Context], None] | None, ...)`). `poll` is `Callable[[_GenericType1,
  _GenericType2], bool]` with `_GenericType2: ID`, unrelated to `type=`. An annotated `def` callback then solves the
  type variable and passes, so a `Material` candidate on an `Object` pointer is not reported.
- **ty** gives a lambda's parameters the parameter types of the `Callable` in its type context
  (`ty/infer/builder.rs:9010-9032`; the body reads them back through `annotated_lambda_parameter_type`,
  `ty/infer/builder/function.rs:1477-1496`). For a call argument, the context is the callee parameter's annotated type
  (`ty/infer/builder.rs:6476-6520`). That is why builtin types a lambda's `self` as `bpy_struct`. On fake-bpy-module,
  the parameter is an unsolved type variable, which `has_provisional_marker` turns into `Unknown`.
- The type context does not wait for other arguments to solve a type variable. A context specialisation comes only
  from the call's own expected type (`argument_type_context_specialization`, `ty/infer/builder.rs:6430-6450`). So
  making `poll` generic in the `type=` class would not type a `poll` lambda's candidate.

### 3.3 The mechanism: rewrite the callee's signature before the call is inferred

Two options were weighed:

- **Check the callback against an expected `Callable` after inference.** This cannot type a lambda's body: the
  lambda is already inferred, with `bpy_struct` or `Unknown` parameters, by the time the check runs. It also leaves
  the stub's own, wrong `invalid-argument-type` in place, which would then need suppressing. Rejected.
- **A context-sensitive hook.** This is the one that works, and ty already has the context mechanism. The hook only
  has to change what the context *is*.

So the annotation takeover infers the call against a rewritten callee: each callback's first parameter becomes the
declaring class, and `poll`'s second becomes the `type=` class (main: `declaration_callee` in
`ty/dedicated/blender/callbacks.rs`). Lambdas then get their types from ty's own `Callable` context, and a `def`
callback is checked against it.

Why keep the stub's other parameter and return types instead of a hand-written table:

- both stubs already encode Blender's conversions (Enum `get -> int`, `set(self, int)`, `items` with
  `Context | None`, vector `get -> Sequence[...]`);
- it keeps generator-specific details in the stubs, where map #1 put stub bugs.

So a wrong callback signature (`-> int` for a String getter, `value: str` for an Int setter) stays an
`invalid-argument-type`.

### 3.4 Open: callbacks of Registered properties

`bpy.types.Scene.my_value = IntProperty(update=lambda self, context: ...)` is an ordinary value-expression call, not
the annotation takeover. On builtin, a `def` callback annotated `self: Scene` is then a false
`invalid-argument-type`, and a lambda's `self` is `bpy_struct`. The same rewrite fits there, with the declaring
class being the class of the assignment target (`bpy.types.Scene`). But it needs a hook in ordinary call
inference, which is an upstream file, and the owner is only known from the enclosing assignment. The same question
applies to a declaration built outside any class, such as a module-level `prop = IntProperty(update=...)` in a
wrapper: `self` is not known where the call is written.
