"""Stand-ins for the UI that the probe scripts draw on in background Blender, which has no editors: a layout, the
panel, menu or list instance passed as ``self``, and a context (shared by ``probe_ui_draw.py`` and
``probe_node_menus.py``).

A probe script makes this directory importable first, as for ``_recorder.py``.
"""

from __future__ import annotations

import inspect
import types

import bpy

# The UILayout methods that take an RNA pointer (positionally first, or by keyword), as Blender's
# `PROP_NEVER_NULL` parameters: None raises TypeError.
POINTER_ARGS = {
    "prop": ("data",),
    "prop_enum": ("data",),
    "prop_menu_enum": ("data",),
    "prop_with_popover": ("data",),
    "prop_with_menu": ("data",),
    "props_enum": ("data",),
    "prop_search": ("data", "search_data"),
    "template_ID": ("data",),
    "template_any_ID": ("data",),
    "template_search": ("data", "search_data"),
    "template_color_picker": ("data",),
    "template_curveprofile": ("data",),
    "template_list": ("dataptr", "active_dataptr"),
}

# Positional parameter names of the methods above (template_list takes two names first).
POSITIONAL = {
    "prop_search": ("data", "property", "search_data"),
    "template_search": ("data", "property", "search_data"),
    "template_list": ("listtype_name", "list_id", "dataptr", "propname", "active_dataptr"),
}


class ProbeError(Exception):
    """The state a check needs could not be built, or the draw broke a rule of the stub."""


class StubProperties:
    """An operator's properties: anything can be set."""

    def __getattr__(self, name: str):
        return None


def check_pointers(method: str, args: tuple, kwargs: dict) -> None:
    names = POSITIONAL.get(method, ("data", "property"))
    bound = dict(zip(names, args))
    bound.update(kwargs)
    for param in POINTER_ARGS[method]:
        if param in bound and bound[param] is None:
            raise TypeError(f"UILayout.{method}(): {param!r} does not support a 'None' assignment")
    data, prop = bound.get("data"), bound.get("property")
    if isinstance(data, bpy.types.bpy_struct) and isinstance(prop, str) and not hasattr(data, prop):
        raise AttributeError(f"UILayout.{method}(): property {prop!r} not found in {type(data).__name__}")


class StubLayout:
    """Records nothing; checks the pointer arguments of the methods that take one. Every other method returns a
    sub-layout (``sub_layout()``, which a subclass overrides to record into the same place)."""

    def __init__(self) -> None:
        object.__setattr__(self, "_attrs", {"operator_context": "INVOKE_DEFAULT", "property_split_factor": 0.4})

    def sub_layout(self) -> StubLayout:
        return StubLayout()

    def operator(self, *_args, **_kwargs):
        return StubProperties()

    def panel(self, *_args, **_kwargs):
        return self.sub_layout(), self.sub_layout()

    def panel_prop(self, *_args, **_kwargs):
        return self.sub_layout(), self.sub_layout()

    def __getattr__(self, name: str):
        if name in self._attrs:
            return self._attrs[name]

        def method(*args, **kwargs):
            if name in POINTER_ARGS:
                check_pointers(name, args, kwargs)
            return self.sub_layout()

        return method

    def __setattr__(self, name: str, value) -> None:
        self._attrs[name] = value


class StandIn:
    """Stands in for the panel, menu or list instance Blender passes to ``draw``: reads the class ``cls`` (binding
    its functions to the stand-in), with a ``layout`` and the given attributes."""

    def __init__(self, cls: type, layout: StubLayout | None = None, **attrs) -> None:
        object.__setattr__(self, "_cls", cls)
        object.__setattr__(self, "_attrs", {"layout": layout or StubLayout(), "is_popover": False, **attrs})

    def __getattr__(self, name: str):
        if name in self._attrs:
            return self._attrs[name]
        value = getattr(self._cls, name)
        if isinstance(inspect.getattr_static(self._cls, name), types.FunctionType):
            return types.MethodType(value, self)
        return value

    def __setattr__(self, name: str, value) -> None:
        self._attrs[name] = value


class Context:
    """The given members; every other member from ``bpy.context``."""

    def __init__(self, **members) -> None:
        self._members = members

    def __getattr__(self, name: str):
        members = self.__dict__["_members"]
        if name in members:
            return members[name]
        return getattr(bpy.context, name)
