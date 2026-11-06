# How does an unannotated override get the parent's types? (#50)

Research for map #49. Fork: `ty-blender/ruff-blender`, branch `blender` at `b4135144e1`, upstream merge-base
`f076cb67a1` (2026-11-04). Paths below are relative to `crates/ty_python_semantic/src/` unless they say otherwise.

## Answer

**Upstream has no parameter inheritance.** Nothing in the fork base or on upstream `main` (`f3d6988`, 2026-11-06)
types an unannotated parameter from the overridden method: `infer_parameter_definition` gives `Unknown` (or
`Unknown | <default>`), and `Parameter::from_node_and_kind` gives `Unknown`. The feature is
[astral-sh/ty#4424](https://github.com/astral-sh/ty/issues/4424), which is open. The maintainers there prefer
`T | Unknown` over `T`, to keep the gradual guarantee. The Blender variant must use the plain parent type `T`,
because the markers need `assert_type(context, Context)` to hold, and `Context | Unknown` fails that. The reason it
may do so: Blender passes these arguments by position, with exactly these types. The variant applies only to the
callbacks in the hand-written table.

**Upstream covers part of the return side, behind a setting.** In `inherited_return_annotation`
(`types/function.rs:1860`, used at `:1835`), an unannotated method takes the return annotation of the nearest base
that has one. It only runs with `[analysis] return-type-inference = "always"`. The default is `"never"`
(`lib.rs:144-151`, `ty_project/src/metadata/options.rs:1638-1645`), and `tests/typecheck/ty.toml` does not set it.
Upstream has no `invalid-return-type` check against the inherited type: `return_type_inference.md:558` has
`# TODO: This should be an invalid-return-type error.` Return statements also get no type context from it, because
`lexical_return_type` (`types/signatures.rs:98-108`) gives `Unknown` without an annotation, so `{"FINISHED"}` would
be inferred as `set[str]`.

### Recommended design

The design has one shared query and four one-line hooks, plus the existing `on_load` hook for `self.layout`.

**The query.** A new file, `types/dedicated/blender/overrides.rs`, holds
`override_types(db, function) -> Option<OverrideTypes>`. It is salsa-tracked with `cycle_initial = None`, the same
as upstream's `inherited_return_annotation`. It answers only for a method that meets all of these:

- it is a method of a class defined in the add-on;
- its name is a callback row in the `ty_blender` table, for one of the class's `bpy_types_bases`
  (`dedicated/blender/symbols.rs:89`). It checks the name against the table before it walks the MRO, which keeps it
  cheap on the hot `raw_signature` path.

**Which base is the parent.** The parent is the first class after the class itself in the MRO that defines the
name, among the classes that are `bpy.types` classes or derive from one. A plain mixin is skipped, so it never
supplies types. An intermediate Blender-based class does supply them, and its own unannotated override has already
been typed recursively. When the parent is overloaded, the query gives no answer, as upstream does.

**What the query returns:**

- **Positional parameters.** For each positional parameter after the receiver that has no annotation, the type of
  the parent's positional parameter at the same index. Names are ignored. A short `draw_item` maps its first 7
  parameters. Positions the parent does not have stay as they are.
- **Keyword-only parameters.** A keyword-only parameter with a default and no annotation gets the default's type,
  promoted (`Type::promote`, `types.rs:3715`): `verbose=False` gives `bool`.
- **`*args` / `**kwargs`.** Untouched.
- **Return.** For an unannotated return, the parent's return type.
- **`bool_result`.** From the table: `poll`, `check`, `poll_instance`, and the other callbacks Blender converts
  with `bool()`.

#51 owns the table rows. This ticket needs only three things from them: whether a name is a callback of a given
root, the `bool_result` flag, and the list of draw callbacks for `self.layout`.

### Hooks

| # | Purpose | Where | Change |
| --- | --- | --- | --- |
| A | Signature: callers, signature help, Liskov | `types/function.rs:771`, in `OverloadLiteral::raw_signature` after `add_implicit_self_annotation` (`:681-769`) | `blender::apply_override_types(db, self, &mut raw_signature);` sets the parameters (`with_annotated_type`, so signature help shows them) and an `Unknown` return type. Because the return type is then no longer `Unknown`, `signature_with_inferred_return_type` (`:1745`) leaves it alone, also under `"always"`. |
| B | Body: parameter bindings (`assert_type` in bodies, hover, completion) | `types/infer/builder/function.rs:1158`, the `else` branch of `infer_parameter_definition` | A first arm, `if let Some(ty) = blender::override_parameter_type(db, definition) { ty } else ...`. This mirrors how upstream keeps implicit `self` in two places (`special_first_method_parameter_type` for the body, `add_implicit_self_annotation` for the signature). |
| C | Type context for `return` values | `types/signatures.rs:107`, `lexical_return_type` (its only caller is `infer_return_statement`, `infer/builder.rs:5496`) | `.unwrap_or_else(Type::unknown)` becomes a fallback to `blender::override_return_context(db, definition)`. It gives `None` for `bool_result` callbacks. `{"FINISHED"}` is then inferred as `set[Literal[...]]`, and `{"DONE"}` stays `set[str]`. |
| D | `invalid-return-type` for an unannotated return | `types/infer/builder/function.rs:182-371`: add `else { self.check_blender_override_returns(function) }` after `if let Some(returns) = ...` | The code goes in a new `infer/builder/function/blender.rs`. The precedent is `type_expression.rs` with `type_expression/blender.rs`. The function checks `self.return_types_and_ranges` against the parent's return type, and checks a reachable end of the scope (`is_end_of_scope_reachable`). It reports through `report_invalid_return_type` / `report_implicit_return_type` (`diagnostic.rs:2765`, `:3021`, which are `pub(super)` in `types`, so reachable from there). It uses the `def` name's range in place of `returns.range()`. It skips `bool_result` callbacks and stub-like bodies. |
| E | `self.layout` | No new hook. Extend the existing `blender::on_load` (`dedicated/blender/member.rs:400`) before the early return on `is_definitely_bound` (`:436`) | When the name is `layout`, find the enclosing function scope with `semantic_index(db, file).try_expression_scope_id(&*attribute.value)` (`ty_python_core/src/lib.rs:433`). If that function is `draw` / `draw_header` / `draw_header_preset` of a class deriving from `Panel` / `Menu` / `Header`, drop `None` from the resolved type. This works on both generators: builtin declares a `UILayout \| None` attribute, and fake-bpy-module a property. |

### Markers that move

The recorded lines for these add-ons are identical on `builtin` and `fake-bpy-module`, so everything below holds
for both generators on `main`.

| Add-on / file | Moves to pass | Hook |
| --- | --- | --- |
| `inh_overrides/__init__.py` | all 33 `type-assertion-failure`s: `context` #1–#15, `properties`, `event` #1–#4, `ctx`, `verbose`, `Context \| None` ×2, `layout` #1–#5, `node`, `text`, `ntree`, `self.layout` | B, plus E for `self.layout` |
| `inh_overrides/check_inh_overrides.py` | all 11 `type-assertion-failure`s and all 4 `unused-ignore-comment`s (`execute(1)`, `invoke(context, context)`, `check(..., verbose="yes")`, `draw_buttons(context, 1)`) | A |
| `inh_override_types/__init__.py` | all 4 `unused-ignore-comment`s (`{"DONE"}`, `"FINISHED"`, `["FINISHED"]`, `def execute` without a return) | C + D |
| `inh_mixins/__init__.py` | `assert_type(context, Context)` and `assert_type(event, Event)` in `INH_MIXINS_OT_base.invoke`. `ExecuteMixin`'s `assert_type(context, Any)` keeps passing, because the mixin is skipped. | B |
| `inh_overrides/ide_inh_overrides.py` | `^hover-contains "Context"` on `ctx`, `^completion mouse_x`, `^hover-contains "UILayout"` (short `draw_item`), so IDE goes from 0/3 to 3/3. The `^signature` record changes from `(ctx) -> Unknown` to `(ctx: Context) -> set[...]`. | B for the three markers, A for `^signature` |
| other diagnostics | `prefs_ext/ui/panel.py` `self.layout.prop(preferences(...), "scale")` (the entry is the line in `draw`; line 16 is the class line), `inh_chains` ×2, `inh_registered_base` `self.layout.label` ×2, `opprops_idnames` ×2, `opprops_sinks` ×5 (`layout = self.layout` in `Panel.draw`), `reg_autoload/panels.py` ×1 | E |

The inheritance row of `main.progress.md` would go from 16/62 to 62/62 for `assert_type`, from 3/42 to 11/42 for
expected errors, and from 0/3 to 3/3 for IDE.

**Not moved here:**

- The `invalid-method-override` lines (`execute(self, ctx)`, the short `draw_item`, `Node.poll(cls, ntree)`, and
  the `inh_mixins` class lines) belong to #51.
- The `blender-*` ignore-comment lines belong to #51 and #52.

### Decisions to hand on (to #54 or the map)

1. **`Operator.draw` is not in the settled list.** `inh_overrides/__init__.py` `self.layout.prop(self, "count")`
   (`unresolved-attribute`) is in `Operator.draw`. Both stubs type `Operator.layout` as `UILayout | None`, and the
   settled narrowing covers only Panel, Menu, Header and UIList, so this line stays failing. **Recommendation:** add
   `Operator.draw` to the narrowing, because Blender sets `layout` for it as it does for panels. Otherwise it must be
   a named exception.
2. **UIList has no `layout` attribute** in either generator's stubs, so it has nothing to narrow. Its `draw_item`
   `layout` is a parameter, which hook B types.
3. **Exact `T`, not `T | Unknown`.** This goes against the direction of the upstream discussion on #4424. It is
   limited to the table's callbacks on classes deriving from a `bpy.types` class.
4. **5.2.** Only re-record. On 5.2, `prefs_ext/__init__.py` and `prefs_legacy` `self.layout.prop(self, "scale")`
   are in `AddonPreferences.draw`, which the settled narrowing does not cover; on `main` those lines already pass.
   The 5.2 `invalid-argument-type` and `invalid-method-override` lines stay stub-blocked or go to #51.

### Risks for the build ticket

- **New errors from typed parameters.** Typing `context` as `Context` exposes `Optional` attributes from the stubs:
  builtin has `scene: Scene | None`, `preferences: Preferences | None`, `window_manager: WindowManager | None`. A
  grep of the test add-ons finds no unguarded `context.<optional>.<attr>` in callback bodies; the one hit,
  `check_props_registered.py:96`, is already annotated. Real add-ons will see these errors, and that is the stubs'
  verdict.
- **`Self` in the parent.** fake-bpy-module's `Node.copy(self, node: Self)` would carry the parent's `Self`. Bind
  it to the child, or skip such parameters. No marker tests this.
- **Cost and cycles.** Hook A runs inside `raw_signature`, which is hot. Do the table check before any MRO walk.
  The query must not read the add-on index or the `register()` walk: parameter typing applies to every subclass of
  a Blender class, registered or not. The IDE test class `IDE_OT_hover` is unregistered and must still get types.

## Evidence

- **Ticket and spec.** `gh issue view 50` and `gh issue view 49`. The rules are in
  `tests/typecheck/features/inheritance/README.md` ("Rules", "Callback signatures", "Return values"). The intended
  signatures are in `inheritance/inh_overrides/_expected/addon/__init__.pyi`: for example
  `def check(self, context: Context, *, verbose: bool = False) -> bool` and
  `def execute(self, ctx: Context) -> set[Literal[...]]`.
- **Upstream parameter typing.**
  - `types/infer/builder/function.rs:1157-1170`: an unannotated parameter is `Unknown`, `Unknown | default`, or the
    special first parameter.
  - `types/signatures.rs:6221-6227` (`from_node_and_kind`): an unannotated parameter gets
    `(Type::unknown(), inferred_annotation = true)`.
  - Implicit `self` lives in two places: `special_first_method_parameter_type` (`infer/builder/function.rs:1252`)
    and `add_implicit_self_annotation` (`signatures.rs:1386`, called at `function.rs:681`).
  - Code search of `astral-sh/ruff` for `inherited_parameter` finds nothing.
  - astral-sh/ty#4424, "Infer unannotated override parameter types from the overridden method": opened
    2026-08-31, open, labels `overrides` and `type-inference`. sharkdp: inferring the base type "would violate the
    gradual guarantee"; carljm: `str | Unknown` "is reasonable".
- **Upstream return typing.**
  - `types/function.rs:1734-1758` (`signature_with_inferred_return_type`) does nothing unless
    `return_type_inference.is_active()` holds and the return type is `Unknown`.
  - `:1835-1836` lets an inherited annotation win over the type inferred from the body.
  - `:1860-1910` is `inherited_return_annotation`: it walks the MRO with `skip(1)` and takes the first base whose
    member has an explicit return annotation, with a single overload and default specialization.
  - mdtest: `resources/mdtest/function/return_type_inference.md:521-563` (the setting is
    `return-type-inference = "always"`, and the TODO is at `:558`).
- **Return check and context.**
  - `types/infer/builder/function.rs:182` is the whole return check, inside `if let Some(returns)`.
  - `infer/builder.rs:5486-5519` is `infer_return_statement`, which gets its type context from
    `lexical_return_type` (`signatures.rs:98`).
- **Stub signatures** (`.cache/bpy-stubs-builtin/main/bpy/types/__init__.pyi`, and fake-bpy-module `main`, read
  with `ast`):

  | Class | Callbacks | `layout` |
  | --- | --- | --- |
  | `Operator` | `execute` / `invoke` / `modal` return `set[...]`; `poll(cls, context: Context) -> bool`; `check -> bool`; `description(cls, context, properties: OperatorProperties) -> str` | `UILayout \| None` |
  | `Panel` | `draw`, `draw_header`, `draw_header_preset` take `context: Context` and return `None` | `UILayout \| None` |
  | `Menu` | `draw(self, context: Context \| None)` | `UILayout \| None` |
  | `Header` | `draw(self, context: Context \| None)` | `UILayout \| None` |
  | `UIList` | `draw_item(self, context: Context \| None, layout: UILayout, data, item, icon: int, active_data, active_property: str, index: int, flt_flag: int)` | none |
  | `Node` | `poll(cls, node_tree: NodeTree \| None) -> bool`; `draw_label(self) -> str` | — |

  fake-bpy-module types `layout` as a property returning `None | UILayout | None`.
- **Recorded results.**
  - `tests/typecheck/expected/{builtin,fake-bpy-module}/main.txt`: the `inh_overrides`, `inh_override_types` and
    `inh_mixins` lines are identical on both generators (`diff`).
  - `main.progress.md`: inheritance has 16/62 `assert_type`, 3/42 expected errors, 0/3 IDE, and 9 other
    diagnostics.
  - `main.ide.md`: the four `ide_inh_overrides.py` sections are identical on both generators.
- **Existing hooks reused.**
  - `on_load`: `dedicated/blender/member.rs:400`, called from `infer/builder.rs:11243`.
  - Builder-extension precedent: `infer/builder/type_expression.rs:1` (`mod blender;`).
  - `bpy_types_bases`: `dedicated/blender/symbols.rs:89`.
  - `derives_from`: `dedicated/blender/classes.rs:24`.
  - `REGISTRABLE_ROOTS`: `ty_blender/src/registration.rs:7`.

Caveat: the fake-bpy-module `bpy-stubs/types/__init__.pyi` in `.cache` was being rewritten (0 bytes) while I
checked `Context` there. The fake signatures above come from an earlier read in this session.
