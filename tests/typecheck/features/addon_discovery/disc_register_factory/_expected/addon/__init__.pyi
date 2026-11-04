"""Reference stub of disc_register_factory."""

from collections.abc import Callable

from bpy.types import Operator

class DISC_REGISTER_FACTORY_OT_run(Operator):
    count: int

classes: tuple[type[DISC_REGISTER_FACTORY_OT_run]]
register: Callable[[], None]
unregister: Callable[[], None]
