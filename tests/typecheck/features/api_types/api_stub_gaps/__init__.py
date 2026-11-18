"""Feature test: facts of the Blender API that introspection alone left out of the stubs. Freestyle's classes have
bases and a Python __init__, BMesh sequences iterate over their elements, an ImBuf buffer is a memoryview, a matrix
row is a Vector, the version arrays are tuples, every struct has bl_rna, a few public module members are not in
__all__ or are not plain constants, and Operator.description may return None (Blender then shows the docstring).
BMesh element links are sequences of one element type, bpy.data collections take a (name, library) key, and
libraries.load and temp_data are context managers. Freestyle calls its overridable methods and Blender a render
engine's update callbacks and a gizmo's draw_select with positional arguments, so overrides may rename the parameters
or drop their defaults.
The stubs must state it (check_api_stub_gaps.py); the helpers below compute the facts for the runtime probes
(_expected/runtime.toml). The assert_type calls in the bodies are no-ops at runtime."""

import importlib
from typing import assert_type

import bpy
from bpy.types import Camera, Gizmo, Node, Operator, RenderEngine, Scene, ViewLayer
from bpy_extras.anim_utils import BakeOptions
from freestyle.types import (AdjacencyIterator, BinaryPredicate1D, ChainingIterator, Interface1D, Stroke,
                             StrokeShader, UnaryPredicate1D, ViewEdge)


class API_STUB_GAPS_OT_describe(Operator):
    """Shown when description returns None"""

    bl_idname = "api_stub_gaps.describe"
    bl_label = "Describe"

    @classmethod
    def description(cls, context, properties):
        return None

    def execute(self, context):
        return {'FINISHED'}


class API_STUB_GAPS_Engine(RenderEngine):
    """Blender passes every argument of the update callbacks, positionally."""

    bl_idname = "API_STUB_GAPS"
    bl_label = "Stub Gaps"

    def update_script_node(self, node):
        assert_type(node, Node | None)

    def update_render_passes(self, scene, renderlayer):
        # Blender calls it only with a scene and a view layer (`RE_engine_update_render_passes`).
        assert_type(scene, Scene)
        assert_type(renderlayer, ViewLayer)

    def update_custom_camera(self, cam):
        assert_type(cam, Camera | None)


class API_STUB_GAPS_GT_select(Gizmo):
    """Blender passes draw_select's optional select_id positionally too."""

    bl_idname = "API_STUB_GAPS_GT_select"

    def draw(self, context):
        pass

    def draw_select(self, context, select_id):
        pass


class LongEdgeUP1D(UnaryPredicate1D):
    """Freestyle calls __call__ with a positional argument, so the override names it as it likes."""

    def __call__(self, edge: Interface1D) -> bool:
        return edge.length_2d > 1.0


class LongerBP1D(BinaryPredicate1D):
    def __call__(self, first: Interface1D, second: Interface1D) -> bool:
        return first.length_2d > second.length_2d


class FirstEdgeIterator(ChainingIterator):
    def traverse(self, iter: AdjacencyIterator) -> ViewEdge | None:
        return None if iter.is_end else iter.object


class ThinShader(StrokeShader):
    def shade(self, s: Stroke) -> None:
        s.update_length()


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


def bmesh_links():
    """The class names of the first item of a cube face's verts, edges and loops, and of a loop's link_loops."""
    import bmesh

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.faces.ensure_lookup_table()
    face = bm.faces[0]
    loop = face.loops[0]
    names = " ".join(type(item).__name__ for item in (face.verts[0], face.edges[0], loop, loop.link_loops[0]))
    bm.free()
    return names


def data_lookup():
    """Whether bpy.data looks a local object up by its (name, None) key."""
    ob = bpy.data.objects.new("api_stub_gaps_lookup", None)
    return bpy.data.objects["api_stub_gaps_lookup", None] == ob


def temp_data():
    """The class name of what entering bpy.data.temp_data() gives."""
    with bpy.data.temp_data() as data:
        return type(data).__name__


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


def math_protocols():
    """Whether a shorter vector compares less, and the class name of a negated quaternion."""
    from mathutils import Quaternion, Vector

    return f"{Vector((1.0, 0.0, 0.0)) < Vector((0.0, 2.0, 0.0))} {type(-Quaternion()).__name__}"


def font_image_binding():
    """The class name of a font's image binding, entered and left."""
    import blf
    import imbuf

    binding = blf.bind_imbuf(0, imbuf.new((4, 4)))
    with binding:
        pass
    return type(binding).__name__


def entered_font_image_binding():
    """What entering a font's image binding gives. The matrix stack and an off-screen binding need a GPU context,
    which background Blender has not; their __enter__ returns None too (gpu_py_matrix.cc, gpu_py_offscreen.cc)."""
    import blf
    import imbuf

    with blf.bind_imbuf(0, imbuf.new((4, 4))) as entered:
        return repr(entered)

def module_members():
    """The class names of the module members the stubs left out."""
    import imbuf

    values = (bpy.utils.system_resource('SCRIPTS'), bpy.utils.is_path_builtin(""), bpy.path.extensions_image,
              next(iter(bpy.path.extensions_image)), imbuf.file_types, next(iter(imbuf.file_types)),
              next(iter(imbuf.file_types.values())))
    return " ".join(type(value).__name__ for value in values)


classes = (API_STUB_GAPS_OT_describe, API_STUB_GAPS_Engine, API_STUB_GAPS_GT_select)
register, unregister = bpy.utils.register_classes_factory(classes)
