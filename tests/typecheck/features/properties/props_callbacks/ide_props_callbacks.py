"""What the editor shows for annotated properties (check:ide; never imported).

The code under a ^completion marker is unfinished, as the user types it; check:features does not check ide_*.py
files, so the errors it causes do not count.
"""

from __future__ import annotations

from . import PROPS_CALLBACKS_Settings


def hover(s: PROPS_CALLBACKS_Settings) -> None:
    s.count
    # ^hover
    # ^hover-contains "int"
    s.target
    # ^hover-contains "Object"
    s.ratio
    # ^hover-contains "float"


def completion(s: PROPS_CALLBACKS_Settings) -> None:
    s.cou
    #    ^completion count
    s.lambda_
    #        ^completion lambda_update lambda_poll lambda_items lambda_get
