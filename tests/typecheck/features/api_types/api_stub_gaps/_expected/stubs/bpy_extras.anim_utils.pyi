"""Reference stub delta: a dataclass has its generated __init__ and its fields."""

class BakeOptions:
    def __init__(self, only_selected: bool, do_pose: bool, do_object: bool, do_visual_keying: bool, do_constraint_clear: bool, do_parents_clear: bool, do_clean: bool, do_location: bool, do_rotation: bool, do_scale: bool, do_bbone: bool, do_custom_props: bool) -> None: ...
    do_pose: bool
