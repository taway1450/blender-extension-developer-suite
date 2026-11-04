"""Feature test: register and unregister made by register_submodule_factory, which imports the listed submodules
(a module and a package) and calls their register() functions."""

import bpy

register, unregister = bpy.utils.register_submodule_factory(__name__, ["ops_module", "ops_package"])
