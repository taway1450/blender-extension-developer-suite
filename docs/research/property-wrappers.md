# How a property annotation is evaluated as a value

Research note, 2026-11-06, for [issue #26](https://github.com/taway1450/blender-extension-developer-suite/issues/26)
(map: issue #21). The question: how does the checker evaluate an annotation such as `common_a: COMMON`,
`from_dict: PROPS["weight"]` or `wrapped: color_property()` as a value, so that anything evaluating to a `bpy.props`
Property declaration counts as that property (`property_wrappers/wrap_values`)? Where does the hook go for non-call
annotations, how does it avoid cycles and stay cheap, what does a declaration carry, how does the Property member
query recognise these members, and what about the 4 failing `ide_*` markers?

Conventions:

- `sem/` is `ty-blender/ruff-blender/crates/ty_python_semantic/src/`, `blender/` is `sem/types/dedicated/blender/`,
  `mdtest/` is `ty-blender/ruff-blender/crates/ty_python_semantic/resources/mdtest/`, `wrap/` is
  `tests/typecheck/features/property_wrappers/wrap_values/`. Fork source read at `blender` commit `c4b93523c0`.
- *Probed* means the output came from the fork's `ty` (dev build of `b8e600480`, with T0–T4b) on a scratch file
  against the fake-bpy-module stubs (`.cache/bpy-stubs/main`), `--python-version 3.11`. Nothing was built for this
  note, and no prototype was written.
- Binding prior decisions: #4 (the `Call` arm is the takeover hook, string pre-filter), #7 (value types; `items=` /
  `options=` read from syntax, `type=` from its inferred type, keywords only), #10 (route B: the tracked query
  `property_declaration(definition)`, no type qualifier), standing preference for one-line hooks.
- My own recommendations are marked **Recommendation**.

---

## 1. Answer

- **No new ty type, and the wrapper's return type carries nothing.** ty gives every `bpy.props` call the stub's
  `_PropertyDeferred`, and an unannotated wrapper's call is `Unknown` (*probed*, section 2.1). So the declaration
  cannot ride on ty's types. It is rebuilt by a small **Property evaluator** in `blender/` that follows the
  annotation's names to their definitions and reads the values there, the way `static_enum_items` already follows
  one module constant (`blender/properties.rs:363-391`).
- **What it produces:** `PropertyValue` = one or more `PropertyDeclaration`s (a union for `float_or_int`), or
  *Opaque* (ty says it is a `_PropertyDeferred`, but which one is unknown). `PropertyDeclaration` gains a three-state
  `Known<T>` (absent / value / unknown) for the options that decide a type, so the `Any` fallbacks are explicit.
- **Hooks:** two new one-line hooks in `type_expression.rs`, both on paths an ordinary annotation already leaves
  through a cheap type test:
  1. top of `infer_name_or_attribute_type_expression` (`sem/types/infer/builder/type_expression.rs:293-299`), for
     `x: COMMON` and `x: module.COMMON`;
  2. top of `infer_subscript_type_expression_no_store` (`type_expression.rs:1495-1502`), for `x: PROPS["weight"]`.

  Calls (`Float(...)`, `ColorProperty()`, `color_property()`, `translation(2)`) already go through the fork's own
  `type_expression/blender.rs`; that file grows, but no upstream line changes.
- **Is it a property:** `property_declaration(definition)` (`blender/properties.rs:305-344`) evaluates the whole
  annotation with the same evaluator instead of insisting on a call. The takeover and the query share one function,
  so they cannot disagree.
- **Cheap and cycle-free:** in type-expression inference the hook fires only when ty's value type of the reference
  is a `_PropertyDeferred` instance; `x: int` never reaches the evaluator. Each followed definition and each wrapper
  function is read in its own tracked query (with `cycle_initial`), so another file's syntax tree is read only
  inside a query keyed on that file's definition, and the result backdates.
- **IDE:** the 4 failing markers need nothing of their own. Hover and completion read the declared type
  (`s.alias` already passes through the same path). Two of them (`partial_color`, `wrapped_size`) also need #25's
  vector table.
- **Two lines stay red for reasons outside this ticket:** `unknown_options` gets stock ty's `invalid-argument-type`
  for `**SETTINGS`, and fake-bpy-module reports `not-subscriptable` on `bpy_prop_array[float]` (section 6).

---

## 2. What ty knows about these values today

### 2.1 Probed value types

| Expression (`wrap/__init__.py`) | ty's value type | As annotation (fork today) |
| --- | --- | --- |
| `COMMON` (`IntProperty(name=..., min=0)`) | `_PropertyDeferred` | `invalid-type-form` "Variable of type `_PropertyDeferred` is not allowed in a type expression" |
| `Float` (`= FloatProperty`) | `def FloatProperty[...](...) -> _PropertyDeferred` | `Float(default=1.0)` already passes: the `Call` arm resolves the alias by type |
| `ColorProperty` (`functools.partial(FloatVectorProperty, subtype="COLOR", size=3)`) | `partial[(..., subtype: ... = "COLOR", ..., size: ... = 3, ...) -> _PropertyDeferred]` | `Function calls are not allowed` |
| `ColorProperty(size=4)` | `_PropertyDeferred` | same |
| `PROPS` | `dict[str, _PropertyDeferred]` | "Variable `PROPS` cannot be used as a type" |
| `PROPS["weight"]`, `PAIR[0]` | `_PropertyDeferred` | same as above (`PAIR`) |
| `color_property` | `def color_property() -> Unknown` | n/a |
| `color_property()`, `translation(2)`, `float_or_int(True)` | `Unknown` | `Function calls are not allowed` |
| `getattr(bpy.props, "x")` | `Any` | `Function calls are not allowed` on the call |
| `SETTINGS` (`dict(subtype="TRANSLATION", size=3)`) | `dict[str, str \| int]` | `FloatVectorProperty(**SETTINGS)`: 18 × `invalid-argument-type` |

Consequences:

- ty does **not** infer return types of unannotated functions (`def color_property() -> Unknown`). A wrapper's
  return type cannot carry the declaration, and adding call-site return inference to ty is far outside the
  one-line-hook budget.
- `_PropertyDeferred` is a plain stub class in both generators (`.cache/bpy-stubs-builtin/main/bpy/props/__init__.pyi:11`,
  `.cache/bpy-stubs/main/bpy-stubs/props/__init__.pyi:152`, issue #4 section 2.7). Every property value has that one
  type, so a value type says "this is a property", never which.
- ty models `functools.partial` precisely: the value is `KnownInstanceType::FunctoolsPartial`
  (`sem/types/known_instance.rs:294-296`), whose interned payload keeps the **wrapped** callable
  (`FunctoolsPartialInstance::wrapped`, `known_instance.rs:63-69`). So `FloatVectorProperty` is recoverable from the
  callee's type. The bound keyword *values* are only defaults of the rewritten signature; they are read from the
  `partial(...)` call's syntax instead (section 4).

### 2.2 Recorded failures

`tests/typecheck/expected/builtin/main.txt:816-843` and `fake-bpy-module/main.txt:779-806`: 15 lines in
`__init__.py` (13 × `invalid-type-form`, 1 × `invalid-argument-type`, `opaque`'s `invalid-type-form`) and 13 failing
`assert_type`s. Already passing: `alias`, `scalar_unknown_options`, and `opaque`'s `assert_type(..., Any)` (because
ty falls back to `Unknown`). IDE (`expected/*/main.ide.md:226-258`, both generators): hovers on `s.common_a`,
`s.partial_color`, `s.wrapped_size` and the `s.from_` completion fail; `s.alias` passes.

### 2.3 Real code uses this

Blender's own `scripts/startup/bl_operators/wm.py` declares module constants such as `rna_path_prop =
StringProperty(...)` (`:88`) and `rna_reverse_prop = BoolProperty(...)` (`:95`) and uses them as annotations 49 times
(`data_path: rna_path_prop`, `:286`, `:306`, ...). The module-constant form is the important one in practice; no
`functools.partial` of a `bpy.props` function or one-line wrapper was found in `scripts/` (grep over
`.cache/blender-src/main/scripts`).

---

## 3. Where the non-call annotations go

### 3.1 The two reference paths

Type-expression inference dispatches on the AST (`type_expression.rs:448-544`):

- **`Name` and dotted `Attribute`** (`:449-471`) call `infer_type_expression_reference` (`:274-291`), which infers the
  name **as a value** and keeps its source definition (`infer_name_load_with_definition`, `sem/types/infer/builder.rs:10779-10805`;
  `Provenance::definition`, `sem/place.rs:113-147`). Both then go to `infer_name_or_attribute_type_expression`
  (`:293-360`), which converts the value with `in_type_expression` (`:317`) and reports `invalid-type-form` on the
  error path (`:330-358`).
- **`Subscript` on a dotted name** (`:493-529`) infers the value the same way, stores it (`:505`) and calls
  `infer_subscript_type_expression_no_store(subscript, slice, value_ty, definition)` (`:1495`). A variable that is
  not an alias is rejected there by `reject_non_alias_reference` (`:1519-1526`), which also infers the slice as a
  value outside strings.

So **both paths already hold the value type and the definition** before any diagnostic. Quoted (`"COMMON"`) and
`__future__` annotations reach them too (issue #4, section 2.2).

### 3.2 Hook 1: names and dotted names

**Recommendation.** First line of `infer_name_or_attribute_type_expression`, before `legacy_type_alias_reference`
(`:301`):

```rust
if let Some(ty) = self.blender_reference_value_type(ty, definition, annotation) { return ty; }
```

`blender_reference_value_type` lives in the fork's `type_expression/blender.rs` (already a fork-only file,
`sem/types/infer/builder/type_expression/blender.rs`):

- **Gate:** `ty` is an instance of `bpy.props._PropertyDeferred` (recognised by defining module, like
  `blender_function_name`, `blender/symbols.rs:30-41`), or a union whose every element is one or dynamic. Anything
  else returns `None`
  at once. This is a match on the `Type` variant plus one cached module lookup, so `x: int`, `x: list[int]` and
  every other ordinary annotation is unaffected.
- **Then:** evaluate the reference with the Property evaluator (section 4) from `definition`, and return the
  `PropertyValue`'s value type. When the evaluator cannot tell which property (Opaque), return `Any`. Either way
  no `invalid-type-form`, as Blender accepts it.

### 3.3 Hook 2: subscripts

**Recommendation.** First line of `infer_subscript_type_expression_no_store` (`:1501`):

```rust
if let Some(ty) = self.blender_subscript_value_type(subscript, value_ty, definition) { return ty; }
```

- **Gate:** `value_ty` is a `dict`, `tuple` or `list` instance whose element types include `_PropertyDeferred`
  (`dict[str, _PropertyDeferred]`, `tuple[_PropertyDeferred, _PropertyDeferred]`). `List[int]`, `Literal[...]`,
  `Annotated[...]` etc. have class literals or special forms as `value_ty` and miss the gate.
- **The slice:** the glue reads it from syntax (a string or integer literal, negative indices included). It must
  also infer it as a value outside strings, as the reject path does (`:1522-1524`), because every expression of
  the file gets a stored type exactly once (`store_expression_type` asserts this, `builder.rs:7150-7153`, issue #4).

### 3.4 The `Call` arm grows, without upstream edits

`infer_call_type_expression` (`type_expression/blender.rs:14-43`) already infers the callee and the call and asks
`blender::annotation_value_type`. **Recommendation:** extend `annotation_value_type` so that a callee that is not a
`bpy.props` function is still evaluated (section 4): a `functools.partial` of one, a first-party function whose
returns are property declarations, or a name bound to either. And one new rule in the same file:

- **Opaque calls:** when the call's type is dynamic (`Any` / `Unknown`, as for
  `getattr(bpy.props, "...")()`), the annotation is the top-level annotation of a class-body member
  (`ScopeKind::Class`, not `IN_NESTED_TYPE_EXPRESSION`) and the file belongs to an add-on (`addon_of_file`,
  `blender/addon.rs:10-20`), return `Any` without `invalid-type-form`. The gate keeps ty's mdtests intact:
  `o: bar()` is a parameter annotation (`mdtest/annotations/invalid.md:105`), and `c: type[missing_call()]` /
  `call: "type[missing_call()]"` are nested and outside add-ons (`invalid.md:304-306`,
  `mdtest/type_of/typing_dot_Type.md:45-60`).

The quoted-annotation pre-filter (`may_be_property_call`, `blender/properties.rs:253-278`) stays as #4 decided. It
already lets `"ColorProperty()"` through (the name ends in `Property`), but not `"color_property()"`. A quoted
wrapper call therefore stays `invalid-type-form`; `wrap_values` has no quoted annotations.

### 3.5 Why not one hook in the annotation fallback arm

The annotation fallback arm (`annotation_expression.rs:352-356`) sees every style, but it gets the type only after
`infer_type_expression_no_store` has reported `invalid-type-form`, and it cannot re-infer the expression (double
inference panics). Pre-inferring there would duplicate ty's name/attribute/subscript logic. The two hooks above sit
exactly where the value type and definition exist and no diagnostic has been emitted yet.

---

## 4. The Property evaluator

**Recommendation:** a new file `blender/evaluate.rs`. It answers "which Property declarations can this expression
evaluate to?", for an expression in a scope, with a lookup for inferred types (the builder's `expression_type` in
type-expression inference, `definition_expression_type_in_scope` in the query, exactly as `PropertyDeclaration::from_call`
is called today, `type_expression/blender.rs:24-31` and `blender/properties.rs:340-343`).

### 4.1 What it produces

```rust
enum PropertyValue<'db> {
    /// One of these declarations; a union of their value types (`float_or_int` gives `float | int`).
    Declarations(Box<[PropertyDeclaration<'db>]>),
    /// A deferred property whose function or options cannot be read: `Any`, still a property.
    Opaque,
}

enum Known<T> { Absent, Value(T), Unknown }
```

`PropertyDeclaration` (`blender/properties.rs:74-87`) keeps `kind` and the `type=` target, and its option fields
become `Known<...>`: `items`, `options` (ENUM_FLAG / READ_ONLY), `subtype`, and the new `size` #25 needs. `Unknown`
means "given, but not readable", typically after an opaque `**mapping`. The value table then states the fallbacks
from `property_wrappers/README.md`:

| Declaration | Unknown option | Value type |
| --- | --- | --- |
| Bool / Int / Float | any | the scalar (no option changes it) |
| String | `subtype` | `str` (the README's scalar rule; `BYTE_STRING` is rare and would need it spelled out) |
| Enum | `items` | `str` (#7, unchanged) |
| Enum | `options` | `Any` (ENUM_FLAG would make it a `set`) |
| BoolVector / IntVector / FloatVector | `subtype` or `size` | `Any` (#25 owns the known cases) |
| Pointer / Collection | `type` | `Unknown`, as today |

Return `Type::any()` rather than `Type::unknown()` for these deliberate fallbacks: `check:ide`'s completion marker
treats an `Unknown` detail as "type not resolved" (`expected/builtin/main.ide.md:253`), and `assert_type(x, Any)`
accepts both (`opaque` passes today with `Unknown`).

### 4.2 Rules

Evaluation is recursive with a depth bound (8 is plenty), and a miss anywhere gives `None` ("not a property") unless
ty's type of the expression is `_PropertyDeferred`, which gives `Opaque`.

| Expression | Rule | `wrap_values` case |
| --- | --- | --- |
| call of a `bpy.props` function (by type, `PropertyKind::of_callee`) | today's `from_call`, with keyword values read through the bindings below | `alias`, `scalar_unknown_options` |
| call of a `functools.partial` value | the wrapped function from `FunctoolsPartialInstance::wrapped`; the partial's keywords from its `functools.partial(F, ...)` call, found by following the callee name; the call's own keywords override them (Python's `partial` semantics) | `partial_color`, `partial_override` (size 4) |
| call of a first-party function | its **wrapper template** (4.3), instantiated with the call's arguments | `wrapped`, `wrapped_size`, `wrapped_kwargs`, `wrapped_enum`, `either` |
| `Name` / dotted `Attribute` | the single source definition (`Provenance::SingleDefinition`, or `definitions_for_name` with aliases resolved, `sem/types/definition_resolution.rs:166`); an assignment's value is evaluated in the definition's scope through a tracked query (4.4) | `common_a`, `common_b` |
| `Subscript` with a literal key / index | the value is a dict, tuple or list literal (directly or through a name); pick the element | `from_dict`, `from_dict_str`, `from_tuple`, `from_tuple_bool` |
| `**mapping` in a property call | a wrapper's own `**kwargs` forwards the call site's keywords; any other mapping makes every option not given explicitly `Unknown` | `unknown_options` (Any), `scalar_unknown_options` (int) |
| anything else | `None`, or `Opaque` when ty types it `_PropertyDeferred` | `opaque` (via the call rule of 3.4) |

`**mapping` is deliberately not evaluated even when it is a readable `dict(...)`: `wrap/check_wrap_values.py:110`
expects `Any` for `FloatVectorProperty(**SETTINGS)`, and following arbitrary dict constants would grow the
evaluator into a general interpreter.

### 4.3 Wrapper templates

A tracked query per function, `wrapper_template(function definition) -> Option<Box<[Template]>>`:

- **Recognised wrapper:** a first-party function whose every `return` (not in nested functions) evaluates, in the
  function's own scope, to a property declaration. Several returns give several templates, the union. A return that
  does not evaluate makes the whole wrapper `None` (or `Opaque` if ty types the call as `_PropertyDeferred`).
- **Template:** a `PropertyDeclaration` whose keyword values may be **parameter references**:
  `translation(size)` stores `size = Param("size")`; `enum_of(items)` stores `items = Param("items")`;
  `vector(**kwargs)` stores "forward the call's extra keywords". `type=` inside the body is stored as the inferred
  type when it does not name a parameter.
- **Instantiation at the call site:** bind the call's arguments to the parameters (positional in order, keywords by
  name, defaults from the `def`), then read each bound argument at the call site exactly as `from_call` reads a
  literal keyword: `translation(2)` gives `size = 2`, `enum_of([("A", ...), ("B", ...)])` gives static items `A`, `B`.
  A parameter that is unbound, or bound to something unreadable, is `Unknown`.
- A wrapper that is itself a `bpy.props` function in disguise (`Float = FloatProperty`) needs no template: the
  callee's type already is the `bpy.props` function.

This is the "typed representation of a declaration" the ticket asks about: callee kind plus known keyword values,
stored as a plain salsa value in `blender/`, not as a ty `Type`. ty's types cannot carry it (2.1), and a new `Type`
or `KnownInstanceType` variant would be a core edit far beyond one-line hooks.

### 4.4 Cost, incrementality and cycles

- **Per-definition queries:** `constant_value(definition) -> Option<PropertyValue>` for a followed assignment and
  `wrapper_template(definition)` for a function. Each reads that definition's syntax tree **inside** a query keyed
  on it, which is what ty's own guidance asks for (methods reading `.node()` should be tracked so one module's
  inference does not depend on another module's AST; `ty-blender/ruff-blender/AGENTS.md`, "Salsa tips"). The
  results are small and compared, so an edit elsewhere in a helper module backdates. This lifts #7's "an imported
  constant is not followed" restriction for property values (a shared `props.py` of constants is the common
  real-world layout); whether enum `items=` constants follow the same route is a separate, optional change.
- **Cycles:** each query has `cycle_initial` → `None`, like `property_declaration` (`blender/properties.rs:305-309`),
  plus the depth bound for chains within one query. `class G(PropertyGroup): x: CONST` with
  `CONST = PointerProperty(type=G)` defined after the class infers `type=G` as the class literal, which does not
  need `G`'s body, so it is not a cycle. A wrapper calling itself is caught by the cycle fallback.
- **Ordinary annotations:** in type-expression inference the hooks bail on the type gate (3.2, 3.3). In the query
  (section 5) the first step is syntactic: only a call, or a name/attribute/subscript whose root name resolves to a
  first-party assignment, is evaluated. `x: int` resolves `int` to a typeshed class and stops. Like #10, measure on
  Blender's `scripts/` with `check:blender` when built.

---

## 5. How the Property member query recognises these members

`property_declaration(definition)` (`blender/properties.rs:305-344`) is the one query behind `hides_class_member`,
`hides_instance_member`, `exempts_attribute_override` and `is_read_only` for Annotated properties
(`blender/member.rs:113-127`, `:250-289`, `:202-236`). Today it accepts only a call or a quoted call.

**Recommendation:**

- It becomes `property_value(definition) -> Option<PropertyValue>`: for a class-scope `AnnotatedAssignment`, evaluate
  the annotation (parsed first when quoted, as today) with the evaluator and `definition_expression_type_in_scope`
  as the type lookup. The callee types it needs were stored by the definition's own inference, so takeover and query
  read the same facts, as #10 required.
- The annotation node itself stores its *type-expression* type (`int`), not its value type
  (`annotation_expression.rs:29-34`, issue #4), so the query never asks for the annotation root's type. It resolves
  the root name through definitions (4.2), and only sub-expressions' stored types (the callee, `type=`) are read.
- `Opaque` counts as a property: the class member is hidden (Blender replaces it), and it is not read-only. A
  `Declarations` union is read-only when any member is.
- `member.rs` changes its `&PropertyDeclaration` to `&PropertyValue`; `instance_value_type` for Annotated properties
  never needs it, because ty already returns the declared (taken-over) type for them (`member.rs:150-200` only runs
  when ty finds nothing).
- Registered properties (`bpy.types.Scene.x = COMMON`) come from the Add-on index, which reads syntax without
  inference (`blender/index.rs`). The same evaluator could serve it later; not needed for this ticket.

---

## 6. Expected results and what stays red

When built together with #25's vector table, `wrap_values` should pass everything on builtin except:

- **`unknown_options: FloatVectorProperty(**SETTINGS)`**: stock ty checks `**SETTINGS` (`dict[str, str | int]`)
  against every keyword parameter and reports `invalid-argument-type` (*probed*, 18 diagnostics on one line). This is
  ty's general behaviour for `**dict` with a widened value type, not Blender's. The marker line expects no error, so
  either the test changes (for example `SETTINGS: dict[str, Any] = dict(...)`, still opaque to the evaluator) or the
  line stays a named exception. Suppressing argument errors inside the takeover would hide real mistakes.
- **fake-bpy-module only:** `assert_type(s.partial_override, bpy_prop_array[float])` reports `not-subscriptable`
  (`expected/fake-bpy-module/main.txt:797`): fake-bpy-module's `bpy_prop_array` is not generic. A stub-side fix,
  with #25.

The vector-typed markers (`partial_color`, `partial_override`, `wrapped`, `wrapped_size`, `wrapped_kwargs`) need
#25's table; this ticket only makes their `subtype` / `size` reach it as `Known` values.

IDE: hovers on `s.common_a`, `s.partial_color`, `s.wrapped_size` and the `s.from_` completion follow from the
declared types (hover reads the inferred type, `ty-blender/ruff-blender/crates/ty_ide/src/hover.rs:121`; completion
lists members with their declared types, and `s.alias` already passes through the same path).

---

## 7. Summary of changes for the build ticket

| Site | Change |
| --- | --- |
| `type_expression.rs:299` (`infer_name_or_attribute_type_expression`) | **new one-line hook** → `blender_reference_value_type` |
| `type_expression.rs:1501` (`infer_subscript_type_expression_no_store`) | **new one-line hook** → `blender_subscript_value_type` |
| `type_expression/blender.rs` (fork file) | the two methods above; the `Call` arm asks the evaluator for non-`bpy.props` callees; opaque-call rule |
| `blender/evaluate.rs` (new) | `PropertyValue`, the evaluator, `constant_value` and `wrapper_template` tracked queries |
| `blender/properties.rs` | `Known<T>` option fields, `size`; `property_declaration` → `property_value`; value-table fallbacks |
| `blender/member.rs` | read `PropertyValue` instead of `PropertyDeclaration` |
| `tests/typecheck/.../wrap_values` | decide the `**SETTINGS` line (section 6) |

Risks:

- **`reject_non_alias_reference` and implicit aliases:** the hooks return before ty's alias logic. A module-level
  `X = COMMON` used as `x: X` is still a property, which is right for Blender. But a non-Blender variable whose type
  merely unions with `_PropertyDeferred` would be taken over too, which is why the gate (3.2) requires every union
  element to be `_PropertyDeferred` or dynamic.
- **Quoted wrapper calls** stay `invalid-type-form` (3.4). Widening the pre-filter to a name lookup is possible later.
- **Nested positions** (`list[COMMON]`) behave like nested calls today; the property-rules work decides both together
  (issue #4, hook 1 note).
- **Not checked:** the evaluator's cost on large add-ons in the language server (#12-style measurement once built).
