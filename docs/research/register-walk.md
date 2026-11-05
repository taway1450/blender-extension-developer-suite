# How `register()` is followed to what it registers

Research note, 2026-11-06, for [#22](https://github.com/taway1450/blender-extension-developer-suite/issues/22)
(map: [#21](https://github.com/taway1450/blender-extension-developer-suite/issues/21)). It builds on
[#8](https://github.com/taway1450/blender-extension-developer-suite/issues/8) (registered-property collection, now
built as the Add-on index) and keeps the map's settled points:

- `register()` is followed. When the walk meets something it cannot resolve, every Blender class of the add-on
  counts as registered, and `blender-unregistered-class` / `blender-unreachable-registration` stay silent for it.
- The walk replaces the directory walk as the source of Registered properties. The directory walk stays only as
  that fallback.
- Code that `register()` reaches outside the add-on root (a shared library) counts toward that add-on.

Conventions:

- `ruff/` is `ty-blender/ruff-blender/` at `c4b93523c0` (branch `blender`). `blender/` is
  `ruff/crates/ty_python_semantic/src/types/dedicated/blender/`. `tests/` is `tests/typecheck/features/`.
  `bpy-src/` is Blender's `scripts/modules/` (`.cache/blender-src/main/`).
- **Recommendation** marks my own design. Everything else is read from source.
- Nothing was built or run. The cost remarks are reasoning, not measurements.

---

## 1. Answer in short

**Recommendation.** The walk is a small abstract interpreter over a per-file, cached summary of the code. It never
infers add-on code.

1. **`registration_ir(ProgramFile)`**, tracked, per file. A syntactic pass turns each function body and the module
   body into a list of *steps* (register / unregister a class, call, assign or delete a property, import, loop),
   with names resolved through `resolve_expression` (`blender/index.rs:232`), extended as in section 3. Loop
   variables and parameters stay symbolic. The result is `Eq`, so an edit that does not change a file's steps
   backdates.
2. **`registration_walk(AddonInProgram, entry)`**, tracked, with `entry` either `register` or `unregister`. It
   starts at the root module: first the module body, then the entry function. It interprets the steps, following
   calls into first-party functions in any file, the add-on root or not. The result is either an ordered list of
   *events* plus the set of functions it entered, or **`Incomplete`** with the place it gave up.
3. **`addon_index(AddonInProgram)`** (today's query, `blender/index.rs:95`) becomes:
   - `registered_classes`: the class events of the register walk, in order;
   - `registered_properties`: the property events of the register walk. If the walk is `Incomplete`, the
     directory walk's `file_facts` are added (today's behaviour);
   - `complete: bool`.
4. **`addon_operators(AddonInProgram)`**, tracked, maps `category -> name -> class`. It is derived from
   `registered_classes`, or from every operator class in the add-on's files when the walk is incomplete. This is
   the only step that infers: it reads `bl_idname`'s type (section 5).

The walk stays syntactic plus name resolution. It infers only the types of class and function definitions, as
`resolve_expression` already does. Sequences are evaluated by the interpreter, not by ty (section 4).

---

## 2. What the tests require

### 2.1 Constructs (registration feature)

| Add-on | Construct | Source |
| --- | --- | --- |
| `reg_explicit` | `bpy.utils.register_class(C)`, `register_class(C)`, `add_class(C)` (an `as` alias); a property in `register()` | `tests/registration/reg_explicit/__init__.py:553-557` |
| `reg_loop` | `for cls in X` over a tuple, a list with `.append` and `+=` at module level, `() + (C,)`, `(*X, C)`, nested loops over a tuple of sequences | `reg_loop/__init__.py:943-961` |
| `reg_factory` | `_register, _unregister = bpy.utils.register_classes_factory((A, B))`, called from a hand-written `register()` | `reg_factory/__init__.py:631-638` |
| `reg_submodule_factory` | `register, unregister = register_submodule_factory(__name__, ["ops_module", "ops_package"])`; a sub-package whose `register()` delegates on | `reg_submodule_factory/__init__.py:1058`, `ops_package/__init__.py:1-10` |
| `reg_delegation` | helpers, a helper calling a helper, `tools.register()`, `for module in MODULES: module.register()`, `for function in (f,): function()`, `Registrar.register()` (a static method) | `reg_delegation/__init__.py:395-433` |
| `reg_imports` | `if "bpy" in locals(): importlib.reload(m) else: from . import m`; `from .ops_renamed import register as register_renamed`; a star import; `from .nested.deep import operators as nested_operators`; `from . import ops_lazy` inside `register()` | `reg_imports/__init__.py:773-797` |
| `reg_autoload` | `auto_load.init()` fills a module list with `classes.append(cls)` where `cls` comes from `inspect.getmembers`; `register()` loops over it | `reg_autoload/auto_load.py:31-47`, `__init__.py:131-137` |
| `reg_conditional` | `if bpy.app.version >= ...`, a module-level conditional `append`, `try`, `hasattr`, `os.environ`; all count | `reg_conditional/__init__.py:226-243` |

Classes that must stay missing: `reg_explicit.never` (`check_reg_explicit.py:484`), the unlisted module and class of
`reg_submodule_factory` (`check_reg_submodule_factory.py:1008-1009`).

### 2.2 What the registration checks need from the walk

| Rule | Needs | Source |
| --- | --- | --- |
| `blender-unregistered-class` | the set of registered classes, and whether the walk is complete | `tests/registration_checks/regchk_unregistered/__init__.py` |
| `blender-unreachable-registration` | the functions the walk entered, against every first-party function that calls `register_class` | `regchk_unreachable/__init__.py:18-23`, `forgotten.py:15`, `reg_submodule_factory/unlisted.py:15` |
| `blender-register-order` | classes **and** property assignments in one ordered list, with the `type=` of pointer properties | `regchk_order/__init__.py:51-57` |
| `blender-duplicate-registration` | one event per registration, each with the place the class was **named**: the second tuple element, not the loop's call | `regchk_duplicate/__init__.py:47-60` |
| `blender-unregister-mismatch` | an unregister walk; handler and menu `append` / `remove`; `del` / `delattr` | `regchk_unregister_leak/__init__.py:56-74`, `regchk_unregister_unknown/__init__.py:26-31` |
| isolation | the shared library's operator only in the add-on that calls `register_tool()` | `regchk_isolation_a/__init__.py:18-21`, `regchk_isolation_b/__init__.py:18-20`, `regchk_shared_lib/__init__.py:16-17` |

The shared library is imported as `import regchk_shared_lib` (`regchk_isolation_a/__init__.py:5`). It is a top-level
package of the same first-party import root, and no add-on root encloses it (`regchk_shared_lib/__init__.py:1-2`).

### 2.3 What Blender's factories do

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

## 3. Name resolution: what exists, what to add

### 3.1 What `resolve_expression` does today

- It follows a `Name` through the definitions of the nearest enclosing scope that has any, and requires them all to
  resolve to the same thing (`blender/index.rs:262-279`, `all_same` at `:321-324`).
- It follows imports, `from` imports with aliases, star imports and re-exports through ty's
  `definition_resolution::resolve_definition` (`:282-318`), submodules (`:327-373`), and name-to-name assignments up
  to 8 deep (`:226`, `:396-408`).
- For class and function definitions it returns `binding_type` (`:390-392`). That infers the definition's header
  (bases, decorators, annotations), not its body.
- It needs no scope inference, so it is safe to call while the index is being built. ty documents this property for
  its name lookups (`ruff/crates/ty_python_semantic/src/types/definition_resolution.rs:152-180`).

This already covers, for the walk: `reg_explicit`'s three spellings, `tools.register`, `register_renamed`, the star
import, `nested_operators.register`, and `from . import ops_lazy` inside `register()`. That import is a definition in
the function's own scope, and `resolve_name` starts at the expression's scope. The reload pattern also resolves:
in `reg_imports/__init__.py:773-778`, `reloaded` has one binding, the `from . import reloaded` of the `else` branch.

### 3.2 What the walk adds

**Recommendation:** keep `resolve_expression` for its current callers, and give the walk an evaluator on top of it
that returns a *value*:

```rust
enum Value<'db> {
    Module(ProgramFile<'db>),
    /// A class, with where it was named (for duplicate and order diagnostics).
    Class(StaticClassLiteral<'db>, Site),
    /// A first-party function or method, by its definition: never `binding_type`.
    Function(Definition<'db>),
    /// One of Blender's own functions (`register_class`, the factories, `setattr`, ...).
    Builtin(Type<'db>),
    /// A sequence the walk could evaluate (section 4).
    Sequence(Box<[Value<'db>]>),
    /// The two functions a factory returns, with what they were built from.
    Factory(FactoryKind, FactoryHalf, Box<[Value<'db>]>),
    /// Something outside first-party code: `bpy.context`, `wm.keyconfigs`, `os.environ`.
    Foreign,
    /// First-party or dynamic, and not understood: `getattr(...)`, `importlib.import_module(...)`.
    Opaque(Site),
}
```

The additions it needs over `resolve_expression`:

- **First-party functions as definitions.** `FunctionType::definition` warns that it creates a cross-module
  dependency on the full AST (`ruff/crates/ty_python_semantic/src/types/function.rs:1595-1605`). The walk reads the
  function's steps from its own file's `registration_ir` instead, so it only needs the `Definition`.
- **Class members.** `Registrar.register` resolves the name in the class body scope
  (`StaticClassLiteral::body_scope`, `ruff/crates/ty_python_semantic/src/types/class/static_literal.rs:89`) through
  `find_symbol_in_scope` (`definition_resolution.rs:818-850`). Plain, static and class methods are all followed.
  Inherited and Blender-side members are `Foreign`.
- **Tuple-unpacking assignments of a factory.** `_register, _unregister = register_classes_factory(...)` binds
  each name with an assignment whose `target_kind()` is `TargetKind::Sequence`
  (`ruff/crates/ty_python_core/src/definition.rs:1210-1214`, `:1566-1568`). `Unpack::target` gives the whole
  target tuple (`ruff/crates/ty_python_core/src/unpack.rs:69`), from which the name's position (`0` = register,
  `1` = unregister) follows. Today `resolve_definition` rejects non-name targets (`blender/index.rs:399-401`).
- **Several definitions.** `resolve_name` gives up when the definitions differ. For sequences that is wrong:
  `LIST_CLASSES = [...]` and `LIST_CLASSES += [...]` are two definitions of one list (`reg_loop/__init__.py:944-946`).
  The evaluator unions the values of all definitions for sequences (section 4). It still requires one meaning for a
  callee or a class.
- **Local bindings of the walk.** Loop variables and parameters are bound by the interpreter, and looked up before
  the semantic index.
- **`__name__` and `__package__`** as the first argument of `register_submodule_factory`. They are the module's own
  name (`file_to_module`), not a typed value: per [#3](https://github.com/taway1450/blender-extension-developer-suite/issues/3),
  `__name__` is not typed per add-on.

### 3.3 Foreign and Opaque

Most of what `register()` does is not registration: keymaps (`wm.keyconfigs.addon.keymaps.new(...)`), handlers,
previews, timers. If every unresolvable call made the walk give up, the fallback would be the norm.

**Recommendation:**

- An expression whose head resolves outside first-party code is **Foreign**, and so is everything derived from it:
  attributes, calls, subscripts. Calls on Foreign values are ignored, except the recognised Blender functions
  (section 3.4).
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
  not followed (open point 7.4).

`reg_autoload` then gives up exactly where it should: `classes` in `auto_load.py` has the element `cls`, bound by a
loop over `inspect.getmembers(...)` (`auto_load.py:40-42`), so it is Opaque. `register()` passes it to
`register_class` (`auto_load.py:46-47`).

### 3.4 Recognised Blender calls

Recognised by `blender_function_name(db, callee, "bpy.utils")` and the builtins' module:

| Call | Event or value |
| --- | --- |
| `register_class(x)` | one `RegisterClass` per class in `x` |
| `unregister_class(x)` | one `UnregisterClass` per class |
| `register_classes_factory(seq)` | `Factory(Classes, ...)`; calling half 0 registers `seq` in order, half 1 unregisters `reversed(seq)` |
| `register_submodule_factory(name, [lits])` | `Factory(Submodules, ...)`; calling half 0 calls `register()` of each listed submodule in order; half 1 `unregister()` reversed. A non-literal name or list is Opaque. |
| `X.attr = <bpy.props call>` / `setattr(X, "lit", <call>)` | `SetProperty`, as in today's `file_facts` (`blender/index.rs:119-166`) |
| `del X.attr` / `delattr(X, "lit")` | `DelProperty` |
| `<menu class>.append/prepend/remove(f)`, `bpy.app.handlers.<h>.append/remove(f)` | `MenuFunction` / `Handler` events, for the unregister-mismatch rule only |

A name in `setattr` / `delattr` that is not a literal is ignored. That is today's rule for computed names
(`tests/properties/props_registered/__init__.py:44-45`).

---

## 4. Sequences without inference

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

- Mutations are collected flow-insensitively, per file, by `registration_ir`. So the module-level
  `if ...: classes.append(C)` of `reg_conditional/__init__.py:226-228` counts, and so does the `append` inside
  `auto_load.init()`. Order: definitions first, then mutations in source order. That is exact for
  `reg_loop/__init__.py:944-946`.
- A mutation through another module (`auto_load.classes.append(x)` in a third file) is not seen (open point 7.3).
- `GROUPS = ((A,), [B])` with a nested loop works because elements are values, and an inner sequence is a
  `Sequence` value.
- Loop targets that are tuples (`for cls, name in [(Scene, "x"), ...]`, used by
  `props_registered/__init__.py:60-75` in `unregister()`) bind element-wise when the element is a sequence of the same
  length. Otherwise every name is Opaque.

---

## 5. Index shape

### 5.1 Events

**Recommendation:**

```rust
pub(super) struct Walk<'db> {
    /// What the code did, in the order Blender runs it: module bodies at import, then the entry function.
    pub(super) events: Box<[Event<'db>]>,
    /// Every first-party function the walk entered (for `blender-unreachable-registration`).
    pub(super) entered: Box<[Definition<'db>]>,
    /// `Some` when the walk gave up, with where: the add-on falls back.
    pub(super) incomplete: Option<Site>,
}

pub(super) enum Event<'db> {
    RegisterClass { class: StaticClassLiteral<'db>, named_at: Site, call: Site },
    UnregisterClass { class: StaticClassLiteral<'db>, named_at: Site, call: Site },
    SetProperty(RegisteredProperty<'db>, Site),
    DelProperty { owner: StaticClassLiteral<'db>, name: Name, site: Site },
    Hook { kind: HookKind, list: HookTarget<'db>, function: Definition<'db>, added: bool, site: Site },
}

/// A place in a file: an expression's range, for diagnostics and `# ty: ignore`.
pub(super) struct Site { file: File, range: TextRange }
```

- `named_at` is where the class expression was spelled: the tuple element of `regchk_duplicate/__init__.py:50`, or
  the argument of `register_class(C)`. `Class` values carry it from where they were evaluated. `call` is the
  `register_class` call.
- Events are kept in walk order with repeats. Duplicates and order are the rules' business.
- Branches are walked in source order (`if` body, then `elif` / `else`; `try` body, handlers, `else`, `finally`), and
  all count, as the README requires ("conditionally registered classes count", `tests/registration/README.md:17`).
  Mutually exclusive branches can produce false duplicates (open point 7.2).

### 5.2 The Add-on index and the queries

```rust
#[salsa::tracked(returns(ref), heap_size=...)]
fn registration_ir<'db>(db, file: ProgramFile<'db>) -> FileSteps<'db>;            // per file, Eq

#[salsa::tracked(returns(ref), cycle_initial=..., heap_size=...)]
fn registration_walk<'db>(db, key: AddonInProgram<'db>, entry: Entry) -> Walk<'db>; // Entry::Register | Unregister

pub(super) struct AddonIndex<'db> {                       // today's struct, blender/index.rs:43-47
    pub(super) registered_classes: Box<[StaticClassLiteral<'db>]>, // in first-registration order, deduplicated
    pub(super) registered_properties: Box<[RegisteredProperty<'db>]>,
    pub(super) complete: bool,
}

#[salsa::tracked(returns(ref), cycle_initial=..., heap_size=...)]
fn addon_operators<'db>(db, key: AddonInProgram<'db>) -> Operators<'db>;          // category -> name -> class
```

- **Keys.** `AddonInProgram` stays the add-on key (`blender/index.rs:78-84`). The program is part of it because
  resolution depends on the program's search paths.
- **The walk reads only the files it reaches.** Their `registration_ir` results backdate, so typing in a
  `check_*.py`, a panel or an operator body does not re-run the walk. A step changes only when the code changes what
  the walk sees: a call, a registration, an import, a sequence.
- **`registration_ir` keeps no AST.** It records ranges and resolved values. It parses with
  `load_then_clear_on_drop` (as `file_facts` does at `blender/index.rs:122`), so closed files do not pin syntax
  trees.
- **Fallback.** With `incomplete`, `registered_properties` is the walk's properties plus the directory walk's
  `file_facts` (`blender/index.rs:96-104`), deduplicated. `registered_classes` is then unused: the checks are silent
  and `addon_operators` reads every operator class of the add-on's files instead. That needs a per-file list of the
  classes defined in a file whose MRO has a `bpy.types` class (`bpy_types_bases`, `blender/symbols.rs:54-65`). The
  `blender-unregistered-class` rule needs the same list, so it belongs in `file_facts`.
- **No `register`.** A root module without a resolvable `register` (a callable `blender-invalid-register` reports,
  `blender/lints.rs:151-180`) is `incomplete` too. A `register` that is Opaque or Foreign is the same.
- **Recursion.** Re-entering a function already on the walk's call stack with the same arguments is skipped (Python
  would recurse forever). More than 64 nested calls give up. `cycle_initial` returns an empty, complete walk as a
  safety net, as `addon_index` does today (`blender/index.rs:90-94`).
- **Module bodies.** A module body is walked once, at the first `import` the walk executes for it: the root
  module's body, then module-level and in-function imports of every walked body. This catches the module-level
  registration of `props_registered/__init__.py:21`. Module bodies run before `register()`, so their events come
  first.
- **Isolation.** Nothing changes at the use site: the index is still looked up by the accessing file's add-on
  (`blender/index.rs:58-75`). The shared library's operator is in `regchk_isolation_a`'s walk only, because only A
  calls `register_tool()`. A file in the shared library belongs to no add-on, so it sees no index.

### 5.3 Operators by idname

`opcall_idname_forms` needs `bl_idname` from a module constant, a concatenation, an f-string, another class's
attribute plus a string, and a mixin, and nothing from `os.environ.get(...)`
(`tests/operator_calls/opcall_idname_forms/__init__.py:11-49`).

**Recommendation:** `addon_operators` infers, for each registered class that has `Operator` (or `Macro`) among its
`bpy_types_bases`:

1. The first class in its MRO whose body binds `bl_idname`. This covers the mixin.
2. The `binding_type` of that binding, rather than the class's public member type. ty widens undeclared class
   attributes to `Unknown | Literal[...]` (`ruff/crates/ty_python_semantic/resources/mdtest/attributes.md:1163`).
   The binding's own inferred type keeps the literal: f-strings of literals fold
   (`resources/mdtest/literal/f_string.md:9-15`).
3. Accept a single string literal, or a union of dynamic types and one string literal. Split it at the first `.`
   into category and name. An invalid idname gets no attribute (and is the `blender-invalid-idname` rule's
   business).

This is the only inference in the index. It runs on class bodies, not on `register()`, and lives in its own query,
so a cycle through it does not empty the registered properties.

**To verify at build:** `OPCALL_IDNAME_FORMS_OT_fstring.bl_idname + "_copy"` reads the other class's public member
type. If that is `str` instead of `Unknown | Literal[...]`, add a small syntactic folder for `Class.attr` (the
same approach #7 took for `items=`).

---

## 6. The `unregister()` walk

The same interpreter runs from `unregister` (`Entry::Unregister`). What `blender-unregister-mismatch` needs from it:

- `UnregisterClass` events, compared with the register walk's `RegisterClass` (leaks: `regchk_unregister_leak/__init__.py:58`;
  unknown classes: `regchk_unregister_unknown/__init__.py:30`).
- `DelProperty` from `del X.attr` and from `delattr` in a loop over `(class, "name")` tuples
  (`props_registered/__init__.py:60-75`), compared with `SetProperty`.
- `Hook` events: `bpy.app.handlers.<h>.append/remove(f)` and `<Menu class>.append/remove(f)`
  (`regchk_unregister_leak/__init__.py:62-68`). The handler list is Foreign, so `HookTarget` keeps its attribute
  path (`bpy.app.handlers.save_post`) instead of a value. Menu classes are `bpy.types` classes.
- The factories' unregister halves (section 3.4) and `if cls.is_registered:` guards, which count like any branch
  (`reg_conditional/__init__.py:246-250`).
- Its own `incomplete`. A mismatch is only reported when both walks are complete.

The register walk never enters `unregister()`, so its deletions no longer erase properties. That resolves #8's
"ignore `del`" decision without a special case.

---

## 7. Open points

1. **The switch can drop properties that are assigned in code `register()` does not reach.** Today any assignment in
   the add-on's files counts (#8). Such add-ons in the tests would show up in the `check:features` diff of the
   build, not before.
2. **Exclusive branches.** `if a: register_class(C) else: register_class(C)` gives two events. Should
   `blender-duplicate-registration` know about branches (a branch id on each event), or accept the false positive?
   This belongs to the registration_checks ticket, but the event shape must carry it if wanted.
3. **Cross-module mutation** of a list (`other.classes.append(C)`) is not collected. Rare; accept, or scan the
   add-on's files for it.
4. **Code in site-packages** (bundled wheels) is Foreign and never followed. Fine for libraries; an add-on framework
   installed as a wheel that registers the add-on's classes would be missed silently, not fall back.
5. **Language-server cost** stays the map's measuring task. The design keeps it bounded: one parse and one
   `registration_ir` per reached file, the interpreter over cached steps, and idname inference per registered
   operator class.

**To verify at build:**

- `TargetKind::Sequence` plus `Unpack::target` finding the tuple position for both factory forms;
- `find_symbol_in_scope` on a class body for the static method;
- reachability: `find_symbol_in_scope` uses `reachable_symbol_bindings` (`definition_resolution.rs:832`). A binding
  under a branch ty proves unreachable (a `sys.version_info` check) is dropped, which is right for Blender's Python;
- the `bl_idname` reading of section 5.3.
