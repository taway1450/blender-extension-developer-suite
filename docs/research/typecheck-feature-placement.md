# Where to implement the typechecker features: ty inference, ty lint, ruff lint or stubs

Research note, 2026-11-04. It follows on from [typecheck-test-addons.md](typecheck-test-addons.md). For each feature in
`tests/typecheck/features/`, the question was where it should live:

1. ty's type inference and semantic model;
2. a ty lint rule;
3. a ruff linter rule;
4. outside both: the stubs, a plugin or a separate tool.

A second question was whether existing ruff rules, ty rules or the formatter get in the way.

Conventions are the same as in the earlier notes:

- Every fact has a source next to it, either a URL or a `path:line`. `ruff/` is short for `ty-blender/ruff/`.
- My own recommendations are marked **Recommendation**.
- *Verified locally* means the output came from running a tool on 2026-11-04:
  - `ty-blender/ruff/target/release/ty.exe`, `ty 0.0.97 (bc913d761)`, with `.cache/bpy-stubs-builtin/main`;
  - the installed `ruff 0.15.4` with `--isolated`.

  Both ran on a small probe add-on in a temp directory, since deleted.

---

## 1. Recommendation

**Recommendation.**

- **Put everything in ty**, inside `ty_python_semantic`, as a Blender module next to ty's built-in Django and
  Pydantic support (`ruff/crates/ty_python_semantic/src/types/dedicated/`).
  - The type features (properties, wrappers, registration, `bpy.ops`, idname sinks, preferences, inherited
    callback types) change what ty *infers*. Only inference reaches hover, completion and signature help in
    `ty server`.
  - The `blender-*` checks become ty lints declared with `declare_lint!`. They need the same resolved types, and
    the test harness already expects them as ty rules.
- **Do not use ruff's linter for any feature.** It has no type information and works on one file at a time.
- **Stubs can only fix stub bugs.** They cannot fix any feature.
- **Ship a recommended ruff configuration.** Several default ruff rules misfire on idiomatic add-on code, and one
  of them has a safe autofix that breaks code (section 5.2).

## 2. Facts that decide it

- **ty has no plugin system and none is planned.** The FAQ says "ty does not have a plugin system and there is
  currently no plan to add one" (`ty-blender/docs/reference/typing-faq.md:459-461`). Library support is built in
  instead (`ty-blender/docs/features/third-party/index.md`). Anything that changes inference therefore has to
  live in the fork.
- **There is a precedent for library support inside the checker.** Django (460 lines) and Pydantic (1488 lines)
  live in `ruff/crates/ty_python_semantic/src/types/dedicated/{django,pydantic}.rs`.
  - They recognise library classes through `KnownClass` entries (`types/class/known.rs:166-176`) and
    `KnownModule` entries (`ty_module_resolver/src/module.rs:267-285`).
  - They hook into a few places, for example `django::synthesized_member` in
    `types/class/static_literal.rs:1746` and the Pydantic field specifiers in
    `infer_annotated_assignment_annotation` (`types/infer/builder.rs:4604-4619`).
  - Pydantic even has its own lint, `PYDANTIC_DISCARDED_EXTRA_ARGUMENT` (`types/diagnostic.rs:1170`).
  - Code outside `dedicated/` refers to Django in 61 places and to `pydantic::` in 28. That is the scale of
    the hooks a Blender module would need too.
- **The fork has no Blender work yet.** The `blender` branch of `ty-blender/ruff` is at the same commit as
  `upstream/main` (`f076cb67a1`; `git log upstream/main..blender` is empty). The `ty-blender` repo itself adds
  only the submodule switch (`bc913d7`).
- **How ty rules are declared.** `declare_lint!` is defined at `ruff/crates/ty_python_semantic/src/lint.rs:257`
  and registered in `register_lints` (`types/diagnostic.rs:71`). The kebab-case name comes from the static's
  name (`lint.rs:274`). So `blender-invalid-idname` would be `static BLENDER_INVALID_IDNAME`.
- **The tests already assume ty lints.** Expected errors are written as `# ty: ignore[blender-…]`.
  - An unknown rule shows up as `ignore-comment-unknown-rule` (`tests/typecheck/README.md`, "Type markers";
    lint declared at `ty_python_semantic/src/suppression.rs:50`). Today 128 such lines are recorded in
    `tests/typecheck/expected/fake-bpy-module/main.txt`.
  - Ruff rules would need `# noqa: CODE` comments and a second harness.
- **Ruff's linter has no type inference.**
  - `ruff/crates/ruff_linter/Cargo.toml` depends on `ruff_python_semantic` (line 28) and on no `ty_*` crate.
  - `SemanticModel` is "a semantic model for a Python module" (`ruff_python_semantic/src/model.rs:58`).
  - Even base-class matching only follows class bindings in the same file: `any_base_class` stops at an import
    binding because it is not a class definition (`ruff_python_semantic/src/analyze/class.rs:55-66`).
  - So a ruff rule cannot know that `class X(MyMixin)` is an `Operator` when `MyMixin` comes from another
    module, and it cannot follow `register()` into submodules.
- **The IDE sees only what ty infers.**
  - Hover is built from `SemanticModel::inferred_type` (`ruff/crates/ty_ide/src/hover.rs:27,121`).
  - String-literal completion is driven by the expected `Literal` type of the argument
    (`ty_ide/src/completion.rs:54-65`, `add_string_literal_completions` at `:2326`, which calls
    `model.expected_string_literal_completions`).
  - So once inference gives `UILayout.operator` a `Literal[...]` idname parameter, idname completion comes for
    free. Ruff's language server publishes diagnostics only, never types.
- **Today's failures are almost all inference gaps.** Out of 1994 recorded non-passes
  (`tests/typecheck/expected/fake-bpy-module/main.txt`):
  - 635 are `type-assertion-failure`, 486 `invalid-type-form` and 401 `unresolved-attribute`;
  - 152 are `not-subscriptable`, a stub bug (section 3, stubs row);
  - only 128 are missing `blender-*` rules.

## 3. Placement per feature

"ty inference" means code in `ty_python_semantic` (types/`dedicated/blender/`). "ty lint" means a `declare_lint!`
rule that is reported from the same code.

| Feature | Home | Reason |
| --- | --- | --- |
| addon_discovery | ty inference (a salsa query "add-on of this file"), `[tool.blender]` read by `ty_project`; rules as ty lints | Every other feature is scoped by it. It must be a tracked query, so that editing `blender_manifest.toml` invalidates results in the server. Deep manifest validation could also be delegated to `blender --command extension validate` (`blender/scripts/addons_core/bl_pkg/cli/blender_ext.py:5716`). |
| bpy_symbols | ty inference (`KnownModule` / `KnownClass` / known-function entries for `bpy.props.*`, `bpy.types.*`, `bpy.utils.register_class`, …) | Alias, re-export and star-import resolution is already ty's job. Keying on resolved symbols, as Django does with `KnownClass::DjangoModel` (`dedicated/django.rs:20-26`), handles every import form and the `sym_negative` look-alikes for free. |
| properties | ty inference: declared type of annotated class members on property hosts; `bpy.types.X.attr = …Property()` on registration | The annotation is a call, so no stub can make it a type (section 6). ty already *infers* the call before rejecting it (`types/infer/builder/type_expression.rs:1177-1188`), so the hook has the value it needs. The four property rules are ty lints. |
| property_wrappers | ty inference (same hook: evaluate the annotation as a value expression) | It needs constant propagation, `functools.partial`, dict and tuple items and inferring the returns of small functions. That is all type inference. |
| registration | ty inference (a cross-module query from `register()`), feeding member synthesis for `bpy.ops.<cat>` modules and Blender classes | It has to follow calls into submodules, loops and factories, which is whole-add-on analysis. Upstream ty avoided this for Django reverse relations ("ty does not recognize reverse relationship attributes", `ty-blender/docs/features/third-party/django.md`), so this is the costliest part to carry. |
| registration_checks | ty lint, reported from the registration query | It needs the same resolved registration graph. Add-on isolation (`regchk_isolation_*`) falls out of keying the query on the add-on root. |
| operator_calls | ty inference: synthesised signature of `bpy.ops.<cat>.<name>` | It feeds `signature_help` and `completion` (`ide_opcall_basic.py` markers). Wrong calls are ty's existing call-binding lints (`invalid-argument-type`, `unknown-argument`, …), which only work if the signature is a real type. |
| operator_properties | ty inference: specialised return types and `Literal` idname parameters on the idname sinks | It is like an overload chosen by a literal argument. The `Literal`-driven idname completion comes from ty_ide for free. `blender-unknown-operator` is a ty lint. |
| addon_preferences | ty inference (`addons[<key>].preferences` specialised, `__package__` typed as the add-on name) | It depends on evaluating the key, and on the module's add-on, from addon_discovery. Stock ty types `__package__` as `str \| None` from typeshed (`ty_python_semantic/resources/mdtest/scopes/moduletype_attrs.md:14`). `blender-preferences-idname` is a ty lint. |
| inheritance | ty inference (parameter types of unannotated overrides from the Blender parent) plus ty lints; changes to ty's own `invalid-method-override` | `blender-invalid-override` must *replace* `invalid-method-override` (`features/inheritance/README.md`, "Rules"). That diagnostic is emitted in `types/overrides.rs:765,1871`, so only a change inside ty can suppress it. |
| *(not a feature)* stub bugs | stubs (fake-bpy-module upstream, or the builtin generator) | `bpy_prop_array` not generic (152 `not-subscriptable`, fake-bpy-module only; `tests/typecheck/oracle/README.md`); mathutils defaults rejected by `FloatVectorProperty`, `bpy_extras` helper overrides and `bpy.app.handlers` argument types (`expected/*/main.txt`, `sym_mathutils`, `sym_bpy_extras`, `sym_handlers`). |

None of the features is a good fit for ruff's linter. The only part that is syntactic is the idname *format*
check in `blender-invalid-idname` (`registration_checks/README.md`, runtime facts). It still needs to know which
classes are Operators, Panels or Menus across modules and to evaluate constant idnames
(`opcall_idname_forms`), so it belongs with the other ty lints.

## 4. Hook points in ty (where the code would go)

- **Annotation as a value.** `infer_annotated_assignment_annotation`
  (`ruff/crates/ty_python_semantic/src/types/infer/builder.rs:4604-4619`) is where Pydantic already changes
  annotation handling. For an annotated member of a property host, the Blender module would:
  - infer the annotation as a value expression;
  - if the value comes from a `bpy.props` function (`_PropertyDeferred` in both generators:
    `.cache/bpy-stubs-builtin/main/bpy/props/__init__.pyi:11,22`; `.cache/bpy-stubs/main/bpy-stubs/props/__init__.pyi:612`),
    return the runtime type computed from the arguments;
  - skip the `invalid-type-form` path at `type_expression.rs:1177-1188`.
- **Synthesised members.** `own_synthesized_member_with_kind` (`types/class/static_literal.rs:1737-1748`) is
  where Django adds `id`, `pk` and `<field>_id`. Registered properties on Blender classes and `bpy.ops` members
  would go through the same kind of hook, plus an equivalent for module members.
- **Attribute writes.** `bpy.types.Scene.x = IntProperty()` is reported as `unresolved-attribute` from
  `types/infer/builder/attribute_assignment.rs:1157`.
- **Overrides.** `types/overrides.rs:765` and `:1871` report `invalid-method-override`.
- **Lints.** `declare_lint!` statics in a Blender diagnostics module, registered from
  `types/diagnostic.rs:71`. Docs go in `resources/lint_docs/*.md` (`types/diagnostic.rs:1169`).
- **Tests.** `resources/mdtest/libraries/` holds library mdtests (`numpy.md`), and Blender mdtests could go
  there next to this repo's feature tests.

## 5. Interference from existing rules and behaviour

### 5.1 ty

| Rule / behaviour | Where | Effect on add-on code | Mitigation |
| --- | --- | --- | --- |
| `invalid-type-form` (default `error`, `types/diagnostic.rs:757-761`) | `type_expression.rs:1177-1188` "Function calls are not allowed in type expressions"; for `PROPS["x"]`: "Variable `PROPS` cannot be used as a type" (*verified locally*) | every `count: IntProperty()` (486 recorded lines) | Code change: the Blender annotation hook in section 4 must take these annotations *before* type-expression inference. Turning the rule off in `ty.toml` would hide real errors. |
| `unresolved-attribute` | `attribute_assignment.rs:1157` | `bpy.types.Scene.x = …`, `del …`, reads of registered properties and `bpy.ops.<cat>` (401 recorded) | Code change (registration synthesis). A metaclass `__getattr__` in the stubs would silence it but would break `regchk_isolation_*`, which *expects* `unresolved-attribute`. |
| `invalid-method-override` | `types/overrides.rs:765,1871` | Blender-accepted overrides (renamed parameters, 7-parameter `draw_item`) and the stub-caused cases (`sym_bpy_extras`, `inh_mixins:131`) | Code change for the Blender rules. Stub fixes for the stub-caused ones. |
| `__package__: str \| None` | typeshed `ModuleType` (`moduletype_attrs.md:14`) | `bl_idname = __package__` is reported as `invalid-assignment`; `addons[__package__]` as `invalid-argument-type` | Code change (addon_discovery types it as a `Literal`). |
| Unannotated parameters are `Unknown` | `features/inheritance/README.md` | no checking inside `execute(self, context)` | Code change (inheritance). |

### 5.2 Ruff linter

The fork's ruff (0.17.3, `ruff/crates/ruff/Cargo.toml:3`) has a much larger default rule set than older ruff
(`ruff/crates/ruff_linter/src/settings/mod.rs:357-…`, used by `ruff_workspace/src/configuration.rs:915`). The
following were *verified locally* with ruff 0.15.4 and `--select`:

| Rule | Default in 0.17.3? | Triggered by | Risk | Mitigation |
| --- | --- | --- | --- | --- |
| **UP037** quoted-annotation | yes (`settings/mod.rs:743`) | `x: PROPS["weight"]` with `from __future__ import annotations` (or Python ≥ 3.14, `ruff_python_ast/src/python_version.rs:94-96`) | **Breaks code.** The safe fix (`Fix::safe_edit`, `rules/pyupgrade/rules/quoted_annotation.rs:137`) rewrites it to `PROPS[weight]`. | `lint.flake8-type-checking.runtime-evaluated-base-classes = ["bpy.types.PropertyGroup", "bpy.types.Operator", …]` stops it (*verified locally*). That works only for classes whose Blender base is visible in the same file. Otherwise ignore UP037 for add-ons. |
| **F821** undefined-name | yes (`:459`) | `x: PROPS["weight"]`: ruff reads the string as a forward reference (*verified locally*; also `features/property_wrappers/wrap_values/__init__.py:52-53`) | false positive | `per-file-ignores`, or `# noqa: F821`. The base-class setting does not help (*verified locally*). |
| F722 forward-annotation-syntax-error | no | `x: PROPS["my label"]` | false positive | the same |
| **RUF012** mutable-class-default | yes (`:646`) | `bl_options = {"REGISTER", "UNDO"}` (`is_mutable_expr` treats `Expr::Set` as mutable, `ruff_python_semantic/src/analyze/typing.rs:424-431`). The exemption list has Pydantic, msgspec and SQLModel only (`rules/ruff/helpers.rs:203-224`) | noise on nearly every operator | ignore RUF012, or annotate `bl_options: ClassVar[set[str]]`. A Blender exemption in ruff would be one `matches!` arm in a fork, but the same-file limit applies. |
| TC001-TC003 typing-only import | no (TC004/005/007/010 are, `:703`) | with the `__future__` import, `from bpy.props import EnumProperty` used only in annotations: TC002 (*verified locally*) | **Breaks code.** Blender evaluates the string annotations with `typing.get_type_hints` at registration (`blender/source/blender/python/intern/bpy_rna.cc:9538-9555`), so the import must stay at runtime. | `runtime-evaluated-base-classes` as above (*verified locally*); keep TC00[1-3] off |
| N801 invalid-class-name | no | `OBJECT_OT_simple`, `MY_PG_settings` (any `_` fails, `rules/pep8_naming/rules/invalid_class_name.rs`) | noise | `lint.pep8-naming.ignore-names = ["*_OT_*", "*_PT_*", "*_MT_*", "*_HT_*", "*_UL_*", "*_PG_*", …]` (*verified locally*) |
| ANN001 / ANN201 / ANN206 | no | `def execute(self, context):`, the style the inheritance feature supports | conflicts with the inheritance goal. `@override` does not exempt ANN001 (`rules/flake8_annotations/rules/definition.rs:663-693`). | leave ANN off for add-ons, or accept annotations |
| ARG002 / ARG003 unused argument | no | an unused `context` in `execute` / `poll` | noise | `@typing.override` exempts it (`rules/flake8_unused_arguments/rules/unused_arguments.rs:64`), or ignore |
| N802, N815, F403/F405, E402 | N802/N815/E402 no; F403/F405 not in the 0.17.3 list | `bl_idname`, `execute` and `draw` names are fine. Star imports (`reg_imports`) and the `if "bpy" in locals()` reload pattern trigger F403/F405/E402 when those rules are selected. | low | per-file config |

The `dataclass_kind` and `has_default_copy_semantics` exemptions (`rules/ruff/rules/mutable_class_default.rs:128-135`)
show the pattern ruff uses for libraries. Any Blender awareness in ruff would be the same kind of per-file name
match.

### 5.3 Formatter

- On the probe add-on, `ruff format --diff` changed nothing (*verified locally*).
- The formatter does not change what annotations mean.
- `# ty:` comments count as pragma comments (`ruff/crates/ruff_python_trivia/src/pragmas.rs:34-38`), so they
  do not count toward line width.
- One remaining risk: when the formatter splits a long `x: FloatVectorProperty(...)  # ty: ignore[...]` over
  several lines, the trailing comment can end up on a different line from the diagnostic. This was not tested.

## 6. Can existing ty mechanisms replace special-casing?

- **`dataclass_transform` field specifiers: no.** Field specifiers are recognised in the *value* position
  (`x: int = field()`). See the typing spec, https://typing.python.org/en/latest/spec/dataclasses.html, and
  ty's `setup_dataclass_field_specifiers` at `builder.rs:4611`. Blender puts the call in the *annotation*,
  and the old `x = IntProperty()` value form is ignored by Blender (`features/properties/README.md`,
  `props_styles`).
- **Descriptors: no.** A `__get__` on `_PropertyDeferred` would give a type to exactly the form Blender ignores,
  and it would not stop `invalid-type-form` on the annotation.
- **Metaclass `__getattr__` / `__setattr__` in the stubs: no.**
  - It would silence `unresolved-attribute` on Blender classes, but give `Any`.
  - It would lose the typo checks and the isolation the tests require (`regchk_isolation_*`).
  - The stubs declare no Blender metaclass (`features/inheritance/README.md`, last paragraph).
- **Generated per-add-on stubs (the oracle approach): only as a stop-gap.**
  - `check:oracle` shows that stock ty plus synthesised `.pyi` deltas satisfies most markers
    (`tests/typecheck/README.md`, "Reference stubs and the oracle").
  - A generator tool could ship this without a fork. But code inside the add-on's own `.py` file still sees
    its own definitions, and its `invalid-type-form` errors stay.
  - The oracle needs `oracle-skip` for "a class defined in the check file" and for `__package__` for the same
    reason.
  - The stubs would also have to be regenerated on every edit for the IDE.
- **The existing Django/Pydantic pattern: yes.** Use it as the template (`dedicated/`, `KnownClass` gating by MRO,
  `synthesized_member`, a lint in `diagnostic.rs`).

## 7. Cost of the fork

- The upstream files a Blender module touches are among the most active in ty: `types/infer/builder.rs`,
  `types/class/static_literal.rs`, `types/overrides.rs`, `types/diagnostic.rs` and `class/known.rs`.
  **Recommendation:** keep each hook to one line that calls into `types/dedicated/blender/`, so that most
  rebases conflict only on those lines. Django's footprint (61 references outside `dedicated/`) is the realistic
  size.
- `register_lints` in `types/diagnostic.rs:71` is a long list that upstream edits often. Register the Blender
  lints from one `blender::register_lints(registry)` call instead.
- The registration query is the part that has no upstream counterpart. It is also where performance and
  invalidation risk is highest in `ty server`.
- ruff stays unforked. All ruff interference is handled through configuration (section 5.2).

## 8. Open questions

- **Add-on root.** How does `ty_python_semantic` learn the add-on root?
  - `ty_python_semantic` has no `toml` dependency (`ty_python_semantic/Cargo.toml`); `ty_project` does
    (`ty_project/Cargo.toml:62`).
  - So `[tool.blender]` and the manifest are probably parsed in `ty_project` and passed down as a setting, like
    `AnalysisSettings` (`ty_python_semantic/src/lib.rs:101`).
  - But a manifest *file* lookup per module has to stay a tracked salsa input, so that edits invalidate results.
- **Registration query in open-files mode.** Is a whole-add-on registration query acceptable in the language
  server when `CheckMode::OpenFiles` (`ty_project/src/lib.rs:1064-1066`)? It would still have to parse every
  module that `register()` reaches.
- **Tolerating the first-time `invalid-type-form`.** Should the Blender hook *always* take over a call
  annotation whose value is a `_PropertyDeferred`, even on a class that is not a property host? The properties
  README wants `blender-unsupported-property-host` there instead of `invalid-type-form`.
- **A Blender preset for ruff.** Should this repo ship a recommended ruff configuration for add-ons: ignore
  RUF012, the N801 `ignore-names`, `runtime-evaluated-base-classes`, and UP037/F821 for property-wrapper files?
  And should we upstream a request that UP037 not unquote string subscripts whose base is not a type?
- **Python 3.14.** Once Blender moves to Python 3.14, annotations are deferred by default
  (`python_version.rs:94-96`), and the UP037/TC risks apply without the `__future__` import. Blender main
  bundles 3.13.13 (`blender/build_files/build_environment/cmake/versions.cmake:384`).
- **Fork rules or upstream support?** Should the `blender-*` rules be kept as fork-only lints, or proposed
  upstream as library support behind the same kind of detection Django uses (installed stubs)?
