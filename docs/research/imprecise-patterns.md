# Imprecise patterns: what add-ons write that is less precise than the stubs

Research note, 2026-11-16, for wayfinder ticket #91 (map #87). Trimmed on 2026-11-18 to the rationale and the
Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings.

The question was which common add-on patterns are less precise than the stubs but should be accepted
(**Imprecise pattern**), which the typechecker can make precise on its own, and whether ty or the fork already
gives an unannotated override its parent's parameter and return types (callback inference).

On main the Imprecise patterns are the rules `blender-imprecise-operator-return` (P3, P4),
`blender-imprecise-enum-value` (P5) and `blender-imprecise-callback-parameter` (P7). They ship at `warn`: ty has
no `info` rule level (§2). The Typechecker fixes found on the way (P6, tuple `filter_items`, the `RenderEngine`
keyword-only parameters) are done.

Conventions:

- Every fact has a source next to it, either a URL or a `path:line`. `ruff-blender/` is short for
  `ty-blender/ruff-blender/`, `blender/` for `.cache/blender-src/main/` (Blender 7031144c2c, the commit
  `check:blender` recorded). Fork paths were read on 2026-11-16.
- Third-party evidence is GitHub code search (`gh api search/code`, 2026-11-16). It counts files, includes
  forks and copies, and is only a rough guide.

---

## 1. Callback inference: does ty or the fork already do it?

**Upstream ty 0.0.98: no.** An unannotated parameter of an override is `Unknown`, and so is its return type unless
return-type inference is turned on.

- The 0.0.98 changelog (`ty-blender/CHANGELOG.md`) and the releases before it have no entry for parameter types
  from the overridden method. The nearest entries are about attributes: "Inherit annotations for unannotated
  subclass defaults" ([ruff#28575](https://github.com/astral-sh/ruff/pull/28575)) and
  "Preserve inherited annotations for unannotated subclass attributes when a base has type `Any` or `Unknown`"
  ([ruff#28973](https://github.com/astral-sh/ruff/pull/28973)).
- Upstream's override mdtests accept unannotated overrides because their parameters are gradual
  (`ruff-blender/crates/ty_python_semantic/resources/mdtest/liskov.md`: "Unannotated overrides of overloaded
  dunder methods should remain accepted").
- Return-type inference exists since 0.0.89 but is off by default: `analysis.return-type-inference`, default
  `"never"` (`ruff-blender/crates/ty/docs/configuration.md`). Even with `"always"` it infers the return from the
  body (`{"FINISHED"}` gives `set[str]`), not from the parent.

**Planned upstream: an open issue, no pull request.**
[astral-sh/ty#4424](https://github.com/astral-sh/ty/issues/4424), "Infer unannotated override parameter types from
the overridden method", opened 2026-08-31 against ty 0.0.75, labels `type-inference` and `overrides`. In the
thread, sharkdp points out that taking the parent's type exactly may be too strict, since a subclass may accept wider
parameter types. carljm suggests inferring `str | Unknown` (the parent's type joined with `Unknown`) as the plan,
and jelle-openai argues for the plain parent type. No pull request is linked. The issue itself says the **return
type should not be inherited**. Two issues in this repo (#50, #54) already cross-reference it.

**Pyright does it for parameters only.** Pyright's docs: for an unannotated parameter "Pyright looks for a method of
the same name implemented in a base class", and "When parameter types are inherited from a base class method, the
return type is not inherited"
([pyright docs/type-inference.md](https://github.com/microsoft/pyright/blob/main/docs/type-inference.md#parameter-type-inference)).
Pyrefly does not do it yet ([pyrefly#4742](https://github.com/facebook/pyrefly/issues/4742), cited in ty#4424).

**The fork: yes, for Blender callbacks, parameters and return** (since the inheritance feature, map #49; see
[override-typing.md](override-typing.md)). It takes the parent's positional parameter types by position (names
don't matter) and its return type, from the first `bpy.types` class (or subclass of one) in the method resolution
order that defines the callback. Plain mixins are skipped. `return` values get the parent's return type as context
and are checked against it; `poll` and the other callbacks whose result Blender turns into a bool accept any value,
and array returns also accept any sequence. The override contract makes the parent's parameters positional-only,
so a renamed parameter or a short `UIList.draw_item` is accepted. **Explicit annotations are still compared with
the parent as they are written.** That is where every Imprecise pattern below comes from.

**What it would take upstream, and the risk for the fork.** ty#4424's conservative scope (not overloaded, one
unambiguous parent, the same parameter shape, specialized for the subclass) is narrower than the fork's
positional, name-blind rule, which matches how Blender calls callbacks. If upstream lands `T | Unknown`, the fork
still needs its own hook, because for a Blender callback Blender passes exactly the parent's types. Both changes
would touch the same places (the function's raw signature and `lexical_return_type`), so expect a rebase conflict
there, not a change in behaviour. Upstream will not take the return type, so the fork's return checking stays
fork-only.

---

## 2. Is "info" available as a level?

ty's rule levels are `ignore`, `warn` and `error` (`ruff-blender/crates/ty_python_semantic/src/lint.rs`), and
`Level` maps only to `Severity::Warning` or `Severity::Error`. `Severity::Info` exists
(`ruff-blender/crates/ruff_db/src/diagnostic/mod.rs`), but only diagnostics outside the rule system use it:
`reveal_type` and pytest's collection and fixture diagnostics. Info diagnostics don't fail the run
(`ruff-blender/crates/ty/src/lib.rs`: `Severity::Hint | Severity::Info => ExitStatus::Success`).

So a rule "at info" would need either a `Level::Info` in the fork, which touches an upstream file plus the
configuration schema, or a diagnostic sent with `Severity::Info`, which users then cannot configure like a rule.
The Imprecise-pattern rules ship at `warn` instead.

---

## 3. The patterns

"Shipped" means `scripts/startup`, `scripts/modules`, `scripts/addons_core`, `scripts/freestyle` and the Cycles
add-on.

| # | Pattern | Upstream ty's verdict | On main |
|---|---|---|---|
| P1 | Unannotated callback `def execute(self, context):` | nothing (gradual) | silent, typed from the parent |
| P2 | Exact annotations, aliases, partial annotations | nothing | silent |
| P3 | `-> set[str]` / `-> Set[str]` on `execute` / `invoke` / `modal` | `invalid-method-override` | Imprecise pattern, typed as the parent |
| P4 | Return set held in a variable (`ret = {"CANCELLED"}` … `return ret`) | `invalid-return-type` | Imprecise pattern |
| P5 | A `str` (or `set[str]`) value where the stubs have an enum `Literal` | `invalid-argument-type` / `invalid-assignment` | Imprecise pattern, only for non-literal `str` |
| P6 | Narrower but precise return (`-> set[Literal["FINISHED", "CANCELLED"]]`, `frozenset`) | `invalid-method-override` (set invariance) | silent (Typechecker fix) |
| P7 | Callback parameter annotated as the subclass Blender passes (`item: MyItem`, `data: Armature`) | `invalid-method-override` | Imprecise pattern if a subtype of the parent's type, else error |
| P8 | Mixins that declare Blender methods with loose types | `invalid-method-override` (base conflict) | covered by P3 / P5 for the types |
| – | Bare `-> set`, `-> Set` | `set[Unknown]`, gradual: nothing | silent |

Why string literals must stay precise: `scripts/startup/bl_operators/anim.py:412` returns
`{'OPERATOR_CANCELLED'}`, which is not an operator return item. Blender raises "incompatible return value"
(`blender/source/blender/python/intern/bpy_rna.cc:10221`; the item lookup error is at `bpy_rna.cc:1401`). So a set
display or string literal that is not an item stays an error in every pattern below.

### P1. Unannotated callbacks: silent

- **Blender:** almost every callback in Blender's own scripts is unannotated. `templates_py` and
  `doc/python_api/examples` are entirely unannotated.
- **Official style:** the manual's add-on tutorial writes `def execute(self, context):` with no annotations
  ([Add-on Tutorial](https://docs.blender.org/manual/en/latest/advanced/scripting/addon_tutorial.html)).
- **Third-party:** `"def execute(self, context):" "bl_idname"` is by far the most common form on GitHub.
- This is the precise path, not an Imprecise pattern: parameters and return come from the parent (§1).

Two related silent cases with no precision at all: an unannotated helper that returns the status
(`return import_svg.load(...)`) is `Unknown` while return-type inference is off, and plain functions Blender calls
(property `update=` / `items=` callbacks, `menu.append(func)`, handlers, timers) get `Unknown` parameters. Neither
produces a diagnostic.

### P2. Exact annotations, aliases and partial annotations: silent

- **Blender:** `context: Context` (`copy_global_transform.py`, `pose_library`), `context: bpy.types.Context`
  (`rigify/__init__.py:282`), `-> None` on `draw`, `-> bool` on `poll`, `layout: UILayout`.
- `bpy.types.Context`, `Context` imported under any alias and the string `"Context"` are all the same class. A
  partly annotated `def invoke(self, context: Context, event)` takes `event` from the parent. The 5.2 stubs type
  `context` as `Context | None`, so there an explicit `Context` is narrower; that is a stub difference and not a
  pattern.

### P3. `-> set[str]` on `execute`, `invoke`, `modal`: Imprecise pattern, typed as the parent

- **Blender:** `copy_global_transform.py:151,181,326` and `node_wrangler/operators/labels_modify.py:40`
  (`set[str]`), `pose_library/operators.py:65,103,116,190` (`typing.Set[str]`), plus two mixins:
  `FixToCameraCommon.execute` (`copy_global_transform.py:640`) and `PoseAssetUser.execute`
  (`pose_library/operators.py:228`).
- **This repo:** the example add-on uses it too (`examples/addons/simple_scatter/__init__.py`).
- **Third-party:** common in typed add-ons and templates (for example Oxicid/UniV `operators/mark.py`,
  SuperFLEB/blender_addon_template `src/operator/an_operator.py`). The precise spellings (`OperatorReturnItems`,
  fake-bpy-module's alias) are rarer. A template that uses `set[str]` spreads it to every add-on made from it.
- **Upstream's verdict:** `invalid-method-override` on each `def`, and a base-class conflict on the mixins. `set` is
  invariant, so `set[str]` is not a `set[Literal["RUNNING_MODAL", ...]]`. Inside the method the returns are checked
  only against `set[str]`, so `return {"FINSHED"}` passes.
- **Why it's imprecise, not wrong:** the literal types exist only in the stubs (map #87), and Blender checks the
  items itself at runtime (`bpy_rna.cc:1401`).
- **Design:** when the override's annotation is the parent's type with its string literals widened to `str`
  (`set[str]` or `Set[str]` for `set[Literal[...]]`), treat the method as if the return were unannotated: callers
  and `return` statements get the parent's `set[Literal[...]]`. Report the annotation once, suggesting the precise
  spelling. That way `return {"FINSHED"}` is still an error, and `return self.execute(context)` in an unannotated
  `invoke` gets no follow-on error. The same rule covers a mixin whose method is the one Blender calls.

### P4. A return set held in a variable: Imprecise pattern

- **Blender:** `io_curve_svg/__init__.py:65-70` (`ret = {'CANCELLED'}` … `ret = {'FINISHED'}` … `return ret`),
  `io_scene_fbx/__init__.py:235`, `bl_operators/userpref.py:522-534` (`result = {'FINISHED'}` / `{'CANCELLED'}`).
- **Third-party:** common in any operator that collects a result across a loop or branches.
- **Upstream's verdict:** `invalid-return-type ... expected set[Literal["RUNNING_MODAL", ...]], found set[str]`. An
  unannotated variable has no type context, so `{'CANCELLED'}` is inferred as `set[str]` (ty, like pyright and
  mypy, widens literals in a mutable container).
- **Can the typechecker make it precise?** Not without an annotation: the type of `ret` comes from its own
  assignments. A narrow fork rule could give an assignment the callback's return type as context when the variable
  is only ever returned. That is more machinery than the pattern is worth.
- **Design:** where a Blender callback's return expects `set[Literal[...]]` and the value is a non-literal
  `set[str]`, accept it and report the Imprecise pattern. A set display whose items are string literals
  (`return {'OPERATOR_CANCELLED'}`) is checked item by item and stays an error. Such a display also has the type
  `set[str]` (`anim.py:412`), so the rule has to look at the expression and not only at the type.

### P5. A `str` value where the stubs have an enum `Literal`: Imprecise pattern

- **Blender (shipped):** `bpy.data.lights.new(type=light_type)` (`io_scene_fbx/import_fbx.py:2234`),
  `owner.constraints.new(con_type)` (`rigify/utils/mechanism.py:85`), `bone.inherit_scale = inherit_scale`
  (`rigify/utils/bones.py:487`), `image_settings.file_format = formats[...]`
  (`node_wrangler/operators/save_viewer_image.py:79`), `km.keymap_items.new(..., hotkey.key, hotkey.input_mode)`
  (`node_wrangler/preferences.py:401-402`), `label(icon=icon)` / `operator(icon=icon)` with a computed icon name
  (`space_node.py:587`, `space_userpref.py:2670`, `properties_strip.py:55`). Tests pass `os.environ` values and
  f-strings (`storm_render_tests.py:208`, `compositor_file_output_tests.py:241`), and `set[str]` to the enum-flag
  `select_mode` (`bl_pyapi_bmesh.py:876,959`).
- **Why it is rare in Blender:** most of its enum values come from unannotated functions and attributes, which are
  `Unknown`. Add-ons with annotated helpers (`def set_mode(mode: str)`) hit it far more often, for example
  `bpy.ops.object.mode_set(mode=mode)`.
- **Design:** only for a value whose type is `str` (or `set[str]` for an enum flag) where the expected type is a
  Blender enum `Literal` (or a set of one). A string literal that is not an item (`obj.mode = "OBJCT"`) is a
  `Literal["OBJCT"]`, not `str`, and stays an error. Blender raises at runtime for an unknown item
  (`blender/source/blender/python/generic/py_capi_utils.cc:1539`, `bpy_rna.cc:1401`), which is the same guarantee
  as for P3 and P4.
- Dynamic enums whose stub `Literal` lists only `"DEFAULT"` (`GREASE_PENCIL_OT_set_material.slot`,
  `NodeTreeInterface.new_socket(socket_type=...)`) are a stub problem, not this pattern: the real items come from a
  callback, so the stub should say `str`.

### P6. A narrower, precise return annotation: silent

- `-> set[Literal["FINISHED", "CANCELLED"]]`, or returning a `frozenset`, is more precise than the stubs. `set`
  is invariant, so upstream's override check rejects it the same way as P3.
- Blender reads the returned set and never writes to it. It accepts any `set` or `frozenset` (`PyAnySet_Check`,
  `bpy_rna.cc:1421`, reached from `bpy_class_call` at `bpy_rna.cc:10213` through `pyrna_py_to_prop`).
- So the fork compares enum-set callback results covariantly, as `collections.abc.Set[Literal[...]]`, the same way
  it widens array outputs to sequences. This is a Typechecker fix, not an Imprecise pattern. The same reasoning
  covers a callback with several outputs: `filter_items` returns a tuple of two arrays, and each element is widened
  on its own.

### P7. Callback parameters annotated with the subclass Blender passes: Imprecise pattern

- **Blender:** `rigify/operators/action_layers.py:359` (`draw_item(..., data: Armature, ...)`; the parent has
  `bpy_struct | None`) and `pose_library/operators.py:285`
  (`description(cls, _context, properties: 'POSELIB_OT_pose_asset_select_bones')`).
- **Third-party:** typed `UIList`s usually annotate `item` with their own `PropertyGroup`.
- **Upstream's verdict:** `invalid-method-override`. Narrowing a parameter breaks Liskov for callers that go
  through the base type, but only Blender calls a callback, and it passes what the add-on gave it
  (`template_list(data, ...)`).
- **Design:** an Imprecise pattern when the annotation is a subtype of the parent's parameter type without
  `None`. Keep the error when it is unrelated (`context: int`, which `inh_override_types` expects to stay an
  error). For `description`, the unannotated form already gets the operator's own properties, so the message can
  point there.

### P8. Mixins that declare Blender methods with loose types

- **Blender:** `FixToCameraCommon` (`copy_global_transform.py:610-640`) declares `poll_message_set(cls, message:
  str)`, `report(self, level: set[str], message: str)` and `execute(...) -> set[str]` so that it type-checks on
  its own. Blender's own `bpy.utils.keyconfig_set` annotates its `report` callback as taking `set[str]`, so
  passing `self.report` fails (`userpref.py:92,281`).
- The types are P3 (return) and P5 (parameter). A mixin parameter wider than the stubs is fine, and a `set[str]`
  return is P3. In Blender's own code these are Blender fixes: use the `_rna_enums` names under
  `if TYPE_CHECKING:`. Third-party mixins get the P3 rule.
