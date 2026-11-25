"""Scatter Tools: scatter linked copies of the active object around it, optionally onto a surface."""

from . import operators, preferences, properties, ui


# demo: registration
def register() -> None:
    properties.register()
    preferences.register()
    operators.register()
    ui.register()


def unregister() -> None:
    ui.unregister()
    operators.unregister()
    preferences.unregister()
    properties.unregister()
