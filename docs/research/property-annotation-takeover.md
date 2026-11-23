# Where a property annotation gets taken over

Research note, 2026-11-05, for [issue #4](https://github.com/taway1450/blender-extension-developer-suite/issues/4)
(map #1). Trimmed on 2026-11-18 to the rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings.

The question: where in ty's inference does an annotation such as `count: IntProperty(min=0)` on a class body
get taken over, so that the instance attribute's declared type is the property's value type, no
`invalid-type-form` is reported, it works with `from __future__ import annotations` and for quoted
`"BoolProperty()"` annotations, and class-level access `Cls.count` stays unresolved.

Conventions:

- Every fact has a `path:line` source next to it. `sem/` is short for
  `ty-blender/ruff-blender/crates/ty_python_semantic/src/`, `mdtest/` for
  `ty-blender/ruff-blender/crates/ty_python_semantic/resources/mdtest/`. Source read at submodule commit
  `f076cb67a1`.
- *Verified locally* means the output came from running a stock ty build (`ty 0.0.97`, no Blender code) with
  `--python-version 3.11` on small scratch files.

What main does: the `Call` arm of type-expression inference calls into the Blender code
(`infer_call_type_expression` in `sem/types/infer/builder/type_expression/blender.rs`), keeping the string
guard behind a syntactic pre-filter (section 2, "Calls inside strings"). Class-level access is hidden by
`hides_class_member` / `hides_instance_member` in `static_literal.rs`, which re-read the declaration
(`annotated_property` in `sem/types/dedicated/blender/member.rs`). The new type qualifier proposed in the
original was never built.

---

## 1. How an annotation travels in stock ty

### 1.1 From the class body to the declared type

- `infer_annotated_assignment_definition` calls `infer_annotated_assignment_annotation`
  (`sem/types/infer/builder.rs:4683`, defined at `:4604-4619`). That calls
  `infer_annotation_expression_allow_pep_613` with `DeferredExpressionState::from(self.defer_annotations())`
  (`:4612-4615`).
- `defer_annotations()` is true for stubs, for files with `from __future__ import annotations`, and on
  Python 3.14+ (`builder.rs:990-995`). The annotation is still inferred right there, during the definition's
  inference. The deferred state only changes how names are looked up (`builder.rs:10816-10822`:
  `PlaceLoadMode::Deferred` or `PlaceLoadMode::StringAnnotation`).
- For a declaration without a value, the resulting `TypeAndQualifiers` is stored as the declaration as-is
  (`builder.rs:5030`, `self.add_declaration(target.into(), definition, declared)`). Its qualifiers travel
  with it into `place_from_declarations` (`sem/place.rs:827`), which both member paths read
  (`sem/types/member.rs:74-110`; `sem/types/class/static_literal.rs:3026`).

So whatever type the annotation expression returns becomes the declaration. Nothing at the annotated-assignment
site has to change.

### 1.2 From the annotation to the `Call` arm

- `infer_annotation_expression_impl` dispatches on the AST (`sem/types/infer/builder/annotation_expression.rs:184-356`).
  A `Call` is not one of its special cases, so it reaches the fallback arm
  `type_expr => ... self.infer_type_expression_no_store(type_expr)` (`:352-356`), and from there the `Call` arm
  of type-expression inference (`sem/types/infer/builder/type_expression.rs:1177-1189`).
- A quoted annotation goes through the `StringLiteral` arm (`annotation_expression.rs:186-188`) to
  `infer_string_annotation_expression` (`:371-389`). That parses the string and calls
  `infer_annotation_expression` on the parsed expression with `DeferredExpressionState::InStringAnnotation`.
  So a parsed `BoolProperty()` comes back to the same fallback arm (`:352-356`) and the same `Call` arm.
- `from __future__` annotations are plain AST calls in the `Deferred` state. They take the same route as plain
  annotations.

So **one site, the fallback arm plus the `Call` arm behind it, sees all three styles**: plain, `__future__`
and quoted. Nested calls such as `list[IntProperty()]` reach the `Call` arm through subscript inference, not
through the fallback arm.

### 1.3 What the `Call` arm does with the call

```rust
ast::Expr::Call(call_expr) => {
    if !self.in_string_annotation() {
        self.infer_call_expression(call_expr, TypeContext::default());
    }
    self.report_invalid_type_expression(expression, format_args!(
        "Function calls are not allowed in {}s", self.type_expression_context()));
    Type::unknown()
}
```

(`sem/types/infer/builder/type_expression.rs:1177-1189`)

- Outside strings the call is fully inferred and its sub-expression types are stored. Inside strings it is
  **not inferred at all**.
- `infer_call_expression` is just `infer_callee(&call.func)` followed by
  `infer_call_expression_impl(call, callable_type, tcx)` (`builder.rs:9342-9350`). So the callee can be inferred
  first and the rest of the call afterwards, without inferring `func` twice.
- Inferring an expression twice panics: `store_expression_type` asserts that no type was stored before
  (`builder.rs:7150-7153`). So a hook that infers the call must also finish the non-Blender case itself. It
  cannot "try and fall through" to code that infers the call again.
- *Verified locally*, stock ty:
  - `call: IntProperty(min=0)` reports `invalid-type-form` and `c.call` is `Unknown`.
  - Under `from __future__ import annotations`, `later: IntProperty(x=Later)` with `Later` defined further
    down reports `invalid-type-form` and `unknown-argument`, but no `unresolved-reference`. So the call *is*
    inferred in the deferred state, and forward references resolve.
  - A quoted `"f('a')"` reports only `invalid-type-form`, with no argument error. The call is not inferred.

### 1.4 Calls inside strings can be inferred safely

- `Annotated` metadata is inferred as value expressions even inside a string annotation
  (`sem/types/infer/builder/subscript.rs:2549-2550`). *Verified locally*:
  `x: "Annotated[int, f('a')]"` reports `invalid-argument-type` for the call inside the string, and
  `"Annotated[int, (lambda: 1)()]"` and `"Annotated[int, [i for i in range(3)]]"` check without errors or
  panics.
- Builder code already guards the string case where it has to: "Parsed string annotations are not indexed"
  (`builder.rs:9150-9153`).
- **Do not drop the string guard for every call.** ty's own mdtests expect only `invalid-type-form` for
  `p: "call()"` with an undefined `call` (`mdtest/annotations/string.md:416-417`) and for `n: "bar()"`
  (`mdtest/annotations/invalid.md:434`). Inferring the callee would add `unresolved-reference` there and break
  the regression guard.
- Hence the syntactic pre-filter: inside a string, infer only a call whose callee's last name segment is one of
  the ten `bpy.props` property functions. It keeps `"call()"` and `"bar()"` exactly as in stock ty. Its cost:
  an aliased import (`from bpy.props import IntProperty as IP`) used *inside a quoted annotation* is not taken
  over. Plain and `__future__` annotations need no pre-filter, because the arm infers their calls anyway.

### 1.5 Member lookup for a class-body declaration without a value

- Instance access: `own_instance_member` reads `place_from_declarations` (`static_literal.rs:3026-3032`). In
  the "declared but not bound in the class body" branch it trusts the declared type (`:3146-3156`).
- Class access: `own_class_member` calls `class_member_with_symbol` (`static_literal.rs:1624`). That returns
  the declared place whenever there is one ("Trust the declared type if we see a class-level declaration",
  `sem/types/member.rs:106-111`).
- ty documents this choice: "If a variable is declared in the class body but not bound anywhere, we consider
  it to be accessible on instances and the class itself" (`mdtest/attributes.md:103-122`).
- *Verified locally*: `class C: count: int` then `C.count` is `int`, with no diagnostic. So `Cls.count` being
  unresolved does not follow from the declared type; the class-member path needs its own hook.
- The target behaviour already exists in ty for attributes declared only in a method. For
  `self.count: int` in `__init__` (*verified locally*):
  - `c.count` is `int`;
  - `c.count = 1.5` reports `invalid-assignment` "Object of type `float*` is not assignable to attribute
    `count` of type `int`";
  - `C.count` reports `unresolved-attribute` "Attribute `count` can only be accessed on instances, not on the
    class object".

  That message comes from `builder.rs:11280-11383`: `bound_on_instance` is true when the class lookup fails
  but `instance_member` succeeds. So the goal is **class member unbound, instance member declared**. This
  matches runtime: after registration the class attribute is gone (`AttributeError`).

### 1.6 Assignments and hover need nothing extra

- Attribute assignment checks against the instance member's declared type, so once the declaration is the
  value type, `s.i = 1.5` is `invalid-assignment` (*verified locally* for the equivalent state above).
- Hover takes the inferred type of the expression under the cursor (`ty-blender/ruff-blender/crates/ty_ide/src/hover.rs:121`).
  For `s.count` that is the member-lookup result.

### 1.7 What a property call is recognised by

- Both stub generators declare every `bpy.props` function as returning `_PropertyDeferred`.
- The ten property functions are `Bool`, `BoolVector`, `Collection`, `Enum`, `Float`, `FloatVector`, `Int`,
  `IntVector`, `Pointer` and `String` + `Property`. `RemoveProperty` returns `None`.
- Issue #2 settled that symbols are recognised by their defining module (precedent
  `pytest/fixtures.rs:388-393`), so the callee is a `FunctionLiteral` from the module `bpy.props`.

---

## 2. Overriding properties

Stock ty reports `class A: x: int` / `class B(A): x: str` as `invalid-attribute-override` "Type `str` is not
assignable to inherited type `int`" (*verified locally*; emitted from `sem/types/overrides/attributes.rs:537`).
Once property declarations become value types, a subclass replacing `IntProperty()` with `StringProperty()`
would get the same diagnostic, though Blender allows the replacement. Main exempts such overrides
(`exempts_attribute_override` in `sem/types/dedicated/blender/member.rs`).
