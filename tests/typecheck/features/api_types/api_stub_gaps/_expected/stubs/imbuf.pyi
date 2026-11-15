"""Reference stub delta: imbuf's read-only dict of file types."""

from types import MappingProxyType

from imbuf.types import ImBufFileType

file_types: MappingProxyType[str, ImBufFileType]
