"""Feature test: the ways __init__.py imports what it registers: the reload pattern, a renamed register function,
a star import, an imported class, a module in a nested package and an import inside register()."""

if "bpy" in locals():
    import importlib

    importlib.reload(reloaded)
else:
    from . import reloaded

import bpy

from .nested.deep import operators as nested_operators
from .ops_class import REG_IMPORTS_OT_class_import
from .ops_renamed import register as register_renamed
from .ops_renamed import unregister as unregister_renamed
from .ops_star import *


def register():
    reloaded.register()
    register_renamed()
    bpy.utils.register_class(REG_IMPORTS_OT_star)
    bpy.utils.register_class(REG_IMPORTS_OT_class_import)
    nested_operators.register()
    from . import ops_lazy

    ops_lazy.register()


def unregister():
    from . import ops_lazy

    ops_lazy.unregister()
    nested_operators.unregister()
    bpy.utils.unregister_class(REG_IMPORTS_OT_class_import)
    bpy.utils.unregister_class(REG_IMPORTS_OT_star)
    unregister_renamed()
    reloaded.unregister()
