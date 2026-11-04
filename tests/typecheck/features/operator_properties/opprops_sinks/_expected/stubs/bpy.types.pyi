"""Reference stub delta: the idname overloads the checker adds for opprops_sinks' operators."""

from typing import Any, Literal, overload

class _opprops_sinks_step_properties(bpy_struct):
    amount: int
    mode: Literal["A", "B"]
    label: str
    flags: set[Literal["A", "B"]]

class _opprops_sinks_bare_properties(bpy_struct): ...

class _opprops_sinks_step_keymap_item(KeyMapItem):
    @property
    def properties(self) -> _opprops_sinks_step_properties: ...

class _opprops_sinks_step_macro(OperatorMacro):
    @property
    def properties(self) -> _opprops_sinks_step_properties: ...

class UILayout:
    @overload
    def operator(self, operator: Literal["opprops_sinks.step", "OPPROPS_SINKS_OT_step"], **kwargs: Any) -> _opprops_sinks_step_properties: ...
    @overload
    def operator(self, operator: Literal["opprops_sinks.bare", "OPPROPS_SINKS_OT_bare"], **kwargs: Any) -> _opprops_sinks_bare_properties: ...
    @overload
    def operator_menu_hold(self, operator: Literal["opprops_sinks.step", "OPPROPS_SINKS_OT_step"], **kwargs: Any) -> _opprops_sinks_step_properties: ...
    @overload
    def operator_menu_enum(self, operator: Literal["opprops_sinks.step", "OPPROPS_SINKS_OT_step"], property: Literal["mode", "flags"], **kwargs: Any) -> _opprops_sinks_step_properties: ...
    @overload
    def operator_enum(self, operator: Literal["opprops_sinks.step", "OPPROPS_SINKS_OT_step"], property: Literal["mode", "flags"], **kwargs: Any) -> None: ...

class KeyMapItems:
    @overload
    def new(self, idname: Literal["opprops_sinks.step", "OPPROPS_SINKS_OT_step"], type: Any, value: Any, **kwargs: Any) -> _opprops_sinks_step_keymap_item: ...

class WindowManager:
    @overload
    @classmethod
    def operator_properties_last(cls, operator: Literal["opprops_sinks.step", "OPPROPS_SINKS_OT_step"]) -> _opprops_sinks_step_properties: ...

class Gizmo:
    @overload
    def target_set_operator(self, operator: Literal["opprops_sinks.step", "OPPROPS_SINKS_OT_step"], **kwargs: Any) -> _opprops_sinks_step_properties: ...

class WorkSpaceTool:
    @overload
    def operator_properties(self, operator: Literal["opprops_sinks.step", "OPPROPS_SINKS_OT_step"]) -> _opprops_sinks_step_properties: ...

class Macro:
    @overload
    @classmethod
    def define(cls, operator: Literal["opprops_sinks.step", "OPPROPS_SINKS_OT_step"]) -> _opprops_sinks_step_macro: ...
