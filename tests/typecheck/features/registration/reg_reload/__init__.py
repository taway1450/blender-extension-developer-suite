"""Feature test: names a module bound on its previous run, which the reload guard reads. Blender reloads an add-on
by re-running its modules in their old namespace, so `"bpy" in locals()` is true only then."""

from typing import Literal, assert_type

if "bpy" in locals():
    import importlib

    # `ops` is imported only inside `register()`, which binds the submodule in the package.
    if "ops" in locals():
        assert_type(ops.LABEL, Literal["Run"])
        importlib.reload(ops)
    importlib.reload(startup)
    importlib.reload(not_a_submodule)  # ty: ignore[unresolved-reference]  # bare-ok: no binding and no submodule

import bpy

from . import startup


def register():
    from . import ops

    ops.register()
    startup.register()


def unregister():
    from . import ops

    startup.unregister()
    ops.unregister()
