"""Reference stub delta: a dynamic enum's items come from a callback, so it takes any str."""

from typing import Literal

def set_material(*, slot: str = "DEFAULT") -> set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]: ...
