"""What the editor shows for wrapped properties (check:ide; never imported).

The code under a ^completion marker is unfinished, as the user types it; check:features does not check ide_*.py
files, so the errors it causes do not count.
"""

from __future__ import annotations

from . import WRAP_VALUES_Settings


def hover(s: WRAP_VALUES_Settings) -> None:
    s.common_a
    # ^hover-contains "int"
    s.alias
    # ^hover-contains "float"
    s.partial_color
    # ^hover-contains "Color"
    s.wrapped_size
    # ^hover-contains "Vector"


def completion(s: WRAP_VALUES_Settings) -> None:
    s.from_
    #      ^completion from_dict from_dict_str from_tuple from_tuple_bool
