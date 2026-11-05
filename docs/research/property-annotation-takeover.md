# Where a property annotation gets taken over

Research note, 2026-11-05, for [issue #4](https://github.com/taway1450/blender-extension-developer-suite/issues/4)
(map: issue #1, charting decisions: issue #2). The question: where in ty's inference does an annotation such as
`count: IntProperty(min=0)` on a class body get taken over, so that

1. the instance attribute's declared type is the property's value type (`assert_type(s.count, int)`);
2. no `invalid-type-form` is reported for the call;
3. it works with `from __future__ import annotations` and for quoted `"BoolProperty()"` annotations;
4. class-level access `Cls.count` stays unresolved (`unresolved-attribute`);
5. assignments are checked against the value type (`s.i = 1.5` is `invalid-assignment`);
6. hover shows the value type;

with the fewest one-line hooks in existing files.

Conventions:

- Every fact has a `path:line` source next to it. `sem/` is short for
  `ty-blender/ruff-blender/crates/ty_python_semantic/src/`, `mdtest/` for
  `ty-blender/ruff-blender/crates/ty_python_semantic/resources/mdtest/`. Source read at submodule commit
  `f076cb67a1` (`.git/modules/ty-blender/modules/ruff-blender/HEAD`).
- *Verified locally* means the output came from running `ty-blender/ruff-blender/target/release/ty.exe`
  (`ty 0.0.97 (368c78c30 2026-11-04)`, stock behaviour, no Blender code) with `--python-version 3.11` on small
  scratch files outside the repo, since deleted.
- My own recommendations are marked **Recommendation**.

---

## 1. Answer

**The `Call` arm is enough for requirements 1, 2, 3, 5 and 6, but not for 4.** And it needs a small change for
quoted annotations, because today it does not infer the call inside a string at all.

- The declared type flows from the annotation to member lookup with no hook at
  `infer_annotated_assignment_annotation` (`sem/types/infer/builder.rs:4604`). Whatever type the annotation
  expression returns becomes the declaration (section 2.1).
- Requirement 4 does not follow from the declared type. Stock ty lets a class-body declaration without a value
  be read on the class: `C.only_declared` is `str` (`mdtest/attributes.md:103-122`). So the class-member path
  needs its own hook. It also needs a way to tell a property declaration apart from `count: int`. The
  qualifier bits that travel with a declared type are the natural carrier (section 3).
- The property-host rule ("off property hosts it creates no attribute", issue #2) cannot be decided in the
  `Call` arm either. `props_hosts` expects `panel.value` to be `unresolved-attribute`
  (`tests/typecheck/features/properties/props_hosts/check_props_hosts.py:31-37`). That needs a hook in the
  instance-member path (section 3, hook 5).

**Recommendation: five hook sites, all in existing files.**

| # | Site | Change | Glue receives |
| --- | --- | --- | --- |
| 1 | `Call` arm of type-expression inference, `sem/types/infer/builder/type_expression.rs:1177-1189` | Infer the call (also inside a string when a syntactic pre-filter matches), ask the glue for the value type, return it without reporting. | `&InferContext`, callee type, call return type, `&ast::ExprCall`, a lookup for argument types |
| 2 | Fallback arm of annotation-expression inference, `sem/types/infer/builder/annotation_expression.rs:352-356` | Add a new qualifier `BLENDER_PROPERTY` when the annotation is a call whose stored callee type is a `bpy.props` function. | callee type |
| 3 | `TypeQualifiers`, `sem/types.rs:11849-11870` and `is_non_standard` at `:11898-11904` | One new non-standard flag; the bitset grows from `u8` to `u16` (all 8 bits are used). | n/a |
| 4 | `StaticClassLiteral::own_class_member`, `sem/types/class/static_literal.rs:1624` | A member whose qualifiers contain `BLENDER_PROPERTY` is `Member::unbound()` on the class. | nothing (a qualifier test) |
| 5 | `StaticClassLiteral::own_instance_member`, `sem/types/class/static_literal.rs:3026-3032` | A `BLENDER_PROPERTY` declaration on a class that is not a property host is `Member::unbound()`. | the declaring `StaticClassLiteral` |

No hook is needed at `infer_annotated_assignment_annotation` (`builder.rs:4604`), in attribute assignment, or in
hover. Section 4 lists the risks, among them a likely new `invalid-attribute-override` on an overriding property.

---

## 2. How an annotation travels today

### 2.1 From the class body to the declared type

- `infer_annotated_assignment_definition` calls `infer_annotated_assignment_annotation`
  (`sem/types/infer/builder.rs:4683`, defined at `:4604-4619`). That calls
  `infer_annotation_expression_allow_pep_613` with `DeferredExpressionState::from(self.defer_annotations())`
  (`:4612-4615`). The only existing library hook there is the Pydantic field-specifier setup (`:4610-4616`).
- `defer_annotations()` is true for stubs, for files with `from __future__ import annotations`, and on
  Python 3.14+ (`builder.rs:990-995`). The annotation is still inferred right there, during the definition's
  inference. The deferred state only changes how names are looked up (`builder.rs:10816-10822`:
  `PlaceLoadMode::Deferred` or `PlaceLoadMode::StringAnnotation`).
- For a declaration without a value, the resulting `TypeAndQualifiers` is stored as the declaration as-is
  (`builder.rs:5030`, `self.add_declaration(target.into(), definition, declared)`). Its qualifiers travel
  with it into `place_from_declarations` (`sem/place.rs:827`), which both member paths read
  (`sem/types/member.rs:74-110`; `sem/types/class/static_literal.rs:3026`).
- The qualifier validation in the annotated-assignment path iterates only the standard `TypeQualifier` enum
  (`builder.rs:4729-4736`), so an extra non-standard flag would pass through it untouched.

So whatever type and qualifiers the annotation expression returns become the declaration. Nothing at
`builder.rs:4604` has to change.

### 2.2 From the annotation to the `Call` arm

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

### 2.3 What the `Call` arm does with the call

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

### 2.4 Calls inside strings can be inferred safely

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

### 2.5 Member lookup for a class-body declaration without a value

- Instance access: `own_instance_member` reads `place_from_declarations` (`static_literal.rs:3026-3032`). In
  the "declared but not bound in the class body" branch it trusts the declared type (`:3146-3156`).
- Class access: `own_class_member` calls `class_member_with_symbol` (`static_literal.rs:1624`). That returns
  the declared place whenever there is one ("Trust the declared type if we see a class-level declaration",
  `sem/types/member.rs:106-111`).
- ty documents this choice: "If a variable is declared in the class body but not bound anywhere, we consider
  it to be accessible on instances and the class itself" (`mdtest/attributes.md:103-122`).
- *Verified locally*: `class C: count: int` then `C.count` is `int`, with no diagnostic.
- The target behaviour already exists in ty for attributes declared only in a method. For
  `self.count: int` in `__init__` (*verified locally*):
  - `c.count` is `int`;
  - `c.count = 1.5` reports `invalid-assignment` "Object of type `float*` is not assignable to attribute
    `count` of type `int`";
  - `C.count` reports `unresolved-attribute` "Attribute `count` can only be accessed on instances, not on the
    class object".

  That message comes from `builder.rs:11280-11383`: `bound_on_instance` is true when the class lookup fails
  but `instance_member` succeeds. So the goal is **class member unbound, instance member declared**. Hook 4
  produces exactly that state.

### 2.6 Assignments and hover need nothing extra

- Attribute assignment checks against the instance member's declared type. The probe above shows the
  `invalid-assignment` message for that state (*verified locally*). `props_scalar` expects exactly this
  (`tests/typecheck/features/properties/generated/props_scalar/check_props_scalar.py:81-91`).
- Hover takes the inferred type of the expression under the cursor (`ty-blender/ruff-blender/crates/ty_ide/src/hover.rs:121`).
  For `s.count` that is the member-lookup result, so `int`. The property hover markers are in
  `props_callbacks/ide_props_callbacks.py:12-19` and `props_registered/ide_props_registered.py:12-19`.

### 2.7 What the glue can identify the call by

- Both stub generators declare every `bpy.props` function as returning `_PropertyDeferred`:
  - builtin: `.cache/bpy-stubs-builtin/main/bpy/props/__init__.pyi:11` (class) and `:16-26`;
  - fake-bpy-module: `.cache/bpy-stubs/main/bpy-stubs/props/__init__.pyi:152` (class) and the defs at
    `:161-837`, for example `IntProperty` returning `_PropertyDeferred` at `:637`.
- The ten property functions are `Bool`, `BoolVector`, `Collection`, `Enum`, `Float`, `FloatVector`, `Int`,
  `IntVector`, `Pointer` and `String` + `Property`. `RemoveProperty` returns `None`.
- Issue #2 settled that symbols are recognised by their defining module (precedent
  `pytest/fixtures.rs:388-393`), so the glue checks the callee's `FunctionLiteral` and its module `bpy.props`.

---

## 3. The hook sites

**Recommendation** for each site below. The order is the data flow.

### Hook 1: the `Call` arm (`sem/types/infer/builder/type_expression.rs:1177-1189`)

Requirements 1, 2, 3 and 5 depend on this hook. Shape:

```rust
ast::Expr::Call(call_expr) => {
    if !self.in_string_annotation() || blender::may_be_property_call(call_expr) {   // changed line
        let callee = self.infer_callee(&call_expr.func);                              // split of infer_call_expression
        let returned = self.infer_call_expression_impl(call_expr, callee, TypeContext::default());
        if let Some(ty) = blender::annotation_value_type(&self.context, callee, returned, call_expr,
                                                         &|e| self.expression_type(e)) { return ty; } // hook
    }
    self.report_invalid_type_expression(...);   // unchanged
    Type::unknown()
}
```

- **What the glue receives:**
  - `&InferContext`: the db, the file and lint reporting, as `pydantic::report_discarded_extra_arguments(&self.context, ...)`
    does (`builder.rs:10023`).
  - The **inferred callee** `Type`: a `FunctionLiteral` for `bpy.props.IntProperty`. The glue checks its
    defining module.
  - The **call's return type**: a `_PropertyDeferred` instance in both generators. It is a cheap first check.
  - The **call expression** `&ast::ExprCall`: keywords such as `type=`, `items=` and `options=` for
    `find_keyword`.
  - **Argument types**: a lookup over the builder's stored expression types (`builder.rs:1036`). The arguments
    were just inferred by `infer_call_expression_impl`. This replaces Django's `definition_expression_type`,
    which needs a finished definition inference and would cycle here.
- **The enclosing class:** not needed for the value type. If the glue ever needs it (for callback `self`
  typing, which is out of scope), `nearest_enclosing_class(db, self.index, self.scope())`
  (`sem/types/infer.rs:1020-1032`) is already used in annotation inference (`annotation_expression.rs:272`).
  Reading the class literal from inside its own body is safe: `setup_dataclass_field_specifiers` does it for
  every annotated assignment (`builder.rs:944-968`).
- **The string pre-filter** (`may_be_property_call`) is pure AST: is the callee's last name segment one of the
  ten names in section 2.7? It keeps `"call()"` and `"bar()"` exactly as today (section 2.4). Its cost: an
  aliased import (`from bpy.props import IntProperty as IP`) used *inside a quoted annotation* is not taken
  over. Plain and `__future__` annotations need no pre-filter, because the arm infers their calls anyway.
- **Non-Blender calls behave as today:** the arm still reports `invalid-type-form` and returns `Unknown`, and
  the call is inferred only where it was before.
- Value types for nested positions such as `list[IntProperty()]` also come through this arm. Blender rejects
  those, and issue #2 says "a property declaration in any annotation is taken over". So the glue may take
  them over too, or check `InferenceFlags::IN_NESTED_TYPE_EXPRESSION` (used at `type_expression.rs:1556-1568`)
  to leave them as `invalid-type-form`. That choice belongs to the property-rules work and does not change the
  hook.

### Hook 2: the annotation fallback arm (`sem/types/infer/builder/annotation_expression.rs:352-356`)

Requirement 4 depends on this hook, because hooks 4 and 5 need to tell a property declaration apart from
`count: int`.

```rust
type_expr => {
    let ty = self.infer_type_expression_no_store(type_expr);
    AnnotationExpressionInference::new(blender::mark_property_annotation(
        TypeAndQualifiers::declared(ty), type_expr, &|e| self.try_expression_type(e)))   // hook
}
```

- **What the glue receives:** the annotation expression. When it is an `ast::Expr::Call`, the glue also gets
  the callee's type, which hook 1 has already stored (`builder.rs:1036-1042`). If that is a `bpy.props`
  function, it adds `TypeQualifiers::BLENDER_PROPERTY`. If the callee was never inferred (a string without a
  pre-filter match), the lookup is `None` and nothing changes.
- This is the only place in the annotation path that builds a `TypeAndQualifiers`, and every top-level style
  passes through it (section 2.2). The `Call` arm returns a bare `Type` (`type_expression.rs:1177`), so it
  cannot set the qualifier itself.
- The type stored for the annotation node is the inner type (`annotation_expression.rs:29-34`, `:363`). So
  hovering the call in the class body shows the value type.

### Hook 3: a new qualifier (`sem/types.rs:11849-11870`, `:11898-11904`)

- `TypeQualifiers` is a `u8` with all eight bits used. The last ones, `IMPLICIT_INSTANCE_ATTRIBUTE` and
  `FROM_MODULE_GETATTR`, are already non-standard internal markers. Adding `BLENDER_PROPERTY = 1 << 8` needs
  `u16`, plus adding the flag to the `NON_STANDARD` set in `is_non_standard`.
- `TypeQualifiers::name` hits `unreachable!` for flags it does not know (`sem/types.rs:11885-11892`). It is only
  meaningful for standard qualifiers, and making the new flag non-standard keeps it out of those paths.
- Reusing `IMPLICIT_INSTANCE_ATTRIBUTE` instead is **not** advisable. It changes how declarations and
  method writes are merged (`sem/types/class.rs:3196-3215`) and metaclass precedence (`sem/types.rs:4765-4767`).

### Hook 4: class-level access (`sem/types/class/static_literal.rs:1624`)

- After `let member = class_member_with_symbol(...)` add:
  `if member.inner.qualifiers.contains(TypeQualifiers::BLENDER_PROPERTY) { return Member::unbound(); }`.
- The MRO lookup then goes on to the bases. The stubs have no such attribute there, so `Cls.count` is
  `unresolved-attribute`, with the "can only be accessed on instances" text on hosts (section 2.5).
- This matches runtime ("After registration the class attribute is gone (`AttributeError`)",
  `tests/typecheck/features/properties/README.md`, "Runtime facts").
- The two `unused-ignore-comment` lines recorded today for `props_styles` turn into passes
  (`tests/typecheck/expected/builtin/main.txt:1782-1783`).
- **What the glue receives:** nothing. It is a qualifier test, so it can be inline in the hook or a
  one-line `blender::` helper.

### Hook 5: off-host instance access (`sem/types/class/static_literal.rs:3026-3032`)

- After `declared_and_qualifiers` is computed: if it carries `BLENDER_PROPERTY` and
  `!blender::is_property_host(db, self)`, return `Member::unbound()`.
- **What the glue receives:** the declaring `StaticClassLiteral` (`self`). It walks the MRO for the host bases
  in the properties README (PropertyGroup, Operator, Macro, AddonPreferences, UIList, Node, NodeSocket,
  NodeTree, Gizmo), recognised by defining module.
- This covers `props_hosts`' `ignored()` markers (`check_props_hosts.py:31-37`).
- **Forward note:** mixin annotations (out of scope, issue #1) are decided by the *accessed* class, not the
  declaring one. `class PROPS_STYLES_MixinFirst(CountMixin, ..., PropertyGroup)`
  (`props_styles/inheritance.py:27`) has `count` from a non-host mixin. When that work lands, this check moves
  up to `instance_member` (`static_literal.rs:2961`), which knows the accessed class. Until then, mixin markers
  stay recorded failures.

---

## 4. Risks and open points

- **`invalid-attribute-override` on overriding properties (not verified with a build).**
  - Stock ty reports `class A: x: int` / `class B(A): x: str` as `invalid-attribute-override` "Type `str` is
    not assignable to inherited type `int`" (*verified locally*; emitted from
    `sem/types/overrides/attributes.rs:537`, `check_override` at `:576`).
  - Once declarations become `int` and `str`, `PROPS_STYLES_Override.base_value: StringProperty()` replacing
    `IntProperty()` (`props_styles/inheritance.py:23-24`) will probably get the same diagnostic. Blender
    allows this replacement.
  - Hook 4 also changes what `own_class_member` returns, and the override checker reads it
    (`sem/types/overrides.rs:1145-1151`). So the outcome is uncertain until it is built.
  - Inherited annotations are out of scope, so the line can be a recorded failure for now. A later fix would
    be a qualifier test in `check_override`.
- **Size tests.** Growing `TypeQualifiers` to `u16` may change the size of `TypeAndQualifiers` and
  `PlaceAndQualifiers`. Two tests guard this: `member_lookup_result_size` (`sem/types/tests.rs:19-26`) and
  `compact_definition_types_omit_owner` (`sem/types/infer/tests.rs:237-241`). They are part of the
  regression guard, so check them first when building. Padding may absorb the extra byte.
- **The quoted-alias gap** from hook 1's pre-filter (section 3, hook 1). The alternative is to infer every
  call in strings and accept the extra diagnostics, but that breaks two ty mdtests (section 2.4). **I
  recommend the pre-filter.**
- **`__future__` and quoted annotations need no extra site.** Both come through the same two arms
  (section 2.2), and forward references resolve in both lookup modes (`builder.rs:10816-10822`; *verified
  locally* for `__future__`).
- **`op.properties.value`** in `props_hosts` (`check_props_hosts.py:18`) goes through `Operator.properties`.
  None of these hooks covers it; it belongs to whoever plans the operator side.
- **Not checked:** completion (`s.cou` → `count`, `ide_props_callbacks.py:23-26`). It lists members through
  ty's member enumeration, not through `own_class_member` / `own_instance_member` one name at a time. Whether
  hook 4 or 5 hides or shows `count` there needs checking once built.
