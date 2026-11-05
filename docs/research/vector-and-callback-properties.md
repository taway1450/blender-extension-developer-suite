# Vector properties and callback `self`: where their types come from

Research note, 2026-11-06, for [#25](https://github.com/taway1450/blender-extension-developer-suite/issues/25) on the
map [#21](https://github.com/taway1450/blender-extension-developer-suite/issues/21). It answers four questions:

- what value type a `FloatVectorProperty` / `IntVectorProperty` / `BoolVectorProperty` gets from its `subtype=` and
  `size=`;
- what a write to such a property accepts;
- how a callback (`update`, `get`, `set`, `poll`, `items`, ...) learns that its `self` is the declaring class;
- which of the in-scope failing markers a stub bug blocks, and which generator fix unblocks them.

It builds on [#7](https://github.com/taway1450/blender-extension-developer-suite/issues/7) (value types of basic
declarations, `docs/research/basic-property-value-types.md` on `research/basic-property-value-types`),
[#4](https://github.com/taway1450/blender-extension-developer-suite/issues/4) (the annotation takeover) and
[#10](https://github.com/taway1450/blender-extension-developer-suite/issues/10) (Property members). Their decisions
hold.

Conventions:

- Paths are relative to the main repo root:
  - `blender/` is the Blender source (`main`);
  - `B/` is `.cache/bpy-stubs-builtin/main/` (builtin generator), `F/` is `.cache/bpy-stubs/main/` (fake-bpy-module);
  - `ty/` is `ty-blender/ruff-blender/crates/ty_python_semantic/src/types/`;
  - `gen` is `scripts/feature_generators/properties.py`;
  - `props/` is `tests/typecheck/features/properties/`;
  - `exp-B` / `exp-F` are `tests/typecheck/expected/{builtin,fake-bpy-module}/main.txt`.
- Every fact below is read from source. Nothing was probed in Blender or ty for this note (the machine-wide
  task queue was saturated); the places where a probe would settle a doubt are marked **Unverified**.
- My own recommendations are marked **Recommendation**.

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
`subtype="NONE"` gives an array. The markers agree with the code.

A multi-dimensional array is a `bpy_prop_array` whose items are `bpy_prop_array`s one dimension down, down to the
scalars (`bpy_rna_array.cc:928-970`). The inner arrays are never mathutils objects.

Quirks that follow from "`len` is the total length" and that no marker covers:

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

### 1.3 What the markers say

`props/generated/props_vector` is generated by `gen:154-294`, with the value function `float_vector_type`
(`gen:176-191`). It covers the 16 subtypes × 8 sizes (`None`, 2, 3, 4, 16, (2, 2), (3, 3), (4, 4)), plus Int and
Bool vectors. I compared it with section 1.1: **every value marker matches the C code.** The reference stubs'
setters do not, see 2.2.

### 1.4 The checker's rule

**Recommendation.** Extend `PropertyDeclaration` (`ty/dedicated/blender/properties.rs:74-87`) with the vector shape,
read in `from_call` (`:98-123`), and replace the `Type::unknown()` arm of `value_type` (`:182-184`):

1. Read `size=` into dimensions:
   - missing: `[3]`;
   - an int: `[n]`;
   - a tuple or list of ints: those ints.
   Read it from the syntax first (an int literal, or a tuple/list display of int literals, as `items=` is read today),
   and else from the inferred type (`Literal[4]`, or a tuple of int literals, which covers a `Final` constant). Values
   out of range (outside `[1, 32]`, or more than 3 dimensions) are a registration error: treat them as unreadable and
   leave the report to `blender-invalid-property` ([#27](https://github.com/taway1450/blender-extension-developer-suite/issues/27)).
2. Read `subtype=` as a string literal, or a `Literal[...]` str from the inferred type. Missing means `NONE`. It
   matters only for `FloatVectorProperty`.
3. **Unreadable** `size=` (any vector kind) or `subtype=` (`FloatVectorProperty`) gives `Any`, the fallback that
   [#26](https://github.com/taway1450/blender-extension-developer-suite/issues/26) already names. For Int and Bool
   an unknown size gives `Any` too, because it decides the nesting.
4. Otherwise, with `E` the element type and `len` the product of the dimensions:
   - FloatVector, 1 dimension, or 2 dimensions with subtype `MATRIX`: the table in 1.1, where a mathutils class gives
     an instance of `mathutils.<Class>`, resolved like `bpy_types_class` (`properties.rs:224-243`) but in module
     `mathutils`. If the module or class does not resolve, give `Unknown`.
   - Otherwise, `E` wrapped in one `bpy_prop_array[...]` per dimension: `bpy_prop_array[bpy_prop_array[E]]` for 2.
5. `E` is `bool` for Bool, `int` for Int, and for Float **what the annotation `float` means**
   (`KnownUnion::Float`, as the scalar arm already does at `properties.rs:130-131`). The marker writes
   `bpy_prop_array[float]`, which ty reads as `bpy_prop_array[int | float]`. `bpy_prop_array[float]` specialised
   with the class `float` alone would fail `assert_type`.
6. Build `bpy_prop_array[E]` like the collection arm does (`properties.rs:165-181`): specialise the stub's class when
   it is generic, use it as it is when it is not. Do not fall back to `Sequence` or `tuple` on a non-generic stub.

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

### 2.2 What the markers say

The `assignments()` markers (`props/generated/props_vector/check_props_vector.py`, from `gen:204-236`):

- tuples of the right shape everywhere;
- a list, `[1.0, 2.0, 3.0]`;
- `Vector((1.0, 2.0, 3.0))` into a `TRANSLATION` vector;
- rejected: `"xyz"` and `1.0` into a float array, `("1", "1")` into an int array.

Today these three rejections are `unused-ignore-comment`s on both generators (exp-B, exp-F), because the value type
is `Unknown`.

The reference stubs' setter for every `Matrix` field is `Matrix | Sequence[Sequence[float]] | Sequence[float]`
(`gen:215-216`). That is looser than Blender in both directions: a 1-D `size=16` property rejects a `Matrix`, and a
2-D `(4, 4)` property rejects a flat sequence of 16. No marker exercises either case, so nothing fails.
**Recommendation:** in `gen:212-219`, make it `Sequence[float]` for a 1-D `Matrix` field and
`Matrix | Sequence[Sequence[float]]` for a 2-D one.

### 2.3 The write type, and where it goes

The value type cannot be the write type: `s.f_translation_3 = (1.0, 1.0, 1.0)` must pass while the attribute reads as
`Vector`. **Recommendation:** add `PropertyDeclaration::write_type`:

- for a vector, `S | V`, where:
  - `S` is `Sequence[E]` nested once per dimension;
  - `V` is the value type, *except* when the property is 1-D and its value is a `Matrix`.

  `V` is needed because neither stub makes all of these values a `Sequence`: builtin's mathutils classes subclass
  `Sequence[float]` / `Sequence[Sequence[float]]` (`B/mathutils/__init__.pyi:7`, `:58`, `:89`, `:181`, `:246`), but
  its `bpy_prop_array` does not (`B/bpy/types/__init__.pyi:2450`), and fake-bpy-module's mathutils classes subclass
  nothing (`F/mathutils-stubs/__init__.pyi:39`, `:312`, `:466`, `:985`, `:1330`).
- for every other property, the value type, as today.

Apply it in the existing store hook `on_store` (`ty/dedicated/blender/member.rs:331-366`), which already wraps every
attribute write (`ty/infer/builder/attribute_assignment.rs:44-50`). Today it rewrites only the `SetAttr` arm, for
Registered properties. Add the case where ty found the Annotated property's declared member (an
`AssignableTo { ty: <value type> }` requirement) and the property's write type differs: swap in the write type. Then
both origins use one rule, there is no new upstream hook, and the read-only check after it (`check_property_write`)
is untouched.

Using `Sequence` rather than `Iterable` at the top level rejects a generator expression, which Blender accepts. I
consider that acceptable, because it keeps the nested and the flat case the same shape.

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
  `:3241-3255`, `:3277-3291`, `:3357-3371`). #7 recorded this (probed then: `IntProperty(get=...)` raises on
  assignment) and left it to this ticket.

### 3.2 What the stubs and ty do today

- **builtin** types every callback's first parameter as `bpy_struct`, and the `poll` candidate as `ID`
  (`B/bpy/props/__init__.pyi:16-26`). A callback annotated `self: PROPS_CALLBACKS_Settings` is not assignable, because
  of parameter contravariance. This gives the `invalid-argument-type` on `count`, `ratio`, `target`, `mode` and
  `lambda_update` in exp-B.
- **fake-bpy-module** makes each function generic in the self type (`def IntProperty[_GenericType1: bpy_struct](...,
  update: Callable[[_GenericType1, Context], None] | None, ...)`, `F/bpy-stubs/props/__init__.pyi:612-637`). `poll`
  is `Callable[[_GenericType1, _GenericType2], bool]` with `_GenericType2: ID`, unrelated to `type=` (`:771-783`).
  An annotated `def` callback then solves the type variable and passes, so `wrong_poll` (a `Material` candidate on an
  `Object` pointer) is not reported (`unused-ignore-comment` in exp-F).
- **ty** gives a lambda's parameters the parameter types of the `Callable` in its type context
  (`ty/infer/builder.rs:9010-9032`; the body reads them back through `annotated_lambda_parameter_type`,
  `ty/infer/builder/function.rs:1477-1496`). For a call argument, the context is the callee parameter's annotated type
  (`ty/infer/builder.rs:6476-6520`). That is why builtin types a lambda's `self` as `bpy_struct`, giving
  `type-assertion-failure` / `unresolved-attribute`. On fake-bpy-module, the parameter is an unsolved type variable,
  which `has_provisional_marker` turns into `Unknown`, giving `type-assertion-failure`.
- The type context does not wait for other arguments to solve a type variable. A context specialisation comes only
  from the call's own expected type (`argument_type_context_specialization`, `ty/infer/builder.rs:6430-6450`). So
  making `poll` generic in the `type=` class would not type a `poll` lambda's candidate.

### 3.3 The mechanism: rewrite the callee's signature before the call is inferred

The question offered two options:

- **Check the callback against an expected `Callable` after inference.** This cannot type a lambda's body: the
  lambda is already inferred, with `bpy_struct` or `Unknown` parameters, by the time the check runs. It also leaves
  the stub's own, wrong `invalid-argument-type` in place, which would then need suppressing.
- **A context-sensitive hook.** This is the one that works, and ty already has the context mechanism. The hook only
  has to change what the context *is*.

**Recommendation.** In the annotation takeover (`ty/infer/builder/type_expression/blender.rs:21-34`, a fork-only
file, so no upstream edit), pass `infer_call_expression_impl` a rewritten callee instead of the stub's function:

```rust
let callee = self.infer_callee(&call.func);
let bound = blender::declaration_callee(db, env, self.scope(), callee, call, /* target */ ...);
self.infer_call_expression_impl(call, bound, TypeContext::default());
// annotation_value_type(..., callee, ...) keeps the original callee, which identifies the function
```

`declaration_callee` (new, in `dedicated/blender/properties.rs` or a new `callbacks.rs`) returns the callee unchanged
unless `callee` is one of the ten `bpy.props` functions and `S`, the declaring class, is known. `S` is the instance
type of the class whose body is `self.scope()` (`nearest_enclosing_class`, `ty/infer.rs:1020-1032`). Otherwise it
returns a `Type::Callable` built from the stub's signature, with the generic context dropped and these parameters
rewritten:

- `update`, `get`, `set`, `get_transform`, `set_transform`, `search`, and the callable arm of `items`: in every
  `Callable[[P0, ...], R]` arm of the parameter's annotated type, `P0` becomes `S`. The other parameters and `R` stay
  as the stub has them.
- `poll`: `P0` becomes `S`, and `P1` becomes `T`, the instance type of the `type=` class (from `target_class`,
  `properties.rs:202-213`). When `T` is unknown, `P1` stays as the stub has it.

`T` has to be known *before* the call is inferred. Infer the `type=` keyword's value with a speculative builder
(`self.speculate()`, as `ty/infer/builder.rs:6573` does) and read its class. The real inference of that argument
then happens as usual inside the call. **Unverified:** that speculative inference of a class reference inside a
deferred annotation leaves no stale state behind. If it does, a narrower fallback is to rewrite `P1` only when
`type=` is a plain `Name` / `Attribute` and resolve it through `definitions_for_name`, as `static_enum_items` does
(`properties.rs:363-391`).

Why keep the stub's other parameter and return types instead of a hand-written table:

- both stubs already encode Blender's conversions (Enum `get -> int`, `set(self, int)`, `items` with
  `Context | None`, vector `get -> Sequence[...]`);
- it keeps generator-specific details in the stubs, where map #1 put stub bugs.

What this gives, against the markers (`props/props_callbacks/__init__.py`):

| Line | Today | With the rewrite |
| --- | --- | --- |
| `count`, `ratio`, `target`, `mode` (typed `def` callbacks) | builtin: `invalid-argument-type` | pass on both: `self: Settings` matches `S` |
| `lambda_update`, `lambda_items`, `lambda_get` | `self` is `bpy_struct` / `Unknown` | `self` is `S`. `assert_type(self, S) and None` is `None`, because neither stub gives `bpy_struct` a `__bool__` or `__len__` (`B/bpy/types/__init__.pyi:15-53`, `F/bpy-stubs/types/__init__.pyi:3337-`), so `S` is always truthy and the lambda's return type is `None`. |
| `lambda_poll` | `obj` is `ID` / `Unknown` | `obj` is `Object` |
| `wrong_get` (`-> int` for a String), `wrong_set` (`value: str` for an Int) | reported on both | still reported: the stub's `R` / `P1` are kept |
| `wrong_poll` (`Material` candidate on an `Object` pointer) | fake: not reported | reported on both: `Callable[[S, Object], bool]` rejects a `Material` parameter |
| `untyped` (`def untyped_update(self, context)`) | passes | passes |

The checker also gets Blender's `self` on both generators the same way, which neither stub can express.

**Recommendation, read-only:** in `PropertyDeclaration::is_read_only` (`properties.rs:190-200`), also return `true`
when `get=` is given and `set=` is not. Add a marker such as `s.lambda_get = 1  # ty: ignore[invalid-assignment]` to
`props_callbacks`. `set=` without `get=` is a `blender-invalid-property`, which belongs to #27.

### 3.4 Not covered by markers: callbacks of Registered properties

`bpy.types.Scene.my_value = IntProperty(update=lambda self, context: ...)` is an ordinary value-expression call, not
the annotation takeover. On builtin, a `def` callback annotated `self: Scene` is then a false
`invalid-argument-type`, and a lambda's `self` is `bpy_struct`. The same `declaration_callee` rewrite fits there, with
`S` being the class of the assignment target (`bpy.types.Scene`). But it needs a hook in ordinary call inference,
which is an upstream file, and the owner is only known from the enclosing assignment. No marker covers it. See
"Surfaced questions".

## 4. The remaining failures in scope, and what blocks them

| Lines (exp-B / exp-F) | What clears them | Stub-blocked? |
| --- | --- | --- |
| `props_vector`, 252 / 252 | section 1 (value type) and section 2.3 (write type: the 3 `unused-ignore-comment`s) | **fake-bpy-module: 205 lines**. builtin: none. |
| `bpy_symbols/generated/*` `assert_type(s.offset, Vector)`, 14 / 14 | section 1: `FloatVectorProperty(subtype="TRANSLATION")` with the default size 3 is `Vector` | no |
| `props_pointer`, 9 / 0 | nothing in the checker | **builtin: all 9** |
| `props_callbacks`, 13 / 5 | section 3.3 | **builtin: 1** (`self["ratio"] = value`) |
| `props_styles`, 1 / 1 (`ignore-comment-unknown-rule` for `blender-legacy-property`) | defining the rule, in [#27](https://github.com/taway1450/blender-extension-developer-suite/issues/27) | no; not this ticket |

### 4.1 fake-bpy-module: `bpy_prop_array` is not generic (205 `props_vector` lines)

- The stub is `class bpy_prop_array(bpy_prop)` with only `foreach_get` / `foreach_set`: no type parameter, no
  `__getitem__`, no `__iter__`, no `__len__` (`F/bpy-stubs/types/__init__.pyi:3658-3671`). The stubs nonetheless
  write `bpy_prop_array[int]` in 331 places.
- So every marker that names `bpy_prop_array[...]` gets `not-subscriptable` on the marker line, and every `[0]` /
  `[3]` index marker fails. That is 205 `assert_type` lines: all of `values()` except the 42 mathutils markers, the
  two `.x` / `.length` markers and `scene.props_vector`. The checker's own value type is correct, and the oracle
  already assumes the fix (`tests/typecheck/oracle/fake-bpy-module/bpy.types.pyi`).
- **Generator fix.** fake-bpy-module already has a mod that declares the generic class with typed `__getitem__`,
  `__iter__` and `__set__` (`fake-bpy-module/src/mods/common/analyzer/new/bpy.types.mod.rst:1-40`). It is a `new`-type
  mod. Since Blender's own RST documents `bpy_prop_array`, the generated class wins and the mod's generic class does
  not reach the output. **Unverified:** that it is this collision and not a later stage. The likely fix is to turn it
  into an `update`/`append` mod, like `bpy_prop_collection` and `bpy_prop_collection_idprop`
  (`mods/common/analyzer/{append,update}/bpy.types.mod.rst`).
- **The spec should name this fix as a precondition** for `props_vector` passing on fake-bpy-module, and record the
  205 lines as named exceptions until it lands. The checker must not work around it: section 1.4, point 6.

### 4.2 builtin: `bpy_prop_collection_idprop` is not generic (the 9 `props_pointer` lines)

These are the 7 markers #7 listed (section 7 of that note), which make 9 recorded lines because two of them also
record `not-subscriptable`. They are all builtin and all blocked by
`class bpy_prop_collection_idprop(bpy_prop_collection)` with `add() -> Any` (`B/bpy/types/__init__.pyi:2463-2467`).
The checker already does its part (`properties.rs:165-181`).

**Generator fix**, in `blender/doc/python_api/sphinx_stub_gen.py`: the generic-class special case lists only
`bpy_prop_array` and `bpy_prop_collection` (`:1393-1397`, `:1425-1437`). Add `bpy_prop_collection_idprop`, deriving
from `bpy_prop_collection[_T]` with `add() -> _T`, as the oracle baseline does
(`tests/typecheck/oracle/builtin/bpy.types.pyi`). This ticket finds no other remaining pointer marker.

### 4.3 builtin: `bpy_struct` item access takes only `int` keys (1 `props_callbacks` line)

`self["ratio"] = value` (`props/props_callbacks/__init__.py:22`) is `invalid-assignment` on builtin. Its `bpy_struct`
has `__getitem__(self, key: int) -> float` and `__setitem__(self, key: int, value: object)`
(`B/bpy/types/__init__.pyi:15-53`). At runtime these are ID-property access by `str` key. fake-bpy-module has
`key: int | str` (`F/bpy-stubs/types/__init__.pyi:3337-` `__getitem__` / `__setitem__` / `__delitem__`).
**Generator fix** in `sphinx_stub_gen.py`: give `bpy_struct`'s item dunders a `str` key (and a value type that is
not `float`). Until it lands, this line is a named builtin exception.

### 4.4 After the checker work, before the generator fixes

| | builtin | fake-bpy-module |
| --- | --- | --- |
| `props_vector` | 0 | 205 (4.1) |
| `s.offset` | 0 | 0 |
| `props_pointer` | 9 (4.2) | 0 |
| `props_callbacks` | 1 (4.3) | 0 |
| `props_styles` | 1 (#27) | 1 (#27) |

## 5. Summary of recommendations

1. Vector value types follow `pyrna_math_object_from_array`, in `properties.rs`:
   - Float, 1-D or 2-D `MATRIX`: a mathutils class by subtype and *total* length;
   - everything else, including all Int and Bool vectors: `bpy_prop_array` nested once per dimension;
   - the element `float` is `int | float`.
   The markers already match the C code.
2. `size=` / `subtype=`: read literals from the syntax, or literal types from inference. Missing means 3 and `NONE`.
   Unreadable or out of range gives `Any`, which matches #26's fallback; the error is #27's.
3. A vector's write type is the nested `Sequence[E]`, plus the value type unless it is a `Matrix` on a 1-D property.
   It goes in `on_store`, for both origins.
4. Callback `self`: in the annotation takeover, infer the call against a rewritten signature. Every callback's first
   parameter becomes the declaring class, and `poll`'s second becomes the `type=` class, inferred speculatively
   first. The stub's other parameter and return types stay. Lambdas then get their types from ty's own `Callable`
   context, and wrong signatures stay `invalid-argument-type`.
5. `get=` without `set=` makes the property read-only. Add a marker.
6. Generator fixes the spec must name, with their markers as exceptions until they land:
   - fake-bpy-module's generic `bpy_prop_array` (205 lines);
   - builtin's generic `bpy_prop_collection_idprop` (9 lines);
   - builtin's `str` keys on `bpy_struct` (1 line).
7. Optional generator fixes:
   - `gen:212-219`: make the `Matrix` setters runtime-accurate;
   - optional markers for the quirks: `MATRIX` `size=9` and `(2, 8)`, `size=(4,)`, three dimensions, an
     `IntVectorProperty` with `subtype="XYZ"` and `size=(2, 2)`.

## Surfaced questions

- **Callbacks of Registered properties** (3.4): should `bpy.types.X.attr = IntProperty(update=...)` type `self` as `X`?
  It needs a hook in ordinary call inference, an upstream file, and has no marker. The same question applies to a
  declaration built outside any class, such as a module-level `prop = IntProperty(update=...)` in #26's wrappers:
  `self` is not known where the call is written.
