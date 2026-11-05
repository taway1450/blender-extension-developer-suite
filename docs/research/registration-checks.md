# Detecting and reporting the registration checks

Research note, 2026-11-06, for [#29](https://github.com/taway1450/blender-extension-developer-suite/issues/29)
(map: [#21](https://github.com/taway1450/blender-extension-developer-suite/issues/21)). It builds on:

- [#22](https://github.com/taway1450/blender-extension-developer-suite/issues/22), the `register()` walk
  (`docs/research/register-walk.md` on `research/register-walk`): ordered events, each class event with
  `named_at` (where the class was spelled) and `call` (the `register_class` call); `entered` functions;
  `incomplete`; the same interpreter from `unregister`;
- [#27](https://github.com/taway1450/blender-extension-developer-suite/issues/27), the reporting site
  (`docs/research/property-rules.md` on `research/property-rules`): `addon_diagnostics` generalised into a per-file
  query that `check_types` already merges;
- [#6](https://github.com/taway1450/blender-extension-developer-suite/issues/6): lints declared in
  `dedicated/blender/`, reported through `InferContext::report_lint` in the anchored file before
  `check_suppressions`;
- the map's note: when the walk is incomplete, `blender-unregistered-class` and
  `blender-unreachable-registration` stay silent for that add-on.

Conventions:

- `ruff/` is `ty-blender/ruff-blender/` (branch `blender`). `blender/` is
  `ruff/crates/ty_python_semantic/src/types/dedicated/blender/`. `tests/` is `tests/typecheck/features/`.
  `bl-src/` is Blender's source at `.cache/blender-src/main/source/blender/`.
- **Recommendation** marks my own design. Everything else is read from source or tests.
- Nothing was built or run, apart from a throwaway Python scan of the test add-ons (section 9).

---

## 1. Answer in short

| Rule | Reads | Silent when | Anchor (the line the marker is on) |
| --- | --- | --- | --- |
| `blender-unregistered-class` | the add-on's Blender classes (per file), the register walk's classes, the classes named by unreachable registering functions | register walk incomplete | the class name in the `class` statement |
| `blender-unreachable-registration` | functions whose own body registers (per file), the register walk's `entered` | register walk incomplete | the function name in the `def` |
| `blender-register-order` | the register walk's events in order, `type=` of each pointer / collection declaration, `bl_parent_id` and panel idnames | the target was never registered and the walk is incomplete; either event inexact | `named_at` of the class event, or the property assignment |
| `blender-duplicate-registration` | the register walk's class events with branch paths; the idname of each registered class | the events are in exclusive branches, or inexact | the later `named_at`; for one idname, the later class's own `bl_idname` binding, else its name |
| `blender-invalid-idname` | the idname of each registered class (the `addon_operators` reading of #22, generalised) | the idname is not a known string | the class's own `bl_idname` binding, else its name |
| `blender-unregister-mismatch` | both walks: class, property and hook events | the walk that would have to prove an absence is incomplete | the register-side event for a leak; the `unregister_class` argument for an unknown class |

1. **One add-on-level query, reported per file.** **Recommendation:** a tracked
   `registration_findings(AddonInProgram) -> Box<[Finding]>` runs all six rules on the walks and returns
   `Finding { rule, file, range, message }`, `Eq` so it backdates. #27's per-file `addon_diagnostics` reports the
   findings whose `file` is its own file through `report_lint`. Findings in files outside the add-on (a shared
   library the walk entered) are dropped. No upstream line beyond #6's hook and `register_lints`.
2. **"An incomplete walk proves presence, never absence."** A rule that reports something that *happens*
   (a duplicate, a bad idname, a pointer to a class registered *later*) still runs on the known events of an
   incomplete walk. A rule that reports something that *does not happen* (never registered, never reached, never
   unregistered, unregistered without being registered) is silent when the walk it reads is incomplete. That
   matches the map's note and extends it to the other rules.
3. **Exclusive branches: know about them.** Each event carries a *branch path*: for every branching statement
   the walk executed on the way to the event, a dynamic id and the arm taken. Two events are exclusive when their
   paths hold one id with different arms. The realistic case is not two `register_class(C)` in an `if` / `else`
   but `classes = (A, B)` / `else: classes = (A, C)` at module level, which a union of definitions turns into
   `A, B, A, C`. Section 5.3.
4. **Base and mixin.** A *mixin* is a class with no registrable `bpy.types` class in its MRO: it is not a Blender
   class, so never reported. A *base* is a Blender class of the add-on that another class of the add-on derives
   from, registered or not. Section 3.
5. **The tests contradict each other once.** A class registered only by an unreachable function is reported as
   unregistered in `reg_submodule_factory/unlisted.py:7`, but not in `regchk_unreachable/__init__.py:10` and
   `forgotten.py:7`. **Recommendation:** one diagnostic per cause: drop the `blender-unregistered-class` marker
   of `unlisted.py:7`. Section 3.3.

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

---

## 3. `blender-unregistered-class`

### 3.1 What a Blender class of the add-on is

**Recommendation.**

- A class statement at module scope in any file of `addon_source_files` (`check_*.py` included, see section 9)
  whose MRO holds a *registrable root*, the list of section 2, through `bpy_types_bases` (`blender/symbols.rs:54-64`).
  `Object`, `Mesh`, `UILayout` or `WorkSpaceTool` subclasses are not Blender classes in this sense
  (`tests/inheritance/inh_bases/check_inh_bases.py:12-24`, `tests/operator_properties/opprops_sinks/check_opprops_sinks_tool.py:7`).
- Classes inside functions are skipped: they are factories' products, and a false positive costs more than a miss.
- The per-file pass of #22 (`registration_ir`, or `file_facts`, which #22 already extends with this list for the
  fallback, register-walk §5.2) records each class with its name range.

### 3.2 Base and mixin

- **Mixin:** a class whose MRO has no registrable root (`_ExecuteMixin`, `tests/registration_checks/regchk_unregistered/__init__.py:12`;
  `CountMixin`, `tests/operator_calls/opcall_inherit/__init__.py:9`). It is not a Blender class, so the rule never
  sees it. No separate test is needed.
- **Base:** a Blender class of the add-on that appears in the MRO of another Blender class of the add-on.
  `REGCHK_UNREGISTERED_PT_base` (`:17`) and `_OT_base` (`:23`) are bases; so are the chains of
  `tests/inheritance/inh_chains/__init__.py:12-80`.
  **Recommendation:** any subclass counts, registered or not. "Derived by a *registered* class" (the README's
  wording) would also work for the tests, but it reports a base whose subclasses are all forgotten, on top of the
  subclasses' own diagnostics, and it needs the walk; "derived by any class" needs only the per-file lists.
- Computed once per add-on: walk the MRO of every Blender class and collect the first-party classes in it other
  than itself. MROs are cached and already computed by member lookups.

### 3.3 When it is reported

A Blender class of the add-on that is not a base is reported when:

1. the register walk is complete (map note);
2. no `RegisterClass` event of the register walk names it (a `register_class` in `unregister()` does not count:
   `tests/registration_checks/regchk_unregister_unknown/__init__.py:16`);
3. no unreachable registering function (section 4) names it in its own `register_class` steps.

Point 3 follows `regchk_unreachable`: `REGCHK_UNREACHABLE_OT_extra` (`__init__.py:10`) and `_OT_lost`
(`forgotten.py:7`) carry no `blender-unregistered-class` marker, only their functions carry
`blender-unreachable-registration`. `tests/registration/reg_submodule_factory/unlisted.py:7` carries both. One
mistake (a registration that never runs) should give one diagnostic, so **Recommendation:** drop that marker. The
alternative is to report both and add two markers to `regchk_unreachable`.

Anchor: the class name. `# ty: ignore` on the `class` line matches (`regchk_unregistered/__init__.py:41-68`,
`imported_only.py:6`, `orphan.py:6`). Orphan modules count because the class list comes from every file of the
add-on, not from what the walk imports.

Message: ``Blender class `X` is never registered: `register()` does not reach a `register_class(X)` ``.

---

## 4. `blender-unreachable-registration`

- **Candidates.** **Recommendation:** every function (and method) at any depth in the add-on's own files whose
  *own* steps (#22's per-file IR) contain a `register_class` call or a call of a factory's register half. A
  function that only calls another registering function is not a candidate, so a forgotten chain gives one
  diagnostic, on the function that registers.
- **Reported** when the register walk is complete and the candidate is not in its `entered` set.
- **Not candidates:** functions that only `unregister_class` (`regchk_unreachable/forgotten.py:19-20` has no
  marker); functions in files outside the add-on (the shared library's `register_tool` is not reported in
  `regchk_isolation_b`, which never calls it: `tests/registration_checks/regchk_isolation_b/__init__.py`).
- Anchor: the function name in the `def` (`regchk_unreachable/__init__.py:18`, `forgotten.py:15`,
  `reg_submodule_factory/unlisted.py:15`).
- Message: ``` `f` registers classes, but `register()` never calls it ```.

**Deferred registration** (`bpy.app.timers.register(late_register)`, a handler that registers) passes a
first-party function to a Foreign callee, and the walk ignores Foreign calls (register-walk §3.3), so `late_register`
would be reported. **Recommendation:** the walk records first-party functions passed to Foreign calls as
*escaped* and walks them after the entry function, as if called later. Their events count (the class is registered
at runtime), they are marked inexact (section 5.2), and the function is in `entered`. No test covers this yet.

---

## 5. Order and branches

### 5.1 What the walk's order means

#22 walks module bodies at first import, then the entry function, branches in source order with all arms taken.
The order is exact for straight-line code, loops over displays, and calls. It is approximate for:

- set displays and `set(...)` (no order);
- `sorted(x)`, which #22 evaluates as `x`;
- comprehensions with an `if` (#22 over-approximates membership);
- mutations of a module-level list from inside a function body (`auto_load.init()`), which #22 appends after the
  definitions;
- escaped functions (section 4).

### 5.2 `exact` on events

**Recommendation:** the sequence evaluator marks each element it yields `exact: false` when one of the above was
involved, and every event carries it. Order-sensitive and count-sensitive rules (order, duplicate) ignore a pair in
which either event is inexact. Membership rules (unregistered, mismatch) still use inexact events: an
over-approximated membership can only make them quieter.

### 5.3 Exclusive branches (the question from #22)

**Recommendation: `blender-duplicate-registration` knows about branches,** through a branch path on each event:

```rust
pub(super) struct BranchPath(Box<[(BranchId, u8)]>); // outermost first
pub(super) struct BranchId(u32);                     // fresh per executed branching statement
```

- The walk gives each branching statement a fresh `BranchId` **each time it executes it**: per call of the
  enclosing function and per loop iteration. Both arms are walked under the same id, each with its arm number.
  A dynamic id keeps the same `if` in two loop iterations or two calls from looking exclusive: there, both
  arms really run.
- Two events are **exclusive** when their paths share an id with different arms.
- Exclusive arms: `if` / `elif` / `else`; `match` cases; a `try`'s `except` handlers among themselves and with
  its `else`; the two values of `a if c else b`. **Not** exclusive: a `try` body with its handlers (the body may
  register, then raise), loop bodies with their `else`.
- **Sequences carry it too.** Each element of a sequence value carries the path of the definition or mutation that
  added it. Module bodies run once, so the static statement is a sufficient id there. With
  `if bpy.app.version >= (4, 2): classes = (A, B)` / `else: classes = (A, C)` the loop in `register()` yields
  `A`, `B`, `A`, `C`, and the two `A` events are exclusive.
- **Definitions that do not reach the use.** #22 unions *all* definitions of a sequence name. `classes = (A,)`
  followed by `classes = (A, B)` would duplicate `A`. **Recommendation:** union only the bindings visible at the
  end of the defining scope (`use_def_map(...).end_of_scope_symbol_bindings`, as `lints.rs:182-195` already
  uses), with an augmented assignment's value being the previous bindings plus its right-hand side.

Why not accept the false positive: the version-conditional class tuple above is common in add-ons that support
several Blender versions, the cost is one small vector per event in a design that is not built yet, and the
alternative is an error-level diagnostic on correct code with no workaround but a suppression.

Other rules use the same test: an earlier registration counts as "before" only when it is not exclusive with the
use (section 6); a duplicate idname is not reported between exclusive registrations.

The event shape of #22 (register-walk §5.1) then becomes:

```rust
pub(super) enum Event<'db> {
    RegisterClass   { class: StaticClassLiteral<'db>, named_at: Site, call: Site, path: BranchPath, exact: bool },
    UnregisterClass { class: StaticClassLiteral<'db>, named_at: Site, call: Site, path: BranchPath, exact: bool },
    SetProperty(RegisteredProperty<'db>, Site, BranchPath, bool),
    DelProperty     { owner: StaticClassLiteral<'db>, name: Name, site: Site },
    Hook            { target: HookTarget<'db>, function: Definition<'db>, added: bool, site: Site },
}
```

`DelProperty` and `Hook` need no path: only set membership is asked of them.

---

## 6. `blender-register-order`

Walk the register events in order, keeping the events seen so far. Report:

1. **A class with a pointer to a later class.** At `RegisterClass(C)`, for every Annotated property of `C`
   (its own and its first-party bases' and mixins', as `typing.get_type_hints` reads them) whose declaration is a
   `PointerProperty` / `CollectionProperty` with `type=T`, `T` a first-party class: report when no earlier,
   non-exclusive `RegisterClass(T)` exists. Anchor: `named_at` of `C`
   (`tests/registration_checks/regchk_order/__init__.py:47`, the tuple element; `:54`, the explicit call).
2. **A Registered property with a pointer to a later class.** The same at `SetProperty` with `type=T`. Anchor:
   the assignment target (`regchk_order/__init__.py:55`).
3. **A subpanel before its parent.** At `RegisterClass(P)` for a panel with a string `bl_parent_id` (read like
   `bl_idname`, section 8.1): when a Panel of the add-on has that idname and no earlier, non-exclusive
   `RegisterClass` of it exists. A `bl_parent_id` naming no panel of the add-on is Blender's own panel
   (`VIEW3D_PT_tools`) and stays silent. Anchor: `named_at` of `P` (`regchk_order/__init__.py:58`).

"Later" versus "never": if `T` is registered later in the walk, the report holds even for an incomplete walk (a
registration hidden in the opaque part would have made the later one a duplicate). If `T` is never registered,
report only for a complete walk, with the message saying "never". Pairs with an inexact event are skipped.

The `unregister()` order is not checked: Blender accepts any order (`regchk_order/__init__.py:62-64`).

Message: ``` `C` points to `T` (`leaf`), which is registered after it; register `T` first ```.

---

## 7. `blender-duplicate-registration`

### 7.1 A class registered twice

Walk the register events, keeping per class its last registration not undone by an `UnregisterClass` of the same
class since. A `RegisterClass(C)` when such a registration exists, both events exact and not exclusive, is reported
at its `named_at`:

- twice explicitly: `regchk_duplicate/__init__.py:60`;
- twice in one sequence: the second tuple element, `:52`, because each loop iteration's event has its own
  element's `named_at`;
- loop, then explicitly: `:63`.

The same site reached twice (a helper called twice) gives one diagnostic, after deduplication by
`(rule, file, range)`. An incomplete walk still reports: both registrations run.

### 7.2 Two classes with one idname

Per idname namespace (the operator family `Operator` / `Macro`, then `Panel`, `Menu`, `Header`, `UIList`
separately), a registered class whose idname (section 8.1) equals that of an earlier registered, still registered,
different class, both exact and not exclusive. Anchor: the later class's **own** `bl_idname` binding when its
body has one (`regchk_duplicate/__init__.py:42`), else its name (`tests/inheritance/inh_inherited_idname/__init__.py:22`,
where the child inherits the parent's `bl_idname`). The anchor is in the class's file, not where it is registered.

Panels, menus, headers and lists default to the class name, so two such classes of one name in two modules are
duplicates too, as in Blender.

Message: ``` `B` has the idname `"x.y"` of `A`, registered before it; Blender replaces `A` ```.

---

## 8. `blender-invalid-idname`

### 8.1 Reading the idname

**Recommendation:** generalise #22's `addon_operators` reading (register-walk §5.3) into a tracked
`class_idname(class) -> Option<Idname>` per class: the first class in the MRO whose body binds `bl_idname`, its
binding's inferred type, a single string literal (or a union of dynamic types and one literal). `Idname` keeps the
string and whether the binding is in the class's own body (for the anchor). `addon_operators`,
`blender-duplicate-registration`, `blender-register-order` (`bl_parent_id`, read the same way) and this rule share
it. Not a literal (`os.environ.get(...)`) means silent.

### 8.2 The rule

For every registered class (the walk's `RegisterClass` classes; for an incomplete walk, every non-base Blender
class of the add-on, the same set `addon_operators` falls back to):

| Kind | Check | Source |
| --- | --- | --- |
| `Operator`, `Macro` | no `bl_idname` anywhere in the MRO | the class name has no `.`, so it always fails |
| `Operator`, `Macro` | characters other than `a-z0-9_.`; not exactly one `.`; `.` first or last; longer than `OP_MAX_PY_IDNAME` | `wm_operators.cc:204-249` |
| `Panel`, `UIList`, `Header`, `Menu` | the idname (or the class name) lacks `_PT_` / `_UL_` / `_HT_` / `_MT_` with an upper-case alphanumeric prefix and an alphanumeric suffix | `rna_access.cc:1218-1272` |

Anchors: the own `bl_idname` binding (`regchk_idname/__init__.py:11-67`, `:118`, `:135`), else the class name
(`:74` missing, `:108` the class name used as idname). The upper-case `"REGCHK_IDNAME_OT_upper_form"` (`:11`) fails
by character, so no special case is needed for the `X_OT_y` form.

Only registered classes: `REGCHK_UNREGISTERED_OT_base` (`regchk_unregistered/__init__.py:23`) has no `bl_idname` and
must stay silent; it is a base and never registered.

---

## 9. `blender-unregister-mismatch`

### 9.1 What is paired

The register walk gives the additions, the unregister walk the removals. Both are sets; counts and order do not
matter (Blender accepts any unregister order, and duplicates are section 7's business).

| Added in the register walk | Removed in the unregister walk | Key |
| --- | --- | --- |
| `RegisterClass` | `UnregisterClass` | the class |
| `SetProperty` (literal names only, as today) | `DelProperty` from `del X.attr` / `delattr(X, "lit")`, also in loops over `(class, "name")` tuples (`tests/properties/props_registered/__init__.py:60-75`) | `(owner, name)` |
| `Hook { added: true }`: `.append` / `.prepend` | `Hook { added: false }`: `.remove` | `(target, function)` |

`HookTarget` is either a first-party class (a menu of the add-on), or the Blender path of the list: the Foreign value
keeps the dotted path it was reached by, resolved as a Blender symbol, so `from bpy.app import handlers` then
`handlers.load_post` is `bpy.app.handlers.load_post` (`tests/bpy_symbols/sym_handlers/__init__.py:29`, `:39`).
`bpy.types.VIEW3D_MT_object` is not in the stubs (it is `unresolved-attribute` in
`tests/typecheck/expected/builtin/main.txt:964`), so the path is taken from the attribute chain on `bpy.types`, not
from a resolved class. `function` is a first-party function's definition; lambdas are skipped.

The unregister walk also walks module bodies first (#22). Only its removal events are read, so the module-level
registrations it re-walks do not matter.

### 9.2 What is reported

- **Leak** (register walk adds, unregister walk never removes), only when the **unregister** walk is complete:
  - a class: at the register event's `named_at` (`tests/registration_checks/regchk_unregister_leak/__init__.py:57`);
  - a property: at the assignment target (`:61`);
  - a hook: at the `append` call (`:63`, `:65`).
- **Unknown class** (`UnregisterClass(C)` with no `RegisterClass(C)` in the register walk), only when the
  **register** walk is complete: at the `unregister_class` event's `named_at`
  (`tests/registration_checks/regchk_unregister_unknown/__init__.py:29`).
- **Not reported:** deleting a property or removing a hook that was not added. Property names in `setattr` can be
  computed (`props_registered/__init__.py:50-51` registers `dyn_a` / `dyn_b` that way and deletes them by literal
  name at `:71-75`), and `if f in handlers: handlers.remove(f)` guards are common. Both are real runtime errors when
  wrong (`del` raises, `list.remove` raises); a later extension can add them for literal names.
- **No `unregister`**, or one the walk cannot resolve, makes the unregister walk incomplete: no leak is reported.
  `tests/addon_discovery/disc_no_unregister/__init__.py:8` registers a property and has no `unregister()`: it already
  gets `blender-invalid-register` and must get nothing else.
- Conditional unregistration (`if cls.is_registered:`, `tests/registration/reg_conditional/__init__.py:73`) counts,
  like every branch.
- Factories pair themselves: `register_classes_factory` and `register_submodule_factory` give the unregister half the
  same classes (register-walk §2.3).

Messages: ``` `X` is registered but `unregister()` never unregisters it ```;
``` `unregister()` unregisters `X`, which `register()` never registers ```.

---

## 10. Reporting

**Recommendation:**

```rust
#[salsa::tracked(returns(ref), heap_size=...)]
fn registration_findings<'db>(db, key: AddonInProgram<'db>) -> Box<[Finding]>;

#[derive(Clone, Debug, PartialEq, Eq, Hash, get_size2::GetSize)]
struct Finding { rule: RegistrationRule, file: File, range: TextRange, message: Box<str> }
```

- It reads `registration_walk(key, Register)`, `registration_walk(key, Unregister)`, the per-file class and
  registering-function lists of every add-on file, and `class_idname`. Sorted by `(file, range, rule)`, deduplicated.
- #27's per-file query (`addon_diagnostics` generalised, `blender/lints.rs:46-70`) adds one loop: for the add-on of
  its file, report each finding whose `file` is that file, through `context.report_lint(&lint_of(rule), range)`.
  `# ty: ignore[...]` then works per #6.
- **Incremental behaviour.** An edit anywhere the walk reads re-runs `registration_findings`; an unchanged result
  backdates, and each file's query only filters. Ranges are part of the findings, so an edit that shifts lines in a
  file changes that file's findings only. (The walk's own sites shift too: whether `registration_ir` backdates under
  such edits is #22's and the map's measuring task.)
- **Findings outside the add-on.** A site in a shared library is dropped. Then a leak caused by the library's
  `register_tool()` (if A's `unregister()` forgot `unregister_tool()`) is lost. If wanted later: each event keeps the
  outermost call site in the add-on's own files (`via: Site`), and such findings move there. Not needed by the tests.
- **Lints.** Six `declare_lint!` in `blender/lints.rs` with docs in `resources/lint_docs/`, registered by the
  existing `register_lints` (`lints.rs:39-42`), plus `cargo dev generate-all` (#6). Proposed default levels:
  `Error` for `register-order`, `duplicate-registration` and `invalid-idname` (registration fails or an operator
  is lost); `Warn` for `unregistered-class`, `unreachable-registration` and `unregister-mismatch` (code that may be
  intentional or only leaks). The panel-prefix case is a Blender warning inside an error rule; acceptable, or split
  it later.

---

## 11. Effect on the tests

- Every `ignore-comment-unknown-rule` line of `registration_checks` in `tests/typecheck/expected/*/main.txt`
  (lines 929-980 on builtin), plus `addon_preferences/prefs_unregistered/__init__.py:7`,
  `inheritance/inh_inherited_idname/__init__.py:22` (its `blender-registered-base` half belongs to inheritance),
  `registration/reg_explicit/__init__.py:37` and the three `reg_submodule_factory` lines, becomes a matched marker.
- **New diagnostics in check files.** A scan of every add-on for registrable classes named only at their
  definition found, besides `reg_autoload` (silent: its walk is incomplete):
  - `tests/bpy_symbols/sym_negative/check_sym_negative.py:13` (`LocalFunctions(bpy.types.PropertyGroup)`);
  - `tests/inheritance/inh_bases/check_inh_bases.py:41`, `:49` (`WithAbc`, `WithSlots`, both `Operator`);
  - `tests/inheritance/inh_overrides/ide_inh_overrides.py:14`, `:26` (`IDE_OT_hover`, `IDE_UL_hover`).

  `check_sym_negative.py:29` (`Local`) is inside a function and its `bpy` is a parameter: silent. These are real
  findings (the classes are never registered). **Recommendation:** add `blender-unregistered-class` to their markers.
  The other option, honouring the manifest's `paths_exclude_pattern` (which lists `check_*.py`), would only cover
  Extensions and makes the checker depend on build settings.
- No two classes in the corpus share a literal `bl_idname` except `regchk_duplicate`'s pair (grep). Order and leak
  false positives elsewhere cannot be ruled out by reading; the build's `check:features` diff shows them.
- `reg_submodule_factory/unlisted.py:7` loses its `blender-unregistered-class` (section 3.3).

---

## 12. Open points

1. **The `unlisted.py` / `regchk_unreachable` contradiction** (section 3.3): drop the marker (recommended) or add two.
2. **Markers for the check-file classes** (section 11), or exclude excluded paths.
3. **Escaped functions** (deferred registration through timers or handlers): walk them last, inexact (section 4).
   This touches the walk of #22 and has no test yet.
4. **Removal without addition** (deleting a property or removing a handler never added): silent for now.
5. **Findings in shared code** are dropped; a `via` site would move them into the add-on (section 10).
6. **Default levels** of the six lints (section 10).
7. **To verify at build:** that `end_of_scope_symbol_bindings` gives both `if` / `else` bindings and only the last of
   straight-line rebindings for the sequence evaluator; that `get_type_hints`-style inherited annotations are what
   `property_declaration` sees for first-party bases and mixins.
