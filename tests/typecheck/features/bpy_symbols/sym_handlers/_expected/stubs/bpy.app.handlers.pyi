"""Reference stub delta: persistent returns the decorated function; a load handler gets (filepath,) if it takes one
parameter, (filepath, None) otherwise."""

from collections.abc import Callable

def persistent[F](func: F, /) -> F: ...
load_post: list[Callable[[str], None] | Callable[[str, None], None]]
