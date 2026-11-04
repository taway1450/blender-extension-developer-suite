"""Feature test: an auto_load module that imports the addon's modules and registers every Blender class it finds.
The checker cannot follow this, so for an addon whose register() reaches a register_class call with a class it
cannot work out, every Blender class in the addon counts as registered."""

from . import auto_load

auto_load.init()


def register():
    auto_load.register()


def unregister():
    auto_load.unregister()
