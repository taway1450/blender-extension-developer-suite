# bpy_symbols

**The checker must:** recognise Blender's symbols however they are imported: `bpy.props` functions, `bpy.types`
base classes, `bpy.utils` registration functions, `bpy.ops`, `bpy.app.handlers`, `mathutils` and `bpy_extras`.
The other features key on these symbols, so a property declared through an alias must be the same property as
one declared through `bpy.props.IntProperty`.

| Addon | Variant |
| --- | --- |
| `generated/sym_*` | one addon per import form (dotted, submodule, module alias, `from bpy import props`, from-imports with and without alias, star import, assigned aliases, re-exports through the addon's own modules, nested re-exports), made by `scripts/feature_generators/bpy_symbols.py` |
| `sym_negative` | look-alikes that are not Blender's: local functions named like properties, fake base classes, a parameter called `bpy` |
| `sym_mathutils` | `mathutils` types and operators |
| `sym_handlers` | `bpy.app.handlers` and `@persistent` (it returns the function; `load_post` handlers get `(str, None)`) |
| `sym_bpy_extras` | `ImportHelper` / `ExportHelper` properties (`filepath`, `check_existing`), `orientation_helper` enums |

**Runtime facts (Blender 5.4):** `from bpy.types import *` only binds the `bpy_*` base classes, so
`PropertyGroup` is undefined after it; `from bpy.app.handlers import *` raises `ImportError`.
