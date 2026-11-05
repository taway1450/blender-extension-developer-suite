# How registered properties are collected per add-on

Research note, 2026-11-05, for [#8](https://github.com/taway1450/blender-extension-developer-suite/issues/8)
(map: [#1](https://github.com/taway1450/blender-extension-developer-suite/issues/1)). It does not re-decide the
charting decisions in [#2](https://github.com/taway1450/blender-extension-developer-suite/issues/2): registered
properties are injected at the use site, keyed on the accessing file's add-on, and any assignment anywhere in the
add-on counts, with no register-flow analysis.

Conventions, as in the earlier notes:

- Every fact has a `path:line` source. `ruff/` is short for `ty-blender/ruff-blender/` at commit `f076cb67a`
  (branch `blender`). `tests/` is short for `tests/typecheck/`.
- My own recommendations are marked **Recommendation**. Everything else is read from the source.
- Nothing was built or run; the cost section is reasoning from the code, not a measurement.

---

## 1. Answer in short

**Recommendation.** Three tracked queries, from cheap to expensive:

1. `addon_source_files(addon) -> [File]` in `ty_blender`: a recursive walk with `ruff_db`'s tracked
   `directory_listing`, starting at the add-on root. It takes every `.py` file whose nearest add-on root is this
   add-on, and nothing reachable only by import.
2. `registered_properties_in_file(ProgramFile) -> [RegisteredProperty]` in `dedicated/blender/`. A syntactic AST
   pass finds candidates: an attribute-target assignment whose value is a call, and a statement-level
   `setattr(<expr>, "<literal>", <call>)`. Only for candidates, the target object and the callee are resolved
   **without scope inference**. The resolution follows names to their definitions and walks the module/class
   attribute chain. A candidate is kept when the target is a `bpy.types` class and the callee is a `bpy.props`
   function.
3. `addon_registered_properties(addon, program) -> map name -> [RegisteredProperty]` merges (2) over (1). The use
   site calls it with the accessing file's add-on and program.

The result entry is `(owner class, attribute name, declaration)`. The declaration is the assignment's `Definition`,
or the standalone `setattr` call expression. The value type is not computed here. It is built lazily at the use
site by the #7 machinery from the declaration.

`del bpy.types.X.attr` and `delattr` are **ignored** in this slice. Every test add-on deletes its properties in
`unregister()`, so without flow analysis, honouring `del` would remove every property (section 4.4).

---

## 2. Which files belong to the add-on

### 2.1 What the tests require

- A file never imported by the add-on still sees its registered properties.
  - `check_ws_alpha.py` expects `scene.ws_value: int` (`tests/features/addon_discovery/disc_workspace/addons/ws_alpha/check_ws_alpha.py:10-12`).
  - Nothing imports it: `__init__.py` imports only `.values` (`.../ws_alpha/__init__.py:6`).
  - The same holds for every `check_*.py` (`tests/features/properties/props_registered/check_props_registered.py:1-11`).
- Two add-ons under one import root stay separate.
  - `ws_alpha` registers `Scene.ws_value` as an `IntProperty`, `ws_beta` as a `StringProperty`
    (`.../ws_alpha/__init__.py:10`, `.../ws_beta/__init__.py:8`).
  - `ws_beta` expects `str`, and `ws_alpha_only` must stay unresolved there (`.../ws_beta/check_ws_beta.py:10-12`).
  - The import root is `features/addon_discovery`, above both add-ons (`tests/ty.toml:9-10`,
    `tests/features/addon_discovery/disc_workspace/README.md:1-3`).
- An assignment may sit in a sub-module that the add-on imports. In `disc_register_reexport`, the assignment is in
  `core.py:8`.
- `.pyi` files lie inside add-on folders and must not count: `disc_extension/_expected/stubs/bpy.types.pyi`.
  `tests/ty.toml:31-33` excludes `_expected` only from ty's project, and a walk of our own does not see that
  setting.

### 2.2 Directory listing, not import reachability

**Recommendation: list the add-on's directory tree.** Reasons:

- Import reachability from the add-on's entry module would also find `core.py`, but it adds work: every module's
  imports must be resolved. And the charting decision already says "any assignment anywhere in the add-on", not
  "in the modules `register()` reaches".
- Add-ons that load their modules dynamically are invisible to an import graph. A directory listing sees them.
  (Not verified here: auto-loader templates that walk the package directory with `pkgutil` are common in add-ons.)
- The accessing file only needs its add-on key (from #3), not a path through imports.

### 2.3 ty's tracked directory listing

`ruff_db` already has a tracked directory listing, and ty's module resolver uses it:

- `directory_listing(db, path)` returns the sorted direct children with their `FileType` (`ruff/crates/ruff_db/src/files/directory.rs:93-100`).
  - The tracked query reads the directory `File`'s `revision` and `permissions`, then calls
    `System::read_directory` (`directory.rs:102-135`).
  - `entry_is_file` / `entry_is_directory` follow symlinks (`directory.rs:33-49`).
  - It is re-exported from `ruff_db::files` (`ruff/crates/ruff_db/src/files.rs:7-8`).
- The module resolver uses it, for example `resolve.rs:567`, `resolve.rs:606`, `resolve.rs:674` and `path.rs:495`
  (`ruff/crates/ty_module_resolver/src/`).
- Invalidation when files appear or disappear: `File::sync_path` re-syncs the parent directory when a path's
  status changed, which bumps the directory's revision (`files.rs:455-461`, `files.rs:549-558`).
  `sync_all_recursive` also syncs the parents (`files.rs:292-307`). A new or deleted file therefore re-runs the
  listing of its parent directory only.
- Editing a file does not touch the listing. Only the file's own `source_text` / `parsed_module` change.

Precedents for tracked file probing:

- pytest's `conftest_files` probes `directory.join("conftest.py")` with `system_path_to_file` on each ancestor up to
  the first-party root (`ruff/crates/ty_python_semantic/src/types/dedicated/pytest/fixtures.rs:1005-1043`).
  - The probe is a tracked read of a possibly missing file's status, so creating a conftest updates resolution.
    The test `creating_conftest_updates_fixture_resolution` shows this (`fixtures.rs:3049-3081`).
  - It is a plain function, not a tracked one. The caching sits in the per-scope queries it feeds
    (`fixture_name_candidates`, `fixtures.rs:867-904`).
- `desperately_resolve_module` is a tracked query keyed on the importing file (`ruff/crates/ty_module_resolver/src/resolve.rs:286-317`).
  It shows that a walk relative to a file is cached as its own query.

The project's file index cannot be used:

- `ty_project` depends on `ty_python_semantic`, not the other way round (`ruff/crates/ty_project/Cargo.toml:30-33`).
- Its `Project::files` index is built by `ProjectFilesWalker`, which is not a tracked query
  (`ruff/crates/ty_project/src/lib.rs:794-815`).
- `Db::should_check_file` is the only project hook visible below (`ruff/crates/ty_python_core/src/db.rs:9-11`).
  In `CheckMode::OpenFiles` it is true only for open files (`ruff/crates/ty_project/src/lib.rs:943-965`,
  `ruff/crates/ty_project/src/db.rs:367-376`), so it cannot enumerate an add-on.

**Recommendation: `addon_source_files`.**

```rust
// ty_blender
#[salsa::tracked(returns(deref), heap_size = ruff_memory_usage::heap_size)]
pub fn addon_source_files(db: &dyn Db, addon: Addon<'_>) -> Box<[File]>
```

- **Single-file add-on:** the file itself.
- **Package add-on:** depth-first over `directory_listing`, starting at the root. The walk:
  - takes the entries with `entry_is_file` and the suffix `.py`;
  - recurses into entries with `entry_is_directory`;
  - skips `__pycache__` and names starting with `.`;
  - **stops at a subdirectory that is itself an add-on root**, using #3's probe. A file then belongs to exactly the
    add-on of its nearest root, the same rule the use site applies to the accessing file.
- **Sort and dedupe** the result, so salsa backdates it when a listing changes without changing the set of `.py`
  files (for example when a `.pyc` or `.toml` appears).
- **No `.pyi`, and no project include/exclude.** Blender loads `.py` only.
- **Its home is `ty_blender`**, next to discovery. It needs only `ruff_db` and the #3 `Addon` key.

---

## 3. Finding the assignments cheaply

### 3.1 The forms to cover

- From `props_registered/__init__.py`:
  - `bpy.types.X.attr = Prop()` at module level (line 21) and in `register()` (lines 26-41);
  - through a from-import alias, `Coll.reg_alias = StringProperty()` (line 42);
  - `setattr(bpy.types.Image, "reg_setattr", FloatProperty())` (line 43);
  - computed names in a loop, which need not be found (lines 44-45, and the docstring of `check_props_registered.py`).
- Every bpy_symbols import form reaches a registered property.
  - The target object can be any of:
    - `bpy.types.Scene` (`sym_dotted`, `sym_submodule`, `sym_star`);
    - `types.Scene` (`sym_from_bpy`, `sym_reexport_module`);
    - `T.Scene` (`sym_from_bpy_alias`, `sym_module_assigned`);
    - `bt.Scene` (`sym_module_alias`);
    - `AliasScene` (`sym_assigned_alias`);
    - a bare `Scene` re-exported through the add-on's own modules (`sym_reexport`, `sym_nested_reexport`,
      `sym_reexport_star`).

    See `tests/features/bpy_symbols/generated/*/__init__.py:39-52`.
  - The callee takes the same range of shapes, for example `AliasPointerProperty`, `P.PointerProperty` and
    `bp.PointerProperty`.
  - Conclusion: **no textual pre-filter on names is sound.** `"bpy"` or `"Property"` need not appear in the
    statement.

### 3.2 Syntactic pre-filter

**Recommendation.** Walk every statement of the parsed module, recursing into function, class, `if`, `for`,
`while`, `try`, `with` and `match` bodies. Collect:

- an `Assign` target, or an `AnnAssign` target, that is `ExprAttribute { value: <dotted chain>, attr }`, whose value
  is an `ExprCall` with a dotted-chain callee. A dotted chain is a `Name` followed by zero or more `.attr`.
  `Assign` may have several targets; each attribute target counts.
- a statement-level `ExprCall` with a dotted-chain callee, exactly three positional arguments, a dotted-chain
  first argument, a string-literal second argument and an `ExprCall` third argument (the `setattr` shape).

Everything else is dropped without semantic work: tuple targets, subscripts, non-call values, computed names.

- Most add-on modules (`check_*`, UI, operators) have no candidate, and **cost only a parse**.
- ty's own workspace scans use this pattern: they cheaply reject files before any semantic work. `references.rs`
  rejects files by text before parsing (`ruff/crates/ty_ide/src/references.rs:180-187`).
- Here a reject by text is not possible (3.1), so the reject happens on the AST.

### 3.3 Resolving the target class and the callee, without scope inference

Neither expression can come from ty's normal scope inference.

**Facts.**

- An attribute-target assignment does create a `Definition` on the member place `bpy.types.Scene.attr`:
  - a store context marks it as a definition (`ruff/crates/ty_python_core/src/builder.rs:3519-3530`);
  - `record_place_definition` adds an `AssignmentDefinitionNodeRef` (`builder.rs:1417-1435`).
- But the target's object (`bpy.types.Scene`) is inferred only in the statement path:
  - `infer_assignment_statement` → `infer_target` → `infer_target_impl` (`ruff/crates/ty_python_semantic/src/types/infer/builder.rs:2995-3034`,
    `3070-3083`);
  - `infer_target_impl` infers the object at `builder.rs:3449-3456`, as part of the enclosing **scope's**
    inference.
- The definition's own inference infers only the value (`builder.rs:3511-3577`). So
  `definition_expression_type(db, definition, object)` returns `Unknown` for the object
  (`ruff/crates/ty_python_semantic/src/types.rs:403-445`).
- Scope inference (`infer_complete_scope_types`) is what `SemanticModel` uses
  (`ruff/crates/ty_python_semantic/src/semantic_model.rs:1036-1048`).
  - Using it would make collection depend on inferring `register()`'s whole body. That body, or any scope
    that both registers and reads a property, asks the use site for registered properties: a salsa cycle.
  - ty documents this hazard and the cycle-safe alternative: `definitions_for_name` "reads bindings and
    declarations from the semantic index without asking `SemanticModel` to infer" and "can therefore be used
    during inference of the enclosing scope" (`ruff/crates/ty_python_semantic/src/types/definition_resolution.rs:152-180`).
  - It walks the visible ancestor scopes and resolves import aliases to their source definitions, modules
    included (`definition_resolution.rs:183-290`, `ResolvedDefinition` at `:46-53`).
- The value is a standalone expression:
  - For a multi-target or attribute-target `Assign`, `infer_assignment_statement` takes
    `self.index.expression(value)` (`infer/builder.rs:3008`).
  - The definition's inference reads the value's standalone `Expression` and merges its expression types into
    the definition region (`builder.rs:3567-3577`). So `definition_expression_type(db, definition, keyword.value)`
    works for the call's arguments, which is Django's `find_keyword` pattern (`ruff/crates/ty_python_semantic/src/types/dedicated/django.rs:44-104`).
  - A statement-level call (our `setattr`) becomes a standalone expression too (`ruff/crates/ty_python_core/src/builder.rs:5551-5560`),
    reachable through `SemanticIndex::expression` / `try_expression` (`ruff/crates/ty_python_core/src/lib.rs:736-747`).

**Recommendation: one structural resolver for dotted chains**, shared with bpy_symbols recognition.

1. Look up the head name with `definitions_for_name(db, scope_of(expr), head, ResolveAliases)`. The scope comes
   from `SemanticIndex::expression_scope_id` (`ruff/crates/ty_python_core/src/lib.rs:424`).
2. For each resolved definition:
   - a `Module(file)` continues as a module;
   - a class `Definition` continues as that class;
   - an `Assignment` whose value is itself a dotted chain (`T = bpy.types`, `AliasScene = bpy.types.Scene`)
     recurses on that value, with a small depth limit.
   - **Not `binding_type`.** Calling `binding_type` on an arbitrary assignment could infer an instance attribute
     read and re-enter the use-site hook.
3. For each further segment:
   - a module member is resolved like an import (a submodule or a module-level symbol, again through
     `definitions_for_name` in that module's global scope);
   - a class member ends the chain. Nested classes are not needed.
4. Accept the result only if it is:
   - for the **target**: a class whose defining module is `bpy.types` and comes from a non-first-party search path
     (the charting decision's recogniser; the precedent is the module-name check in `fixtures.rs:386-392`);
   - for the **callee**: one of the `bpy.props` functions;
   - for **`setattr`**: the builtin `setattr`.

   The class literal (`binding_type` of the class definition) is computed only now. That is cheap, and it is a stub
   class, not add-on code.

As a safety net, give `addon_registered_properties` a `cycle_initial` that returns an empty map. ty uses this
pattern, for example in `ruff/crates/ty_python_semantic/src/dunder_all.rs:15`.

**Unverified.** Whether `definitions_for_name` resolves a star import (`sym_star`, `sym_reexport_star`) and a
nested re-export to the class definition rather than the import. This should be checked with the first build
ticket. If not, step 3's "resolve like an import" covers these cases.

### 3.4 Which classes count

**Recommendation: collect every `bpy.types` target, including `Area`, `Modifier`, `Window` and the other classes
that do not accept properties.**

- Those lines carry `# ty: ignore[blender-unsupported-property-target]`, a deferred rule
  (`props_registered/__init__.py:46-51`).
- No check expects them to have, or lack, the attribute.
- Filtering by host belongs to the use site and to the later rule, which then reads the same query.
- First-party classes are rejected by the recogniser in step 4.

---

## 4. Result and key

### 4.1 Shapes

**Recommendation.**

```rust
// ty_python_semantic/src/types/dedicated/blender/registered.rs
#[derive(Debug, Clone, PartialEq, Eq, get_size2::GetSize, salsa::SalsaValue)]
pub(crate) struct RegisteredProperty<'db> {
    /// The `bpy.types` class the property is assigned to (`Scene`, `ID`, `Node`, ...).
    pub(crate) owner: StaticClassLiteral<'db>,
    pub(crate) name: Name,
    pub(crate) declaration: RegisteredDeclaration<'db>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, get_size2::GetSize, salsa::SalsaValue)]
pub(crate) enum RegisteredDeclaration<'db> {
    /// `X.attr = Prop(...)`: the member-place definition. Arguments read via `definition_expression_type`.
    Assignment(Definition<'db>),
    /// `setattr(X, "attr", Prop(...))`: the standalone call. Arguments read via `infer_expression_types`.
    Setattr(Expression<'db>),
}

#[salsa::tracked(returns(deref), heap_size = ruff_memory_usage::heap_size)]
fn registered_properties_in_file<'db>(db: &'db dyn Db, file: ProgramFile<'db>)
    -> Box<[RegisteredProperty<'db>]>;

#[salsa::tracked(returns(ref), heap_size = ruff_memory_usage::heap_size,
                 cycle_initial = ...)]  // empty
pub(crate) fn addon_registered_properties<'db>(db: &'db dyn Db, addon: Addon<'db>, program: Program<'db>)
    -> RegisteredProperties<'db>;  // FxHashMap<Name, SmallVec<[RegisteredProperty<'db>; 1]>>
```

- **Owner type.** `StaticClassLiteral` is what Django keys on (`django.rs:117-118`). A `bpy.types` stub class is
  static.
- **Which property function** (Int, Enum, Pointer...) is not stored. The value type comes from the declaration at
  the use site (#7), so this query never evaluates `items=`, `type=` or other arguments. That keeps the query free
  of first-party type inference.
- **The add-on key.**
  - It is #3's `Addon` (open ticket), plus the accessing file's `Program`.
  - The add-on's files become `ProgramFile`s under that program, as `conftest_files` does with
    `request_file.program(db)` (`fixtures.rs:1011`, `:1041`).
  - The program matters because a file's semantics depend on its program's Python version and search paths
    (`ruff/crates/ty_python_core/src/program_file.rs:8-63`).
- **Salsa arguments.** Two salsa arguments are fine for a tracked function. Alternatively, an interned
  `AddonInProgram` can carry both.

### 4.2 Why the per-file split

The split follows the precedents:

- pytest splits per scope: `fixture_name_candidates(scope)`. Its doc comment says the split "lets Salsa reuse
  scope-specific fixture discovery across parameters" (`fixtures.rs:867-904`).
- Django splits per class: `own_model_fields(class)` (`django.rs:116-156`).

The split also enables backdating:

- `parsed_module` is `no_eq` (`ruff/crates/ruff_db/src/parsed.rs:20-35`), so every edit invalidates whatever reads
  the AST directly.
- `registered_properties_in_file` returns an `Eq` value, so salsa backdates it when an edit leaves the file's
  registrations unchanged. Typing in a `check_*.py` or a panel module then never re-runs the add-on merge or
  invalidates use sites in other files.

### 4.3 Use-site lookup (for #9)

The lookup is in scope for #9, but the result shape constrains it:

- On an instance of class `C`, look up `name` in the map.
- Keep the entries whose `owner` is in `C`'s MRO:
  - `reg_id` on `ID` reaches `Scene`, `Object` and `Material` (`check_props_registered.py:20`, `:29-31`);
  - `reg_float` on `Object` must not reach `Scene` (`:24`, `:28`).
- If several remain (the same name on a class and on its base, or assigned twice), prefer the most-derived owner;
  between equals, take the union. This rule is #9's to confirm.

Only call the query on a **failed** instance-attribute lookup on a `bpy.types` class. Files that never read a
registered property then never trigger the scan.

### 4.4 `del` and `delattr`

**Recommendation: ignore them in this slice.** This deviates from the ticket's "`del bpy.types.X.attr` removes
one".

- Every add-on in the tests that registers a property deletes it in `unregister()`:
  - `ws_alpha/__init__.py:14-16`;
  - `disc_extension/__init__.py:13-14`;
  - `props_registered/__init__.py:54-67`, via `delattr`;
  - all `sym_*` add-ons, for example `sym_dotted/__init__.py:43`.
- Their checks expect the property to exist (`check_ws_alpha.py:11-12`, `check_disc_extension.py:14-15`).
- Without register-flow analysis, a delete cannot be ordered against the assignment, so honouring it would empty
  the result.
- In ty's semantic index, `del` is a use and a definition of the place (`ruff/crates/ty_python_core/src/builder.rs:3527`,
  `:5477-5508`). This later lets register-flow work tell a delete in `unregister()` from one at module level.

### 4.5 Forward compatibility with registration

**Recommendation.** Keep `declaration` as the `Definition` / `Expression`. Both know their scope
(`definition.scope(db)`). The later registration feature can then filter the same per-file candidates by "inside a
function reachable from `register()`" or "at module level" without reshaping the result. This is a partial answer
to the map's "forward compatibility" item, not a decision.

---

## 5. Cost in open-files mode

Facts:

- In `CheckMode::OpenFiles` ty checks only open files (`ruff/crates/ty_project/src/lib.rs:943-965`). Without this
  feature, it parses and indexes only those files and the modules their inference reaches through imports.
- In `CheckMode::AllFiles`, every project file is indexed (`lib.rs:794-815`) and checked, so the collection adds
  almost nothing beyond resolving the few candidates.
- `parsed_module` has an LRU of 200 modules (`ruff/crates/ruff_db/src/parsed.rs:31-35`).
  `ParsedModule::load_then_clear_on_drop` drops a closed file's AST after a scan, "intended for use in language
  server operations that scan all of the files in a workspace" (`parsed.rs:159-174`). ty_ide's workspace scans use
  it (`ruff/crates/ty_ide/src/references.rs:254-257`, `symbols.rs:398`, `goto_implementation.rs:105`).

Cost of the first failed lookup on a `bpy.types` instance in an add-on (reasoning, not measured):

| Work | Files | Notes |
| --- | --- | --- |
| directory listings | each directory of the add-on | one `read_dir` each, cached until a child is added or removed |
| read and parse | every `.py` of the add-on | the dominant cost; no semantic index for files without candidates |
| semantic index and name resolution | files with candidates, plus modules on re-export chains | usually `__init__.py` and maybe one `core.py` / `props.py` |
| type inference | none of the add-on's code | only stub classes (`binding_type` of the target class) |

After the first lookup:

- An edit re-parses only the edited file and re-runs only its `registered_properties_in_file`. The result backdates
  unless the registrations changed.
- Creating or deleting a file re-runs one directory listing, then `addon_source_files`, then the merge.

**Recommendations:**

- Use `load_then_clear_on_drop` for the pre-filter pass, so a large add-on does not pin hundreds of ASTs. The files
  with candidates are parsed again for their semantic index, a small extra cost.
- Do not add a textual pre-filter. Section 3.1 shows that no name is guaranteed to occur.
- Do not add a performance budget now. The map's "Performance in the language server" item can use this table as
  its starting point once there is a build to measure.

---

## 6. Open points handed on

- **#3:** the `Addon` key, and the probe for whether a directory is an add-on root, which `addon_source_files` uses
  to stop at nested add-ons.
- **#7:** building the value type from `RegisteredDeclaration`. For `Setattr`, use the standalone call's inference,
  not `definition_expression_type`.
- **#9:** where the failed-lookup hook sits; the MRO filter and the precedence between several entries (4.3);
  whether completion lists registered names (`ide_props_registered.py:22-24` expects them).
- **To verify during build:**
  - star imports and nested re-exports through `definitions_for_name` (3.3);
  - that a `setattr` statement nested in a `for` or `if` body is still a standalone expression
    (`builder.rs:5510-5560` handles every `Stmt::Expr`, but this was not exercised).
