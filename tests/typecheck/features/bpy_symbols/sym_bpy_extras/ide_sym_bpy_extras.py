"""What the editor shows for the properties @orientation_helper adds (check:ide; never imported).

The code under a ^completion marker is unfinished, as the user types it; check:features does not check ide_*.py
files, so the errors it causes do not count.
"""

from __future__ import annotations

from . import SYM_BPY_EXTRAS_OT_import


def hover(imp: SYM_BPY_EXTRAS_OT_import) -> None:
    imp.axis_up
    #   ^hover-contains "-Z"


def completion(imp: SYM_BPY_EXTRAS_OT_import) -> None:
    imp.axis_
    #        ^completion axis_forward axis_up
