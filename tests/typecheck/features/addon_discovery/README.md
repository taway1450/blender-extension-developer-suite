# addon_discovery

**The checker must:** find the add-ons in a project: a folder with `blender_manifest.toml` (extension) or an
`__init__.py` with `bl_info` (legacy add-on), or a single `.py` file with `bl_info`; find the add-on's
`__init__.py` and its `register` / `unregister`. Everything the other features do is scoped to one add-on found
here. A `pyproject.toml` with `[tool.blender] addons = [...]` overrides the search.

| Addon | Variant |
| --- | --- |
| `disc_extension` | extension with a manifest and a subpackage |
| `disc_legacy` | legacy add-on with `bl_info` |
| `disc_single.py` | single-file legacy add-on |
| `disc_both` | manifest and `bl_info` together (the manifest wins) |
| `disc_workspace` | a folder holding several add-ons (`addons/ws_alpha`, `addons/ws_beta`) |
| `disc_override` | `[tool.blender]` in `pyproject.toml` points at `src/disc_override_addon` |
| `disc_register_factory` | `register, unregister = register_classes_factory(...)` |
| `disc_register_reexport` | `register` imported from a submodule |
| `disc_register_alias` | `register = _register` |
| `disc_no_register`, `disc_no_unregister` | missing entry points (Blender fails to enable them) |
| `disc_register_signature` | `register` that takes a parameter (Blender fails to call it) |
| `disc_bad_bl_info`, `disc_bad_manifest` | metadata Blender rejects |

**Rules:** `blender-invalid-register` (missing or wrong `register` / `unregister`; on line 1 of `__init__.py`
when a function is missing), `blender-invalid-addon-metadata` (on the `bl_info` entry, or on line 1 of
`__init__.py` for problems in the manifest).
