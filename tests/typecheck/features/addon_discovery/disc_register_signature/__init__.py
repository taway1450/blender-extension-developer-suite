"""Feature test: register() and unregister() must take no arguments; Blender calls them without any."""


def register(context):  # ty: ignore[blender-invalid-register]
    pass


def unregister(context, extra):  # ty: ignore[blender-invalid-register]
    pass
