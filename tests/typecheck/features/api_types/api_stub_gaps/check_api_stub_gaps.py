"""Facts introspection alone left out of the stubs: class bases and Python __init__, iteration and context-manager
protocols, the Vector and Quaternion operators, the version tuples, bl_rna, module members outside __all__ or not plain
constants, the private module members Blender's own scripts read, a callback that may return None, BMesh links of one
element type, bpy.data's (name, library) key, the context store members Blender's UI sets, the context managers, the
item and slice assignment and buffer protocol of the math types, rna_type, the sequences a BMesh operator's element
buffer takes, the argument types of C functions and RNA functions, the type ID.copy returns, BMesh layer access,
context.property, positional callbacks, dynamic enums, read-only attributes, the ID id_data is from, two documented
returns and Freestyle's undocumented members and generators, the AnimData animation_data_create always gives an ID
type that has one, the gpu buffer protocols, the pointers Blender always allocates, the typed items and values of a
collection, a shape key's points, refined bases and the members every subclass declares, and the argument types
docstrings left too narrow. These are stub facts.
The overrides of Freestyle's methods, the render engine's update callbacks and a gizmo's draw_select are in __init__.py:
an incompatible override would be an unexpected diagnostic there."""

from __future__ import annotations

import array
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
from bpy.props import BoolVectorProperty, FloatVectorProperty, IntVectorProperty
from bpy.types import (AnimData, Area, Armature, AssetShelf, Attribute, BlendData, BoneCollection, Camera,
                       ColorManagedDisplaySettings, ColorManagedViewSettings, Constraint, Context, Curve, Depsgraph,
                       DopeSheet, FreestyleModuleSettings, Gizmo, ID, Image, ImageStrip, Itasc, KeyMap, Library, Light,
                       Material, Mesh, MeshVertex, Modifier, Node, NodeTree, NodeTreeInterface, NodeTreeInterfaceSocket,
                       Object, Operator, OperatorProperties, Pose, PoseBone, Preferences, PropertyGroup, RenderEngine,
                       Scene, ShapeKey, ShapeKeyBezierPoint, ShapeKeyCurvePoint, ShapeKeyPoint, Space, SpaceGraphEditor,
                       SpaceNLA, Strip, StripCrop, StripTransform, Struct, UILayout, UserAssetLibrary, ViewLayer,
                       WorkSpaceTool, bpy_prop_collection, bpy_struct)
from bpy_extras.asset_utils import SpaceAssetInfo
from bpy_extras.anim_utils import BakeOptions
from freestyle.chainingiterators import pyChainSilhouetteGenericIterator
from freestyle.functions import pyDensityAnisotropyF1D
from freestyle.predicates import QuantitativeInvisibilityUP1D, TrueUP1D
from freestyle.shaders import ConstantThicknessShader, SamplingShader
from freestyle.types import (Interface0DIterator, Interface1D, Noise, Operators, Stroke, StrokeVertex,
                             UnaryFunction0DDouble, UnaryFunction1DDouble, UnaryPredicate1D, ViewEdge)
from freestyle.utils import BoundingBox, get_strokes, iter_distance_from_camera, iter_t2d_along_stroke, pairwise, stroke_normal
from gpu.types import Buffer, GPUFrameBuffer, GPUOffScreen, GPUShader, GPUStorageBuf, GPUVertFormat
from gpu_extras.batch import batch_for_shader
from imbuf.types import ImBuf, ImBufFileType
from mathutils import Matrix, Quaternion, Vector

from . import API_STUB_GAPS_OT_describe, bake_options

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]
AttributeData: TypeAlias = (
    bpy_prop_collection[bpy.types.BoolAttributeValue] | bpy_prop_collection[bpy.types.ByteColorAttributeValue] |
    bpy_prop_collection[bpy.types.ByteIntAttributeValue] | bpy_prop_collection[bpy.types.Float2AttributeValue] |
    bpy_prop_collection[bpy.types.Float4AttributeValue] | bpy_prop_collection[bpy.types.Float4x4AttributeValue] |
    bpy_prop_collection[bpy.types.FloatAttributeValue] | bpy_prop_collection[bpy.types.FloatColorAttributeValue] |
    bpy_prop_collection[bpy.types.FloatVectorAttributeValue] | bpy_prop_collection[bpy.types.Int2AttributeValue] |
    bpy_prop_collection[bpy.types.IntAttributeValue] | bpy_prop_collection[bpy.types.QuaternionAttributeValue] |
    bpy_prop_collection[bpy.types.Short2AttributeValue] | bpy_prop_collection[bpy.types.StringAttributeValue]
)


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


def id_data_owner(node: Node, pose_bone: PoseBone, modifier: Modifier, vertex: MeshVertex, strip: Strip) -> None:
    assert_type(node.id_data, NodeTree)  # bare-ok: a stub fact: a node's ID is its node tree
    assert_type(pose_bone.id_data, Object)  # bare-ok: a stub fact: a pose bone's is its armature object
    assert_type(modifier.id_data, Object)  # bare-ok: a stub fact: a modifier's is its object
    assert_type(vertex.id_data, Mesh)  # bare-ok: a stub fact: a mesh element's is its mesh
    assert_type(vertex.id_data.attributes.id_data, Mesh)  # bare-ok: a stub fact: and its attributes'
    assert_type(strip.id_data, Scene)  # bare-ok: a stub fact: a strip's is its scene


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


def animation_data_create(ob: Object, material: Material, scene: Scene, id_: ID) -> None:
    assert_type(ob.animation_data_create(), AnimData)  # bare-ok: a stub fact: an ID type with animation data always gets it
    assert_type(material.animation_data_create(), AnimData)  # bare-ok: a stub fact: an ID type with animation data always gets it
    assert_type(scene.animation_data_create(), AnimData)  # bare-ok: a stub fact: an ID type with animation data always gets it
    assert_type(id_.animation_data_create(), AnimData | None)  # bare-ok: a stub fact: None for an ID type without animation data


def gpu_buffers(buffer: Buffer, framebuffer: GPUFrameBuffer, storage: GPUStorageBuf, data: bytes,
                values: array.array[float]) -> None:
    assert_type(memoryview(buffer), memoryview)  # bare-ok: a stub fact: a gpu Buffer is a buffer
    assert_type(bytes(buffer), bytes)  # bare-ok: a stub fact: so bytes() copies it
    assert_type(list(buffer), list[Any])  # bare-ok: a stub fact: it iterates over its items (a value, or a row Buffer)
    assert_type(gpu.types.GPUStorageBuf(data), GPUStorageBuf)  # bare-ok: a stub fact: a storage buffer takes any buffer
    storage.update(values)  # a stub fact: and so does its update
    buffer.dimensions = 16  # a stub fact: the dimensions take an int
    buffer.dimensions = (4, 4)  # a stub fact: or a sequence of ints
    assert_type(buffer.dimensions, list[int])  # bare-ok: a stub fact: and read as a list
    with framebuffer.bind():  # a stub fact: a frame buffer binding is a context manager
        pass
    assert_type(framebuffer.bind(), AbstractContextManager[None])  # bare-ok: a stub fact: entering it gives None


def always_allocated(strip: ImageStrip, area: Area, graph: SpaceGraphEditor, nla: SpaceNLA) -> None:
    assert_type(strip.transform, StripTransform)  # bare-ok: a stub fact: allocated for every strip but a sound strip
    assert_type(strip.crop, StripCrop)  # bare-ok: a stub fact: allocated for every strip but a sound strip
    assert_type(area.spaces.active, Space)  # bare-ok: a stub fact: an area always has a space
    assert_type(graph.dopesheet, DopeSheet)  # bare-ok: a stub fact: the Graph editor allocates it
    assert_type(nla.dopesheet, DopeSheet)  # bare-ok: a stub fact: the NLA editor allocates it


def collection_items(data: BlendData) -> None:
    assert_type(data.objects.items(), list[tuple[str, Object]])  # bare-ok: a stub fact: (name, item) pairs
    assert_type(data.objects.values(), list[Object])  # bare-ok: a stub fact: the items


def shape_key_points(shape_key: ShapeKey) -> None:
    assert_type(shape_key.data[0], ShapeKeyPoint | ShapeKeyCurvePoint | ShapeKeyBezierPoint)  # bare-ok: a stub fact: refined by the Key's owner


def array_buffers(image: Image, values: array.array[float], vector: Vector) -> None:
    image.pixels.foreach_get(values)  # a stub fact: an array fills a buffer
    image.pixels.foreach_set(values)  # a stub fact: and reads one
    assert_type(vector.cross((0.0, 0.0, 1.0)), Vector | float)  # bare-ok: a stub fact: cross takes any sequence of floats


def refined_bases(pose: Pose, light: Light, library: UserAssetLibrary, attribute: Attribute,
                  bone_collection: BoneCollection) -> None:
    assert_type(pose.ik_param, Itasc | None)  # bare-ok: a stub fact: only the iTaSC solver has parameters
    assert_type(light.shadow_maximum_resolution, float)  # bare-ok: a stub fact: every light type declares it
    assert_type(library.path, str)  # bare-ok: a stub fact: both asset library types declare it
    assert_type(attribute.data, AttributeData)  # bare-ok: a stub fact: every attribute type declares it, of its values
    assert_type(bone_collection.id_data, Armature)  # bare-ok: a stub fact: a bone collection's ID is its armature


def matrix_get(self: bpy_struct) -> tuple[tuple[float, float], tuple[float, float]]:
    return (1.0, 0.0), (0.0, 1.0)


def matrix_set(self: bpy_struct, value: tuple[Any, ...]) -> None:
    pass


def docstring_types(view_settings: ColorManagedViewSettings, display_settings: ColorManagedDisplaySettings,
                    curve: Curve, data: BlendData, space: Space | None, shader: GPUShader,
                    indices: array.array[int], vertices: list[tuple[float, float]]) -> None:
    FloatVectorProperty(size=(2, 2), get=matrix_get, set=matrix_set)  # a stub fact: a nested sequence for a 2D size
    IntVectorProperty(size=(2, 2), get=lambda self: ((1, 0), (0, 1)))  # a stub fact: a nested sequence for a 2D size
    BoolVectorProperty(size=(2, 2), get=lambda self: ((True, False), (False, True)))  # a stub fact: and of bools
    assert_type(view_settings.view_transform, str)  # bare-ok: a stub fact: the view transforms of the OCIO configuration
    assert_type(view_settings.look, str)  # bare-ok: a stub fact: the looks of the OCIO configuration
    assert_type(display_settings.display_device, str)  # bare-ok: a stub fact: the displays of the OCIO configuration
    assert_type(curve.fill_mode, str)  # bare-ok: a stub fact: a 2D curve has other fill modes than a 3D one
    assert_type(data.curves.bl_rna, Struct)  # bare-ok: a stub fact: a collection with functions has their struct's bl_rna
    assert_type(data.curves.rna_type, Struct)  # bare-ok: a stub fact: and its rna_type
    assert_type(isinstance(data.curves.new, bpy.types.bpy_func), bool)  # bare-ok: a stub fact: the class of an RNA function
    assert_type(issubclass(bpy.types.bpy_struct_meta_idprop, type), bool)  # bare-ok: a stub fact: the metaclass of the classes with ID properties
    assert_type(SpaceAssetInfo.is_asset_browser(space), bool)  # bare-ok: a stub fact: it tests for None
    assert_type(bpy.path.ensure_ext(b"name", b".blend"), bytes)  # bare-ok: a stub fact: a bytes path gives bytes
    assert_type(bpy.path.ensure_ext("name", ".blend"), str)  # bare-ok: a stub fact: and a str path a str
    assert_type(bpy.types.UI_UL_list.filter_items_by_name("*", 1, data.objects), list[int])  # bare-ok: a stub fact: a collection's items
    assert_type(bpy.types.UI_UL_list.sort_items_by_name(data.objects), list[int])  # bare-ok: a stub fact: a collection's items
    batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)  # a stub fact: the indices take a buffer
