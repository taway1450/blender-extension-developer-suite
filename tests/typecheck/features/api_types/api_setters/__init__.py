"""Feature test: a math property (a Vector, Color, Euler, Quaternion or Matrix) and an array property take any
sequence of the right length on assignment, and an array property a sequence on slice assignment, while reading them
still gives the math object or the bpy_prop_array. The stubs must state it (check_api_setters.py); the helpers below
assign through a scratch object for the runtime probes (_expected/runtime.toml)."""

import bpy

ROWS = [[2.0, 0.0, 0.0, 1.0], [0.0, 2.0, 0.0, 2.0], [0.0, 0.0, 2.0, 3.0], [0.0, 0.0, 0.0, 1.0]]


def math_setters():
    """The class names of math properties after assigning sequences to them, and the world matrix's determinant."""
    ob = bpy.data.objects.new("api_setters", None)
    ob.location = (1, 2, 3)
    ob.rotation_euler = (0.0, 0.0, 1.0)
    ob.rotation_quaternion = [1.0, 0.0, 0.0, 0.0]
    ob.matrix_world = ROWS
    light = bpy.data.lights.new("api_setters", 'POINT')
    light.color = (1.0, 0.5, 0.0)
    names = " ".join(type(value).__name__ for value in (
        ob.location, ob.rotation_euler, ob.rotation_quaternion, ob.matrix_world, light.color))
    return f"{names} {ob.matrix_world.determinant()}"


def array_setters():
    """The class names of array properties after assigning tuples to them and to a slice of them, and their values."""
    ob = bpy.data.objects.new("api_setters", None)
    ob.lock_location = (True, False, True)
    ob.color[0:3] = (0.25, 0.5, 0.75)
    image = bpy.data.images.new("api_setters", 2, 2, float_buffer=True)
    image.pixels[:] = [0.5] * 16
    material = bpy.data.materials.new("api_setters")
    material.diffuse_color = (1.0, 0.0, 0.0, 1.0)
    names = " ".join(type(value).__name__ for value in (ob.lock_location, ob.color, image.pixels))
    return f"{names} {tuple(ob.lock_location)} {tuple(ob.color)} {image.pixels[15]} {tuple(material.diffuse_color)}"


def wrong_element():
    """Assigning a tuple with a string in it to a math property."""
    bpy.data.objects.new("api_setters", None).location = ("1", 2, 3)  # ty: ignore[invalid-assignment]  # bare-ok: raises TypeError


def register():
    pass


def unregister():
    pass
