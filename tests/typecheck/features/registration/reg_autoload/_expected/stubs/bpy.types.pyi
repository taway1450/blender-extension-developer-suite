"""Reference stub delta: the property reg_autoload's PropertyGroup.register() adds to Scene."""

from reg_autoload.settings import REG_AUTOLOAD_PG_settings

class Scene:
    @property
    def reg_autoload_settings(self) -> REG_AUTOLOAD_PG_settings: ...
