# How `addons[<key>].preferences` resolves to the add-on's own class

Research note, 2026-11-06, for [#30](https://github.com/taway1450/blender-extension-developer-suite/issues/30) (map:
[#21](https://github.com/taway1450/blender-extension-developer-suite/issues/21)). It builds on
[#22](https://github.com/taway1450/blender-extension-developer-suite/issues/22) (the `register()` walk, registered
classes in the Add-on index, the whole-add-on fallback; branch `research/register-walk`),
[#23](https://github.com/taway1450/blender-extension-developer-suite/issues/23) (extending `on_load` without a new
upstream hook; `research/operator-calls`), [#26](https://github.com/taway1450/blender-extension-developer-suite/issues/26)
(the Property evaluator that follows names and constants across modules; `research/property-wrappers`),
[#27](https://github.com/taway1450/blender-extension-developer-suite/issues/27) (the per-file lint query;
`research/property-rules`) and [#5](https://github.com/taway1450/blender-extension-developer-suite/issues/5)
(`__package__` per add-on: a `Literal` for a Legacy add-on, `str` for an Extension).

Conventions:

- `R/` is `ty-blender/ruff-blender/crates/ty_python_semantic/src/`, `BL/` is Blender's source at
  `.cache/blender-src/main/`, `T/` is `tests/typecheck/`, `F/` is `T/features/addon_preferences/`, `SB/` and `SF/` are
  the builtin and fake-bpy-module stubs at `.cache/bpy-stubs-builtin/main/` and `.cache/bpy-stubs/main/`.
- **Recommendation** marks my own design. Everything else is read from source, stubs or recorded test results
  (`T/expected/*/main.txt`, `main.ide.md`, `.cache/typecheck-results/5.2/*/summary.md`). Nothing was built or run.

---

## 1. Answer in short

**Recommendation:**

1. **No new hook.** `blender::on_load` (`R/types/dedicated/blender/member.rs:297-323`, called for every attribute
   load at `R/types/infer/builder.rs:11257`) gets a `preferences` arm **before** its "already bound" early return:
   when the attribute is `preferences`, the receiver is an instance of Blender's `Addon`, and the receiver
   *expression* is `<x>.addons[KEY]` (or a name whose single binding is `<x>.addons.get(KEY)`), and `KEY` names the
   checked add-on, the attribute is an instance of the add-on's preferences class. Otherwise ty's place is kept.
2. **The key is decided by provenance, not by type.** An Extension's `__package__` is `str` (#5,
   `R/types/dedicated/blender/module_dunders.rs:22-24`), and so is any constant holding it, so a `Literal` match
   cannot work. A small **Add-on key evaluator** (new `blender/addon_key.rs`) follows names, imports and
   constants (sharing #26's / `index.rs`'s name resolution) to one of: a module path relative to an add-on root,
   a string literal, or unknown. The key names the add-on when it is the root path `[]` of the accessing file's
   add-on, or, for a Legacy add-on, the literal Add-on name.
3. **Spellings this covers:** `__package__` in the root `__init__.py` or a direct submodule; `__name__` in the root
   `__init__.py` (or a single-file add-on); `__name__.rpartition(".")[0]` in a direct submodule;
   `from .. import __package__` (the dunder is evaluated in the module it is imported from); a module constant
   holding any of these, through `from . import ADDON_ID`; the literal Add-on name of a Legacy add-on.
4. **Which class:** a tracked `addon_preferences(AddonInProgram)` takes the registered classes of #22's walk that
   have `AddonPreferences` among their `bpy_types_bases`, evaluates each one's `bl_idname` with the same key
   evaluator, and picks the **last** registered match: Blender replaces an earlier type with the same idname
   (`BL/source/blender/makesrna/intern/rna_userdef.cc:1465-1487`). None registered: the stub type stays. Walk
   incomplete: every such class in the add-on's files counts, as #22's fallback does for operators.
5. **`blender-preferences-idname`** is reported by #27's per-file query from the same `addon_preferences` result:
   a `bl_idname` that does not evaluate to the add-on (on the assignment), a missing `bl_idname` (on the class
   name), and a later class that replaces an earlier one (on its `bl_idname`). An unknown value is silent.
6. **The unresolved `self.layout.prop(self, "scale")` lines** are a builtin stub gap, not this feature:
   `AddonPreferences` has no `layout` in the builtin stubs (`SB/bpy/types/__init__.pyi:387-393`), while
   fake-bpy-module adds `layout: UILayout` through a mod file. The `ui/panel.py` line is `Panel.layout` being
   `UILayout | None`, which the inheritance feature owns.
7. **Test fixes needed:** the three "through functions" markers rely on return-type inference, which ty leaves
   off by default (`R/../lib.rs:143-150`); `check_prefs_ext.py:18-19` also shadows the function `preferences` with
   its parameter (`call-non-callable`). Builtin's `bpy_prop_collection.get` returns `bpy_struct`, so the `.get`
   marker stays red on builtin until a generator fix.
8. **ID pointers on `AddonPreferences` (#27's question):** `blender-invalid-property`, from #27's
   `property_problems`, with `AddonPreferences` as an owner that forbids data-block properties. This feature adds no
   code for it.

---

## 2. What the tests require

| Add-on | What it pins down | Source |
| --- | --- | --- |
| `prefs_ext` | `addons[__package__]`, `addons[ADDON_ID]` (a root constant), `__name__.rpartition(".")[0]` in `helpers.py`, `from .. import __package__` in `ui/panel.py`; members `scale` / `mode`, a write, a bad write, a missing member; `.get(__package__)` narrowed; other keys (`"other_addon"`, a `str` parameter, the check module's own `__name__`) keep `AddonPreferences \| None` | `F/prefs_ext/check_prefs_ext.py:13-43`, `helpers.py:6-7`, `ui/panel.py:6-20`, `__init__.py:13-28` |
| `prefs_ext` IDE | completion `scale` after `addons[__package__].preferences.sc`; hover on `.preferences` contains `PREFS_EXT_Preferences` | `F/prefs_ext/ide_prefs_ext.py:12-16` |
| `prefs_legacy` | the literal `"prefs_legacy"` and `__package__`; `bl_idname = __name__` in the root; another add-on's literal keeps the stub type | `F/prefs_legacy/check_prefs_legacy.py:12-25`, `__init__.py:16-17` |
| `prefs_bad` | `blender-preferences-idname` on a wrong literal, a missing `bl_idname`, `__name__` in a submodule, a second class for the add-on | `F/prefs_bad/__init__.py:12-35`, `submodule.py:7-8` |
| `prefs_unregistered` | a class that is never registered: the stub type | `F/prefs_unregistered/check_prefs_unregistered.py:10-11` |

The reference stub for the legacy case spells the intended result as a synthesised `Addon` subclass whose
`preferences` is the add-on's class, selected by a `Literal` overload of `Addons.__getitem__`
(`F/prefs_legacy/_expected/stubs/bpy.types.pyi:7-16`). That is the oracle's view; the checker need not build
such a class (section 4.4).

Today every line fails on both generators (`T/expected/builtin/main.txt:8-34`,
`T/expected/fake-bpy-module/main.txt:10-33`), and both IDE markers of `prefs_ext` fail
(`T/expected/*/main.ide.md:6-16`). The recorded messages (`.cache/typecheck-results/5.2/*/summary.md:120-132`) show
three causes besides the missing feature:

- `check_prefs_ext.py:19:17` "Object of type `Preferences` is not callable": the parameter `preferences` of
  `through_functions` shadows the imported function `preferences` (`check_prefs_ext.py:9`, `:18-19`).
- `__init__.py:24:9` (builtin only) "Object of type `Self@draw` has no attribute `layout`".
- `ui/panel.py:16:13` (both) "Attribute `prop` is not defined on `None` in union `UILayout | None`".
- `check_prefs_ext.py:36:21` (builtin only) "Object of type `bpy_struct` has no attribute `preferences`".

---

## 3. What Blender does

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

---

## 4. The hook

### 4.1 Why `on_load` is enough

`infer_attribute_load` calls `blender::on_load(db, env, file, attribute, value_type, member)` for every attribute
load, with the attribute's syntax, the receiver type and ty's place (`R/types/infer/builder.rs:11246-11264`).
Today `on_load` returns ty's place whenever it is definitely bound (`member.rs:305-307`), so it only ever adds
names. `Addon.preferences` is bound in both stubs (`SB/bpy/types/__init__.pyi:385`, a `@property` in
`SF/bpy-stubs/types/__init__.pyi:15948`), so the new arm must run before that return.

**Recommendation:** in `member.rs::on_load`, first:

```rust
if let Some(ty) = super::preferences::addon_preferences_load(db, env, file, attribute, receiver) {
    return Place::bound(ty).into();
}
```

`addon_preferences_load` (new file `blender/preferences.rs`) returns `None` at once unless all of these hold, in
this order, so ordinary attribute loads pay a string comparison:

1. `attribute.attr == "preferences"`;
2. `addon_of_file(db, file)` is some add-on (`blender/addon.rs`);
3. `receiver` is a `NominalInstance` of the `bpy.types` class `Addon` (a new `is_bpy_types_class_named(db, class,
   "Addon")` beside `bpy_types_class_name`, `blender/symbols.rs:41-50`). A union is not taken apart: after
   `if addon is not None` the receiver is `Addon` already;
4. the receiver expression `attribute.value` is an **add-on entry** of a key (4.2), and the key names the file's
   add-on (section 5);
5. `addon_preferences(AddonInProgram)` has a class (section 6).

The result is the class's instance type. Narrowing is then applied by the caller as for any load
(`builder.rs:11265-11267`).

This changes no upstream line, like #23's module arm. It does change `on_load`'s contract from "adds missing
names" to "adds missing names, and specialises `Addon.preferences`"; the doc comment should say so.

### 4.2 Add-on entries

The receiver expression is an add-on entry of `KEY` when it is:

- `<x>.addons[KEY]`, a `Subscript` whose value is an attribute named `addons`;
- `<x>.addons.get(KEY)` or `<x>.addons.get(KEY, default)`, a call;
- a `Name` whose bindings in the nearest scope that has any are all assignments (or a walrus) of one of the two
  forms above with the same key. This covers `F/prefs_ext/check_prefs_ext.py:34-36`
  (`addon = preferences.addons.get(__package__)`, then `addon.preferences` under `is not None`).

The syntax check on `.addons` is safe because the receiver must also be an `Addon` instance (4.1 step 3): only
`Preferences.addons` yields `Addon`s.

The expression's scope comes from `semantic_index(db, file).try_expression_scope_id(...)`, as `file_facts` does
(`blender/index.rs:134-136`). The name's bindings come from `find_symbol_in_scope`, as `resolve_name` does
(`index.rs:262-279`).

### 4.3 What it does not cover

- `addon = preferences.addons[KEY]` passed into a function typed `Addon`, then `.preferences` there: the
  parameter has no key. Rare; the stub type stays.
- On **builtin**, `bpy_prop_collection.get` returns `bpy_struct` (`SB/bpy/types/__init__.pyi:148-152`), and
  `Addons` derives from the bare `bpy_prop_collection` (`:395`). So `addon` is `bpy_struct`, and
  `addon.preferences` fails before the arm can apply (step 3). This is a generator fix: `Addons(bpy_prop_collection[Addon])`
  and `get(...) -> _T | Any` (fake-bpy-module already has a generic `get`, `SF/bpy-stubs/types/__init__.pyi:3724-3726`).
  Until then `check_prefs_ext.py:36` stays red on builtin.

### 4.4 Alternatives not taken

- **A key `Literal` on the subscript's type.** Works for Legacy add-ons (`__package__` is
  `Literal["prefs_legacy"]`, `module_dunders.rs:28-39`), not for Extensions, whose `__package__` and every constant
  holding it are `str`. Typing an Extension's `__package__` more precisely was rejected in #5 (the repository is
  unknown).
- **A specialised `Addon` type from the subscript and the `.get` call** (an intersection `Addon & <protocol with
  preferences: C>`, or a synthesised class as in the reference stub). It would carry the key through parameters
  and make `addons[KEY]` itself display the class. But it needs new hooks in subscript and call inference, two
  upstream lines on hot paths, and a synthesised class has no anchor (#23 note, section 4.3). The `on_load` arm
  covers every marker, so this stays the fallback if the build finds a gap.
- **Rewriting `Addons.__getitem__` per add-on.** Member lookups are cached per class, so an add-on-specific
  overload would leak between add-ons (`index.rs:13-15`).

---

## 5. The Add-on key evaluator

### 5.1 Values

**Recommendation:** `blender/addon_key.rs`:

```rust
enum KeyValue {
    /// A module name, as a path below an add-on root: `[]` is the root package itself,
    /// `["helpers"]` is `<root>.helpers`. The add-on is part of the value.
    Module { addon: Addon, path: Box<[Name]> },
    /// A string literal.
    Literal(Box<str>),
    /// Anything else: a parameter, `os.environ[...]`, a call.
    Unknown,
}
```

A key **names** add-on `A` when it is `Module { addon: A, path: [] }`, or `Literal(s)` with `A` a Legacy (package
or single-file) add-on and `s == A.name`. An Extension's name is never a literal: its key is
`bl_ext.<repository>.<id>`.

### 5.2 Rules

For an expression in a scope of file `f`, with `p(f)` the path of `f` below its add-on root (the module path
`module_dunders.rs:29-37` already computes; `__init__.py` is its package's path):

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
  ADDON_ID` in `check_prefs_ext.py` gives the root's `__package__`; `from .. import __package__ as base_package`
  in `ui/panel.py` gives `__package__` of the root module (`F/prefs_ext/ui/panel.py:6`), `[]`. A bare `__package__`
  in `ui/panel.py` would be `["ui"]` and does **not** name the add-on: the README's "`__package__` (any module of
  the add-on)" only holds for the root and its direct submodules.
- `from .. import __package__`: the root module binds no `__package__`, so ty's definition resolution finds no
  definition for it. The evaluator special-cases an `import from` of an implicit module dunder (the names
  `place.rs:2530` answers) by evaluating the dunder in the source module.
- Files outside every add-on (a shared library) give `Module` values of no add-on, so they never name one.
- Name following, imports, re-exports and the alias depth limit are those of `resolve_expression`
  (`index.rs:226-407`). **Recommendation:** share them with #26's evaluator rather than adding a third walker:
  #26 already plans tracked per-definition evaluation with `cycle_initial`, which this evaluator needs too
  (`key_of_definition(Definition) -> KeyValue`, tracked, `cycle_initial` `Unknown`).
- It never infers add-on code, so it is safe to call from `on_load` and from the index.

Not covered, and not in the tests: `__name__.split(".")[0]` / `.partition(".")[0]` (the top package; right for a
Legacy add-on only, `bl_ext` for an Extension), `__package__.rpartition(".")[0]` in a nested module (falls out of
the `rpartition` rule anyway), `os.path.basename(os.path.dirname(__file__))`, f-strings. They can be added as rows.

### 5.3 The markers, evaluated

| Line | Key value | Names the add-on? |
| --- | --- | --- |
| `check_prefs_ext.py:14` `__package__` | `Module([])` | yes |
| `:15` `ADDON_ID` → root `__package__` | `Module([])` | yes |
| `helpers.py:7` `__name__.rpartition(".")[0]` | `["helpers"]` → `[]` | yes |
| `ui/panel.py:20` `base_package` → root `__package__` | `Module([])` | yes |
| `:40` `"other_addon"` (Extension) | `Literal` | no |
| `:41` `name: str` | `Unknown` | no |
| `:43` `__name__` in `check_prefs_ext.py` | `Module(["check_prefs_ext"])` | no |
| `check_prefs_legacy.py:13` `"prefs_legacy"` | `Literal`, Legacy add-on of that name | yes |
| `:21` `__package__` | `Module([])` | yes |
| `:25` `"prefs_ext"` | `Literal`, not this add-on's name | no |
| `prefs_unregistered` `__package__` | `Module([])` | yes, but no registered class (section 6) |

---

## 6. Which class, and `blender-preferences-idname`

### 6.1 The query

**Recommendation:** in `blender/preferences.rs`,

```rust
#[salsa::tracked(returns(ref), cycle_initial = ..., heap_size = ...)]
fn addon_preferences<'db>(db, key: AddonInProgram<'db>) -> Preferences<'db>;

struct Preferences<'db> {
    /// The class `addons[<this add-on>].preferences` is: the last registered match.
    class: Option<StaticClassLiteral<'db>>,
    /// Problems for `blender-preferences-idname`, each with its class and range.
    problems: Box<[PreferencesProblem<'db>]>,
}
```

1. **Candidates:** #22's `registered_classes` (registration order) that have `AddonPreferences` among their
   `bpy_types_bases` (`blender/symbols.rs:54-64`). When the walk is incomplete, every such class in the add-on's
   files (the per-file class list #22 adds to `file_facts` for the same fallback), minus classes that another
   candidate derives from.
2. **Idname:** the first class in the MRO whose body binds `bl_idname` (as #22 reads operator idnames, its section
   5.3); its class-body assignment's value is evaluated by the key evaluator in the class body scope. No binding
   at all, or only the stub's `bl_idname: str` declaration, is *missing*.
3. **Class:** the last candidate, in registration order, whose idname names the add-on. Blender's replacement rule
   makes the last one effective (section 3). In the fallback the order is the file walk's, which is a guess; with
   one match per add-on (the normal case) it does not matter.
4. **Problems:**
   - idname evaluates to something that does not name the add-on (`Literal` or `Module` of another path) → on the
     `bl_idname` assignment's value;
   - missing → on the class name;
   - a match after an earlier match (complete walk only, since order is needed) → on the later class's
     `bl_idname`. Its message says the class replaces the earlier one and that unregistering the earlier fails.
   - `Unknown` → nothing: the checker cannot tell.

This yields exactly the four markers of `F/prefs_bad`: `PREFS_BAD_Wrong` (`__init__.py:13`), `PREFS_BAD_Missing`
(`:18`), `PREFS_BAD_Second` (`:29`), `PREFS_BAD_Submodule` (`submodule.py:8`, `Module(["submodule"])`), while
`PREFS_BAD_First` stays clean. The resolved class of `prefs_bad` is `PREFS_BAD_Second`, the last match, as at
runtime.
`prefs_unregistered` has no registered candidate, so its `addons[__package__].preferences` keeps the stub type;
the `blender-unregistered-class` marker there belongs to registration_checks.

### 6.2 Reporting

`blender-preferences-idname` is declared with `declare_lint!` beside the existing lints
(`R/types/dedicated/blender/lints.rs:21-42`), documented under `resources/lint_docs/`, and registered in
`register_lints`. It is reported by #27's generalised per-file query (today `addon_diagnostics`,
`lints.rs:46-70`, merged at `R/types.rs:261`): for the file being checked, the `problems` whose class is defined in
that file. `# ty: ignore[blender-preferences-idname]` then works on the marked lines, as #6 / #27 describe. No new
upstream line.

### 6.3 Cost and cycles

`addon_preferences` reads the walk (no inference), `bpy_types_bases` of the candidates (class headers) and the
key evaluator (definitions only). `on_load` calls it only after the four cheap checks of 4.1 pass, so only
`.preferences` loads on an `Addon` in add-on code pay for it, once per add-on. A cycle (the walk inferring a class
header that reads `.preferences`) cannot happen in a header; `cycle_initial` returns no class as a safety net.

---

## 7. The other red lines

### 7.1 `self.layout.prop(self, "scale")` (builtin, `prefs_ext/__init__.py:24`, `prefs_legacy/__init__.py:24`)

`AddonPreferences` in the builtin stubs has only `bl_idname` and the `bl_*` helpers
(`SB/bpy/types/__init__.pyi:387-393`). fake-bpy-module adds `layout: UILayout` through
`fake-bpy-module/src/mods/common/analyzer/append/bpy.types.mod.rst:5-9`, and the line passes there. Neither the RST
docs nor RNA have `layout` (`.cache/bpy-rst/main/sphinx-in/bpy.types.AddonPreferences.rst`; section 3). So this is
a **builtin generator fix**: Blender's `doc/python_api/sphinx_stub_gen.py` (run by `scripts/generate_stubs.py:247`)
should declare `layout: UILayout` on `AddonPreferences`, as fake-bpy-module does. Nothing in the checker.

### 7.2 `self.layout.prop(preferences(context.preferences), "scale")` (both, `prefs_ext/ui/panel.py:16`)

The error is `Panel.layout` being `UILayout | None` in both stubs (`SB/bpy/types/__init__.pyi:19388`,
`SF/bpy-stubs/types/__init__.pyi:86711`). Typing `self.layout` as `UILayout` inside `Panel.draw` is the
inheritance feature's (`T/features/inheritance/inh_overrides/__init__.py:100-102`), outside this map. The line
stays red with that reason.

### 7.3 The "through functions" markers (`check_prefs_ext.py:18-21`)

`helpers.preferences`, `panel.preferences` and the root's `preferences` have no return annotation. ty infers a
call's return type from the body only with `analysis.return-type-inference = "always"`; the default is `never`
(`R/../lib.rs:138-150`, `R/types/function.rs:1734-1759`), and `T/ty.toml` does not set it. So these three markers
cannot pass whatever the feature does. Two options:

- **Recommendation:** annotate the three helpers with `-> PREFS_EXT_Preferences` (imported under `TYPE_CHECKING`
  to avoid the import cycle). The test then checks the feature directly: without it, each `return` is an
  `invalid-return-type`; the `assert_type`s in `check_prefs_ext.py` pass by the annotation, as the reference stub
  already says (`F/prefs_ext/_expected/addon/__init__.pyi:17`). This is also how real add-ons write such helpers.
- Or set `[analysis] return-type-inference = "always"` in `T/ty.toml`. That changes every feature's results and
  tests a setting users do not have by default.

Either way, rename the parameter of `through_functions` (`check_prefs_ext.py:18`): it shadows the imported function
`preferences`, which is the `call-non-callable`.

### 7.4 Summary of the expected `check:features` effect

With the design and the test fixes above, every `addon_preferences` line passes on fake-bpy-module except
`ui/panel.py:16` (inheritance). On builtin, additionally `check_prefs_ext.py:36` (`get` returns `bpy_struct`) and the
two `self.layout` lines in `__init__.py` wait for generator fixes. Both IDE markers follow from the type: hover
reads the attribute's type, and completion lists the class's annotated members.

---

## 8. ID pointers on `AddonPreferences` (#27's question)

Blender refuses a `PointerProperty` / `CollectionProperty` whose type contains data-blocks on a struct that forbids
data-block ID properties, with a `ValueError` at `register_class`
(`BL/source/blender/python/intern/bpy_rna.cc:9483-9501`; `RNA_struct_idprops_datablock_allowed`,
`BL/source/blender/makesrna/intern/rna_access.cc:803-811`). `AddonPreferences` is such a struct
(`STRUCT_NO_DATABLOCK_IDPROPERTIES`, `rna_userdef.cc:4965`).

**Recommendation: `blender-invalid-property`.** It is a property-declaration error like the others #27 lists
(Blender rejects the declaration at registration), it is decided from the declaration and its owner kind, and #27's
`property_problems(db, scope, owner_kind, call, ...)` already takes the owner for exactly this check. The
addon_preferences feature only resolves the preferences class; it has no reason to inspect property declarations.
To keep one diagnostic per line, `property_problems` returns one `DataBlockPointer` problem and the reporter picks
the rule by owner: `Operator` / `Macro` → `blender-invalid-operator-property` (#23, which also needs the truncation
of the operator signature), any other owner (`AddonPreferences`, the registered targets #27 lists) →
`blender-invalid-property`. No marker covers the `AddonPreferences` case yet; it belongs in the properties feature
(`props_defaults` or `props_hosts`), with `check:load` confirming the failure.

---

## 9. Files touched (for the build ticket)

| File | Change |
| --- | --- |
| `blender/preferences.rs` (new) | `addon_preferences_load` (the `on_load` arm), add-on entries, `addon_preferences` query, problems |
| `blender/addon_key.rs` (new) | the key evaluator; shares name resolution with #26's evaluator / `index.rs` |
| `blender/member.rs` | one call at the top of `on_load`, and its doc comment |
| `blender/symbols.rs` | recognise the `bpy.types` class `Addon` |
| `blender/lints.rs` (#27's per-file query) | `blender-preferences-idname`: declare, register, report |
| upstream files | none |
| tests | annotate the three helpers (or enable return-type inference), rename the shadowing parameter; README: `__package__` names the add-on in the root and direct submodules, and `.get(key)`'s result keeps the stub type while its `.preferences` is the class |
| stub generators | builtin: `layout: UILayout` on `AddonPreferences`; `Addons` generic over `Addon` with a `get` that returns it |

---

## 10. Open points

- **README wording.** "`.get(key)` gives the specialised `Addon | None`": with the `on_load` arm, `addon` itself
  stays `Addon | None`; only its `.preferences` is the class. No marker asserts on `addon`. If a marker should, the
  specialised-type alternative (4.4) is needed.
- **Fallback order.** With an incomplete walk and two matching classes, which one wins is a guess (file-walk
  order). The "second class" problem is only reported on a complete walk.
- **Shared libraries** that define the preferences class with a `bl_idname` passed in from the add-on
  (`bl_idname = name` in a factory) give `Unknown`: no class, no diagnostic.
- **To verify at build:** that ty's definition resolution really finds nothing for `from .. import __package__`
  (so the special case is reached) rather than a synthetic binding; that `on_load`'s replaced place keeps hover and
  completion on `.preferences` as expected.
