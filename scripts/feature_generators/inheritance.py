"""Generated addons for the ``inheritance`` feature: one addon per class Blender rejects at registration (a callback
signature it does not accept, a required callback that is missing). Each addon registers only that class, so
check:load confirms each mistake on its own, and ``_expected/runtime.toml`` names the error Blender raises.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._common import manifest, python_file

MODULE = "inheritance"

PANEL = ['bl_label = "Invalid"', 'bl_space_type = "VIEW_3D"', 'bl_region_type = "UI"']
UL_ALL = "self, context, layout, data, item, icon, active_data, active_property, index, flt_flag"


@dataclass
class Case:
    name: str
    doc: str
    base: str  # Blender base class
    body: list[str]  # class body; the marker goes on the line that ends with "#!"
    rule: str
    error: str  # text Blender's error contains
    on_class: bool = False  # the marker goes on the class line instead


def op(*body: str) -> list[str]:
    return ['bl_idname = "{id}.run"', 'bl_label = "Invalid"', "", *body]


def method(signature: str, result: str = '{"FINISHED"}', decorator: str = "") -> list[str]:
    return [*([decorator] if decorator else []), f"def {signature}:  #!", f"    return {result}"]


CASES = [
    Case(
        "inh_invalid_execute_fewer",
        "execute without the context parameter",
        "Operator",
        op(*method("execute(self)")),
        "blender-invalid-override",
        '"execute" function to have 2 args, found 1',
    ),
    Case(
        "inh_invalid_execute_default",
        "execute with an extra parameter that has a default (defaults count)",
        "Operator",
        op(*method("execute(self, context, extra=None)")),
        "blender-invalid-override",
        '"execute" function to have 2 args, found 3',
    ),
    Case(
        "inh_invalid_execute_varargs",
        "execute(self, *args): *args does not stand for the context",
        "Operator",
        op(*method("execute(self, *args)")),
        "blender-invalid-override",
        '"execute" function to have 2 args, found 1',
    ),
    Case(
        "inh_invalid_execute_classmethod",
        "execute as a classmethod",
        "Operator",
        op(*method("execute(cls, context)", decorator="@classmethod")),
        "blender-invalid-override",
        "to be a function, not a method",
    ),
    Case(
        "inh_invalid_invoke_fewer",
        "invoke without the event parameter",
        "Operator",
        op(*method("invoke(self, context)")),
        "blender-invalid-override",
        '"invoke" function to have 3 args, found 2',
    ),
    Case(
        "inh_invalid_poll_instance",
        "poll as an instance method",
        "Operator",
        op(*method("poll(self, context)", "True")),
        "blender-invalid-override",
        "to be a static/class method",
    ),
    Case(
        "inh_invalid_poll_static",
        "poll as a staticmethod",
        "Operator",
        op(*method("poll(context)", "True", "@staticmethod")),
        "blender-invalid-override",
        '"poll" attribute to be a static/class method',
    ),
    Case(
        "inh_invalid_poll_fewer",
        "poll without the context parameter",
        "Operator",
        op(*method("poll(cls)", "True", "@classmethod")),
        "blender-invalid-override",
        '"poll" function to have 2 args, found 1',
    ),
    Case(
        "inh_invalid_description_instance",
        "description as an instance method",
        "Operator",
        op(*method("description(self, context, properties)", '""')),
        "blender-invalid-override",
        "to be a static/class method",
    ),
    Case(
        "inh_invalid_draw_item_fewer",
        "UIList.draw_item with 6 parameters (it takes 7 to 10)",
        "UIList",
        method("draw_item(self, context, layout, data, item, icon)", "None"),
        "blender-invalid-override",
        '"draw_item" function to have between 10 and 7 args',
    ),
    Case(
        "inh_invalid_draw_item_more",
        "UIList.draw_item with 11 parameters (it takes 7 to 10)",
        "UIList",
        method(f"draw_item({UL_ALL}, extra)", "None"),
        "blender-invalid-override",
        '"draw_item" function to have between 10 and 7 args',
    ),
    Case(
        "inh_invalid_panel_draw_extra",
        "Panel.draw with an extra parameter",
        "Panel",
        [*PANEL, "", *method("draw(self, context, extra)", "None")],
        "blender-invalid-override",
        '"draw" function to have 2 args, found 3',
    ),
    Case(
        "inh_invalid_draw_header_extra",
        "Panel.draw_header with an extra parameter",
        "Panel",
        [*PANEL, "", *method("draw_header(self, context, extra)", "None"), "", "def draw(self, context):", "    pass"],
        "blender-invalid-override",
        '"draw_header" function to have 2 args, found 3',
    ),
    Case(
        "inh_invalid_menu_draw_default",
        "Menu.draw with an extra parameter that has a default",
        "Menu",
        ['bl_label = "Invalid"', "", *method("draw(self, context, extra=1)", "None")],
        "blender-invalid-override",
        '"draw" function to have 2 args, found 3',
    ),
    Case(
        "inh_invalid_panel_no_draw",
        "a Panel without draw",
        "Panel",
        PANEL,
        "blender-missing-callback",
        '"draw" attribute',
        on_class=True,
    ),
    Case(
        "inh_invalid_menu_no_draw",
        "a Menu without draw",
        "Menu",
        ['bl_label = "Invalid"'],
        "blender-missing-callback",
        '"draw" attribute',
        on_class=True,
    ),
    Case(
        "inh_invalid_header_no_draw",
        "a Header without draw",
        "Header",
        ['bl_space_type = "VIEW_3D"'],
        "blender-missing-callback",
        '"draw" attribute',
        on_class=True,
    ),
    Case(
        "inh_invalid_socket_no_draw",
        "a NodeSocket without draw",
        "NodeSocket",
        ['bl_idname = "{prefix}_Socket"', 'bl_label = "Invalid"'],
        "blender-missing-callback",
        '"draw" attribute',
        on_class=True,
    ),
]


def init_file(case: Case) -> str:
    prefix = case.name.upper()
    suffix = {
        "Operator": "_OT_run",
        "UIList": "_UL_list",
        "Panel": "_PT_panel",
        "Menu": "_MT_menu",
        "Header": "_HT_header",
        "NodeSocket": "_Socket",
    }[case.base]
    cls = prefix + suffix
    marker = f"  # ty: ignore[{case.rule}]"
    body = []
    for line in case.body:
        line = line.replace("{id}", case.name).replace("{prefix}", prefix)
        body.append(line[: -len("  #!")] + marker if line.endswith("  #!") else line)
    head = f"class {cls}({case.base}):" + (marker if case.on_class else "")
    lines = [
        "import bpy",
        f"from bpy.types import {case.base}",
        "",
        "",
        head,
        *(f"    {line}" if line else "" for line in body),
        "",
        "",
        f"classes = ({cls},)",
        "register, unregister = bpy.utils.register_classes_factory(classes)",
    ]
    doc = (
        f"Feature test: {case.rule}: {case.doc}. Blender rejects the class when it is registered (checked in "
        "Blender 4.2 and 5.4)."
    )
    return python_file(MODULE, doc, "\n".join(lines))


def generate() -> dict[str, str]:
    files = {}
    for case in CASES:
        files[f"{case.name}/blender_manifest.toml"] = manifest(case.name, f"Feature test: {case.name}", case.doc)
        files[f"{case.name}/__init__.py"] = init_file(case)
        files[f"{case.name}/_expected/runtime.toml"] = (
            f"# Generated by scripts/generate_features.py ({MODULE}); do not edit.\n"
            f'register = "fails"\nreason = "{case.doc}"\nerror = \'{case.error}\'\n'
        )
    return files
