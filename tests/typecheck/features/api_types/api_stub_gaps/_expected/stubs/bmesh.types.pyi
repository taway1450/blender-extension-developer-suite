"""Reference stub delta: BMesh sequences iterate over their elements, and an element link is a BMElemSeq of one
element type. An element is indexed by a custom-data layer."""

from collections.abc import Iterator
from typing import Any, Generic, TypeVar, overload

class BMVertSeq:
    def __iter__(self) -> Iterator[BMVert]: ...

class BMEdgeSeq:
    def __iter__(self) -> Iterator[BMEdge]: ...

class BMFaceSeq:
    def __iter__(self) -> Iterator[BMFace]: ...

class BMEditSelSeq:
    def __iter__(self) -> Iterator[BMVert | BMEdge | BMFace]: ...

_T = TypeVar("_T")

class BMElemSeq(Generic[_T]):
    @overload
    def __getitem__(self, key: int, /) -> _T: ...
    @overload
    def __getitem__(self, key: slice, /) -> list[_T]: ...
    def __iter__(self) -> Iterator[_T]: ...

class BMVert:
    link_faces: BMElemSeq[BMFace]

class BMEdge:
    verts: BMElemSeq[BMVert]

class BMFace:
    verts: BMElemSeq[BMVert]
    edges: BMElemSeq[BMEdge]
    loops: BMElemSeq[BMLoop]

class BMLoop:
    link_loops: BMElemSeq[BMLoop]
    def __getitem__(self, key: BMLayerItem, /) -> Any: ...
    def __setitem__(self, key: BMLayerItem, value: Any, /) -> None: ...
