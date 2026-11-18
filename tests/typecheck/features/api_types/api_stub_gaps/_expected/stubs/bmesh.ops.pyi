"""Reference stub delta: an element buffer takes any sequence of its elements, the mesh's sequence of each of its
element types or an element sequence of one."""

from collections.abc import Sequence
from typing import Any, Literal

from bmesh.types import BMEdge, BMEdgeSeq, BMElemSeq, BMesh, BMFace, BMFaceSeq, BMVert, BMVertSeq

def dissolve_verts(bm: BMesh, verts: Sequence[BMVert] | BMVertSeq | BMElemSeq[BMVert] = [], use_face_split: bool = False, use_boundary_tear: bool = False) -> None: ...
def triangulate(bm: BMesh, faces: Sequence[BMFace] | BMFaceSeq | BMElemSeq[BMFace] = [], quad_method: Literal['BEAUTY', 'FIXED', 'ALTERNATE', 'SHORT_EDGE', 'LONG_EDGE'] = 'BEAUTY', ngon_method: Literal['BEAUTY', 'EAR_CLIP'] = 'BEAUTY') -> dict[str, Any]: ...
def delete(bm: BMesh, geom: Sequence[BMVert | BMEdge | BMFace] | BMVertSeq | BMEdgeSeq | BMFaceSeq | BMElemSeq[BMVert] | BMElemSeq[BMEdge] | BMElemSeq[BMFace] = [], context: Literal['VERTS', 'EDGES', 'FACES_ONLY', 'EDGES_FACES', 'FACES', 'FACES_KEEP_BOUNDARY', 'TAGGED_ONLY'] = 'VERTS') -> None: ...
