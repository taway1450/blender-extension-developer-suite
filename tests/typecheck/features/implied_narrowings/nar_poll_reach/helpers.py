"""Poll helpers the add-on's polls call with their context, or with a member of it."""


def has_object(context):
    return context.object is not None


def has_material(context):
    # Reading through a None object raises AttributeError, which the helper turns into False.
    try:
        return context.object.active_material is not None
    except AttributeError:
        return False


def is_mesh(ob):
    return ob and ob.type == 'MESH'
