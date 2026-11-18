# How a property annotation is evaluated as a value

Research note, 2026-11-06, for [issue #26](https://github.com/taway1450/blender-extension-developer-suite/issues/26)
(map #21). Trimmed on 2026-11-18 to the rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings.

The question: how does the checker evaluate an annotation such as `common_a: COMMON`, `from_dict: PROPS["weight"]`
or `wrapped: color_property()` as a value, so that anything evaluating to a `bpy.props` Property declaration counts
as that property?

Conventions:

- `sem/` is `ty-blender/ruff-blender/crates/ty_python_semantic/src/`, `blender/` is `sem/types/dedicated/blender/`.
  Fork source read at `blender` commit `c4b93523c0`.
- *Probed* means the output came from the fork's `ty` (dev build of `b8e600480`) on a scratch file against the
  fake-bpy-module stubs, `--python-version 3.11`.
- Builds on [property-annotation-takeover.md](property-annotation-takeover.md) (#4: the `Call` arm is the takeover
  hook, string pre-filter), [basic-property-value-types.md](basic-property-value-types.md) (#7) and #10 (a tracked
  query over the definition, no type qualifier).

What main does: the Property evaluator is `blender/evaluate.rs`. It serves the annotation takeover, the Property
member query and, unlike the original plan, Registered properties too (`bpy.types.Scene.x = COMMON`, read in a query
of its own; `blender/index.rs`).

---

## 1. What ty knows about these values

| Expression | ty's value type | As annotation (stock behaviour) |
| --- | --- | --- |
| `COMMON` (`IntProperty(name=..., min=0)`) | `_PropertyDeferred` | `invalid-type-form` "Variable of type `_PropertyDeferred` is not allowed in a type expression" |
| `Float` (`= FloatProperty`) | `def FloatProperty[...](...) -> _PropertyDeferred` | `Float(default=1.0)` passes: the `Call` arm resolves the alias by type |
| `ColorProperty` (`functools.partial(FloatVectorProperty, subtype="COLOR", size=3)`) | `partial[(..., subtype: ... = "COLOR", ..., size: ... = 3, ...) -> _PropertyDeferred]` | `Function calls are not allowed` |
| `ColorProperty(size=4)` | `_PropertyDeferred` | same |
| `PROPS` | `dict[str, _PropertyDeferred]` | "Variable `PROPS` cannot be used as a type" |
| `PROPS["weight"]`, `PAIR[0]` | `_PropertyDeferred` | same as above (`PAIR`) |
| `color_property` | `def color_property() -> Unknown` | n/a |
| `color_property()`, `translation(2)`, `float_or_int(True)` | `Unknown` | `Function calls are not allowed` |
| `getattr(bpy.props, "x")` | `Any` | `Function calls are not allowed` on the call |
| `SETTINGS` (`dict(subtype="TRANSLATION", size=3)`) | `dict[str, str \| int]` | `FloatVectorProperty(**SETTINGS)`: `invalid-argument-type` per keyword parameter |

(*Probed.*) Consequences:

- ty does **not** infer return types of unannotated functions (`def color_property() -> Unknown`). A wrapper's
  return type cannot carry the declaration, and adding call-site return inference to ty is far outside the
  one-line-hook budget.
- `_PropertyDeferred` is a plain stub class in both generators. Every property value has that one type, so a value
  type says "this is a property", never which.
- ty models `functools.partial` precisely: the value is `KnownInstanceType::FunctoolsPartial`
  (`sem/types/known_instance.rs:294-296`), whose interned payload keeps the **wrapped** callable
  (`FunctoolsPartialInstance::wrapped`, `known_instance.rs:63-69`). So `FloatVectorProperty` is recoverable from the
  callee's type. The bound keyword *values* are only defaults of the rewritten signature; they are read from the
  `partial(...)` call's syntax instead.
- `**SETTINGS` with a widened value type gets stock ty's `invalid-argument-type` against every keyword parameter.
  That is ty's general behaviour for `**dict`, not Blender's, and suppressing argument errors inside the takeover
  would hide real mistakes.

Real code uses this: Blender's own `scripts/startup/bl_operators/wm.py` declares module constants such as
`rna_path_prop = StringProperty(...)` and uses them as annotations (`data_path: rna_path_prop`) dozens of times.
The module-constant form is the important one in practice; no `functools.partial` of a `bpy.props` function or
one-line wrapper was found in Blender's `scripts/`.

## 2. Where the non-call annotations are caught

Names, dotted names and subscripts are caught where type-expression inference already holds the value type and the
source definition, before any diagnostic: `infer_name_or_attribute_type_expression` and
`infer_subscript_type_expression_no_store`. The hook fires only when ty's value type is a `_PropertyDeferred`
instance (or a union whose every element is one or dynamic), so `x: int` never reaches the evaluator.

### Why not one hook in the annotation fallback arm

The annotation fallback arm (`annotation_expression.rs:352-356`) sees every style, but it gets the type only after
`infer_type_expression_no_store` has reported `invalid-type-form`, and it cannot re-infer the expression (double
inference panics). Pre-inferring there would duplicate ty's name/attribute/subscript logic. The two hooks sit
exactly where the value type and definition exist and no diagnostic has been emitted yet.

## 3. The Property evaluator

It answers "which Property declarations can this expression evaluate to?", for an expression in a scope, with a
lookup for inferred types.

### 3.1 What it produces

A `PropertyValue` is one or more declarations (a union of their value types: `float_or_int` gives `float | int`),
or *Opaque*: ty says it is a `_PropertyDeferred`, but which one is unknown. A declaration's options that decide a
type are three-state (absent / value / unknown), so the fallbacks are explicit. "Unknown" means "given, but not
readable", typically after an opaque `**mapping`:

| Declaration | Unknown option | Value type |
| --- | --- | --- |
| Bool / Int / Float | any | the scalar (no option changes it) |
| Enum | `items` | `str` |
| Enum | `options` | `Any` (`ENUM_FLAG` would make it a `set`) |
| BoolVector / IntVector / FloatVector | `subtype` or `size` | `Any` |
| Pointer / Collection | `type` | `Unknown` |

These deliberate fallbacks are `Any` rather than `Unknown`: `check:ide`'s completion marker treats an `Unknown`
detail as "type not resolved", and `assert_type(x, Any)` accepts both.

### 3.2 Rules

Evaluation is recursive with a depth bound, and a miss anywhere gives "not a property" unless ty's type of the
expression is `_PropertyDeferred`, which gives Opaque.

| Expression | Rule |
| --- | --- |
| call of a `bpy.props` function (by type) | read the keywords, with their values read through the bindings below |
| call of a `functools.partial` value | the wrapped function from `FunctoolsPartialInstance::wrapped`; the partial's keywords from its `functools.partial(F, ...)` call, found by following the callee name; the call's own keywords override them (Python's `partial` semantics) |
| call of a first-party function | its wrapper template (3.3), instantiated with the call's arguments |
| `Name` / dotted `Attribute` | the single source definition, with aliases resolved; an assignment's value is evaluated in the definition's scope through a tracked query (3.4) |
| `Subscript` with a literal key / index | the value is a dict, tuple or list literal (directly or through a name); pick the element |
| `**mapping` in a property call | a wrapper's own `**kwargs` forwards the call site's keywords; any other mapping makes every option not given explicitly unknown |
| anything else | not a property, or Opaque when ty types it `_PropertyDeferred` |

`**mapping` is deliberately not evaluated even when it is a readable `dict(...)`: `FloatVectorProperty(**SETTINGS)`
is expected to be `Any`, and following arbitrary dict constants would grow the evaluator into a general interpreter.

An opaque call (`getattr(bpy.props, "...")()`, typed `Any` / `Unknown`) as the top-level annotation of a class-body
member in an add-on is `Any` without `invalid-type-form`, since Blender accepts any `_PropertyDeferred`. The gate
keeps ty's mdtests intact: `o: bar()` is a parameter annotation (`mdtest/annotations/invalid.md:105`), and
`c: type[missing_call()]` is nested and outside add-ons (`invalid.md:304-306`).

### 3.3 Wrapper templates

- **Recognised wrapper:** a first-party function whose every `return` (not in nested functions) evaluates, in the
  function's own scope, to a property declaration. Several returns give several templates, the union. A return that
  does not evaluate makes the whole wrapper not a property (or Opaque if ty types the call as `_PropertyDeferred`).
- **Template:** a declaration whose keyword values may be **parameter references**: `translation(size)` stores
  `size = Param("size")`; `vector(**kwargs)` stores "forward the call's extra keywords".
- **Instantiation at the call site:** bind the call's arguments to the parameters (positional in order, keywords by
  name, defaults from the `def`), then read each bound argument at the call site exactly as a literal keyword is
  read: `translation(2)` gives `size = 2`. A parameter that is unbound, or bound to something unreadable, is
  unknown.
- A wrapper that is itself a `bpy.props` function in disguise (`Float = FloatProperty`) needs no template: the
  callee's type already is the `bpy.props` function.

Why the declaration is not a ty `Type`: it is callee kind plus known keyword values, stored as a plain salsa value
in `blender/`. ty's types cannot carry it (section 1), and a new `Type` or `KnownInstanceType` variant would be a
core edit far beyond one-line hooks.

### 3.4 Cost, incrementality and cycles

- **Per-definition queries:** one for a followed assignment, one for a wrapper function. Each reads that
  definition's syntax tree **inside** a query keyed on it, which is what ty's own guidance asks for (methods reading
  `.node()` should be tracked so one module's inference does not depend on another module's AST;
  `ty-blender/ruff-blender/AGENTS.md`, "Salsa tips"). The results are small and compared, so an edit elsewhere in a
  helper module backdates. This also lets an imported constant be followed (a shared `props.py` of constants is the
  common real-world layout).
- **Cycles:** each query has a `cycle_initial` of "not a property", plus the depth bound for chains within one
  query. `class G(PropertyGroup): x: CONST` with `CONST = PointerProperty(type=G)` defined after the class infers
  `type=G` as the class literal, which does not need `G`'s body, so it is not a cycle. A wrapper calling itself is
  caught by the cycle fallback.
- **The member query shares the evaluator.** The query behind hiding the class member, override exemption and
  read-only evaluates the whole annotation with the same evaluator instead of insisting on a call, so the takeover
  and the query cannot disagree. The annotation node itself stores its *type-expression* type, not its value type,
  so the query resolves the root name through definitions and reads only sub-expressions' stored types (the callee,
  `type=`). Opaque counts as a property: the class member is hidden (Blender replaces it), and it is not read-only.
  A union of declarations is read-only when any member is.

## 4. Known limits

- **Implicit aliases:** the hooks return before ty's alias logic. A module-level `X = COMMON` used as `x: X` is
  still a property, which is right for Blender. A non-Blender variable whose type merely unions with
  `_PropertyDeferred` is not taken over, because the gate requires every union element to be `_PropertyDeferred` or
  dynamic.
- **Quoted wrapper calls** stay `invalid-type-form`: the quoted-annotation pre-filter lets `"ColorProperty()"`
  through (the name ends in `Property`), but not `"color_property()"`.
