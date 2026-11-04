"""Reference stub delta: persistent returns the decorated function; load handlers get (filepath, None)."""

from collections.abc import Callable

def persistent[F](func: F, /) -> F: ...
load_post: list[Callable[[str, None], None]]
