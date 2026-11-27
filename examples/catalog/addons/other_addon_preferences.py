# /// catalog
# title = "Preferences of another add-on"
# section = "preferences"
# status = "handled"
# safeguards = ["stub-generator"]
# features = ["addon_preferences"]
# ///
"""Another add-on's `preferences` are `None` until it registers its class, and their class is not known to this
add-on. The stub type `AddonPreferences | None` says so, so a read needs a check first. (Indexing `addons` with the
name of an add-on that is not enabled raises `KeyError`; `addons.get()` gives `None` instead.)"""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import AddonPreferences, Preferences


def example(preferences: Preferences) -> None:
    other = preferences.addons["node_wrangler"].preferences
    assert_type(other, AddonPreferences | None)
    other.bl_idname  # ty: ignore[missing-union-attribute]
    if other is not None:
        print(other.bl_idname)
