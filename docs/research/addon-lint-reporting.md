# Reporting add-on-level `blender-*` lints so `# ty: ignore` applies

Research note, 2026-11-05, for [issue #6](https://github.com/taway1450/blender-extension-developer-suite/issues/6)
under the map [#1](https://github.com/taway1450/blender-extension-developer-suite/issues/1). The charting decisions
in [#2](https://github.com/taway1450/blender-extension-developer-suite/issues/2) are taken as given; one of them
meets a hard constraint, described in section 4.2.

The question: how can the glue report `blender-invalid-register` and `blender-invalid-addon-metadata` so that
`# ty: ignore[...]` on the reported line suppresses them, and `unused-ignore-comment` fires when nothing is
reported there?

Conventions:

- Every fact has a `path:line` source. `ruff-blender/` is short for `ty-blender/ruff-blender/` (branch `blender`),
  read at the state checked out on 2026-11-05. Test paths are relative to this repo.
- My own recommendations are marked **Recommendation**.
- Nothing here was built or run. All facts come from reading the source.

---

## 1. Answer in brief

1. **Suppression is applied when the diagnostic is reported, not afterwards.** `InferContext::report_lint`
   looks up the file's suppressions and marks a matching one as *used*. `check_suppressions` then runs once at
   the end of `check_types` and reports every unused suppression as `unused-ignore-comment`. A blender lint
   gets both behaviours only if it is reported through an `InferContext` of the file it is anchored in, and that
   context's diagnostics are merged in `check_types` before `check_suppressions` runs. Diagnostics added later,
   in `ty_project::check_file_impl`, skip suppression, and their `ty: ignore` comment is then reported as unused.
2. **Where to report.** Use a per-file pass in `check_types` (`types.rs:198-278`) over the module's global scope,
   anchored in the add-on's `__init__.py`. There are two places with precedent. One is the end of module-scope
   inference (`check_final_without_value`, `builder.rs:1294`). The other is a separate tracked query whose
   diagnostics `check_types` merges, the way legacy type aliases are merged (`types.rs:239-258`).
   **Recommendation:** the separate tracked query, hooked with one line in `check_types`.
3. **Anchor for "line 1".** Use a range that starts at offset 0. A trailing `# ty: ignore[...]` after the
   module docstring covers everything from offset 0 to the comment, so it also covers a docstring that spans
   several lines. `bl_info` problems are anchored on the `bl_info` target or on the dict entry.
4. **Registration.** Add one line at the end of `types::diagnostic::register_lints`. Everything else reads
   `default_lint_registry()`: suppression parsing, rule selection, `[rules]` config, `ty rule`, `ty.schema.json`,
   `rules.md` and the mdtest registry. **Constraint:** `declare_lint!` cannot be used in `ty_blender`. The macro
   expands to `ty_python_semantic::lint::LintMetadata`, and `ty_blender` sits *below* `ty_python_semantic`, so
   the declarations have to live in the glue (`types/dedicated/blender/`).
5. **Generated files.** Run `cargo dev generate-all` and commit two files in the fork:
   `crates/ty/docs/rules.md` and `ty.schema.json`. Both have up-to-date tests in `ruff_dev`, which belong to the
   regression suite. `ty-blender`'s `scripts/autogenerate_files.sh` copies `rules.md` into
   `docs/reference/rules.md`.
6. **`ignore-comment-unknown-rule`.** It stops firing as soon as the name is in the registry. Each code in a
   `ty: ignore[...]` comment is resolved with `db.lint_registry().get(code)`, and only a failed lookup becomes
   an unknown-rule suppression. From then on, a marker with nothing reported on its line gets
   `unused-ignore-comment` instead.

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
  declaration range through `context.report_lint` (`post_inference/final_variable.rs:11-61`). That is the shape
  an add-on check needs: once per module, a range of our choosing, the suppression-aware reporter.
- Cost: a check here becomes part of `infer_scope_types` for the module scope. Any input it reads, such as the
  manifest through `ty_blender`'s tracked probes, becomes a dependency of the module's whole inference. A
  manifest edit would then re-infer the module scope of `__init__.py`.

### 3.2 A separate query merged in `check_types`

- `check_types` already merges diagnostics from queries other than `infer_scope_types`. It pops each legacy type
  alias, calls the tracked `infer_legacy_type_alias` (`types/infer.rs:110-146`), and merges
  `inference.context.diagnostics` with `extend_filtered`, before `check_suppressions` (`types.rs:239-258`).
- `InferContext::new(db, env, scope, file, program_file, module)` (`context.rs:165-192`) can be built from:
  - `global_scope(db, program_file)` (`ty_python_core/src/lib.rs:231`);
  - `ProgramEnvironment::from_file` (`context.rs:43-48`);
  - `parsed_module(db, python_file).load(db)`.

  `infer_legacy_type_alias` builds these pieces the same way (`infer.rs:133-145`). `Unpacker` builds its own
  `InferContext` too (`types/unpacker.rs:59`). The context must be consumed with `finish()`
  (`context.rs:137-148`, `:419-433`).
- A tracked `fn blender_addon_diagnostics(db, file: ProgramFile) -> TypeCheckDiagnostics` under
  `types/dedicated/blender/` would depend on the manifest and `bl_info` facts only for files that are an add-on
  entry. Its result would be merged with one `diagnostics.extend(...)` line in `check_types`.
- Both patterns report from the global scope of the checked file. `severity_and_source` already returns nothing
  for files that are not checked (`context.rs:683-685`, `should_check_file`). In open-files mode, an
  `__init__.py` that is not open gets no add-on diagnostics.

**Recommendation (3.2).** Report the add-on rules from a separate tracked query in `types/dedicated/blender/`,
called from `check_types` just before `check_suppressions` (between `types.rs:258` and `:267`).

- It is one line in an existing file. That matches #2's "existing files get one-line hooks".
- Module inference stays independent of manifest edits.
- The query can look up the type of `register` through the normal public APIs. It runs outside the module-scope
  query, so there is no risk of a cycle with it. Reading the type of `register` is needed for re-exports,
  `register_classes_factory` and aliases (`tests/typecheck/features/addon_discovery/README.md:16-18`).
- It returns early, without reading anything, for files that are not an add-on's entry `__init__.py` (or its
  single-file add-on).

### 3.3 Anchors

The anchor must be a range in the file whose `check_types` reports it (section 2).

| Case | Test | Anchor | Why the marker matches |
| --- | --- | --- | --- |
| missing `register` / `unregister` | `disc_no_register/__init__.py:1` | **Recommendation:** a range starting at offset 0, such as the first line or `TextRange::empty(0)` | The trailing marker after the docstring covers `0..comment_end` (`suppression.rs:116-120`, `:141-143`). That holds even for a docstring over several lines. If line 1 is a comment-only `# ty: ignore[...]`, it is a file suppression (`suppression.rs:674-678`), which also covers offset 0, but then it suppresses that rule in the whole file. |
| manifest problems | `disc_bad_manifest/__init__.py:1` | same, offset 0 of `__init__.py` | `blender_manifest.toml` is not a Python file. Suppressions exist only for `PythonFile`s (`suppression.rs:89`), so the TOML itself can never carry a marker. |
| wrong `register` signature | `disc_register_signature/__init__.py:4,8` | the `def` statement's name or parameter list in `__init__.py` | The diagnostic starts on line 4 / 8. |
| `register` re-exported from a submodule | `disc_register_reexport` | the import or assignment in `__init__.py`, not the submodule's `def` | A diagnostic in another file cannot be suppressed from `__init__.py` (the span is always `ctx.file`, `context.rs:232-234`). |
| `bl_info` missing a key | `disc_bad_bl_info/__init__.py:3` | **Recommendation:** the `bl_info` assignment target (line 3 only), not the whole dict | If the anchor covered the whole dict, its end on line 7 would also count (`applies_to` checks the end inclusively, `suppression.rs:522-525`). A narrow anchor avoids matching unrelated markers. |
| `bl_info` entry with a bad value | `disc_bad_bl_info/__init__.py:5` | the key/value of the entry (line 5) | The line-5 trailing marker covers only line 5. |

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

**Recommendation.** Put a `pub(crate) fn register_lints(registry: &mut LintRegistryBuilder)` in
`types/dedicated/blender/` (for example `blender/diagnostic.rs`). It registers `BLENDER_INVALID_REGISTER` and
`BLENDER_INVALID_ADDON_METADATA`. Call it with one line at the end of `types::diagnostic::register_lints` (the function spans
`types/diagnostic.rs:71-211`), as #2 / the placement note proposed
(`docs/research/typecheck-feature-placement.md:207-208`). The module also needs `pub(super) mod blender;` in
`types/dedicated/mod.rs` (currently three lines: `django`, `pydantic`, `pytest`). The glue reaches the statics
the way `dedicated/pydantic.rs:21` imports `PYDANTIC_DISCARDED_EXTRA_ARGUMENT`.

### 4.2 Constraint: the declarations cannot live in `ty_blender`

#2 lists "the `blender-*` lint declarations" among the contents of `crates/ty_blender`, a crate *below*
`ty_python_semantic`. That cannot compile:

- `declare_lint!` expands to `$crate::lint::LintMetadata` and `$crate::lint::lint_metadata_defaults`
  (`lint.rs:272`, `:279`), where `$crate` is `ty_python_semantic`. The type `LintMetadata` is defined in
  `ty_python_semantic/src/lint.rs:10-31`.
- `ty_python_semantic` will depend on `ty_blender`, so `ty_blender` cannot depend back on it (a Cargo
  dependency cycle). `ty_python_semantic`'s current dependencies are at `ty_python_semantic/Cargo.toml:13-55`.
- The ways around it are all worse than moving the declarations:
  - moving `lint.rs` into a lower crate rewrites a core upstream file;
  - `#[doc = include_str!("<path into ty_blender>")]` with the static still in `ty_python_semantic` only moves
    the Markdown.
  - `#[doc = SOME_CONST]` is not an option: the macro only accepts `#[doc = $doc:expr]` attributes
    (`lint.rs:261`), and the compiler accepts only literals and macro calls as attribute values, not paths to
    constants. (Rust language rule, not checked in this repo.)

**Recommendation.** Declare the `blender-*` lints in `ty_python_semantic/src/types/dedicated/blender/` together
with their reporters. Put their docs in `ty_python_semantic/resources/lint_docs/blender-*.md` and include them
with `#[doc = include_str!(...)]`, the upstream convention (`types/diagnostic.rs:213-215`,
`suppression.rs:30-31`). `ty_blender` keeps the type-free *facts* the lints are about: discovery results, parsed
manifest / `bl_info` errors with their text ranges. The glue turns them into diagnostics. This is a correction to
one bullet of #2's architecture and should be recorded on the map. It does not change the crate split itself.

### 4.3 Generated files the fork must update

`AGENTS.md:237` (in `ruff-blender`) says to run `cargo dev generate-all` after changing lint rules.
`generate_all::main` runs every generator (`ruff_dev/src/generate_all.rs:41-54`). Two outputs depend on the lint
registry:

| File (in `ruff-blender`) | Generator | Guarded by |
| --- | --- | --- |
| `crates/ty/docs/rules.md` | `generate_ty_rules.rs:26-59` (one section per registered lint) | test `ty_rules_up_to_date` (`generate_ty_rules.rs:192-195`) |
| `ty.schema.json` | `generate_ty_schema.rs:18-24`, through the `Rules` schema above | test `test_generate_json_schema` (`generate_ty_schema.rs:62-70`; `TY_UPDATE_SCHEMA=1` rewrites) |

Both tests are part of ty's existing suite, which #2 keeps as the regression guard. Without the regenerated
files they fail. `pydantic-discarded-extra-argument` shows the footprint of one dedicated lint: it appears in
exactly `ty.schema.json`, `crates/ty/docs/rules.md`, its `resources/lint_docs/*.md`, its mdtest and
`diagnostic.rs` (search of `ruff-blender`).

In `ty-blender`, `scripts/autogenerate_files.sh:24` copies `rules.md` to `docs/reference/rules.md`, so that copy
changes on the next run. The "View source" link in `rules.md` points at `astral-sh/ruff/blob/main/{file}`
(`generate_ty_rules.rs:166`), which will be a dead link for fork-only lints. That is cosmetic.

**Recommendation.** The build ticket that adds the two lints also commits the regenerated `rules.md` and
`ty.schema.json` in the fork (and `docs/reference/rules.md` in `ty-blender`). After that, every new `blender-*`
lint repeats the same step.

---

## 5. How `ignore-comment-unknown-rule` stops firing

- `check_unknown_rule` reports one `IGNORE_COMMENT_UNKNOWN_RULE` per entry of `suppressions.unknown`
  (`suppression.rs:196-207`). Entries are added only when `lint_registry.get(code)` fails
  (`suppression.rs:727-741`).
- Once `blender-invalid-register` is in `default_lint_registry()`, the code resolves, and the comment becomes a
  normal `SuppressionTarget::Lint` suppression (`suppression.rs:728-736`).
- From then on there are two outcomes:
  - it is used, because a diagnostic reported through `InferContext::report_lint` matched it
    (`context.rs:705-710`);
  - or it is reported as `unused-ignore-comment` (`suppression/unused.rs:37-60`).

  For the test harness this is exactly the change from "rule ty does not have yet" to pass / fail
  (`tests/typecheck/README.md:64-66`).
- Two edge cases follow from section 2:
  - If a user disables a `blender-*` rule in `[rules]`, its markers become `unused-ignore-comment`. The severity
    check returns before the suppression is marked used (`context.rs:688`), and `check_unused_suppressions` only
    checks whether the *unused* rules are enabled (`unused.rs:20-25`). This is the same for every ty rule.
  - A diagnostic that does not go through `report_lint` never marks a suppression. Its `ty: ignore` is reported
    as unused even though the diagnostic is shown.

---

## 6. Summary of recommendations

1. Declare `BLENDER_INVALID_REGISTER` and `BLENDER_INVALID_ADDON_METADATA` with `declare_lint!` in
   `ty_python_semantic/src/types/dedicated/blender/`, not in `ty_blender` (section 4.2). Put the docs in
   `resources/lint_docs/blender-*.md`.
2. Register them from `blender::register_lints(registry)`, called with one line at the end of
   `types/diagnostic.rs` `register_lints`. Add `pub(super) mod blender;` to `types/dedicated/mod.rs`.
3. Report them from a tracked per-file query in the glue. It builds an `InferContext` on the file's global scope,
   reports through `context.report_lint`, and returns the finished diagnostics. Merge them with one line in
   `check_types` before `check_suppressions` (`types.rs:258-267`). Never append them in `ty_project`.
4. Anchors:
   - missing entry points and manifest problems: a range starting at offset 0 of `__init__.py`;
   - signature problems: the `def` in `__init__.py`;
   - re-exported entry points: the import or assignment in `__init__.py`;
   - `bl_info`: the target name (missing keys) or the entry (bad values).
5. Run `cargo dev generate-all` and commit `crates/ty/docs/rules.md` and `ty.schema.json` in the fork. Copy
   `rules.md` into `ty-blender/docs/reference/` with `scripts/autogenerate_files.sh`.
