"""Reference stub of inh_chains."""

from bpy.types import Menu, Operator, Panel, PropertyGroup

class INH_CHAINS_OT_base(Operator):
    count: int

class INH_CHAINS_OT_middle(INH_CHAINS_OT_base):
    label: str

class INH_CHAINS_OT_leaf(INH_CHAINS_OT_middle):
    factor: float

class INH_CHAINS_OT_sibling(INH_CHAINS_OT_base): ...

class INH_CHAINS_A(PropertyGroup):
    a: int

class INH_CHAINS_B(INH_CHAINS_A):
    b: str

class INH_CHAINS_C(INH_CHAINS_B):
    c: float

class INH_CHAINS_PT_base(Panel): ...
class INH_CHAINS_PT_main(INH_CHAINS_PT_base): ...
class INH_CHAINS_PT_sub(INH_CHAINS_PT_base): ...
class INH_CHAINS_MT_base(Menu): ...
class INH_CHAINS_MT_one(INH_CHAINS_MT_base): ...
class INH_CHAINS_MT_two(INH_CHAINS_MT_base): ...

def register() -> None: ...
def unregister() -> None: ...
