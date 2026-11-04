# addon_preferences

**The checker must:** give `preferences.addons[<key>].preferences` the add-on's own `AddonPreferences` class,
without `None`, when the key names the add-on that is being checked, and check the `bl_idname` of preferences
classes. Spellings of the key: `__package__` (any module of the add-on), a constant holding it, `__name__` in a
legacy add-on's `__init__.py`, `__name__.rpartition(".")[0]` in a direct submodule, `from .. import __package__`,
the literal name of a legacy add-on. `.get(key)` gives the specialised `Addon | None`. Other keys keep the stub
type `AddonPreferences | None`.

| Addon | Variant |
| --- | --- |
| `prefs_ext` | every key spelling in an extension, through helper functions in submodules |
| `prefs_legacy` | a `bl_info` add-on: `__name__` and the literal name |
| `prefs_bad` | `blender-preferences-idname`: a wrong literal, `__name__` in a submodule, no `bl_idname`, a second class for the add-on (it replaces the first, so unregister fails) |
| `prefs_unregistered` | a preferences class that is never registered: the stub type |

The oracle cannot check `__package__` keys (stock ty types `__package__` as `str | None`), so those lines are
`oracle-skip`.
