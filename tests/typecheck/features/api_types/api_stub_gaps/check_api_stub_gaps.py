"""Facts introspection alone left out of the stubs: class bases and Python __init__, iteration and context-manager
protocols, the version tuples, bl_rna, module members outside __all__ or not plain constants, a callback that may
return None, BMesh links of one element type, bpy.data's (name, library) key, the context store members Blender's UI
sets, the context managers, positional callbacks, dynamic enums and two documented returns. These are stub facts.
The overrides of Freestyle's methods and of the render engine's update callbacks are in __init__.py: an incompatible
override would be an unexpected diagnostic there."""

from __future__ import annotations

from contextlib import AbstractContextManager
from types import MappingProxyType
from typing import Any, Literal, TypeAlias, assert_type

import bpy
import imbuf
from bmesh.types import BMEdge, BMElemSeq, BMesh, BMFace, BMLoop, BMVert
from bpy.types import (AssetShelf, BlendData, Camera, Constraint, Context, FreestyleModuleSettings, Gizmo, ID, KeyMap,
                       Library, Material, Node, NodeTreeInterface, NodeTreeInterfaceSocket, Object, Operator,
                       OperatorProperties, Preferences, RenderEngine, Scene, Struct, ViewLayer, WorkSpaceTool)
from bpy_extras.anim_utils import BakeOptions
from freestyle.chainingiterators import pyChainSilhouetteGenericIterator
from freestyle.functions import pyDensityAnisotropyF1D
from freestyle.predicates import QuantitativeInvisibilityUP1D
from freestyle.types import UnaryFunction1DDouble, UnaryPredicate1D, ViewEdge
from imbuf.types import ImBuf, ImBufFileType
from mathutils import Matrix, Vector

from . import API_STUB_GAPS_OT_describe, bake_options

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


def as_predicate(predicate: UnaryPredicate1D) -> UnaryPredicate1D:
    return predicate


def as_function(function: UnaryFunction1DDouble) -> UnaryFunction1DDouble:
    return function


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


def versions(data: BlendData, preferences: Preferences, library: Library) -> None:
    assert_type(data.version, tuple[int, int, int])  # bare-ok: a stub fact: a thick-wrapped array is a tuple
    assert_type(preferences.version, tuple[int, int, int])  # bare-ok: a stub fact: a thick-wrapped array is a tuple
    assert_type(library.version, tuple[int, int, int])  # bare-ok: a stub fact: a thick-wrapped array is a tuple
    assert_type(preferences.version >= (4, 2, 0), bool)  # bare-ok: a stub fact: so it compares with a tuple


def bl_rna(ob: Object) -> None:
    assert_type(Operator.bl_rna, Struct)  # bare-ok: a stub fact: every RNA class has bl_rna
    assert_type(ob.bl_rna, Struct)  # bare-ok: a stub fact: readable from an instance too


def module_members() -> None:
    assert_type(bpy.utils.system_resource('SCRIPTS'), str)  # bare-ok: a stub fact: public, though not in __all__
    assert_type(bpy.utils.is_path_builtin(""), bool)  # bare-ok: a stub fact: public, though not in __all__
    assert_type(bpy.path.extensions_image, frozenset[str])  # bare-ok: a stub fact: a frozenset in __all__
    assert_type(imbuf.file_types, MappingProxyType[str, ImBufFileType])  # bare-ok: a stub fact: a read-only dict


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
