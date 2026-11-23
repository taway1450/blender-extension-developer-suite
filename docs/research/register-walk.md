# How `register()` is followed to what it registers

Research note, 2026-11-06, for [#22](https://github.com/taway1450/blender-extension-developer-suite/issues/22)
(map [#21](https://github.com/taway1450/blender-extension-developer-suite/issues/21)). Trimmed on 2026-11-18 to the
rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings. It
builds on [#8](https://github.com/taway1450/blender-extension-developer-suite/issues/8) (registered-property
collection, now built as the Add-on index) and keeps the map's settled points:

- `register()` is followed. When the walk meets something it cannot resolve, every Blender class of the add-on
  counts as registered, and `blender-unregistered-class` / `blender-unreachable-registration` stay silent for it.
- The walk replaces the directory walk as the source of Registered properties. The directory walk stays only as
  that fallback.
- Code that `register()` reaches outside the add-on root (a shared library) counts toward that add-on.

Conventions:

- Citations were read at `ty-blender/ruff-blender/` `c4b93523c0` (branch `blender`), written `ruff/`.
  `blender/` is `ruff/crates/ty_python_semantic/src/types/dedicated/blender/`. `tests/` is
  `tests/typecheck/features/`. `bpy-src/` is Blender's `scripts/modules/` (`.cache/blender-src/main/`).
- **Recommendation** marks my own design. Everything else is read from source.

What main does: the walk is `blender/walk.rs` (its module doc is the current description). Each event carries the
branches it depends on and whether its order is known (`exact`), which settled the original's open point on
mutually exclusive branches.

---

## 1. What Blender's factories do

Both are plain Python in `bpy-src/bpy/utils/__init__.py`:

- `register_classes_factory(classes)` returns `register`, which runs `for cls in classes: register_class(cls)`, and
  `unregister`, which runs the same over `reversed(classes)` (`:1001-1019`).
- `register_submodule_factory(module_name, submodule_names)` returns `register`, which imports
  `module_name` with `fromlist=submodule_names`, then calls each submodule's `register()` in list order
  (`:1022-1049`), and `unregister`, which calls `unregister()` in reverse order (`:1051-1057`).
- `register_class` and `unregister_class` come from `_bpy` (`:52-62`). Both stub generators declare all four as
  functions of `bpy.utils` (builtin: `.cache/bpy-stubs-builtin/main/bpy/utils/__init__.pyi:16,20,34,35`;
  fake-bpy-module: `.cache/bpy-stubs/main/bpy-stubs/utils/__init__.pyi:189,214,265,396`). So
  `blender_function_name(db, ty, "bpy.utils")` (`blender/symbols.rs:29-40`) recognises them however imported.

**Recommendation:** model the factories by these semantics, rather than walking Blender's source. The source is
not on ty's search paths (only the stubs are), and the factories' `__import__` and `getattr` would make any walk of
them give up.

---

## 2. Foreign and Opaque

Most of what `register()` does is not registration: keymaps (`wm.keyconfigs.addon.keymaps.new(...)`), handlers,
previews, timers. If every unresolvable call made the walk give up, the fallback would be the norm.

**Recommendation:**

- An expression whose head resolves outside first-party code is **Foreign**, and so is everything derived from it:
  attributes, calls, subscripts. Calls on Foreign values are ignored, except the recognised Blender functions
  (`register_class`, the factories, `setattr` / `delattr`, menu and handler `append` / `remove`).
- Calls to `getattr`, `importlib.import_module`, `__import__`, `globals`, `vars`, `inspect.getmembers` and
  `pkgutil.iter_modules`, and subscripts of `sys.modules`, give **Opaque**: this is runtime discovery.
- A name the evaluator cannot resolve (several different definitions, an unbound parameter, an instance attribute,
  a comprehension it does not understand) is **Opaque**.
- **The walk gives up** (`Incomplete`) only when an Opaque value:
  - is passed to `register_class` or `unregister_class`, or ends up in a factory's sequence;
  - is called (it might be a `register()`);
  - is the iterable of a loop whose body registers, calls or assigns a property through the loop variable.

  An Opaque value that is stored, printed or passed to a Foreign function does not matter.
- Calls into non-first-party Python (site-packages) are Foreign. A bundled wheel that registers Blender classes is
  not followed: an add-on framework installed as a wheel would be missed silently, not fall back.

What main does: a Foreign value also makes the walk give up when it is registered (`register_class(type(...))`, a
class taken from a dict's `.values()`), since the walk can't tell which class it is (`blender/walk.rs` module doc).

`reg_autoload` then gives up exactly where it should: `classes` in `auto_load.py` has the element `cls`, bound by a
loop over `inspect.getmembers(...)` (`tests/registration/reg_autoload/auto_load.py:40-42`), so it is Opaque.
`register()` passes it to `register_class` (`auto_load.py:46-47`).

---

## 3. Sequences without inference

ty's inference widens list displays (`list[...]`), as found in
[#7](https://github.com/taway1450/blender-extension-developer-suite/issues/7). Inferring the add-on's module would
also read the index it is building. So sequences are evaluated syntactically.

**Recommendation.** The value of an expression used as a sequence:

| Expression | Value |
| --- | --- |
| tuple / list / set display | its elements in order; `*x` splices `x` |
| `a + b` | `a` then `b` |
| `reversed(x)`, `list(x)`, `tuple(x)`, `sorted(x)` | `x` (reversed for `reversed`) |
| `[e for v in x]`, `(e for v in x)` with `e` the loop variable, any `if` | `x` (an over-approximation) |
| a name | the union, in source order, of all its definitions (`=`, `+=`, and the `for` / unpack forms the walk binds), plus every `NAME.append(e)`, `NAME.extend(x)`, `NAME.insert(i, e)` and `NAME += x` **anywhere in the defining file** where `NAME` resolves to that same global |
| `module.NAME` | the same, in that module's file |
| a call to a first-party function | the union of its `return` expressions |
| anything else | Opaque |

- Mutations are collected flow-insensitively, per file. So the module-level `if ...: classes.append(C)` of
  `tests/registration/reg_conditional/__init__.py:226-228` counts, and so does the `append` inside
  `auto_load.init()`. Order: definitions first, then mutations in source order. That is exact for
  `reg_loop/__init__.py:944-946`.
- A mutation through another module (`auto_load.classes.append(x)` in a third file) is not seen. It is rare.
- `GROUPS = ((A,), [B])` with a nested loop works because elements are values, and an inner sequence is a
  `Sequence` value.
- Loop targets that are tuples (`for cls, name in [(Scene, "x"), ...]`, used by
  `tests/properties/props_registered/__init__.py:60-75` in `unregister()`) bind element-wise when the element is a
  sequence of the same length. Otherwise every name is Opaque.

---

## 4. The `unregister()` walk

The same interpreter runs from `unregister`. What `blender-unregister-mismatch` needs from it:

- `UnregisterClass` events, compared with the register walk's `RegisterClass` (leaks:
  `tests/registration_checks/regchk_unregister_leak/__init__.py:58`; unknown classes:
  `regchk_unregister_unknown/__init__.py:30`).
- `DelProperty` from `del X.attr` and from `delattr` in a loop over `(class, "name")` tuples
  (`props_registered/__init__.py:60-75`), compared with `SetProperty`.
- `Hook` events: `bpy.app.handlers.<h>.append/remove(f)` and `<Menu class>.append/remove(f)`
  (`regchk_unregister_leak/__init__.py:62-68`). The handler list is Foreign, so the event keeps its attribute
  path (`bpy.app.handlers.save_post`) instead of a value. Menu classes are `bpy.types` classes.
- The factories' unregister halves and `if cls.is_registered:` guards, which count like any branch
  (`reg_conditional/__init__.py:246-250`).
- Its own `incomplete`. A mismatch is only reported when both walks are complete.

The register walk never enters `unregister()`, so its deletions no longer erase properties. That resolves #8's
"ignore `del`" decision without a special case.

---

## 5. ty facts the walk relies on

- `definition_resolution`'s name lookups need no scope inference, so they are safe to call while the index is being
  built (`ruff/crates/ty_python_semantic/src/types/definition_resolution.rs:152-180`).
- `FunctionType::definition` warns that it creates a cross-module dependency on the full AST
  (`ruff/crates/ty_python_semantic/src/types/function.rs:1595-1605`). The walk reads a function's steps from its own
  file's cached summary instead, so it only needs the `Definition`.
- A tuple-unpacking assignment (`_register, _unregister = register_classes_factory(...)`) binds each name with an
  assignment whose `target_kind()` is `TargetKind::Sequence` (`ruff/crates/ty_python_core/src/definition.rs:1210-1214`,
  `:1566-1568`). `Unpack::target` gives the whole target tuple (`ruff/crates/ty_python_core/src/unpack.rs:69`).
- `find_symbol_in_scope` uses `reachable_symbol_bindings` (`definition_resolution.rs:832`). A binding under a branch
  ty proves unreachable (a `sys.version_info` check) is dropped, which is right for Blender's Python.
- ty widens undeclared class attributes to `Unknown | Literal[...]`
  (`ruff/crates/ty_python_semantic/resources/mdtest/attributes.md:1163`). The binding's own inferred type keeps the
  literal, and f-strings of literals fold (`resources/mdtest/literal/f_string.md:9-15`). So an operator's
  `bl_idname` is read from the `binding_type` of the first class in its MRO whose body binds it, not from the
  class's public member type.
