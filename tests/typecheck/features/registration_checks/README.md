# registration_checks

**The checker must:** report registration mistakes, and keep add-ons apart: what one add-on registers is not
visible in another, unless that one declares it in its manifest.

| Addon | Rule | Variant |
| --- | --- | --- |
| `regchk_unregistered` | `blender-unregistered-class` | operators, panels, menus, UI lists, PropertyGroups and preferences never registered, also in imported and in orphan modules; base classes and mixins are not reported |
| `regchk_unreachable` | `blender-unreachable-registration` | functions that register classes but that `register()` never calls; a function `register()` hands to a timer is reachable (its operator's use is reported, `blender-assumed-registration`). A class registered only by such a function gets no `blender-unregistered-class`: one diagnostic per mistake |
| `regchk_order` | `blender-register-order` | pointers and collections to a PropertyGroup registered later, the same on a Blender class, a subpanel before its parent (fails to load) |
| `regchk_duplicate` | `blender-duplicate-registration` | a class registered twice (explicit, loop, twice in a sequence); two classes with one `bl_idname` (fails to load) |
| `regchk_paths` | | registration that is valid on every path: a branch that returns, a list rebound in a branch, a tuple concatenated onto itself, a helper calling itself with other keywords; nothing is reported |
| `regchk_main_guard` | | Blender's bundled add-ons' shape: a reload guard, a registration loop and `if __name__ == "__main__": register()`, which never runs in an add-on; nothing is reported |
| `regchk_idname` | `blender-invalid-idname` | operator idnames Blender refuses, a missing `bl_idname`; panel / menu idnames without `_PT_` / `_MT_` (fails to load) |
| `regchk_type_bases` | | a Menu without `bl_idname` that is only the base of menus made with `type(name, (Base,), namespace)`: a base, neither checked nor unregistered |
| `regchk_unregister_leak` | `blender-unregister-mismatch` | classes, properties, handlers and menu functions that `unregister()` leaves behind |
| `regchk_unregister_unknown` | `blender-unregister-mismatch` | `unregister_class` for a class that was not registered (fails in unregister) |
| `regchk_isolation_a`, `_b` | `missing-attribute` | each sees only its own operators and properties; only A calls the shared library's `register_tool()` |
| `regchk_shared_lib` | | a package both import; not an add-on (`load = false`) |
| `regchk_uses`, `regchk_uses_provider` | `missing-attribute` | an add-on that declares another in its manifest (`[tool.blender] uses = ["regchk_uses_provider"]`, a table Blender ignores) reads that add-on's Registered properties after its own (its own `Scene.regchk_uses_shared` wins); an add-on it does not declare stays unseen, and a declared name no module provides is `blender-invalid-addon-metadata` |

**Runtime facts (Blender 5.4):** a valid operator idname is `category.name` with lower case letters, digits and
underscores (`OBJECT_OT_x`, upper case, two dots, dashes and a missing part raise `RuntimeError`). A pointer to an
unregistered PropertyGroup raises `ValueError`; a subpanel before its parent `RuntimeError`; registering a class
twice `ValueError`. Two operators with one idname, panel names without `_PT_` and unregistering in the wrong order
only print a message.
