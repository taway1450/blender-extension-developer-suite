"""Checks for props_id_data_opaque."""

from typing import assert_type

from bpy.types import Scene

from . import PROPS_ID_DATA_OPAQUE_Group


def opaque_owner(group: PROPS_ID_DATA_OPAQUE_Group) -> None:
    # The Object registration may store this group too: the Scene alone is not known.
    assert_type(group.id_data, Scene)  # ty: ignore[type-assertion-failure]  # bare-ok: the stubs' type stays
