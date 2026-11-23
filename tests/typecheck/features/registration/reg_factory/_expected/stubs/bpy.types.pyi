"""Reference stub delta: the Scene properties and the classes the addon registers."""

from reg_factory import REG_FACTORY_OT_first as REG_FACTORY_OT_first
from reg_factory import SecondOperator as _SecondOperator

REG_FACTORY_OT_second = _SecondOperator

class Scene:
    reg_factory_label: str
