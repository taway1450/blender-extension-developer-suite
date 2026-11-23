"""Reference stub delta: the private handler lists addon_utils and the Extensions add-on use."""

from collections.abc import Callable

_extension_repos_update_pre: list[Callable[..., None]]
_extension_repos_update_post: list[Callable[..., None]]
_extension_repos_sync: list[Callable[..., None]]
_extension_repos_files_clear: list[Callable[..., None]]
