"""Reference stub delta: the properties the addon registers, and those of the add-on it declares."""

from regchk_uses_provider import REGCHK_USES_PROVIDER_Settings

class Scene:
    @property
    def regchk_uses_provider(self) -> REGCHK_USES_PROVIDER_Settings: ...
    regchk_uses_shared: str

class Object:
    regchk_uses_provider_count: int
    regchk_uses_label: str
