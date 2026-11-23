# How does an unannotated override get the parent's types? (#50)

Research note, 2026-11-06, for [#50](https://github.com/taway1450/blender-extension-developer-suite/issues/50)
(map #49). Trimmed on 2026-11-18 to the rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings.

Fork: `ty-blender/ruff-blender`, branch `blender` at `b4135144e1`, upstream merge-base `f076cb67a1` (2026-11-04).
Paths below are relative to `crates/ty_python_semantic/src/` and were read at that commit.

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
(`types/function.rs`), an unannotated method takes the return annotation of the nearest base that has one. It only
runs with `[analysis] return-type-inference = "always"`. The default is `"never"`, and `tests/typecheck/ty.toml`
does not set it. Upstream has no `invalid-return-type` check against the inherited type:
`return_type_inference.md` has `# TODO: This should be an invalid-return-type error.` Return statements also get no
type context from it, because `lexical_return_type` (`types/signatures.rs`) gives `Unknown` without an annotation,
so `{"FINISHED"}` would be inferred as `set[str]`. So the fork adds its own return side for Blender callbacks: on
main an unannotated callback override's `return` values get the parent's return type as context and are checked
against it (`override_return_type` in `dedicated/blender/overrides.rs`), except for callbacks Blender converts with
`bool()`.

### What the parent is

The parent is the first class after the class itself in the MRO that defines the name, among the classes that are
`bpy.types` classes or derive from one. A plain mixin is skipped, so it never supplies types. An intermediate
Blender-based class does supply them, and its own unannotated override has already been typed recursively. When the
parent is overloaded, nothing is inherited, as upstream does.

Positional parameters take the parent's type by index, ignoring names (a short `draw_item` maps its first 7).
A keyword-only parameter with a default and no annotation gets the default's type, promoted: `verbose=False`
gives `bool`. `*args` and `**kwargs` are untouched.

Parameter typing applies to every subclass of a Blender class, registered or not, so it must not read the add-on
index or the `register()` walk. Upstream keeps implicit `self` in two places (one for the body, one for the
signature), and the parent's types follow the same split: the signature for callers, signature help and Liskov,
the parameter bindings for the body.

`self.layout`: on main it is `UILayout` in every instance method of `Panel`, `Menu` and `Header`, and in
`Operator.draw` (`DRAWN_CLASSES` / `DRAW_CALLBACKS` in `dedicated/blender/member.rs`). A Panel, Menu or Header
instance exists only while Blender draws it. Elsewhere (`poll`, a timer, `AddonPreferences.draw`, an operator's
`execute`) it may be `None`. `UIList` has no `layout` attribute in either generator's stubs; its `draw_item`
`layout` is a parameter.

### Decision: exact `T`, not `T | Unknown`

This goes against the direction of the upstream discussion on #4424. It is limited to the table's callbacks on
classes deriving from a `bpy.types` class.

### Risks

- **New errors from typed parameters.** Typing `context` as `Context` exposes `Optional` attributes from the stubs:
  builtin has `scene: Scene | None`, `preferences: Preferences | None`, `window_manager: WindowManager | None`.
  Real add-ons will see these errors, and that is the stubs' verdict.
- **`Self` in the parent.** fake-bpy-module's `Node.copy(self, node: Self)` would carry the parent's `Self`. Bind
  it to the child, or skip such parameters. No marker tests this.
- **Cost and cycles.** The signature query runs inside `raw_signature`, which is hot. Check the name against the
  table before any MRO walk.

## Evidence

- **Upstream parameter typing.**
  - `types/infer/builder/function.rs` (`infer_parameter_definition`): an unannotated parameter is `Unknown`,
    `Unknown | default`, or the special first parameter.
  - `types/signatures.rs` (`from_node_and_kind`): an unannotated parameter gets
    `(Type::unknown(), inferred_annotation = true)`.
  - Implicit `self` lives in two places: `special_first_method_parameter_type` (body) and
    `add_implicit_self_annotation` (signature).
  - Code search of `astral-sh/ruff` for `inherited_parameter` finds nothing.
  - astral-sh/ty#4424, "Infer unannotated override parameter types from the overridden method": opened
    2026-08-31, open, labels `overrides` and `type-inference`. sharkdp: inferring the base type "would violate the
    gradual guarantee"; carljm: `str | Unknown` "is reasonable".
- **Upstream return typing.**
  - `signature_with_inferred_return_type` (`types/function.rs`) does nothing unless
    `return_type_inference.is_active()` holds and the return type is `Unknown`. An inherited annotation then wins
    over the type inferred from the body.
  - `inherited_return_annotation` walks the MRO with `skip(1)` and takes the first base whose member has an
    explicit return annotation, with a single overload and default specialization.
  - mdtest: `resources/mdtest/function/return_type_inference.md` (the setting is
    `return-type-inference = "always"`, and the TODO is there).
  - The whole upstream return check sits inside `if let Some(returns)` in `infer/builder/function.rs`, and
    `infer_return_statement` gets its type context only from `lexical_return_type`.
- **Stub signatures** (`.cache/bpy-stubs-builtin/main/bpy/types/__init__.pyi`, and fake-bpy-module `main`):

  | Class | Callbacks | `layout` |
  | --- | --- | --- |
  | `Operator` | `execute` / `invoke` / `modal` return `set[...]`; `poll(cls, context: Context) -> bool`; `check -> bool`; `description(cls, context, properties: OperatorProperties) -> str` | `UILayout \| None` |
  | `Panel` | `draw`, `draw_header`, `draw_header_preset` take `context: Context` and return `None` | `UILayout \| None` |
  | `Menu` | `draw(self, context: Context \| None)` | `UILayout \| None` |
  | `Header` | `draw(self, context: Context \| None)` | `UILayout \| None` |
  | `UIList` | `draw_item(self, context: Context \| None, layout: UILayout, data, item, icon: int, active_data, active_property: str, index: int, flt_flag: int)` | none |
  | `Node` | `poll(cls, node_tree: NodeTree \| None) -> bool`; `draw_label(self) -> str` | — |

  fake-bpy-module types `layout` as a property returning `None | UILayout | None`.
