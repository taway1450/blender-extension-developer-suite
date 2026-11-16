"""Feature test: facts of the Blender API that introspection alone left out of the stubs. Freestyle's classes have
bases and a Python __init__, BMesh sequences iterate over their elements, an ImBuf buffer is a memoryview, a matrix
row is a Vector, the version arrays are tuples, every struct has bl_rna, a few public module members are not in
__all__ or are not plain constants, and Operator.description may return None (Blender then shows the docstring).
The stubs must state it (check_api_stub_gaps.py); the helpers below compute the facts for the runtime probes
(_expected/runtime.toml)."""

import importlib

import bpy
from bpy.types import Operator
from bpy_extras.anim_utils import BakeOptions


class API_STUB_GAPS_OT_describe(Operator):
    """Shown when description returns None"""

    bl_idname = "api_stub_gaps.describe"
    bl_label = "Describe"

    @classmethod
    def description(cls, context, properties):
        return None

    def execute(self, context):
        return {'FINISHED'}


def bases(module_name, class_name):
    """The names of the bases of ``module_name.class_name``."""
    cls = getattr(importlib.import_module(module_name), class_name)
    return " ".join(base.__name__ for base in cls.__bases__)


def bake_options() -> BakeOptions:
    """The options anim_utils.bake_action takes, built as an add-on builds them: a dataclass with 12 fields."""
    return BakeOptions(only_selected=True, do_pose=True, do_object=False, do_visual_keying=False, do_constraint_clear=False, do_parents_clear=False, do_clean=True, do_location=True, do_rotation=True, do_scale=True, do_bbone=True, do_custom_props=False)


def bmesh_items():
    """The class names of the first item of a cube's vertex, edge and face sequences, when iterated."""
    import bmesh

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    names = " ".join(type(next(iter(seq))).__name__ for seq in (bm.verts, bm.edges, bm.faces))
    bm.free()
    return names


def imbuf_buffer():
    """The class name of what entering an ImBuf's buffer gives."""
    import imbuf

    with imbuf.new((4, 4)).with_buffer() as buf:
        return type(buf).__name__


def matrix_rows():
    """The class names of a matrix column and of an item of its rows, when iterated."""
    from mathutils import Matrix

    matrix = Matrix()
    return f"{type(matrix.col[0]).__name__} {type(next(iter(matrix.row))).__name__}"


def module_members():
    """The class names of the module members the stubs left out."""
    import imbuf

    values = (bpy.utils.system_resource('SCRIPTS'), bpy.utils.is_path_builtin(""), bpy.path.extensions_image,
              next(iter(bpy.path.extensions_image)), imbuf.file_types, next(iter(imbuf.file_types)),
              next(iter(imbuf.file_types.values())))
    return " ".join(type(value).__name__ for value in values)


classes = (API_STUB_GAPS_OT_describe,)
register, unregister = bpy.utils.register_classes_factory(classes)
