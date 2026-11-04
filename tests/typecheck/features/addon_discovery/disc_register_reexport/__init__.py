"""Feature test: __init__.py only re-exports register and unregister from a submodule."""

from .core import register, unregister

__all__ = ["register", "unregister"]
