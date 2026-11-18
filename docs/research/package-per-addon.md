# Where `__package__` is typed per add-on

Research note, 2026-11-05, for [#5](https://github.com/taway1450/blender-extension-developer-suite/issues/5)
(map #1). Trimmed on 2026-11-18 to the rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings.

The questions were where ty infers the module-level `__package__`, the type it should get per add-on, whether
`__name__` gets the same treatment, and what `bl_idname = __package__` and `addons[__package__]` see afterwards.

Conventions:

- Every fact has a `path:line` source. `ruff-blender/` is short for `ty-blender/ruff-blender/crates/`, and
  `blender/` is the Blender source checkout (`main`, read on 2026-11-05).
- *Verified locally* means the output came from running a tool on 2026-11-05 on throwaway files: a stock ty build
  (`ty 0.0.97`) or Blender's bundled Python 3.13.13.

What main does: `__package__` is typed per add-on (`package_type` in
`ruff-blender/ty_python_semantic/src/types/dedicated/blender/module_dunders.rs`):

| Case | Runtime value in Blender | Type |
| --- | --- | --- |
| legacy add-on, `__init__.py` or direct submodule | `"disc_legacy"` | `Literal["disc_legacy"]` |
| legacy add-on, module in sub-package `sub/` | `"disc_legacy.sub"` | `Literal["disc_legacy.sub"]` |
| single-file add-on | `""` | `Literal[""]` |
| extension, any module | `"bl_ext.<repo>.<id>"` or `"bl_ext.<repo>.<id>.sub"` | `str` |
| file outside any add-on | whatever Python gives | `str \| None`, ty's type, unchanged |

The original also recommended typing `__name__` the same way. Main does not: `__name__` keeps ty's `str`
(section 3 has the hazard that argues against it).

---

## 1. What Blender and Python set at runtime

- **Blender imports an add-on by its module name.** `addon_utils.enable` calls
  `importlib.import_module(module_name)` (`blender/scripts/modules/addon_utils.py:462-464`).
- **Legacy add-ons and single-file add-ons are top-level modules.**
  - The `addons_core` and `addons` script directories are listed with an empty package prefix
    (`addon_utils.py:113`; the comment at `addon_utils.py:103-104` explains it).
  - Module names come from `bpy.path.module_names` (`blender/scripts/modules/bpy/path.py:368-407`):
    - a `.py` file gives its stem (`path.py:391-393`);
    - a directory with an `__init__.py` gives the directory name (`path.py:394-399`).
  - So the name of a legacy add-on is its folder name or its file stem. It is not the dotted name that ty's
    module resolver derives from the first-party roots: for an add-on below a root, ty's module name
    (`ruff-blender/ty_module_resolver/src/resolve.rs:340-352`) is not the name Blender imports. So the type is
    computed from the add-on root and the file's path, not from `file_to_module`. The name of the add-on is the
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
    it is longer. That is why add-ons import the name with `from .. import __package__` in a sub-package.
- **The add-on's key in `preferences.addons` is the same module name.**
  - `Addon.module` is the module path that was imported (`addon_utils.py:110-111`).
  - Blender's own add-ons use these idioms:
    - `bl_idname = __package__` (`blender/scripts/addons_core/io_scene_gltf2/__init__.py:2285`,
      `addons_core/node_wrangler/preferences.py:73`);
    - `bl_idname = __name__` in `__init__.py` (`addons_core/rigify/__init__.py:200`);
    - `__name__.split(".")[0]` in a submodule (`addons_core/ui_translate/settings.py:100`).
- **The `check:load` harness does not load extensions like Blender does.** It puts the feature folder on
  `sys.path` and imports each add-on as a top-level module (`scripts/blender/load_feature_addons.py:55-59`).
  An extension's `__package__` at load time is therefore `"<id>"`, not `"bl_ext.<repo>.<id>"`. The `str`
  type cannot be checked by a runtime probe in that harness; it follows from Blender's loader above.

## 2. Where stock ty types it

- **Inside the module (bare name `__package__`).** A global name that a module does not bind falls back to
  `module_type_implicit_global_symbol` (`ruff-blender/ty_python_semantic/src/place.rs:2500-2581`). That function
  special-cases `__file__` (`str`), `__doc__` and a few more. Any other name, `__package__` included, is looked
  up as an attribute of `types.ModuleType`, whose typeshed declaration is `str | None`. ty's own test pins the
  result (`resources/mdtest/scopes/moduletype_attrs.md:14`).
- **From another module.** `pkg.__package__` and `from pkg import __package__` go through
  `ModuleLiteralType::static_member`, which calls `imported_symbol`. Its fallback special-cases `__file__` and
  `__builtins__`, and sends the rest to `ModuleType` (`place.rs:579-605`).
- **Completions** list the implicit globals through `all_implicit_module_globals`, which calls
  `module_type_implicit_global_symbol` for each name (`place.rs:2650-2671`), and **hover** shows the inferred type,
  so both follow the first fallback for free.
- **Assignments to the name.** An explicit `__package__ = ...` is checked against the typeshed *declaration*
  (`module_type_implicit_global_declaration`, `place.rs:2460-2484`), which must stay `str | None`: otherwise
  `__package__ = None`, which is legal Python, would start to error.
- *Verified locally* with stock ty: after `__package__ = "x"` the name is `Literal["x"]`, also inside a function.
  An explicit binding wins over the implicit global, so a hook there never overrides user code.

## 3. The `__name__` hazard

A `Literal` `__name__` makes `if __name__ == "__main__":` statically false.

- *Verified locally:* with `n: Literal["legacy"]`, the body of `if n == "__main__":` is unreachable:
  `reveal_type(n)` gives `Never`, and `1 + "x"` in it is not reported.
- Blender's own add-on template ends with exactly that guard
  (`blender/scripts/templates_py/addon_add_object.py:83-84`), so it is common in single-file add-ons.
- Inside Blender, as an add-on, the block really never runs. The same file run from the Text Editor has
  `__name__ == "__main__"`.

## 4. What the consumers see

- `AddonPreferences.bl_idname` is `str` in both stubs, and the key parameter of `addons[...]` accepts `str`. ty's
  `str | None` for `__package__` made both `bl_idname = __package__` and `addons[__package__]` errors; a `str` or
  `Literal` is assignable.
- For a legacy add-on, `Literal["prefs_legacy"]` *is* the key, so a preferences lookup can compare literals.
- For an extension the type is `str`. It is the same type for `__package__` in `__init__.py` (the key),
  `__package__` in `ui/panel.py` (not the key: `bl_ext.<repo>.prefs_ext.ui`), and any other string. So **decide
  the add-on key by the expression, not its type**: through the definition chain (the implicit global
  `__package__` in a module directly in the add-on root, a constant bound to it, an `import`-from of it,
  `__name__.rpartition(".")[0]`), or with a tracked "add-on key" provenance beside the type.
