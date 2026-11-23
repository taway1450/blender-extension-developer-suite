# How `addons[<key>].preferences` resolves to the add-on's own class

Research note, 2026-11-06, for [#30](https://github.com/taway1450/blender-extension-developer-suite/issues/30) (map
[#21](https://github.com/taway1450/blender-extension-developer-suite/issues/21)). Trimmed on 2026-11-18 to the
rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings. It
builds on [#22](https://github.com/taway1450/blender-extension-developer-suite/issues/22) (the `register()` walk,
[register-walk.md](register-walk.md)), [#26](https://github.com/taway1450/blender-extension-developer-suite/issues/26)
(the Property evaluator, [property-wrappers.md](property-wrappers.md)),
[#27](https://github.com/taway1450/blender-extension-developer-suite/issues/27) (the per-file lint query,
[property-rules.md](property-rules.md)) and [#5](https://github.com/taway1450/blender-extension-developer-suite/issues/5)
(`__package__` per add-on: a `Literal` for a Legacy add-on, `str` for an Extension).

Conventions:

- `R/` is `ty-blender/ruff-blender/crates/ty_python_semantic/src/`, `BL/` is Blender's source at
  `.cache/blender-src/main/`, `F/` is `tests/typecheck/features/addon_preferences/`, `SB/` and `SF/` are the builtin
  and fake-bpy-module stubs at `.cache/bpy-stubs-builtin/main/` and `.cache/bpy-stubs/main/`.
- **Recommendation** marks my own design. Everything else is read from source or stubs.

What main does: `R/types/dedicated/blender/preferences.rs` and `addon_key.rs` (their module docs are the current
description). Only the attribute load `.preferences` changes, decided from the receiver's syntax
(`<x>.addons[KEY]`, `<x>.addons.get(KEY)`, or a name bound to either). When the `register()` walk is incomplete,
every matching preferences class counts, and the attribute is any of them.

---

## 1. What Blender does

- `Preferences.addons` is a collection of `Addon`, keyed by the name property `module`
  (`BL/source/blender/makesrna/intern/rna_userdef.cc:4789-4800`). `addon_utils` sets `module` to the module name it
  enables (`BL/scripts/modules/addon_utils.py:321-326`): the folder name for a Legacy add-on,
  `bl_ext.<repository>.<id>` for an Extension. So the key is the root package's `__package__` / `__name__`, and a
  string literal can only name a Legacy (or single-file) add-on.
- `Addon.preferences` looks up the registered preferences type by `addon->module` and returns `None` when there is
  none (`rna_userdef.cc:1398-1412`, `BL/source/blender/blenkernel/intern/addon.cc:91-103`). So the value is the
  instance of the class whose `bl_idname` equals the key, and only once that class is registered.
- `bl_idname` of `AddonPreferences` is stored in `module` (`rna_userdef.cc:4969-4974`). Registering a second class
  with the same idname unregisters the first, with an `INFO` report only
  (`rna_userdef.cc:1465-1487`). The first class's later `unregister_class` then fails, which is why `prefs_bad`
  is `register = "fails"` (`F/prefs_bad/_expected/runtime.toml`). A wrong idname, `__name__` of a submodule and a
  missing `bl_idname` all register fine and are simply never found (`F/prefs_bad/__init__.py:1-3`).
- `layout` is not an RNA property of `AddonPreferences` (`rna_userdef.cc:4952-4977`). The preferences editor sets
  it as a class attribute around the call to `draw` (`BL/scripts/startup/bl_ui/space_userpref.py:2487-2501`).
  fake-bpy-module declares `layout: UILayout` through a mod file
  (`fake-bpy-module/src/mods/common/analyzer/append/bpy.types.mod.rst:5-9`); the builtin stubs need the same.

---

## 2. Alternatives not taken

- **A key `Literal` on the subscript's type.** Works for Legacy add-ons (`__package__` is
  `Literal["prefs_legacy"]`, `R/types/dedicated/blender/module_dunders.rs:28-39`), not for Extensions, whose
  `__package__` and every constant holding it are `str`. Typing an Extension's `__package__` more precisely was
  rejected in #5 (the repository is unknown).
- **A specialised `Addon` type from the subscript and the `.get` call** (an intersection `Addon & <protocol with
  preferences: C>`, or a synthesised class as in the reference stub). It would carry the key through parameters
  and make `addons[KEY]` itself display the class. But it needs new hooks in subscript and call inference, two
  upstream lines on hot paths, and a synthesised class has no anchor. The attribute-load hook covers every marker,
  so this stays the fallback if a gap appears.
- **Rewriting `Addons.__getitem__` per add-on.** Member lookups are cached per class, so an add-on-specific
  overload would leak between add-ons.

Consequence: `addon = preferences.addons[KEY]` passed into a function typed `Addon`, then `.preferences` there, has
no key. The stub type stays.

---

## 3. The Add-on key evaluator

### 3.1 Values

A key is one of: a module path below an add-on root (`[]` is the root package itself, `["helpers"]` is
`<root>.helpers`), a string literal, or unknown (a parameter, `os.environ[...]`, a call).

A key **names** add-on `A` when it is the module path `[]` of `A`, or a literal equal to `A`'s name with `A` a
Legacy (package or single-file) add-on. An Extension's name is never a literal: its key is
`bl_ext.<repository>.<id>`.

### 3.2 Rules

The key is decided by where the value comes from, not by its `Literal` type. For an expression in a scope of file
`f`, with `p(f)` the path of `f` below its add-on root (`__init__.py` is its package's path):

| Expression | Value |
| --- | --- |
| `__name__`, not bound in any enclosing scope | `Module(p(f))` |
| `__package__`, not bound in any enclosing scope | `Module(p(f))` for `__init__.py`, `Module(p(f) minus its last part)` otherwise; a single-file add-on gives `Literal("")` |
| `e.rpartition(".")[0]` | `e`'s module path minus its last part (`Unknown` for `[]`) |
| `"..."` (also an implicitly concatenated literal) | `Literal` |
| a name bound by an assignment `N = e` (all bindings in the nearest scope that has any must agree) | `e`, evaluated in the scope of that assignment |
| a name bound by `from m import X [as N]` | `X` evaluated in module `m`; for `X` = `__package__` / `__name__` this is the dunder of `m` |
| `m.X` with `m` a module | `X` evaluated in `m` |
| anything else | `Unknown` |

- **Dunders are evaluated where they are spelled.** `ADDON_ID = __package__` in the root and `from . import
  ADDON_ID` in a submodule gives the root's `__package__`; `from .. import __package__ as base_package`
  in `ui/panel.py` gives `__package__` of the root module (`F/prefs_ext/ui/panel.py:6`), `[]`. A bare `__package__`
  in `ui/panel.py` would be `["ui"]` and does **not** name the add-on: "`__package__` names the add-on" only holds
  for the root and its direct submodules.
- `from .. import __package__`: the root module binds no `__package__`, so ty's definition resolution finds no
  definition for it. The evaluator special-cases an `import from` of an implicit module dunder (the names
  `place.rs:2530` answers) by evaluating the dunder in the source module.
- Files outside every add-on (a shared library) give `Module` values of no add-on, so they never name one.
- It never infers add-on code, so it is safe to call from attribute inference and from the index.
- An `AddonPreferences` class's `bl_idname` is read by the same evaluator, in the class body scope. An `Unknown`
  idname is not checked: the checker cannot tell.

Not covered: `__name__.split(".")[0]` / `.partition(".")[0]` (the top package; right for a Legacy add-on only,
`bl_ext` for an Extension), `os.path.basename(os.path.dirname(__file__))`, f-strings. They can be added as rows.

---

## 4. ID pointers on `AddonPreferences`

Blender refuses a `PointerProperty` / `CollectionProperty` whose type contains data-blocks on a struct that forbids
data-block ID properties, with a `ValueError` at `register_class`
(`BL/source/blender/python/intern/bpy_rna.cc:9483-9501`; `RNA_struct_idprops_datablock_allowed`,
`BL/source/blender/makesrna/intern/rna_access.cc:803-811`). `AddonPreferences` is such a struct
(`STRUCT_NO_DATABLOCK_IDPROPERTIES`, `rna_userdef.cc:4965`).

**Recommendation: `blender-invalid-property`.** It is a property-declaration error like the others #27 lists
(Blender rejects the declaration at registration), it is decided from the declaration and its owner kind, and #27's
property checks already take the owner for exactly this check. The addon_preferences feature only resolves the
preferences class; it has no reason to inspect property declarations. To keep one diagnostic per line, the check
yields one data-block-pointer problem and the reporter picks the rule by owner: `Operator` / `Macro` →
`blender-invalid-operator-property`, any other owner (`AddonPreferences`, the other registered targets) →
`blender-invalid-property`.

---

## 5. A ty fact

ty infers a call's return type from an unannotated body only with `analysis.return-type-inference = "always"`; the
default is `never` (`ty-blender/ruff-blender/crates/ty_python_semantic/src/lib.rs:138-150`,
`R/types/function.rs:1734-1759`). So helpers that return `addons[__package__].preferences` need a return annotation
for their callers to see the class. That is also how real add-ons write such helpers.
