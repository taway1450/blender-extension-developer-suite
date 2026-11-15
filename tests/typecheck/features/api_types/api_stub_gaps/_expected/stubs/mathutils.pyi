"""Reference stub delta: a matrix row or column is a Vector."""

from collections.abc import Iterator

class MatrixAccess:
    def __getitem__(self, key: int, /) -> Vector: ...
    def __iter__(self) -> Iterator[Vector]: ...
