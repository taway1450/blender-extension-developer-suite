# Detecting and reporting the registration checks

Research note, 2026-11-06, for [#29](https://github.com/taway1450/blender-extension-developer-suite/issues/29)
(map [#21](https://github.com/taway1450/blender-extension-developer-suite/issues/21)). Trimmed on 2026-11-18 to the
rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings. It
builds on the `register()` walk of [#22](https://github.com/taway1450/blender-extension-developer-suite/issues/22)
([register-walk.md](register-walk.md)): ordered events, the functions it entered, whether it is complete, and the
same interpreter from `unregister`.

Conventions:

- `blender/` is `ty-blender/ruff-blender/crates/ty_python_semantic/src/types/dedicated/blender/` (branch `blender`).
  `tests/` is `tests/typecheck/features/`. `bl-src/` is Blender's source at `.cache/blender-src/main/source/blender/`.
- **Recommendation** marks my own design. Everything else is read from source or tests.

What main does: the checks are `blender/registration_checks.rs`; the rules and their tests are in
`tests/registration_checks/README.md`.

---

## 1. The principles

1. **"An incomplete walk proves presence, never absence."** A rule that reports something that *happens*
   (a duplicate, a bad idname, a pointer to a class registered *later*) still runs on the known events of an
   incomplete walk. A rule that reports something that *does not happen* (never registered, never reached, never
   unregistered, unregistered without being registered) is silent when the walk it reads is incomplete.
2. **Exclusive branches: know about them.** Each event carries a *branch path*: for every branching statement
   the walk executed on the way to the event, an id and the arm taken. Two events are exclusive when their
   paths hold one id with different arms. The realistic case is not two `register_class(C)` in an `if` / `else`
   but `classes = (A, B)` / `else: classes = (A, C)` at module level, which a union of definitions turns into
   `A, B, A, C`. Section 4.3.
3. **Base and mixin.** A *mixin* is a class with no registrable `bpy.types` class in its MRO: it is not a Blender
   class, so never reported. A *base* is a Blender class of the add-on that another class of the add-on derives
   from, registered or not. Section 3.
4. **One diagnostic per mistake.** A class registered only by an unreachable function gets
   `blender-unreachable-registration` on the function, not also `blender-unregistered-class` on the class.

---

## 2. What Blender does (facts)

| Mistake | Blender's check | Effect |
| --- | --- | --- |
| A class registered twice | `register_class` finds `bl_rna` in the class's own dict (`bl-src/python/intern/bpy_rna.cc:10560-10567`) | `ValueError: ... already registered as a subclass` |
| A pointer / collection to an unregistered class | `pointer_type_from_py` needs the class's `bl_rna` (`bl-src/python/intern/bpy_props.cc:5366-5391`, called at `:5512`, `:5664`) | `TypeError`, then `ValueError` from the deferred registration (`tests/registration_checks/README.md`) |
| A subpanel before its parent | `rna_Panel_register` looks the parent up by idname among registered panel types (`bl-src/makesrna/intern/rna_ui.cc:361-363`), then reports "parent ... not found" (`:371-375`) | `RuntimeError` |
| An invalid operator idname | `operator_idname_ok_or_report_impl`: only `a-z`, `0-9`, `_` and exactly one `.` not at either end, at most `OP_MAX_PY_IDNAME` characters (`bl-src/windowmanager/intern/wm_operators.cc:204-249`), called from `rna_Operator_register` and the macro's (`bl-src/makesrna/intern/rna_wm.cc:1868`, `:2018`) | `RuntimeError` |
| Panel / UI list / header / menu idname without `_PT_` / `_UL_` / `_HT_` / `_MT_` | `RNA_struct_bl_idname_ok_or_report` (`bl-src/makesrna/intern/rna_access.cc:1218-1272`, called at `rna_ui.cc:369, 768, 909, 1067`): an upper-case alphanumeric prefix, the separator, an alphanumeric suffix | a warning only: the function returns `true` on failure ("TODO: make error", `:1225-1232`) |
| No `bl_idname` on a panel, list, header or menu | the class name is used (`rna_ui.cc:1935`, `:2070`, `:2259`, `:2337`) | checked as above |
| Two classes with one idname | "has been registered before, unregistering previous" (`rna_wm.cc:1424, 1849, 2028`; `rna_ui.cc:331, 748, 888, 1047`) | the second silently replaces the first |
| `unregister_class` of a class not registered | `pyrna_struct_as_srna(py_class, false, ...)` (`bpy_rna.cc:10838`) finds no `bl_rna` (`:9350-9355`) | `RuntimeError: missing bl_rna attribute ... (may not be registered)` |

Which classes `register_class` accepts: the RNA structs with register functions,
`RNA_def_struct_register_funcs` (`bl-src/makesrna/intern/*.cc`, grep): `PropertyGroup`, `Operator`, `Macro`,
`Panel`, `Menu`, `Header`, `UIList`, `AddonPreferences`, `KeyConfigPreferences`, `KeyingSetInfo`, `RenderEngine`,
`AssetShelf`, `FileHandler`, `Gizmo`, `GizmoGroup`, `Node` (and `ShaderNode`, `CompositorNode`, `TextureNode`,
`GeometryNode`, `FunctionNode`), `NodeTree`, `NodeSocket`, `NodeTreeInterfaceSocket` and `USDHook`. `ID` has only an
instance function (`rna_ID.cc:2797`). `WorkSpaceTool` is not among them: it is registered by `bpy.utils.register_tool`.

Unregistering is order-free: Blender accepts any `unregister_class` order (`tests/registration_checks/regchk_order/__init__.py:62-64`).

---

## 3. `blender-unregistered-class`

### 3.1 What a Blender class of the add-on is

- A class statement at module scope in any file of the add-on whose MRO holds a *registrable root*, the list of
  section 2. `Object`, `Mesh`, `UILayout` or `WorkSpaceTool` subclasses are not Blender classes in this sense.
- Classes inside functions are skipped: they are factories' products, and a false positive costs more than a miss.
- Orphan modules count, because the class list comes from every file of the add-on, not from what the walk
  imports.

### 3.2 Base and mixin

- **Mixin:** a class whose MRO has no registrable root (`_ExecuteMixin`, `tests/registration_checks/regchk_unregistered/__init__.py:12`;
  `CountMixin`, `tests/operator_calls/opcall_inherit/__init__.py:9`). It is not a Blender class, so the rule never
  sees it.
- **Base:** a Blender class of the add-on that appears in the MRO of another Blender class of the add-on.
  **Recommendation:** any subclass counts, registered or not. "Derived by a *registered* class" would also work for
  the tests, but it reports a base whose subclasses are all forgotten, on top of the subclasses' own diagnostics,
  and it needs the walk; "derived by any class" needs only the per-file lists.

### 3.3 Classes in check files

Test add-ons define registrable classes in `check_*.py` files that are never registered. These are real findings
and get markers. The other option, honouring the manifest's `paths_exclude_pattern` (which lists `check_*.py`),
would only cover Extensions and makes the checker depend on build settings.

---

## 4. `blender-unreachable-registration`, order and branches

### 4.1 Candidates

A function whose *own* body contains a `register_class` call or a call of a factory's register half. A function
that only calls another registering function is not a candidate, so a forgotten chain gives one diagnostic, on the
function that registers. Functions that only `unregister_class` are not candidates either.

**Deferred registration** (`bpy.app.timers.register(late_register)`, a handler that registers) passes a
first-party function to a Foreign callee. The walk records such functions as *escaped* and walks them after the
entry function, as if called later. Their events count (the class is registered at runtime), they are inexact
(section 4.2), and the function counts as reached. What main does: a use of an operator registered this way is
reported under `blender-assumed-registration` (`tests/registration_checks/README.md`, `regchk_unreachable`).

### 4.2 What the walk's order means, and `exact`

The walk runs module bodies at first import, then the entry function, branches in source order with all arms taken.
The order is exact for straight-line code, loops over displays, and calls. It is approximate for:

- set displays and `set(...)` (no order);
- `sorted(x)`, which the walk evaluates as `x`;
- comprehensions with an `if` (membership is over-approximated);
- mutations of a module-level list from inside a function body (`auto_load.init()`), appended after the
  definitions;
- escaped functions (timers, handlers).

Each event carries `exact: false` when one of the above was involved. Order-sensitive and count-sensitive rules
(order, duplicate) ignore a pair in which either event is inexact. Membership rules (unregistered, mismatch) still
use inexact events: an over-approximated membership can only make them quieter.

### 4.3 Exclusive branches

`blender-duplicate-registration` knows about branches, through a branch path on each event:

- The walk gives each branching statement of a function body a fresh id **each time it executes it**: per call of
  the enclosing function and per loop iteration. Both arms are walked under the same id, each with its arm number.
  A dynamic id keeps the same `if` in two loop iterations or two calls from looking exclusive: there, both
  arms really run. Module bodies run once, so the statement itself is a sufficient id there.
- Two events are **exclusive** when their paths share an id with different arms.
- Exclusive arms: `if` / `elif` / `else`; `match` cases; a `try`'s `except` handlers among themselves and with
  its `else`; the two values of `a if c else b`. **Not** exclusive: a `try` body with its handlers (the body may
  register, then raise), loop bodies with their `else`.
- **Sequences carry it too.** Each element of a sequence value carries the path of the definition or mutation that
  added it. With `if bpy.app.version >= (4, 2): classes = (A, B)` / `else: classes = (A, C)` the loop in
  `register()` yields `A`, `B`, `A`, `C`, and the two `A` events are exclusive.
- **Definitions that do not reach the use.** A union of *all* definitions of a sequence name would turn
  `classes = (A,)` followed by `classes = (A, B)` into a duplicate `A`. So only the bindings visible at the end of
  the defining scope are unioned (`use_def_map(...).end_of_scope_symbol_bindings`), with an augmented assignment's
  value being the previous bindings plus its right-hand side.

Why not accept the false positive: the version-conditional class tuple above is common in add-ons that support
several Blender versions, and the alternative is an error-level diagnostic on correct code with no workaround but a
suppression.

Other rules use the same test: an earlier registration counts as "before" only when it is not exclusive with the
use; a duplicate idname is not reported between exclusive registrations.

### 4.4 `blender-register-order`: later versus never

If a pointer's target `T` is registered later in the walk, the report holds even for an incomplete walk (a
registration hidden in the opaque part would have made the later one a duplicate). If `T` is never registered,
report only for a complete walk. A `bl_parent_id` naming no panel of the add-on is Blender's own panel
(`VIEW3D_PT_tools`) and stays silent.

---

## 5. `blender-unregister-mismatch`

The register walk gives the additions, the unregister walk the removals. Both are sets; counts and order do not
matter (Blender accepts any unregister order, and duplicates are another rule's business). Classes pair with
`unregister_class`, Registered properties with `del` / `delattr`, and handler or menu `append` / `prepend` with
`remove`.

A handler list is keyed by the Blender path it was reached by, resolved as a Blender symbol, so
`from bpy.app import handlers` then `handlers.load_post` is `bpy.app.handlers.load_post`. Built-in menus such as
`bpy.types.VIEW3D_MT_object` are not in the stubs, so their path is taken from the attribute chain on `bpy.types`,
not from a resolved class.

What is reported:

- **Leak** (register walk adds, unregister walk never removes), only when the **unregister** walk is complete.
- **Unknown class** (`UnregisterClass(C)` with no `RegisterClass(C)` in the register walk), only when the
  **register** walk is complete.
- **Not reported:** deleting a property or removing a hook that was not added. Property names in `setattr` can be
  computed (`tests/properties/props_registered/__init__.py:50-51` registers `dyn_a` / `dyn_b` that way and deletes
  them by literal name at `:71-75`), and `if f in handlers: handlers.remove(f)` guards are common. Both are real
  runtime errors when wrong (`del` raises, `list.remove` raises); a later extension can add them for literal names.
- **No `unregister`**, or one the walk cannot resolve, makes the unregister walk incomplete: no leak is reported.
  An add-on without `unregister()` already gets `blender-invalid-register` and nothing else.
- Conditional unregistration (`if cls.is_registered:`) counts, like every branch.
- Factories pair themselves: `register_classes_factory` and `register_submodule_factory` give the unregister half the
  same classes ([register-walk.md](register-walk.md) section 1).

**Findings outside the add-on.** A site in a shared library is dropped. Then a leak caused by the library's
`register_tool()` (if the add-on's `unregister()` forgot `unregister_tool()`) is lost. If wanted later, each event
could keep the outermost call site in the add-on's own files and report there.
