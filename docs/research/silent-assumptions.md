# Where the fork assumes or guesses silently

Research note, 2026-11-16, for [#89](https://github.com/taway1450/blender-extension-developer-suite/issues/89) (map
[#87](https://github.com/taway1450/blender-extension-developer-suite/issues/87)). Trimmed on 2026-11-18 to the
rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings.

The question: where does ty-blender (and the stubs the Blender fork generates) give up soundness without telling the
user, and should each place stay silent, become an **Assumption** (its own `blender-*` rule), or become an error?
The original proposed `info` levels; ty has no info rule level, so on main the Assumptions ship at `warn` (see
[imprecise-patterns.md](imprecise-patterns.md) §2).

Most of the places the note proposed to report have since been built: popover narrowing
(`blender-narrowed-by-popover`), registration on a branch (`blender-assumed-registration`), the whole-add-on
fallback when the `register()` walk gives up (`blender-assumed-complete-registration`), preferences read in the
registration window (`blender-assumed-preferences`), foreign values reaching `register_class` (the walk gives up),
and the dynamic context members (`context.object`, ...), which main's builtin stubs type `X | None`, narrowed by a
`poll()` check (`blender-narrowed-by-poll`). Their rules and feature READMEs (`tests/typecheck/features/`) document
them. What stays here is why the rest stays silent.

Conventions: `blender/` is `.cache/blender-src/main/` (the commit `check:blender` recorded on 2026-11-16).
Fork file names are under `ty-blender/ruff-blender/crates/`.

---

## 1. Guaranteed context members in callbacks

Inside a Blender callback, `preferences`, `window_manager`, `blend_data`, `scene`, `view_layer` and `tool_settings`
of any `Context` instance drop `None`. The callback is found by name in a class deriving from a callback root, not
by registration.

**When it fails.** Only when user code empties the context: `context.temp_override(scene=None)` around a call that
reaches a callback (#68). Other edge cases hold:

- `bpy.ops` overrides: the legacy positional override dict is gone since 4.0. `temp_override(window=..., area=...)`
  keeps a scene: the scene comes from the window, or the loaded file's scene without one (#68).
- RenderEngine callbacks are called with no context (`rna_ext.call(nullptr, ...)`,
  `blender/source/blender/makesrna/intern/rna_render.cc:118` and the eleven calls after it), so `bpy.context` there
  is Blender's global context (`BPY_context_get()`, `blender/source/blender/python/intern/bpy_rna.cc:9992-9993`),
  which holds a scene. It is not thread-safe in a render job, but it is not None.
- A lambda in a callback that escapes to a timer would read a later context: no such lambda in Blender.

**Decision: stay silent** inside callbacks. It never fails in ordinary use, and a diagnostic would fire on hundreds
of lines of Blender's own UI for nothing. The one way to break it is visible at its own call site. (Reads outside a
callback are `blender-assumed-context-member` on main.)

---

## 2. Types

On main a Type tag test narrows nothing in a scope that writes the same tag anywhere (`Light.type`, `Area.type`;
`ty_blender::tag_writers`), so a writable tag no longer stays silently narrowed.

### 2.1 Single-subclass collections

`ActionStrips` items are typed `ActionKeyframeStrip`, "the only strip type Blender creates" (#75 BS2, generator commit
`d4ab3d704ec` in #78: single-subclass tags type pointers and collections). It fails only when a future Blender adds a
strip type, and then the probe, which runs per Blender version, picks it up. **Stay silent**: a per-version fact the
generator re-derives, not a guess the user can act on.

### 2.2 Setters and array outputs accept any sequence length

BS4's setters take `Sequence[float]` for `Vector` / `Color` / `Euler` / `Quaternion`, `Sequence[Sequence[float]]` for
`Matrix`, and `Sequence[T]` for `bpy_prop_array[T]` (#75 BS4); H4 accepts `bpy_prop_array[T] | Sequence[T]` as an
array output (`NodeSocket.draw_color`, #63). Blender checks the length at runtime:
`material.diffuse_color = (1, 0, 0)` raises "sequences of dimension 0 should contain 4 items, not 3", and a 3-tuple
from `draw_color` fails the same way. This is a classic add-on mistake, so it fails in ordinary use. But it is a
missing check, not an assumption about Blender: Blender does accept any sequence, of the right length. **Not an
Assumption; a later error rule** (a tuple display or fixed-length tuple of the wrong length), once the generator
states array lengths.

---

## 3. Places that should stay silent

Each holds in every case found, or fails only in code that no type rule could judge:

- **Nested lambdas and comprehensions count as the callback** (`context_members.rs`, `member.rs`): a lambda that
  escapes to a timer would read a later context. None of the lambdas in Blender's shipped callbacks reads a
  guaranteed member or goes to `bpy.app.timers.register`.
- **Callbacks are found by name, not registration** (`context_members.rs`, `member.rs`, `overrides.rs`): an
  unregistered base's `draw` is the registered subclass's. A `draw` called by hand with a foreign `self` is the
  only miss.
- **`self.layout` is `UILayout`** in every instance method of a Panel, Menu or Header, and in `Operator.draw`
  (`member.rs`): Blender sets the layout before calling them, and a Panel, Menu or Header instance exists only while
  it is drawn. `poll` (a classmethod) and other classes keep `| None`.
- **Never-None pointers and callback parameters** (BS1, #69/#77): by-value struct members (read-only, a pointer
  into the parent) and callback parameters whose C callers always pass a context. `RenderEngine.view_draw` keeps
  `Context | None` because Blender passes None off-screen. Sound by construction.
- **Override typing** (H3/H4): parameters take the parent's type by position; Blender calls by position with exactly
  those types. `bool_result` callbacks accept anything because Blender applies `bool()` (`ty_blender/src/callbacks.rs`).
- **Reload guard** (`ty_blender/src/reload_guard.rs`): names in `if "bpy" in locals():` take the module's global
  type; on a reload the module dict still holds them. Fails only when a hot reload adds a name the old module never
  bound.
- **The `__main__` arm never runs** (`ty_blender/src/script_guard.rs`): an add-on is imported as a module.
- **Conditional idnames** (B4, #85): `"a" if c else "b"` refines to the union only when every arm is known, checks every
  arm, and reports a property one arm lacks. Sound.
- **`X.bl_idname` with `X` a class or `self`** (`operator_properties.rs`): the enclosing class's idname, so a
  subclass with its own idname is typed with the base's properties, a subset of its own unless the subclass removes one
  with a plain annotation. False positives only.
- **Registered properties exist everywhere in the add-on**, also at import time and after `unregister()`, and the last
  registration of a name wins (`member.rs`). Reads at import time go through `bpy.context`, which is already
  nullable there.
- **Opaque properties and the partial C-module stubs** are `Any` (GLOSSARY "Property evaluator"; BS5's
  `__getattr__ -> Any`). That is gradual typing, visible on hover, not a hidden assumption.

---

## 4. Blender facts behind the rules built since

- **Popovers.** `layout.popover(...)` / `wm.call_panel` draw the panel in the opening editor's area without checking
  its space type (#68: `popover_panel_invoke`). A `VIEW_3D` panel opened from the Image editor's header reads a
  `SpaceImageEditor`. Popover-only panels use `bl_region_type = 'HEADER'`, Blender's "dummy region". Area and region
  are always set in a popover.
- **A Panel's callback called from another class.** `properties_render.py:1065-1093` calls
  `VIEW3D_PT_shading_lighting.draw(self, context)` and two others from a `PROPERTIES` panel. It survives because
  those draws go through `VIEW3D_PT_shading.get_shading(context)`, a classmethod that checks
  `context.space_data.type` (`space_view3d.py:6757-6763`).
- **Dynamic context members.** Blender's own stub generator writes the screen-context members (`object`,
  `active_object`, `edit_object`, `active_node`, ...) from a hand-written `context_type_map` with no `| None`
  (`blender/doc/python_api/sphinx_doc_gen.py:2337-2346`, written at `:2540-2548`). At runtime
  `context.active_object` with nothing active is `None`: `CTX_data_get` returns `CTX_RESULT_NO_DATA` or a null
  pointer (`blender/source/blender/python/intern/bpy_rna.cc:4936-4943`, `:5022-5024`). A member the current editor
  doesn't provide (`context.edit_bone` outside edit mode) is not found, so `AttributeError` (`bpy_rna.cc:5026-5028`);
  a type can't express that.
- **Registration on a branch.** A `register()` that registers under `bpy.app.version`, a build option
  (`viewport_vr_preview` registers `VIEW3D_PT_vr_info` only when `xr_openxr` is off,
  `blender/scripts/addons_core/viewport_vr_preview/__init__.py:34-36`) or an environment variable may leave the class
  unregistered. Reporting at the use, not at the registration, is the point: the registration itself is fine on
  every version-gated add-on, and only the use can be wrong.
- **The whole-add-on fallback.** When the walk gives up, every class and property of the add-on counts as
  registered and the missing-registration rules go quiet. `auto_load` modules are a common, legitimate reason, so
  the fallback is right, but without a diagnostic the user cannot tell "all fine" from "not checked". Cycles gives
  up at `ui.py`'s `register_class` of the classes `node_panel()` builds (#86).
- **Foreign values.** A dict of classes (`for cls in CLASSES.values(): register_class(cls)`) used to leave a
  complete walk that registered nothing, so a false `blender-unregistered-class`. A foreign value reaching
  `register_class` now gives up the walk instead.
- **Add-on preferences.** Blender adds the `Addon` entry before calling `register()`
  (`blender/scripts/modules/addon_utils.py:448-451`, `:550`), but `Addon.preferences` is None until the preferences
  class is registered, and again after `unregister_class`. So only reads in the registration window can see None;
  callbacks run with the add-on fully registered.
