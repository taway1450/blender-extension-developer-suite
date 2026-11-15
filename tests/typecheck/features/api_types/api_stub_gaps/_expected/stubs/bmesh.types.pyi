"""Reference stub delta: BMesh sequences iterate over their elements."""

from collections.abc import Iterator

class BMVertSeq:
    def __iter__(self) -> Iterator[BMVert]: ...

class BMEdgeSeq:
    def __iter__(self) -> Iterator[BMEdge]: ...

class BMFaceSeq:
    def __iter__(self) -> Iterator[BMFace]: ...

class BMEditSelSeq:
    def __iter__(self) -> Iterator[BMVert | BMEdge | BMFace]: ...
