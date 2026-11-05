# Where `__package__` is typed per add-on

Research note, 2026-11-05, for [#5](https://github.com/taway1450/blender-extension-developer-suite/issues/5)
(map [#1](https://github.com/taway1450/blender-extension-developer-suite/issues/1); the scope and crate split
in [#2](https://github.com/taway1450/blender-extension-developer-suite/issues/2) are taken as given).

The questions were:

- where ty infers the module-level `__package__`;
- the smallest hook that types it per add-on from the add-on-of-file query;
- the expected type in each case;
- whether `__name__` gets the same treatment;
- what `bl_idname = __package__` and `addons[__package__]` see afterwards.

Conventions:

- Every fact has a `path:line` source.
  - `ruff-blender/` is short for `ty-blender/ruff-blender/crates/`.
  - `blender/` is the Blender source checkout.
  - `features/` is `tests/typecheck/features/`.
  - `stubs-builtin/` is `.cache/bpy-stubs-builtin/main/`, and `stubs-fake/` is `.cache/bpy-stubs/main/`.
- My own recommendations are marked **Recommendation**.
- *Verified locally* means the output came from running a tool on 2026-11-05 on throwaway files in a temp
  directory:
  - `ty-blender/ruff-blender/target/release/ty.exe`, `ty 0.0.97 (368c78c30 2026-11-04)`;
  - Blender's bundled Python 3.13.13 (`.cache/blender-bin/main/5.4/python/bin/python.exe`).

---

## 1. Answer

| Case | Runtime value in Blender | Type (**Recommendation**) | Marker |
| --- | --- | --- | --- |
| legacy add-on, `__init__.py` | `"disc_legacy"` | `Literal["disc_legacy"]` | none in `__init__.py`; see the next row |
| legacy add-on, direct submodule | `"disc_legacy"` | `Literal["disc_legacy"]` | `features/addon_discovery/disc_legacy/check_disc_legacy.py:11`, `features/addon_preferences/prefs_legacy/check_prefs_legacy.py:21` |
| legacy add-on, module in sub-package `sub/` | `"disc_legacy.sub"` | `Literal["disc_legacy.sub"]` | none yet |
| single-file add-on | `""` | `Literal[""]` | `features/addon_discovery/disc_single.py:29` |
| extension, any module | `"bl_ext.<repo>.<id>"` or `"bl_ext.<repo>.<id>.sub"` | `str` | `disc_extension/check_disc_extension.py:11`, `disc_extension/sub/check_disc_extension_sub.py:9`, `disc_both/check_disc_both.py:11`, `disc_override/src/disc_override_addon/check_disc_override.py:11` |
| file outside any add-on | whatever Python gives | `str \| None`, ty's type, unchanged | none |

- **Where ty infers it.** ty has no per-file logic for `__package__`. A global name that a module does not bind
  falls back to `module_type_implicit_global_symbol` (`ruff-blender/ty_python_semantic/src/place.rs:2500-2581`).
  That function special-cases `__file__`, `__doc__`, `__builtins__` and a few more. Any other name, `__package__`
  included, is looked up as an attribute of `types.ModuleType`, whose typeshed declaration is `str | None`.
  The same name seen from another module (`from .. import __package__`, `pkg.__package__`) goes through a
  second fallback, in `imported_symbol` (`place.rs:579-605`).
- **Smallest hook (Recommendation).** Add one match arm to each of these two fallbacks. The arm calls a new
  tracked function `blender::module_dunder_type(db, file, name)` in `types/dedicated/blender/`. When it returns
  `None`, ty's own lookup runs unchanged (section 3).
- **`__name__` (Recommendation).** Use the same hook and the same rule:
  - `Literal["<addon>"]` or `Literal["<addon>.<mod>"]` in a legacy add-on;
  - the file stem in a single-file add-on;
  - `str` (unchanged) in an extension.

  One hazard follows from this: an `if __name__ == "__main__":` block in a legacy add-on becomes unreachable
  (section 4).
- **The consumers.** `bl_idname = __package__` stops reporting `invalid-assignment`, and so does
  `addons[__package__]` (`invalid-argument-type`). Both become `str` or a `Literal`. The result of
  `addons[__package__].preferences` stays the stub type `AddonPreferences | None`. Specialising it to the
  add-on's own class is addon_preferences work, which the map leaves out of scope. For an extension, the type
  `str` cannot carry "this is the add-on's key" (section 5).

## 2. What Blender and Python set at runtime

- **Blender imports an add-on by its module name.** `addon_utils.enable` calls
  `importlib.import_module(module_name)` (`blender/scripts/modules/addon_utils.py:462-464`).
- **Legacy add-ons and single-file add-ons are top-level modules.**
  - The `addons_core` and `addons` script directories are listed with an empty package prefix
    (`addon_utils.py:113`; the comment at `addon_utils.py:103-104` explains it).
  - Module names come from `bpy.path.module_names` (`blender/scripts/modules/bpy/path.py:368-407`):
    - a `.py` file gives its stem (`path.py:391-393`);
    - a directory with an `__init__.py` gives the directory name (`path.py:394-399`).
  - So the name of a legacy add-on is its folder name or its file stem. It is not the dotted name that ty's
    module resolver derives from the first-party roots. Example: `disc_workspace/addons/ws_alpha` sits under
    the root `features/addon_discovery` (`tests/typecheck/ty.toml:9`). The name of the add-on is the
    question of [#3](https://github.com/taway1450/blender-extension-developer-suite/issues/3).
- **Extensions are sub-modules of `bl_ext.<repo>`.**
  - Each enabled repository is listed with the package `bl_ext.<repo.module>` (`addon_utils.py:122`, and
    `_ext_base_pkg_idname = "bl_ext"` at `addon_utils.py:1449`).
  - An extension is therefore `bl_ext.<repo>.<id>` (`addon_utils.py:106-111`).
  - Blender itself calls that name the extension's `__package__`, and rejects a name without 3 parts
    (`_extension_module_name_decompose`, `addon_utils.py:1453-1472`).
  - `<repo>` comes from the user's preferences (`_preferences.extensions.repos`, `addon_utils.py:114-122`),
    so the checker cannot know it.
- **Python sets `__package__` from the module's place in the package.**
  - *Verified locally:* importing a tree laid out like Blender's printed:

    | Module | `__name__` | `__package__` |
    | --- | --- | --- |
    | `legacy/__init__.py` | `'legacy'` | `'legacy'` |
    | `legacy/mod.py` | `'legacy.mod'` | `'legacy'` |
    | `legacy/sub/__init__.py` | `'legacy.sub'` | `'legacy.sub'` |
    | `legacy/sub/m.py` | `'legacy.sub.m'` | `'legacy.sub'` |
    | `single.py` | `'single'` | `''` |
    | `bl_ext/repo/ext/__init__.py` | `'bl_ext.repo.ext'` | `'bl_ext.repo.ext'` |
    | `bl_ext/repo/ext/mod.py` | `'bl_ext.repo.ext.mod'` | `'bl_ext.repo.ext'` |
    | `bl_ext/repo/ext/sub/m.py` | `'bl_ext.repo.ext.sub.m'` | `'bl_ext.repo.ext.sub'` |

  - So `__package__` names the add-on only in its `__init__.py` and in its direct submodules. In a sub-package
    it is longer. That is why `prefs_ext/ui/panel.py:6` imports the name with `from .. import __package__`.
- **The add-on's key in `preferences.addons` is the same module name.**
  - `Addon.module` is the module path that was imported (`addon_utils.py:110-111`).
  - Blender's own add-ons use the idioms that the markers test:
    - `bl_idname = __package__` (`blender/scripts/addons_core/io_scene_gltf2/__init__.py:2285`,
      `addons_core/node_wrangler/preferences.py:73`);
    - `bl_idname = __name__` in `__init__.py` (`addons_core/rigify/__init__.py:200`);
    - `__name__.split(".")[0]` in a submodule (`addons_core/ui_translate/settings.py:100`).
- **The harness does not load extensions like Blender does.** `check:load` puts the feature folder on
  `sys.path` and imports each add-on as a top-level module (`scripts/blender/load_feature_addons.py:55-59`).
  An extension's `__package__` at load time is therefore `"<id>"`, not `"bl_ext.<repo>.<id>"`. The `str`
  markers cannot be checked by a runtime probe in that harness. They follow from Blender's loader above.

## 3. Where ty types it, and the hook

### 3.1 ty today

- **Inside the module (bare name `__package__`).**
  - A name the module never binds resolves through
    `ImplicitPlaceLoad::ModuleImplicitGlobal { file, name }`, which calls
    `module_type_implicit_global_symbol(db, file, &name)` (`ruff-blender/ty_python_semantic/src/types/infer/builder.rs:10943-10945`).
  - That function matches on the name (`place.rs:2506-2580`):
    - `__file__` is `str` (`place.rs:2510`);
    - `__doc__` is `str` when the module has a docstring (`place.rs:2515-2520`);
    - everything else is a member lookup on `ModuleType` (`place.rs:2564-2579`).
  - The function receives the `ProgramFile`, so a per-file answer fits there without a new parameter.
  - ty's own test pins the result: `reveal_type(__package__)  # revealed: str | None`
    (`ruff-blender/ty_python_semantic/resources/mdtest/scopes/moduletype_attrs.md:14`).
- **From another module.**
  - `pkg.__package__` and `from pkg import __package__` go through `ModuleLiteralType::static_member`
    (`ruff-blender/ty_python_semantic/src/types.rs:12556-12591`), which calls
    `imported_symbol(db, env, file, name, None)`.
  - Its fallback special-cases `__file__` and `__builtins__`, and sends the rest to `ModuleType`
    (`place.rs:579-605`). `file` is the imported module's `ProgramFile`, or `None` for a namespace package.
- **Completions** list the implicit globals through `all_implicit_module_globals`, which calls
  `module_type_implicit_global_symbol` for each name (`place.rs:2650-2671`). They follow the first hook for free.
- **Hover** shows the inferred type of the name, so it follows too.
- **Assignments to the name.**
  - An explicit `__package__ = ...` or `__package__: T = ...` in the module is checked against the typeshed
    *declaration* (`module_type_implicit_global_declaration`, `place.rs:2460-2484`, used at
    `builder.rs:1645-1647`), so the hook does not change it.
  - A declaration with an annotation is also checked against `module_type_implicit_global_symbol`
    (`builder.rs:1896-1919`). See section 4.
- *Verified locally* with stock ty, on an `myaddon/__init__.py` and `myaddon/sub/mod.py` pair:
  - `__package__` is `str | None`;
  - `from .. import __package__` is `str | None`;
  - `myaddon.__package__` is `str | None`;
  - `__name__` is `str`;
  - `from .. import __name__` is `str`;
  - after `__package__ = "x"` the name is `Literal["x"]`, also inside a function. An explicit binding wins
    over the implicit global, so the hook never overrides user code.

### 3.2 The hook (Recommendation)

- **New code**, in `ty_python_semantic/src/types/dedicated/blender/module_dunders.rs`:

  ```rust
  /// The type of `__package__` / `__name__` in `file` when `file` is a module of a discovered add-on,
  /// or `None` to keep ty's own type.
  #[salsa::tracked]
  pub(crate) fn module_dunder_type<'db>(db: &'db dyn Db, file: ProgramFile<'db>, name: DunderName) -> Option<Type<'db>>
  ```

  - It calls the add-on-of-file query from `ty_blender` (question [#3](https://github.com/taway1450/blender-extension-developer-suite/issues/3)).
    It needs three things from it: the add-on's **kind** (extension, legacy package, single-file), its **root**
    (folder or file) and its **name**. For a legacy add-on, the name is the folder name or file stem.
  - It returns `None` when the file is in no add-on, or when it is not a `.py` file.
  - For an **extension** it returns `str` (`KnownClass::Str.to_instance`, as `__file__` does at `place.rs:2510`).
  - For a **single-file** add-on:
    - `__package__` is `Literal[""]`;
    - `__name__` is `Literal["<stem>"]`.
  - For a **legacy package**, let `parts` be the folders from the root down to the file's folder, the root
    included:
    - `__package__` is `Literal[".".join(parts)]`;
    - `__name__` is the same in an `__init__.py`, and `Literal["<package>.<stem>"]` in any other module.

    `Type::string_literal` builds the literal (`ruff-blender/ty_python_semantic/src/types.rs:3385`).
  - It works from the add-on root and the file's path, not from `file_to_module`. ty's module name depends on
    the configured roots (`ruff-blender/ty_module_resolver/src/resolve.rs:340-352`), and for an add-on below a
    root it is not the name Blender imports (section 2).
- **Hook 1 (inside the module).** Add one arm before the catch-all in `module_type_implicit_global_symbol`
  (`place.rs:2564`):

  ```rust
  "__package__" | "__name__" if let Some(ty) = blender::module_dunder_type(db, file, name.into()) => Place::bound(ty).into(),
  ```

- **Hook 2 (from another module).** Add the same arm in `imported_symbol`'s fallback (`place.rs:580`), with a
  guard on `file` being `Some`.
- **Why not elsewhere.**
  - `module_type_implicit_global_declaration` must stay typeshed's `str | None` declaration. Otherwise
    `__package__ = None`, which is legal Python, would start to error.
  - The two fallbacks are the only places where ty answers "what is this module's implicit `X`". Each gets one
    line. That fits the standing preference for one-line hooks in existing ty files (map #1).
- **Cost.** `module_type_implicit_global_symbol` is on the hot path of name resolution (`place.rs:2559-2563`).
  The hook adds a string match on the name before any query. The add-on lookup runs only for
  `__package__` / `__name__` reads, and is cached per file and name.

## 4. `__name__`

- **Runtime.**
  - In a legacy add-on, `__name__` is the add-on name in `__init__.py` and the dotted module path elsewhere.
  - In a single-file add-on it is the stem.
  - In an extension it starts with `bl_ext.<repo>.`.
  - (Section 2 table.)
- **ty today:** `str` everywhere (`moduletype_attrs.md:10`; *verified locally*).
- **Markers that depend on it:**
  - `bl_idname = __name__` in a legacy `__init__.py` (`features/addon_preferences/prefs_legacy/__init__.py:17`);
  - `__name__` in a submodule as a wrong key (`features/addon_preferences/prefs_bad/submodule.py:8`);
  - `__name__.rpartition(".")[0]` in an extension submodule (`features/addon_preferences/prefs_ext/helpers.py:7`);
  - `addons[__name__]` in an extension's check module keeps the stub type
    (`features/addon_preferences/prefs_ext/check_prefs_ext.py:43`).

  None of them is an `assert_type` on `__name__` itself. All of them are addon_preferences work.
- **Recommendation: type `__name__` with the same hook, now.**
  - It costs one more name in the same arm.
  - It gives addon_preferences a literal key for legacy add-ons for free.
  - Its precision matches `__package__`'s, so the two stay consistent.
- **Hazard.** A `Literal` `__name__` makes `if __name__ == "__main__":` statically false.
  - *Verified locally:* with `n: Literal["legacy"]`, the body of `if n == "__main__":` is unreachable:
    `reveal_type(n)` gives `Never`, and `1 + "x"` in it is not reported.
  - Blender's own add-on template ends with exactly that guard
    (`blender/scripts/templates_py/addon_add_object.py:83-84`), so it is common in single-file add-ons.
  - Inside Blender, as an add-on, the block really never runs, so the type is faithful. The same file run from
    the Text Editor has `__name__ == "__main__"`.
  - **Recommendation:** accept it. It matches Blender's add-on loading, which is the premise of the
    add-on-scoped behaviour. Add a marker so the choice is visible, for example a `disc_single`-style
    `assert_type(__name__, Literal["disc_single"])`. Revisit if users report it.
- **Annotated redeclaration.**
  - `__name__: str = ...` in a legacy add-on would report `invalid-declaration`, because `str` is not
    assignable to the literal (`builder.rs:1912-1919`).
  - The same already happens with ty's `str` for `__file__` and a `str | None` annotation, so it is an
    accepted kind of edge.
  - **Recommendation:** no special case.

## 5. What the consumers see

- **`bl_idname = __package__`.**
  - Both stubs declare `AddonPreferences.bl_idname: str` (`stubs-builtin/bpy/types/__init__.pyi:387,393`;
    `stubs-fake/bpy-stubs/types/__init__.pyi:15979-15980`).
  - Today `str | None` is reported as `invalid-assignment` (`tests/typecheck/expected/builtin/main.txt:67,74`).
  - After the hook, `str` or a `Literal` is assignable, so the error goes away. In
    `prefs_bad/__init__.py:29` the `invalid-assignment` goes too, and only the deferred
    `blender-preferences-idname` remains.
- **`addons[__package__]`.**
  - The key parameter is `str` in the builtin stubs (`stubs-builtin/bpy/types/__init__.pyi:395,404-409`), and
    `int | str | tuple[str, ...]` on `bpy_prop_collection`, which `Addons` subclasses, in fake-bpy-module
    (`stubs-fake/bpy-stubs/types/__init__.pyi:3673,3761,4332`).
  - Today `str | None` is reported as `invalid-argument-type` (`expected/builtin/main.txt:79-80`).
  - After the hook the call type-checks and gives `Addon`, so `.preferences` is the stub's
    `AddonPreferences | None`.
  - The `assert_type(..., PREFS_EXT_Preferences)` markers keep failing. They need the addon_preferences
    feature, which is out of scope for this map (#1, "Out of scope").
- **What the type can and cannot carry for later.**
  - For a legacy add-on, `Literal["prefs_legacy"]` *is* the key. A later addon_preferences lookup can compare
    literals, the same rule as the literal key in `check_prefs_legacy.py:13`.
  - For an extension the type is `str`. It is the same type for:
    - `__package__` in `__init__.py`, which is the key;
    - `__package__` in `ui/panel.py`, which is not (`bl_ext.<repo>.prefs_ext.ui`);
    - any other string.

    `assert_type(__package__, str)` pins it to exactly `str`, so no hidden marker type can tell them apart.
  - **Recommendation:** when addon_preferences is planned, recognise extension keys from the key
    *expression*, not from its type. Two ways:
    - through the definition chain: implicit global `__package__` in a module directly in the add-on root, a
      constant bound to it, an `import`-from of it, `__name__.rpartition(".")[0]`;
    - with a tracked "add-on key" provenance beside the type.

    Nothing in this ticket blocks either.

## 6. Conflicts and gaps in the tests

- **The IDE marker contradicts the type marker.**
  - `features/addon_preferences/prefs_ext/ide_prefs_ext.py:20-21` expects the hover on `__package__` to contain
    `"prefs_ext"`.
  - `prefs_ext` is an extension (`features/addon_preferences/prefs_ext/blender_manifest.toml` exists), so its
    `__package__` is `str`, as `disc_extension` asserts. ty's hover shows the type, so it will show `str`.
    It currently records `FAIL: does not contain "prefs_ext"` (`expected/builtin/main.ide.md:18-22`).
  - This needs a decision:
    - change the marker to `^hover-contains "str"`;
    - or move it to a legacy add-on;
    - or let hover say which add-on, which belongs with the map's open "IDE presentation" item.

  **Recommendation:** move it to `prefs_legacy`, where the hover would show `Literal["prefs_legacy"]`.
- **Missing markers (Recommendation):**
  - `__package__` in a sub-package of a legacy add-on (`Literal["<addon>.sub"]`);
  - `__package__` and `__name__` read through `from .. import` in a legacy add-on, which covers hook 2;
  - `__name__` in each kind of add-on;
  - a file outside any add-on that keeps `str | None`, as a `bare-ok` guard.
- **The workspace case.** `disc_workspace/addons/ws_alpha` and `ws_beta` are extensions
  (`blender_manifest.toml` in each), so their type is `str` whatever ty's module path says. A *legacy* add-on
  below a root is the case where computing from `file_to_module` would give the wrong literal
  (`disc_workspace.addons.x`). No marker covers it yet.
