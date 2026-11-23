# Reporting add-on-level `blender-*` lints so `# ty: ignore` applies

Research note, 2026-11-05, for [issue #6](https://github.com/taway1450/blender-extension-developer-suite/issues/6)
(map #1). Trimmed on 2026-11-18 to the rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings.

The question: how can the Blender code in ty report `blender-invalid-register` and `blender-invalid-addon-metadata`
so that `# ty: ignore[...]` on the reported line suppresses them, and `unused-ignore-comment` fires when nothing is
reported there?

Conventions:

- Every fact has a `path:line` source. `ruff-blender/` is short for `ty-blender/ruff-blender/` (branch `blender`),
  read at the state checked out on 2026-11-05.
- Nothing here was built or run. All facts come from reading the source.

---

## 1. Answer in brief

1. **Suppression is applied when the diagnostic is reported, not afterwards.** `InferContext::report_lint`
   looks up the file's suppressions and marks a matching one as *used*. `check_suppressions` then runs once at
   the end of `check_types` and reports every unused suppression as `unused-ignore-comment`. A blender lint
   gets both behaviours only if it is reported through an `InferContext` of the file it is anchored in, and that
   context's diagnostics are merged in `check_types` before `check_suppressions` runs. Diagnostics added later,
   in `ty_project::check_file_impl`, skip suppression, and their `ty: ignore` comment is then reported as unused.
2. **Where to report.** A separate tracked query whose diagnostics `check_types` merges, the way legacy type
   aliases are merged, rather than a check at the end of module-scope inference (section 3).
3. **Anchor for "line 1".** Use a range that starts at offset 0. A trailing `# ty: ignore[...]` after the
   module docstring covers everything from offset 0 to the comment, so it also covers a docstring that spans
   several lines.
4. **Registration.** Everything reads `default_lint_registry()`: suppression parsing, rule selection, `[rules]`
   config, `ty rule`, `ty.schema.json`, `rules.md` and the mdtest registry. **Constraint:** `declare_lint!` cannot
   be used in `ty_blender` (section 4.2).
5. **`ignore-comment-unknown-rule`.** It stops firing as soon as the name is in the registry (section 5).

---

## 2. How ty's suppression works (facts)

- **Parsing.** `suppressions(db, file)` is a tracked query over the file's tokens
  (`ty_python_semantic/src/suppression.rs:88-149`). It builds a `SuppressionsBuilder` with
  `db.lint_registry()` (`suppression.rs:98`).
- **Codes are resolved at parse time.** For `ty: ignore[a, b]`, each code goes through
  `self.lint_registry.get(code)` (`suppression.rs:727`):
  - `Ok(lint)` gives a `Suppression` with target `SuppressionTarget::Lint(lint)` (`suppression.rs:728-736`);
  - `Err(error)` gives an `UnknownSuppression` (`suppression.rs:737-741`).

  `LintRegistry::get` returns `GetLintError::Unknown` only when the name is missing from `by_name`
  (`lint.rs:425-453`).
- **What one comment covers.**
  - A comment before any non-trivia token is a *file* suppression and covers the whole file
    (`suppression.rs:674-678`).
  - An own-line `ty:` comment covers the next logical line (`suppression.rs:679-682`, `own_line_suppression_range`
    at `suppression.rs:758`).
  - A trailing comment covers `TextRange::new(line_start, comment_end)` (`suppression.rs:116-120`, `:684`).
    `line_start` moves forward only at `Newline` / `NonLogicalNewline` tokens (`suppression.rs:141-143`). So a
    trailing comment after a docstring that spans several lines covers everything from the start of the logical
    line to the comment.
- **When a suppression applies.** A suppression applies to a diagnostic if the suppressed range contains the
  diagnostic's start, or contains its end (inclusive) (`suppression.rs:522-525`). It also has to match the lint
  (`suppression.rs:527-533`).
- **Suppression is checked when a diagnostic is reported.** `LintDiagnosticGuardBuilder::new` runs in this order
  (`types/context.rs:698-728`):
  1. it looks up severity; a disabled rule returns `None` before the suppression check (`context.rs:688`);
  2. it calls `suppressions(...).find_suppression(range, lint_id)`;
  3. on a match it calls `mark_used` and returns `None` (`context.rs:705-710`);
  4. it drops diagnostics in unreachable code (`context.rs:715-717`).

  It is reached through `InferContext::report_lint` (`context.rs:332-342`), which is `pub(super)` in `types`. So
  any module under `types/`, including `types/dedicated/blender/`, can call it. The span is always in
  `ctx.file` (`context.rs:232-234`). A suppression can therefore only cover a diagnostic in the file that the
  context belongs to.
- **Used marks travel with the diagnostics.** `TypeCheckDiagnostics::extend` / `extend_filtered` copy
  `used_suppressions` along with the diagnostics (`types/diagnostic.rs:1508-1526`).
- **Unused suppressions are found once per file.**
  - `check_types` gathers scope diagnostics, legacy-alias diagnostics and semantic syntax errors. It then calls
    `check_suppressions(db, file.python_file(db), diagnostics)` (`types.rs:209-267`).
  - That function runs `check_unknown_rule`, `check_renamed_rules`, `check_invalid_suppression`,
    `check_blanket_suppressions` and `check_unused_suppressions` (`suppression.rs:151-165`).
  - Every suppression not marked used becomes `unused-ignore-comment` (`suppression/unused.rs:37-60`, `:81-98`).
- **Diagnostics added after `check_types` skip all of this.**
  - `ty_python_semantic::check_file` appends parse errors and `check_types(...)` (`lib.rs:233-274`).
  - `ty_project::check_file_impl` then appends script settings and dependency diagnostics *after*
    `ty_python_semantic::check_file` (`ty_project/src/lib.rs:1024-1045`).
  - Diagnostics added at that stage are never matched against suppressions. Any `ty: ignore` written for them
    is reported as unused.

  This is the in-tree example of what #2 means by "lints reported outside the crate bypass `# ty: ignore`".

---

## 3. Which pass can report a diagnostic that is not tied to an expression?

The add-on rules talk about the add-on, not about one inferred expression: a missing `register`, a bad
manifest. Two existing patterns report such facts through an `InferContext` that `check_types` collects.

### 3.1 Post-inference checks at the end of scope inference

- `infer_region_scope` handles `NodeWithScopeKind::Module` (`types/infer/builder.rs:1146-1150`). After deferred
  inference, while `should_check_file` holds, it runs the `post_inference::*` checks with `&self.context`
  (`builder.rs:1209-1295`).
- `post_inference::final_variable::check_final_without_value(&self.context, self.index)` (`builder.rs:1294`)
  is one example. It runs once per scope, walks the use-def map, and reports `FINAL_WITHOUT_VALUE` on a
  declaration range through `context.report_lint` (`post_inference/final_variable.rs:11-61`).
- Cost: a check here becomes part of `infer_scope_types` for the module scope. Any input it reads, such as the
  manifest through `ty_blender`'s tracked probes, becomes a dependency of the module's whole inference. A
  manifest edit would then re-infer the module scope of `__init__.py`.

### 3.2 A separate query merged in `check_types`

- `check_types` already merges diagnostics from queries other than `infer_scope_types`. It pops each legacy type
  alias, calls the tracked `infer_legacy_type_alias` (`types/infer.rs:110-146`), and merges
  `inference.context.diagnostics` with `extend_filtered`, before `check_suppressions` (`types.rs:239-258`).
- `InferContext::new(db, env, scope, file, program_file, module)` (`context.rs:165-192`) can be built from
  `global_scope(db, program_file)`, `ProgramEnvironment::from_file` and `parsed_module(db, python_file).load(db)`,
  as `infer_legacy_type_alias` does (`infer.rs:133-145`). The context must be consumed with `finish()`
  (`context.rs:137-148`, `:419-433`).
- Both patterns report from the global scope of the checked file. `severity_and_source` already returns nothing
  for files that are not checked (`context.rs:683-685`, `should_check_file`). In open-files mode, an
  `__init__.py` that is not open gets no add-on diagnostics.

**Why the separate query wins:**

- It is one line in an existing file (`check_types`).
- Module inference stays independent of manifest edits.
- The query can look up the type of `register` through the normal public APIs. It runs outside the module-scope
  query, so there is no risk of a cycle with it. Reading the type of `register` is needed for re-exports,
  `register_classes_factory` and aliases.
- It returns early, without reading anything, for files that are not an add-on's entry.

### 3.3 Anchors

The anchor must be a range in the file whose `check_types` reports it (section 2).

| Case | Anchor | Why |
| --- | --- | --- |
| missing `register` / `unregister` | a range starting at offset 0, such as the first line or `TextRange::empty(0)` | The trailing marker after the docstring covers `0..comment_end` (`suppression.rs:116-120`, `:141-143`). That holds even for a docstring over several lines. If line 1 is a comment-only `# ty: ignore[...]`, it is a file suppression (`suppression.rs:674-678`), which also covers offset 0, but then it suppresses that rule in the whole file. |
| manifest problems | same, offset 0 of `__init__.py` | `blender_manifest.toml` is not a Python file. Suppressions exist only for `PythonFile`s (`suppression.rs:89`), so the TOML itself can never carry a marker. |
| wrong `register` signature | the `def` statement's name or parameter list in `__init__.py` | The diagnostic starts on the `def` line. |
| `register` re-exported from a submodule | the import or assignment in `__init__.py`, not the submodule's `def` | A diagnostic in another file cannot be suppressed from `__init__.py` (the span is always `ctx.file`, `context.rs:232-234`). |
| `bl_info` missing a key | the `bl_info` assignment target, not the whole dict | If the anchor covered the whole dict, its end on a later line would also count (`applies_to` checks the end inclusively, `suppression.rs:522-525`). A narrow anchor avoids matching unrelated markers. |
| `bl_info` entry with a bad value | the key/value of the entry | A trailing marker covers only its own line. |

---

## 4. Registering the lints

### 4.1 How registration reaches every consumer

- `declare_lint!` (`lint.rs:256-282`) builds a `static NAME: LintMetadata`.
  - The rule name is the kebab-case of the static's name (`lint.rs:273`), so `static BLENDER_INVALID_REGISTER`
    becomes `blender-invalid-register`.
  - `file!()` / `line!()` are recorded for the "View source" link (`lint.rs:276-277`).
  - The default level is `Error` unless given (`lint.rs:152-162`). `LintStatus::preview` is `pub(crate)`
    (`lint.rs:206`).
- `LintRegistryBuilder::register_lint` panics on duplicate names (`lint.rs:371-383`).
- The **only** production registry is `default_lint_registry()`, a `LazyLock` filled by
  `ty_python_semantic::register_lints` (`lib.rs:78-98`). That function calls `types::register_lints`
  (= `types/diagnostic.rs:71`, re-exported at `types.rs:39`) and then registers the six suppression lints. Its
  readers:
  - the project DB's `lint_registry()`, used by suppression parsing (`ty_project/src/db.rs:621-623`);
  - rule ordering for `[rules]` (`ty_project/src/metadata/options.rs:137`, `metadata/pyproject.rs:49`);
  - `ty rule` / rule listing in the CLI (`ty/src/rule.rs:53`, `:70`);
  - the `Rules` JSON schema, with one property per lint (`ty_project/src/metadata/options.rs:2367-2406`);
  - the rules doc generator (`ruff_dev/src/generate_ty_rules.rs:59-69`).
- Default rule selection takes every registered lint whose default level is not `Ignore`
  (`RuleSelection::from_registry`, `lint.rs:592-618`). A registered lint is on by default with no config.
- The mdtest DB builds its own registry by calling `register_lints` and then adding a test-only lint
  (`ty_test/src/db.rs:356-373`). So Blender lints registered inside `register_lints` show up in mdtests
  automatically.
- That `ty_test` lint is the in-tree example of a lint declared in *another crate*. It works because `ty_test`
  depends on `ty_python_semantic` and on `ruff_macros`; the comment says "`declare_lint!` expands to a call to
  `ruff_macros::kebab_case!`" (`ty_test/Cargo.toml:14-15`, `:24`, `:29`). It is registered only into
  `ty_test`'s private registry (`db.rs:365-371`), never into `default_lint_registry()`.

### 4.2 Constraint: the declarations cannot live in `ty_blender`

#2 listed "the `blender-*` lint declarations" among the contents of `crates/ty_blender`, a crate *below*
`ty_python_semantic`. That cannot compile:

- `declare_lint!` expands to `$crate::lint::LintMetadata` and `$crate::lint::lint_metadata_defaults`
  (`lint.rs:272`, `:279`), where `$crate` is `ty_python_semantic`. The type `LintMetadata` is defined in
  `ty_python_semantic/src/lint.rs:10-31`.
- `ty_python_semantic` depends on `ty_blender`, so `ty_blender` cannot depend back on it (a Cargo dependency
  cycle).
- The ways around it are all worse than moving the declarations:
  - moving `lint.rs` into a lower crate rewrites a core upstream file;
  - `#[doc = include_str!("<path into ty_blender>")]` with the static still in `ty_python_semantic` only moves
    the Markdown.
  - `#[doc = SOME_CONST]` is not an option: the macro only accepts `#[doc = $doc:expr]` attributes
    (`lint.rs:261`), and the compiler accepts only literals and macro calls as attribute values, not paths to
    constants. (Rust language rule, not checked in this repo.)

So the `blender-*` lints are declared in `ty_python_semantic/src/types/dedicated/blender/` together with their
reporters, with their docs in `ty_python_semantic/resources/lint_docs/blender-*.md` included with
`#[doc = include_str!(...)]`, the upstream convention (`types/diagnostic.rs:213-215`, `suppression.rs:30-31`).
`ty_blender` keeps the type-free *facts* the lints are about: discovery results, parsed manifest / `bl_info` errors
with their text ranges.

### 4.3 Generated files the fork must update

Two generated files depend on the lint registry; `mise run ty:generate` rewrites them:

| File (in `ruff-blender`) | Generator | Guarded by |
| --- | --- | --- |
| `crates/ty/docs/rules.md` | `generate_ty_rules.rs:26-59` (one section per registered lint) | test `ty_rules_up_to_date` (`generate_ty_rules.rs:192-195`) |
| `ty.schema.json` | `generate_ty_schema.rs:18-24`, through the `Rules` schema above | test `test_generate_json_schema` (`generate_ty_schema.rs:62-70`; `TY_UPDATE_SCHEMA=1` rewrites) |

Both tests are part of ty's existing suite, so without the regenerated files they fail. The "View source" link
in `rules.md` points at `astral-sh/ruff/blob/main/{file}` (`generate_ty_rules.rs:166`), which is a dead link for
fork-only lints. That is cosmetic.

---

## 5. How `ignore-comment-unknown-rule` stops firing

- `check_unknown_rule` reports one `IGNORE_COMMENT_UNKNOWN_RULE` per entry of `suppressions.unknown`
  (`suppression.rs:196-207`). Entries are added only when `lint_registry.get(code)` fails
  (`suppression.rs:727-741`).
- Once a `blender-*` name is in `default_lint_registry()`, the code resolves, and the comment becomes a
  normal `SuppressionTarget::Lint` suppression (`suppression.rs:728-736`).
- From then on there are two outcomes:
  - it is used, because a diagnostic reported through `InferContext::report_lint` matched it
    (`context.rs:705-710`);
  - or it is reported as `unused-ignore-comment` (`suppression/unused.rs:37-60`).
- Two edge cases follow from section 2:
  - If a user disables a `blender-*` rule in `[rules]`, its markers become `unused-ignore-comment`. The severity
    check returns before the suppression is marked used (`context.rs:688`), and `check_unused_suppressions` only
    checks whether the *unused* rules are enabled (`unused.rs:20-25`). This is the same for every ty rule.
  - A diagnostic that does not go through `report_lint` never marks a suppression. Its `ty: ignore` is reported
    as unused even though the diagnostic is shown.
