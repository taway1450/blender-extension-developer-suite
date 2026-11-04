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
| `reg_autoload` | an `auto_load` module that finds classes at runtime: every Blender class of the add-on counts as registered |
| `reg_conditional` | version checks, `try`, `hasattr`, environment variables: conditionally registered classes count |

Code reached by `register()` counts toward that add-on, also when it lives in a package shared with other add-ons
(see `registration_checks/regchk_isolation_*`).
