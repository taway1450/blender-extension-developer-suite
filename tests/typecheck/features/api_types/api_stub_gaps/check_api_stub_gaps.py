"""Facts introspection alone left out of the stubs: class bases and Python __init__, iteration and context-manager
protocols, the version tuples, bl_rna, module members outside __all__ or not plain constants, and a callback that may
return None. These are stub facts."""

from __future__ import annotations

from types import MappingProxyType
from typing import assert_type

import bpy
import imbuf
from bmesh.types import BMEdge, BMesh, BMFace, BMVert
from bpy.types import BlendData, Context, Library, Object, Operator, OperatorProperties, Preferences, Struct
from bpy_extras.anim_utils import BakeOptions
from freestyle.chainingiterators import pyChainSilhouetteGenericIterator
from freestyle.functions import pyDensityAnisotropyF1D
from freestyle.predicates import QuantitativeInvisibilityUP1D
from freestyle.types import UnaryFunction1DDouble, UnaryPredicate1D, ViewEdge
from imbuf.types import ImBuf, ImBufFileType
from mathutils import Matrix, Vector

from . import API_STUB_GAPS_OT_describe


def as_predicate(predicate: UnaryPredicate1D) -> UnaryPredicate1D:
    return predicate


def as_function(function: UnaryFunction1DDouble) -> UnaryFunction1DDouble:
    return function


def classes(edge: ViewEdge, iterator: pyChainSilhouetteGenericIterator, options: BakeOptions) -> None:
    assert_type(edge.length_2d, float)  # bare-ok: a stub fact: a ViewEdge is an Interface1D
    assert_type(iterator.is_begin, bool)  # bare-ok: a stub fact: a Python chaining iterator is a ChainingIterator
    assert_type(as_predicate(QuantitativeInvisibilityUP1D(0)), UnaryPredicate1D)  # bare-ok: a stub fact: a C predicate's base
    assert_type(as_function(pyDensityAnisotropyF1D(4)), UnaryFunction1DDouble)  # bare-ok: a stub fact: a Python class's base and __init__
    assert_type(BakeOptions(only_selected=True, do_pose=True, do_object=False, do_visual_keying=False, do_constraint_clear=False, do_parents_clear=False, do_clean=True, do_location=True, do_rotation=True, do_scale=True, do_bbone=True, do_custom_props=False), BakeOptions)  # bare-ok: a stub fact: a dataclass's __init__
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
