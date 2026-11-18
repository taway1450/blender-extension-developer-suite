"""Facts introspection alone left out of the stubs: class bases and Python __init__, iteration and context-manager
protocols, the Vector and Quaternion operators, the version tuples, bl_rna, module members outside __all__ or not plain
constants, the private module members Blender's own scripts read, a callback that may return None, BMesh links of one
element type, bpy.data's (name, library) key, the context store members Blender's UI sets, the context managers, the
item and slice assignment and buffer protocol of the math types, rna_type, the sequences a BMesh operator's element
buffer takes, the argument types of C functions and RNA functions, the type ID.copy returns, BMesh layer access,
context.property, positional callbacks, dynamic enums, read-only attributes, two documented returns and Freestyle's
undocumented members and generators. These are stub facts.
The overrides of Freestyle's methods, the render engine's update callbacks and a gizmo's draw_select are in __init__.py:
an incompatible override would be an unexpected diagnostic there."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager
from types import MappingProxyType
from typing import Any, Literal, TypeAlias, assert_type

import blf
import bmesh
import bpy
import gpu
import imbuf
from bmesh.types import BMEdge, BMElemSeq, BMesh, BMFace, BMLayerItem, BMLoop, BMVert
from bpy.types import (Area, AssetShelf, BlendData, Camera, Constraint, Context, Depsgraph, FreestyleModuleSettings,
                       Gizmo, ID, KeyMap, Library, Material, Mesh, Node, NodeTreeInterface, NodeTreeInterfaceSocket,
                       Object, Operator, OperatorProperties, Preferences, PropertyGroup, RenderEngine, Scene, Struct,
                       UILayout, ViewLayer, WorkSpaceTool, bpy_struct)
from bpy_extras.anim_utils import BakeOptions
from freestyle.chainingiterators import pyChainSilhouetteGenericIterator
from freestyle.functions import pyDensityAnisotropyF1D
from freestyle.predicates import QuantitativeInvisibilityUP1D, TrueUP1D
from freestyle.shaders import ConstantThicknessShader, SamplingShader
from freestyle.types import (Interface0DIterator, Interface1D, Noise, Operators, Stroke, StrokeVertex,
                             UnaryFunction0DDouble, UnaryFunction1DDouble, UnaryPredicate1D, ViewEdge)
from freestyle.utils import BoundingBox, get_strokes, iter_distance_from_camera, iter_t2d_along_stroke, pairwise, stroke_normal
from gpu.types import GPUOffScreen, GPUShader, GPUVertFormat
from imbuf.types import ImBuf, ImBufFileType
from mathutils import Matrix, Quaternion, Vector

from . import API_STUB_GAPS_OT_describe, bake_options

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def as_predicate(predicate: UnaryPredicate1D) -> UnaryPredicate1D:
    return predicate


def as_function(function: UnaryFunction1DDouble) -> UnaryFunction1DDouble:
    return function


def as_floats(values: Sequence[float]) -> Sequence[float]:
    return values


def classes(edge: ViewEdge, iterator: pyChainSilhouetteGenericIterator, options: BakeOptions) -> None:
    assert_type(edge.length_2d, float)  # bare-ok: a stub fact: a ViewEdge is an Interface1D
    assert_type(iterator.is_begin, bool)  # bare-ok: a stub fact: a Python chaining iterator is a ChainingIterator
    assert_type(as_predicate(QuantitativeInvisibilityUP1D(0)), UnaryPredicate1D)  # bare-ok: a stub fact: a C predicate's base
    assert_type(as_function(pyDensityAnisotropyF1D(4)), UnaryFunction1DDouble)  # bare-ok: a stub fact: a Python class's base and __init__
    assert_type(bake_options(), BakeOptions)  # bare-ok: a stub fact: a dataclass's __init__, which bake_options() calls with every field
    assert_type(options.do_pose, bool)  # bare-ok: a stub fact: a dataclass's fields


def protocols(bm: BMesh, ibuf: ImBuf, matrix: Matrix) -> None:
    for vert in bm.verts:
        assert_type(vert, BMVert)  # bare-ok: a stub fact: a BMVertSeq iterates over its vertices
    for edge in bm.edges:
        assert_type(edge, BMEdge)  # bare-ok: a stub fact: a BMEdgeSeq iterates over its edges
    for face in bm.faces:
        assert_type(face, BMFace)  # bare-ok: a stub fact: a BMFaceSeq iterates over its faces
    for elem in bm.select_history:
        assert_type(elem, BMVert | BMEdge | BMFace)  # bare-ok: a stub fact: the selection history iterates over elements
    with ibuf.with_buffer() as buf:
        assert_type(buf, memoryview)  # bare-ok: a stub fact: entering an ImBuf buffer gives a memoryview
    assert_type(matrix.col[0], Vector)  # bare-ok: a stub fact: a matrix column is a Vector
    for row in matrix.row:
        assert_type(row, Vector)  # bare-ok: a stub fact: a matrix row is a Vector


def math_protocols(vector: Vector, other: Vector, quaternion: Quaternion) -> None:
    assert_type(as_floats(vector), Sequence[float])  # bare-ok: a stub fact: a Vector is a sequence of floats
    assert_type(vector < other, bool)  # bare-ok: a stub fact: vectors compare by length
    assert_type(vector >= other, bool)  # bare-ok: a stub fact: vectors compare by length
    assert_type(-quaternion, Quaternion)  # bare-ok: a stub fact: a quaternion negates


def math_item_assignment(vector: Vector, other: Vector, quaternion: Quaternion, matrix: Matrix) -> None:
    vector[:] = 1.0, 2.0, 3.0  # a stub fact: a slice takes any sequence of floats
    vector[:] = other  # a stub fact: a slice takes another vector
    vector[0:2] = other[:2]  # a stub fact: a slice takes a tuple of floats
    quaternion[:] = 1.0, 0.0, 0.0, 0.0  # a stub fact: so does a quaternion's
    matrix[0] = 1.0, 0.0, 0.0, 0.0  # a stub fact: a matrix row takes a sequence of floats
    matrix[0][0:3] = 0.0, 1.0, 2.0  # a stub fact: a matrix row is a Vector, whose slice takes floats
    assert_type(memoryview(vector), memoryview)  # bare-ok: a stub fact: a Vector is a buffer
    assert_type(memoryview(quaternion), memoryview)  # bare-ok: a stub fact: a Quaternion is a buffer
    assert_type(memoryview(matrix), memoryview)  # bare-ok: a stub fact: a Matrix is a buffer


def c_argument_types(shader: GPUShader, vertex_format: GPUVertFormat, mesh: Mesh, ob: Object, data: BlendData,
                     ints: list[int], flags: list[bool], objects: set[Object], path: str) -> None:
    assert_type(vertex_format.attr_add(id="pos", comp_type='F32', len=3, fetch_mode='FLOAT'), int)  # bare-ok: a stub fact: the attribute's index
    shader.uniform_float("matrix", Matrix())  # a stub fact: a uniform takes a 3x3 or 4x4 matrix
    mesh.vertices.foreach_get("index", ints)  # a stub fact: foreach_get fills a list of ints
    mesh.vertices.foreach_get("select", flags)  # a stub fact: or of bools
    assert_type(Vector(value for value in (1.0, 2.0)), Vector)  # bare-ok: a stub fact: a vector takes any iterable
    assert_type(Quaternion(iter((1.0, 0.0, 0.0, 0.0))), Quaternion)  # bare-ok: a stub fact: so does a quaternion
    bpy.msgbus.subscribe_rna(key=ob.location, owner=ob, args=(), notify=print)  # a stub fact: a key is a math value with an owner
    bpy.msgbus.subscribe_rna(key=(bpy.types.Object, "location"), owner=ob, args=(), notify=print)  # a stub fact: or a (struct type, name) pair
    data.libraries.write(path, objects)  # a stub fact: write takes a set of one ID type


def rna_argument_types(area: Area, layout: UILayout, view_layer: ViewLayer, scene: Scene) -> None:
    area.header_text_set(None)  # a stub fact: a string argument without PROP_NEVER_NULL takes None
    layout.template_ID(view_layer.objects, "active")  # a stub fact: an AnyType argument takes a typed collection
    layout.prop_search(scene.keying_sets, "active", scene, "keying_sets")  # a stub fact: and so does prop_search's
    scene.render.engine = 'CYCLES'  # a stub fact: an add-on's render engine is an engine too


def rna_returns(ob: Object, mesh: Mesh, depsgraph: Depsgraph, context: Context, loop: BMLoop,
                uv_layer: BMLayerItem) -> None:
    assert_type(ob.copy(), Object)  # bare-ok: a stub fact: a copy has the type of the original
    assert_type(mesh.copy(), Mesh)  # bare-ok: a stub fact: a copy has the type of the original
    assert_type(ob.evaluated_get(depsgraph), Object)  # bare-ok: a stub fact: so has the evaluated data-block
    assert_type(loop[uv_layer], Any)  # bare-ok: a stub fact: an element's layer value has the layer's type
    assert_type(context.property, tuple[bpy_struct, str, int] | None)  # bare-ok: a stub fact: the data, its path and index


def gpu_context_managers(offscreen: GPUOffScreen, font_id: int, ibuf: ImBuf) -> None:
    with gpu.matrix.push_pop():  # a stub fact: the matrix stack is a context manager
        pass
    with offscreen.bind():  # a stub fact: an off-screen binding is a context manager
        pass
    with blf.bind_imbuf(font_id, ibuf):  # a stub fact: a font's image binding is a context manager
        pass


def versions(data: BlendData, preferences: Preferences, library: Library) -> None:
    assert_type(data.version, tuple[int, int, int])  # bare-ok: a stub fact: a thick-wrapped array is a tuple
    assert_type(preferences.version, tuple[int, int, int])  # bare-ok: a stub fact: a thick-wrapped array is a tuple
    assert_type(library.version, tuple[int, int, int])  # bare-ok: a stub fact: a thick-wrapped array is a tuple
    assert_type(preferences.version >= (4, 2, 0), bool)  # bare-ok: a stub fact: so it compares with a tuple


def bl_rna(ob: Object, node: Node, data: BlendData, group: PropertyGroup) -> None:
    assert_type(Operator.bl_rna, Struct)  # bare-ok: a stub fact: every RNA class has bl_rna
    assert_type(ob.bl_rna, Struct)  # bare-ok: a stub fact: readable from an instance too
    assert_type(ob.rna_type, Struct)  # bare-ok: a stub fact: every RNA struct has the rna_type property
    assert_type(node.rna_type, Struct)  # bare-ok: a stub fact: a node's too
    assert_type(data.rna_type, Struct)  # bare-ok: a stub fact: and bpy.data's
    ob.rna_type = node.rna_type  # ty: ignore[invalid-assignment]  # a stub fact: a read-only attribute can't be assigned
    group.name = "renamed"  # a stub fact: a property group's name is an ID property, which can be set


def bmesh_operator_buffers(bm: BMesh, face: BMFace) -> None:
    bmesh.ops.triangulate(bm, faces=bm.faces)  # a stub fact: an element buffer takes the mesh's sequence of its type
    bmesh.ops.dissolve_verts(bm, verts=face.verts)  # a stub fact: or an element sequence of its type
    bmesh.ops.dissolve_verts(bm, verts=bm.verts[:])  # a stub fact: or a list of its elements
    bmesh.ops.delete(bm, geom=bm.verts[:] + bm.edges[:])  # a stub fact: or a list of some of the element types it takes


def module_members() -> None:
    assert_type(bpy.utils.system_resource('SCRIPTS'), str)  # bare-ok: a stub fact: public, though not in __all__
    assert_type(bpy.utils.is_path_builtin(""), bool)  # bare-ok: a stub fact: public, though not in __all__
    assert_type(bpy.path.extensions_image, frozenset[str])  # bare-ok: a stub fact: a frozenset in __all__
    assert_type(imbuf.file_types, MappingProxyType[str, ImBufFileType])  # bare-ok: a stub fact: a read-only dict


def private_module_members() -> None:
    # Private members Blender's own scripts read (addon_utils, the Extensions add-on), which the API docs leave out.
    assert_type(bpy.app.handlers._extension_repos_update_pre, list[Callable[..., None]])  # bare-ok: a stub fact: a private handler list
    assert_type(bpy.app.handlers._extension_repos_update_post, list[Callable[..., None]])  # bare-ok: a stub fact: a private handler list
    assert_type(bpy.app.handlers._extension_repos_sync, list[Callable[..., None]])  # bare-ok: a stub fact: a private handler list
    assert_type(bpy.app.handlers._extension_repos_files_clear, list[Callable[..., None]])  # bare-ok: a stub fact: a private handler list
    assert_type(bpy.utils._sys_path_ensure_append(""), None)  # bare-ok: a stub fact: a private function


def description(context: Context, properties: OperatorProperties) -> None:
    assert_type(Operator.description(context, properties), str | None)  # bare-ok: a stub fact: None shows the docstring
    assert_type(API_STUB_GAPS_OT_describe.description(context, properties), str | None)


def bmesh_links(vert: BMVert, edge: BMEdge, face: BMFace, loop: BMLoop) -> None:
    assert_type(face.loops, BMElemSeq[BMLoop])  # bare-ok: a stub fact: an element link names its element type
    assert_type(face.loops[0].vert, BMVert)  # bare-ok: a stub fact: an item of a face's loops is a BMLoop
    assert_type(face.verts[0], BMVert)  # bare-ok: a stub fact: an item of a face's verts is a BMVert
    assert_type(face.edges[:], list[BMEdge])  # bare-ok: a stub fact: a slice of a face's edges
    assert_type(vert.link_faces[0], BMFace)  # bare-ok: a stub fact: an item of a vertex's link_faces is a BMFace
    assert_type(edge.verts[1], BMVert)  # bare-ok: a stub fact: an item of an edge's verts is a BMVert
    for linked in loop.link_loops:
        assert_type(linked, BMLoop)  # bare-ok: a stub fact: a loop's link_loops iterates over loops


def data_keys(data: BlendData, name: str, library: str | None) -> None:
    assert_type(data.objects[name, None], Object)  # bare-ok: a stub fact: a local object by its (name, None) key
    assert_type(data.materials[name, library], Material)  # bare-ok: a stub fact: a linked material by its library path


def context_store(context: Context) -> None:
    assert_type(context.constraint, Constraint | None)  # bare-ok: a stub fact: set by the constraint panels' layouts
    assert_type(context.keymap, KeyMap | None)  # bare-ok: a stub fact: set by the keymap editor
    assert_type(context.animated_id, ID | None)  # bare-ok: a stub fact: set by the driver editor's layout
    assert_type(context.freestyle_module, FreestyleModuleSettings | None)  # bare-ok: a stub fact: set by the Freestyle panel
    assert_type(context.tool, WorkSpaceTool | None)  # bare-ok: a stub fact: set by the tool settings' layouts
    assert_type(context.asset_shelf, AssetShelf | None)  # bare-ok: a stub fact: set by an asset shelf's layout


def context_managers(data: BlendData, path: str) -> None:
    assert_type(data.libraries.load(path), AbstractContextManager[tuple[Any, Any]])  # bare-ok: a stub fact: entering it gives the input and output libraries
    with data.libraries.load(path, link=True) as (data_from, data_to):
        data_to.objects = data_from.objects
    with data.temp_data() as temp:
        assert_type(temp, BlendData)  # bare-ok: a stub fact: entering temp_data gives a temporary BlendData


def positional_callbacks(engine: RenderEngine, scene: Scene, view_layer: ViewLayer, node: Node, camera: Camera) -> None:
    assert_type(engine.update_render_passes(scene, view_layer), None)  # bare-ok: a stub fact: Blender passes them positionally
    assert_type(engine.update_script_node(node), None)  # bare-ok: a stub fact: Blender passes it positionally
    assert_type(engine.update_custom_camera(camera), None)  # bare-ok: a stub fact: Blender passes it positionally


def dynamic_enums(interface: NodeTreeInterface, idname: str) -> None:
    assert_type(interface.new_socket("Value", socket_type=idname), NodeTreeInterfaceSocket)  # bare-ok: a stub fact: the socket types come from a callback
    assert_type(bpy.ops.grease_pencil.set_material(slot=idname), Result)  # bare-ok: a stub fact: the material slots come from a callback


def documented_returns(gizmo: Gizmo, path: str) -> None:
    assert_type(bpy.utils.keyconfig_set(path), bool)  # bare-ok: a stub fact: whether the key configuration loaded
    assert_type(gizmo.target_set_value("offset", 1.0), None)  # bare-ok: a stub fact: the value parameter is documented


def freestyle_shaders() -> None:
    shaders = [ConstantThicknessShader(2), SamplingShader(5.0)]
    assert_type(Operators.create(TrueUP1D(), shaders), None)  # bare-ok: a stub fact: a list of any shader types
    Operators.create(TrueUP1D(), (SamplingShader(5.0),))  # ty: ignore[invalid-argument-type]  # bare-ok: a stub fact: the C code requires a list


def freestyle_members(it: Interface0DIterator, inter: Interface1D, function_0d: UnaryFunction0DDouble,
                      function_1d: UnaryFunction1DDouble, noise: Noise, box: BoundingBox) -> None:
    assert_type(function_0d(it), float)  # bare-ok: a stub fact: a unary function base is callable
    assert_type(function_1d(inter), float)  # bare-ok: a stub fact: a unary function base is callable
    assert_type(pyDensityAnisotropyF1D(4)(inter), float)  # bare-ok: a stub fact: a Python function calls through its base
    assert_type(noise.rand(), float)  # bare-ok: a stub fact: documented in C since the fork
    assert_type(noise.turbulence_smooth(0.5, 2), float)  # bare-ok: a stub fact: documented in C since the fork
    assert_type(box.corners, tuple[Vector, Vector])  # bare-ok: a stub fact: an attribute set in __init__


def freestyle_generators(stroke: Stroke, points: list[Vector]) -> None:
    assert_type(pairwise(points), Iterator[tuple[Any, Any]])  # bare-ok: a stub fact: a generator, not None
    assert_type(iter_t2d_along_stroke(stroke), Iterator[float])  # bare-ok: a stub fact: a generator, not None
    assert_type(iter_distance_from_camera(stroke, 0.0, 1.0, 1.0), Iterator[tuple[StrokeVertex, float]])  # bare-ok: a stub fact: a generator, not None
    assert_type(stroke_normal(stroke), Iterator[Vector])  # bare-ok: a stub fact: a generator, not None
    assert_type(get_strokes(), tuple[Stroke, ...])  # bare-ok: a stub fact: the strokes, not None
