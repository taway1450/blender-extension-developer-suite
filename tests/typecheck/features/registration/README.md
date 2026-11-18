# registration

**The checker must:** follow `register()` of an add-on to every `register_class` call it reaches and every
property it assigns to a Blender class. A registered operator becomes an attribute of `bpy.ops.<category>`; a
registered property an attribute of its class. Classes that are never registered do not.

| Addon | Variant |
| --- | --- |
| `reg_explicit` | `bpy.utils.register_class`, a from-import of it and an alias |
| `reg_loop` | loops over tuples, lists (extended with `append` and `+=`), concatenations, unpacking, nested loops |
| `reg_factory` | `register_classes_factory` results called from a hand-written `register()` |
| `reg_submodule_factory` | `register_submodule_factory(__name__, [...])` with a module and a subpackage |
| `reg_delegation` | helper functions, nested helpers, `module.register()`, loops over modules and functions, a static method |
| `reg_imports` | the `importlib.reload` pattern, a renamed `register`, a star import, an imported class, a nested package, an import inside `register()` |
| `reg_reload` | names the reload guard reads (`if "bpy" in locals():`, `if "x" not in locals(): ... else:`): a global bound later in the module, or in a package a submodule imported only inside `register()`; a package that imports its submodules with `__import__(name=__name__, fromlist=_modules)`, as `bl_ui` does |
| `reg_autoload` | an `auto_load` module that finds classes at runtime: every Blender class of the add-on counts as registered (reported once, `blender-assumed-complete-registration`), and the properties a `PropertyGroup.register()` classmethod assigns exist |
| `reg_foreign` | `register_class` over a dict's `.values()`, which the checker cannot follow to a class: it gives up, and every Blender class counts as registered (reported once, `blender-assumed-complete-registration`) |
| `reg_conditional` | version checks, `try`, `hasattr`, environment variables: conditionally registered classes count, each use reported under `blender-assumed-registration` (a `try` body always runs) |
| `reg_classmethod` | a `PropertyGroup` whose `register()` / `unregister()` classmethods assign properties and register a class, as Cycles does |
| `reg_classmethod_plain` | a `PropertyGroup` whose `register()` is a plain method: `register_class` calls it without arguments, which fails before its body runs, so its property does not exist |

Code reached by `register()` counts toward that add-on, also when it lives in a package shared with other add-ons
(see `registration_checks/regchk_isolation_*`).
