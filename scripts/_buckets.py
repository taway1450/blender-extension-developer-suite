"""Sort check:blender's diagnostics into causes, each with a group, and into areas of the Blender source.

A **cause** is why a diagnostic is reported; its **group** says where the fix belongs (spec #95):

- ``blender-fix``: Blender's own Python code is wrong (slices BF1, BF2);
- ``assumption`` / ``implied-narrowing`` / ``imprecise-annotation``: right code the typechecker accepts and reports
  under a dedicated ``blender-*`` rule (S6, S5, S4);
- ``typechecker-fix``: RNA flags, the stub generator or ``ty_blender`` (S1, S2, S3);
- ``typing-debt``: out of scope (general typing debt, or a cause the spec leaves as it is);
- ``unsorted``: recognised kinds with no slice, and everything else.

``CAUSES`` is a first-match table over a diagnostic's rule, message, the source line it points at (read from the
worktree ty just checked, so message and line always belong together), its path and its enclosing class and
function (``Scope``). Each cause names the slice that addresses it. The patterns come from the spec's slices and
the research on the ``research/*`` branches (``blender-true-problems``, ``false-positive-fixes``,
``candidate-assumptions``, ``imprecise-patterns``, ``silent-assumptions``, ``stub-gaps``, ``check-blender-setup``).
The causes of the Imprecise annotations, Implied narrowings and Assumptions (S4-S6) are their dedicated rules
(``blender-narrowed-by-poll``, ...): an error of the same shape is code the rule did not accept.
``area(path)`` names the part of the source tree a path is in.
"""

from __future__ import annotations

import collections
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from pathlib import Path

GROUPS = [
    "blender-fix",
    "assumption",
    "implied-narrowing",
    "imprecise-annotation",
    "typechecker-fix",
    "typing-debt",
    "unsorted",
]

DIAGNOSTIC_LINE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):\d+: (?P<severity>\w+)\[(?P<rule>[\w-]+)\] (?P<msg>.*)$", re.MULTILINE
)

AREAS = [
    (
        "shipped",
        (
            "scripts/startup/",
            "scripts/modules/",
            "scripts/addons_core/",
            "scripts/freestyle/",
            "intern/cycles/blender/addon/",
        ),
    ),
    ("presets", ("scripts/presets/",)),
    ("examples", ("doc/python_api/examples/",)),
    ("templates", ("scripts/templates_py/",)),
]
AREA_NAMES = [name for name, _ in AREAS] + ["other"]


@dataclass(frozen=True)
class Scope:
    """Where a diagnostic sits: the enclosing class (name and bases as written), the enclosing function and its
    parameter names, whether the class defines ``poll`` itself, and the Registered property names its file assigns
    (``bpy.types.X.name = <Property>(...)``)."""

    cls: str = ""
    bases: str = ""
    function: str = ""
    params: tuple[str, ...] = ()
    has_poll: bool = False
    registers: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Diagnostic:
    path: str  # relative to the source root, as ty prints it
    line: int
    rule: str
    msg: str
    text: str  # the source line
    severity: str = "error"
    scope: Scope = field(default_factory=Scope)

    @property
    def cause(self) -> Cause:
        return cause(self)

    @property
    def area(self) -> str:
        return area(self.path)


@dataclass(frozen=True)
class Cause:
    name: str
    group: str
    slice: str  # the spec slice that addresses it, "" when none
    matches: Callable[[Diagnostic], bool]
    rule: str = ""  # the dedicated blender-* rule that reports it once its slice has landed


# --- facts read off a diagnostic -------------------------------------------------------------------------------

NULLABLE = re.compile(r"\| None`|`None \||in union `[^`]*None|found `[^`]*\| None`")
STRING_LITERAL = re.compile(r"""['"]""")
CONTEXT = r"\b(?:context|ctx|C|_context)\."

OPERATOR_RETURNS = {"execute", "invoke", "modal"}
INTERACTIVE_CALLBACKS = {"invoke", "modal", "exit"}
UI_ROOTS = {"panel", "menu", "header", "uilist"}
UI_DRAW_CALLBACKS = {"draw", "draw_header", "draw_header_preset", "draw_item", "draw_filter"}
# Callback parameters Blender always fills, by position counting ``self``/``cls`` (S1); ``draw_item``'s ``item``
# (position 4) is the list-item Assumption (S6) instead.
NEVER_NONE_PARAMETERS = {
    "draw_item": {3},
    "filter_items": {3},
    "iterator": {2},
    "generate": {2},
    "asset_poll": {1},
    "draw_context_menu": {2, 3},
    "update": {2},
    "render": {1},
    "bake": {1},
    "view_update": {2},
    "view_draw": {2},
}
CONTEXT_STORE_MEMBERS = {"constraint", "keymap", "animated_id", "freestyle_module", "tool", "asset_shelf"}
FREESTYLE_OVERRIDES = re.compile(
    r"`(?:Unary|Binary)(?:Predicate|Function)\w*\.__call__`|`ChainingIterator\.traverse`|`StrokeShader\.shade`"
)
RENDER_ENGINE_UPDATES = re.compile(r"`RenderEngine\.update(?:_render_passes|_script_node|_custom_camera)?`")
# 2.7x API and functions removed from Python (BF1).
DEAD_API = re.compile(r"no (?:attribute|member) `(?:texture_slots|users_material|formatargspec)`")
# Sub-pointers that exist for one value of a type enum (`fluid_type == 'DOMAIN'`): out of scope.
SETTINGS_POINTER = re.compile(
    r"(?:Domain|Flow|Effector)Settings|RigidBody\w*|FieldSettings|ParticleSettings|Brush\w*Settings|SceneEEVEE"
    r"|DynamicPaint\w*Settings|CollisionSettings|SoftBodySettings"
)
# Sub-pointers that exist for one value of a type or mode enum, or a flag, read without a check: an armature's
# `Object.pose`, a Grease Pencil material's `grease_pencil`, a paint mode's `tool_settings.<mode>`, the `node_tree`
# of a material using nodes or of a group node (research `candidate-assumptions`, "not covered").
SUB_POINTER = re.compile(
    r"\b(?:Pose|MaterialGPencilStyle|VertexPaint|Sculpt|ImagePaint|UvSculpt|CurvesSculpt|ParticleEdit|Gp\w*Paint)"
    r" \| None`"
)
# Functions and classes of Python code that is untyped as a whole (glTF's dicts and numpy, rigify's
# `IdPropSequence` / `TypedObject`, Freestyle's functors, `_bl_i18n_utils`, `bl_app_override`): typing debt, out of
# scope (research `blender-true-problems`, "Ruled out").
UNTYPED_PACKAGES = (
    "scripts/addons_core/io_scene_gltf2/",
    "scripts/addons_core/rigify/",
    "scripts/freestyle/",
    "scripts/modules/_bl_i18n_utils/",
    "scripts/modules/bl_app_override/",
)
RIGIFY = "scripts/addons_core/rigify/"
NUMPY = re.compile(r"\bndarray\b|\bnumpy\.")
# Optional settings Blender's stubs lack because the Blender that generated them was built without the feature.
BUILD_OPTION_TYPE = re.compile(r"`FFmpegSettings`")
# Blender's code that reads a pointer its poll() does not check, or that has no poll() (research
# `blender-true-problems`, cause 4): (path, enclosing class or "", enclosing function or "", text on the line).
UNCHECKED_POINTER_BUGS = [
    ("scripts/addons_core/viewport_vr_preview/operators.py",
     "VIEW3D_OT_vr_location_scouting_active_camera_to_capture", "", ""),
    ("scripts/addons_core/viewport_vr_preview/operators.py",
     "VIEW3D_OT_vr_location_scouting_viewfinder_capture", "poll", ""),
    ("scripts/startup/bl_operators/anim.py", "ANIM_OT_keying_set_export", "", ""),
    ("scripts/modules/addon_utils.py", "", "", "ex.name"),
]  # fmt: skip
BASE_CLASS = re.compile(
    r"`(?:NodeSocket|Node|Constraint|Modifier|Strip|ActionStrip|Light|LightProbe|Curve|Texture|TextureSlot|IKParam"
    r"|Gizmo|Space|ID|bpy_struct|AnyType)(?:\[\w+\])?(?: & ~\w+)*`"
)
OTHER_CONTEXT_TYPE = re.compile(r"`(?:Space|Region|Area|Screen|Window|WorkSpace|Context) \| None`")
NEVER_NONE_CONTEXT_TYPE = re.compile(r"`(?:Preferences|WindowManager) \| None`")
CALLBACK_PARAMETER_TYPE = re.compile(r"`(?:bpy_struct|AnyType|KeyingSet|AssetRepresentation|Depsgraph) \| None`")
STUB_GAP_RULES = {
    "not-iterable",
    "unsupported-operator",
    "not-subscriptable",
    "call-non-callable",
    "invalid-method-override",
    "invalid-attribute-override",
    "invalid-property-type-override",
    "invalid-mutable-override",
}
GENERAL_TYPING_RULES = {
    "deprecated",
    "empty-body",
    "unused-type-ignore-comment",
    "unused-ignore-comment",
    "unresolved-global",
}
# Attributes Python code sets on its own functions and modules (`fn._is_first = False`, `mod.__addon_enabled__`).
PYTHON_OBJECT_ATTRIBUTE = re.compile(r"^Function `\w+` has no attribute|on type `(?:def |ModuleType`)")
MISSING_ATTRIBUTE = re.compile(
    r"has no attribute `(\w+)`|Attribute `(\w+)` is not defined on|Unresolved attribute `(\w+)` on type"
)


def missing_attribute(msg: str) -> str | None:
    match = MISSING_ATTRIBUTE.search(msg)
    return next((g for g in match.groups() if g), None) if match else None


# A type in a union that is no Blender type: a builtin or other lowercase type, a literal, an intersection, or one
# ty could not infer.
PYTHON_TYPE = re.compile(r"(?:[a-z_][\w.]*(?:\[.*\])?|Unknown|Any|Divergent|LiteralString|Literal\[.*\]|\(.*\))$")


# A Blender type as ty prints it: a capitalised class name, without type arguments.
BLENDER_TYPE = re.compile(r"[A-Z][A-Za-z0-9]*$")


# The types a message names, not its attribute, method, function or parameter names.
TYPE_IN_MESSAGE = re.compile(r"(?:type|found|Expected|union|and) `([^`]*)`")
PYTHON_CLASSES = {"None", "EllipsisType", "ModuleType", "~None"}
PYTHON_USE_RULES = {
    "not-subscriptable",
    "not-iterable",
    "call-non-callable",
    "unsupported-operator",
    "unresolved-attribute",
}


def union_members(type_: str) -> list[str]:
    """The members of a union type as ty prints it, split at the top level."""
    depth, current, members = 0, "", []
    for char in type_:
        depth += char in "(["
        depth -= char in ")]"
        current += char
        if depth == 0 and current.endswith(" | "):
            members.append(current[:-3])
            current = ""
    return [*members, current]


def python_optional(d: Diagnostic) -> bool:
    """Whether the nullable types in the message hold no Blender type: a plain Python ``Optional``."""
    unions = [t for t in re.findall(r"`([^`]*)`", d.msg) if "None" in union_members(t)]
    members = [m for t in unions for m in union_members(t) if m != "None"]
    return bool(members) and all(PYTHON_TYPE.match(m) and not m.startswith("bpy_") for m in members)


def unchecked_pointer_bug(d: Diagnostic) -> bool:
    path = d.path.replace("\\", "/")
    return nullable(d) and any(
        path == p and (not c or d.scope.cls == c) and (not f or d.scope.function == f) and t in d.text
        for p, c, f, t in UNCHECKED_POINTER_BUGS
    )


def python_types_only(d: Diagnostic) -> bool:
    """Whether a value is used in a way its type does not allow (subscript, iteration, call, operator, attribute)
    and every type the message names is a Python one (``None``, ``EllipsisType``, a builtin): plain Python typing
    debt, such as an instance attribute initialised to ``None`` or a ``...`` default. A mismatch of an argument or
    return type is left out: it can be a wrong annotation (BF2)."""
    if d.rule not in PYTHON_USE_RULES or NUMPY.search(d.msg):
        return False
    members = [m.removesuffix(" & ~AlwaysFalsy") for t in TYPE_IN_MESSAGE.findall(d.msg) for m in union_members(t)]
    return bool(members) and all(
        m in PYTHON_CLASSES or (PYTHON_TYPE.match(m) and not m.startswith(("bpy_", "Literal["))) for m in members
    )


def correlated_union(d: Diagnostic) -> bool:
    """Whether the message names a union of Blender types, without ``None``, that the code tells apart by a mode, a
    flag or a type field ty does not follow (``PoseBone | EditBone | Object`` picked by ``is_ebone``)."""
    if d.rule not in {"unresolved-attribute", "invalid-assignment"}:
        return False
    for type_ in re.findall(r"(?:on type|in union|Object of type) `([^`]*)`", d.msg):
        members = union_members(type_)
        if len(members) > 1 and all(
            BLENDER_TYPE.match(m) and m != "None" and not PYTHON_TYPE.match(m) for m in members
        ):
            return True
    return False


def untyped_python(d: Diagnostic) -> bool:
    return d.path.replace("\\", "/").startswith(UNTYPED_PACKAGES) or NUMPY.search(d.msg) is not None


def in_scripts(d: Diagnostic) -> bool:
    """Whether the diagnostic is in a doc example or a text-editor template."""
    return d.area in {"examples", "templates"}


def in_presets(d: Diagnostic) -> bool:
    return d.path.replace("\\", "/").startswith("scripts/presets/")


def in_tests(d: Diagnostic) -> bool:
    return d.path.replace("\\", "/").startswith("tests/")


def nullable(d: Diagnostic) -> bool:
    return NULLABLE.search(d.msg) is not None


def root(scope: Scope) -> str:
    """The Blender base of the enclosing class (``panel``, ``menu``, ``header``, ``operator``, ``gizmogroup``,
    ``uilist``), from its idname-style name or its bases as written; ``""`` when neither says."""
    for marker, name in (
        ("_PT_", "panel"),
        ("_MT_", "menu"),
        ("_HT_", "header"),
        ("_OT_", "operator"),
        ("_GGT_", "gizmogroup"),
        ("_UL_", "uilist"),
    ):
        if marker in scope.cls:
            return name
    for base in re.findall(r"\w+", scope.bases):
        if base.lower() in {"panel", "menu", "header", "operator", "gizmogroup", "uilist"}:
            return base.lower()
    return ""


def names_parameter(d: Diagnostic, positions: Iterable[int]) -> bool:
    params = d.scope.params
    return any(i < len(params) and re.search(rf"\b{re.escape(params[i])}\b", d.text) for i in positions)


def callback_never_none(d: Diagnostic) -> bool:
    if "AssetShelf.asset_poll" in d.msg or "AssetShelf.draw_context_menu" in d.msg:
        return True
    positions = NEVER_NONE_PARAMETERS.get(d.scope.function)
    if not positions or not nullable(d) or not CALLBACK_PARAMETER_TYPE.search(d.msg):
        return False
    if d.scope.function == "draw_item":
        return names_parameter(d, positions) and not names_parameter(d, [4])
    return True


def registered_property(d: Diagnostic) -> bool:
    if in_addon(d):
        return False
    if re.search(r"Unresolved attribute `\w+` on type `<class", d.msg):
        return True
    if re.match(r"\s*del\b", d.text) and d.msg.startswith("Class"):
        return True
    if d.rule == "invalid-assignment" and d.msg.startswith("Object of type `_PropertyDeferred` is not assignable"):
        return True
    return missing_attribute(d.msg) in d.scope.registers


def in_addon(d: Diagnostic) -> bool:
    path = d.path.replace("\\", "/")
    return path.startswith(("scripts/addons_core/", "intern/cycles/blender/addon/"))


def ui_draw_pointer(d: Diagnostic) -> bool:
    """A nullable read in the draw callback of a Panel, Menu, Header or UIList: Blender draws it only where its
    pointers exist (its poll, its editor or mode, or the panel's own logic), which ty does not follow (research
    ``blender-true-problems``, "Ruled out": the UI's draw code is guarded by construction)."""
    return nullable(d) and root(d.scope) in UI_ROOTS and d.scope.function in UI_DRAW_CALLBACKS


def layout_in(roots: set[str]) -> Callable[[Diagnostic], bool]:
    return lambda d: "UILayout | None" in d.msg and root(d.scope) in roots


def rule(*names: str) -> Callable[[Diagnostic], bool]:
    return lambda d: d.rule in names


def any_of(*predicates: Callable[[Diagnostic], bool]) -> Callable[[Diagnostic], bool]:
    return lambda d: any(p(d) for p in predicates)


def outside_tests(predicate: Callable[[Diagnostic], bool]) -> Callable[[Diagnostic], bool]:
    return lambda d: not in_tests(d) and predicate(d)


# --- the table, first match wins -------------------------------------------------------------------------------

CAUSES = [
    # The Imprecise annotations (S4), Implied narrowings (S5) and Assumptions (S6): the code their dedicated rule
    # accepts and reports. An error of the same shape is code the rule did not accept, and has another cause.
    *(Cause(name, group, slice_, rule(f"blender-{name}"), f"blender-{name}") for group, slice_, names in (
        ("imprecise-annotation", "S4",
         ("imprecise-operator-return", "imprecise-enum-value", "imprecise-callback-parameter")),
        ("implied-narrowing", "S5", ("narrowed-by-menu-prefix", "narrowed-by-popover", "narrowed-by-poll")),
        ("assumption", "S6", ("assumed-registration", "assumed-complete-registration", "assumed-preferences",
                              "assumed-list-item", "assumed-context-member")),
    ) for name in names),
    # Blender's own code is wrong (BF1 runtime, BF2 annotations).
    Cause("property-on-panel", "blender-fix", "BF1", rule("blender-unsupported-property-host")),
    Cause("dead-api", "blender-fix", "BF1", outside_tests(lambda d: DEAD_API.search(d.msg) is not None)),
    Cause("reload-idiom", "typing-debt", "", lambda d: d.rule == "unresolved-reference" and "reload(" in d.text),
    Cause("undefined-name", "blender-fix", "BF1", outside_tests(rule("unresolved-reference"))),
    Cause("missing-argument", "blender-fix", "BF1", outside_tests(rule("missing-argument"))),
    Cause("rigify-get-bone", "blender-fix", "BF2", lambda d: d.path.replace("\\", "/").startswith(RIGIFY)
          and re.search(r"EditBone \| PoseBone|PoseBone \| EditBone", d.msg) is not None),
    Cause("correlated-union", "typing-debt", "", correlated_union),
    Cause("tooldef", "blender-fix", "BF2", lambda d: "ToolDef" in d.msg),
    Cause("none-for-non-optional", "blender-fix", "BF2", outside_tests(any_of(
        rule("invalid-parameter-default"),
        lambda d: d.rule == "invalid-argument-type" and d.msg.endswith("found `None`")))),
    Cause("wrong-annotation", "blender-fix", "BF2", outside_tests(any_of(
        lambda d: d.rule == "invalid-type-form" and "bpy.context" in d.text,
        lambda d: d.rule == "invalid-base" and "`Menu`" in d.msg,
        lambda d: "Expected `Menu`, found `<class" in d.msg,
        lambda d: re.search(r"Expected `dict\[[^`]*`, found `tuple\[", d.msg) is not None))),
    # Typechecker fixes (S1 RNA never-None, S2 stub generator, S3 ty_blender).
    Cause("context-never-none", "typechecker-fix", "S1", lambda d: NEVER_NONE_CONTEXT_TYPE.search(d.msg) is not None),
    Cause("callback-never-none", "typechecker-fix", "S1", callback_never_none),
    # ObjectModifiers.new() really returns None when the modifier cannot be added (only a warning report), so an
    # unchecked result is typing debt, not a typechecker fix.
    Cause("modifiers-new", "typing-debt", "", lambda d: nullable(d) and ".modifiers.new(" in d.text),
    Cause("bmesh-elem-seq", "typechecker-fix", "S2", lambda d: "`BMEdge`" in d.msg and "loop" in d.text),
    Cause("blend-data-lib-key", "typechecker-fix", "S2", lambda d: "`tuple[str, " in d.msg and "[" in d.text),
    Cause("context-store-member", "typechecker-fix", "S2", lambda d: d.msg.startswith("Object of type `Context`")
          and missing_attribute(d.msg) in CONTEXT_STORE_MEMBERS),
    Cause("freestyle-positional", "typechecker-fix", "S2", lambda d: d.rule == "invalid-method-override"
          and FREESTYLE_OVERRIDES.search(d.msg) is not None),
    Cause("render-engine-positional", "typechecker-fix", "S2", lambda d: d.rule == "invalid-method-override"
          and RENDER_ENGINE_UPDATES.search(d.msg) is not None),
    Cause("dynamic-enum", "typechecker-fix", "S2", lambda d: "Literal['DEFAULT']`" in d.msg
          or 'Literal["DEFAULT"]`' in d.msg),
    Cause("stub-context-manager", "typechecker-fix", "S2", lambda d: d.rule == "invalid-context-manager"
          and re.search(r"libraries\.load|temp_data", d.text) is not None),
    Cause("stub-docstring", "typechecker-fix", "S2", lambda d: re.search(
        r"\bkeyconfig_set\b|\btarget_set_value\b", d.text) is not None),
    Cause("layout-in-helper", "typechecker-fix", "S3", layout_in({"panel", "menu", "header"})),
    Cause("layout-in-operator-helper", "typing-debt", "", layout_in({"operator"})),
    Cause("cross-file-registered-property", "typing-debt", "", lambda d: re.search(
        r"has no attribute `(?:cycles\w*|selection_sets)`", d.msg) is not None),
    Cause("file-registered-property", "typechecker-fix", "S3", registered_property),
    Cause("bl-rna-property", "typechecker-fix", "S3", lambda d: d.msg.startswith("Object of type `Property`")),
    Cause("type-call-bases", "typechecker-fix", "S3", rule("blender-invalid-idname")),
    Cause("filter-items-tuple", "typechecker-fix", "S3", lambda d: d.rule == "invalid-return-type"
          and d.scope.function == "filter_items"),
    # Returns that contradict the operator API or the function's own annotation.
    Cause("operator-return-misuse", "blender-fix", "BF1", outside_tests(
        lambda d: d.rule == "invalid-return-type" and d.scope.function in OPERATOR_RETURNS)),
    Cause("return-annotation", "blender-fix", "BF2", outside_tests(rule("invalid-return-type"))),
    # Nullable reads, from the most specific source.
    Cause("unchecked-pointer-bug", "blender-fix", "BF1", unchecked_pointer_bug),
    Cause("mixin-self", "typing-debt", "", lambda d: "Self@" in d.msg),
    Cause("type-enum-sub-pointer", "typing-debt", "", lambda d: nullable(d) and (
        SETTINGS_POINTER.search(d.msg) is not None or SUB_POINTER.search(d.msg) is not None
        or ("NodeTree | None" in d.msg and ".node_tree" in d.text))),
    Cause("python-optional", "typing-debt", "", lambda d: nullable(d) and python_optional(d)),
    # A preset's module-level reads of the context members of the panel that runs it (`bpy.context.cloth`,
    # `edit_movieclip`, `active_strip`, a keymap preset's `preferences`): not covered by the context-member
    # Assumption, which takes only `scene`, `view_layer` and `tool_settings`.
    Cause("preset-context-member", "typing-debt", "", lambda d: nullable(d) and in_presets(d)),
    Cause("ui-draw-pointer", "typing-debt", "", outside_tests(ui_draw_pointer)),
    Cause("object-data-untagged", "typing-debt", "", lambda d: re.search(r"`ID( \| None)?`", d.msg) is not None
          and "data" in d.text),
    # The window, screen, area, region, space and workspace of the editor an operator's `invoke` / `modal` (or a
    # gizmo's `exit`) runs in: those run interactively only, so the members exist (research
    # `blender-true-problems`, "Ruled out": None only in exotic states). Not covered by an Assumption.
    Cause("editor-context-member", "typing-debt", "", lambda d: OTHER_CONTEXT_TYPE.search(d.msg) is not None
          and d.scope.function in INTERACTIVE_CALLBACKS),
    # A doc example or template reading the context it documents (`bpy.context.object` with an active object),
    # directly or, at module level, through what it read (`obj = bpy.context.object`, then `obj.data`).
    Cause("script-context-member", "typing-debt", "", lambda d: nullable(d) and in_scripts(d)
          and (not d.scope.function or re.search(CONTEXT + r"\w+", d.text) is not None)),
    Cause("context-member-outside-callback", "unsorted", "", lambda d: OTHER_CONTEXT_TYPE.search(d.msg) is not None
          or (nullable(d) and re.search(CONTEXT + r"\w+", d.text) is not None and not d.scope.function)),
    Cause("unchecked-pointer", "unsorted", "", nullable),
    # The rest, by rule.
    Cause("base-class-subtype", "typing-debt", "", lambda d: d.rule == "unresolved-attribute"
          and BASE_CLASS.search(d.msg) is not None),
    Cause("operator-call", "typing-debt", "", lambda d: "bpy.ops." in d.text or "OperatorProperties" in d.msg
          or ("`dict[str, Any]`" in d.msg and re.match(r"\s*props\.\w+_OT_", d.text) is not None)
          or (d.rule == "too-many-positional-arguments" and STRING_LITERAL.search(d.text) is not None)),
    Cause("unresolved-import", "typing-debt", "", lambda d: d.rule in {
        "import-not-found", "unresolved-import", "possibly-missing-submodule"} or "Cannot resolve imported" in d.msg),
    Cause("general-typing", "typing-debt", "", lambda d: d.rule in GENERAL_TYPING_RULES
          or PYTHON_OBJECT_ATTRIBUTE.search(d.msg) is not None or python_types_only(d)),
    Cause("untyped-python", "typing-debt", "", untyped_python),
    Cause("private-member", "typing-debt", "", lambda d: re.search(r"has no member `_\w+`", d.msg) is not None),
    Cause("build-option-gap", "typing-debt", "", lambda d: BUILD_OPTION_TYPE.search(d.msg) is not None),
    Cause("stub-gap", "unsorted", "", lambda d: d.rule in STUB_GAP_RULES or "object.__init__" in d.msg
          or re.search(r"Module `[\w.]+` has no member", d.msg) is not None),
    Cause("blender-rule", "unsorted", "", lambda d: d.rule.startswith("blender-")),
    Cause("unsorted", "unsorted", "", lambda d: True),
]  # fmt: skip
CAUSE_BY_NAME = {c.name: c for c in CAUSES}
# The dedicated rules of S4-S6 name their cause, ahead of every pattern.
CAUSE_BY_RULE = {c.rule: c for c in CAUSES if c.rule}


def none_last(msg: str) -> str:
    """``msg`` with ``None`` moved to the end of every union it names (fake-bpy-module's stubs spell
    ``None | Scene``), so the facts need to know one spelling."""

    def reorder(match: re.Match[str]) -> str:
        members = union_members(match[1])
        if "None" not in members[:-1]:
            return match[0]
        return "`" + " | ".join([m for m in members if m != "None"] + ["None"]) + "`"

    return re.sub(r"`([^`]*)`", reorder, msg)


def cause(d: Diagnostic) -> Cause:
    """The cause of a diagnostic: the one its dedicated rule reports, else the first entry of CAUSES that
    matches it (with ``None`` last in each union)."""
    if d.rule in CAUSE_BY_RULE:
        return CAUSE_BY_RULE[d.rule]
    d = replace(d, msg=none_last(d.msg))
    return next(c for c in CAUSES if c.matches(d))


# The causes in report order: by group, then in table order.
REPORTED = [c for g in GROUPS for c in CAUSES if c.group == g]


# --- reading ty's output ---------------------------------------------------------------------------------------

DEF = re.compile(r"(?:async\s+)?def\s+(\w+)\s*\(")
CLASS = re.compile(r"class\s+(\w+)\s*(?:\((.*)\))?\s*:")
REGISTERS = re.compile(r"^\s*bpy\.types\.\w+\.(\w+)\s*=\s*(?:bpy\.props\.|props\.)?\w*Property\(", re.MULTILINE)


def indentation(line: str) -> int:
    return len(line) - len(line.lstrip())


def parameters(lines: list[str], index: int) -> tuple[str, ...]:
    """The parameter names of the ``def`` starting at ``lines[index]``, which may span lines."""
    text = ""
    for line in lines[index : index + 20]:
        text += line.split("#")[0] + " "
        if re.search(r"\)\s*(->.*)?:\s*$", line.split("#")[0]):
            break
    start = text.index("(") + 1
    depth, current, parts = 0, "", []
    for char in text[start:]:
        if char in "([{":
            depth += 1
        elif char in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(current)
            current = ""
            continue
        current += char
    parts.append(current)
    names = (re.split(r"[:=]", part)[0].strip().lstrip("*").strip() for part in parts)
    return tuple(n for n in names if n and n != "/")


def class_has_poll(lines: list[str], index: int) -> bool:
    indent = indentation(lines[index])
    for line in lines[index + 1 :]:
        if line.strip() and not line.lstrip().startswith("#") and indentation(line) <= indent:
            return False
        if re.match(r"\s*def\s+poll\s*\(", line):
            return True
    return False


def enclosing_scope(lines: list[str], line: int, registers: frozenset[str]) -> Scope:
    """The class and function around the 1-based ``line``, found by indentation."""
    index = line - 1
    if not 0 <= index < len(lines):
        return Scope(registers=registers)
    limit = indentation(lines[index]) if lines[index].strip() else 1 << 30
    if limit == 0:
        return Scope(registers=registers)
    function, params = "", ()
    for i in range(index - 1, -1, -1):
        text = lines[i]
        stripped = text.strip()
        if not stripped or stripped.startswith(("#", "@", ")", "]", "}")) or indentation(text) >= limit:
            continue
        limit = indentation(text)
        if not function and (match := DEF.match(stripped)):
            function, params = match[1], parameters(lines, i)
        elif match := CLASS.match(stripped):
            return Scope(match[1], match[2] or "", function, params, class_has_poll(lines, i), registers)
        if limit == 0:
            break
    return Scope(function=function, params=params, registers=registers)


def read_diagnostics(output: str, source: Path) -> list[Diagnostic]:
    """The diagnostics of ty's concise ``output``, run in ``source``, each with the source line it points at and
    its enclosing scope."""
    files: dict[str, tuple[list[str], frozenset[str]]] = {}
    diagnostics = []
    for match in DIAGNOSTIC_LINE.finditer(output):
        path, line = match["path"], int(match["line"])
        if path not in files:
            try:
                content = (source / path.replace("\\", "/")).read_text(encoding="utf-8", errors="replace")
            except OSError:
                content = ""
            files[path] = (content.splitlines(), frozenset(REGISTERS.findall(content)))
        lines, registers = files[path]
        text = lines[line - 1] if 0 < line <= len(lines) else ""
        scope = enclosing_scope(lines, line, registers)
        diagnostics.append(Diagnostic(path, line, match["rule"], match["msg"], text, match["severity"], scope))
    return diagnostics


# --- reports ---------------------------------------------------------------------------------------------------


def samples(diagnostics: list[Diagnostic], per_cause: int = 20) -> str:
    """The first ``per_cause`` diagnostics of each cause with their source line and scope, for reading."""
    by_cause: dict[str, list[Diagnostic]] = collections.defaultdict(list)
    for d in diagnostics:
        by_cause[d.cause.name].append(d)
    out = []
    for c in REPORTED:
        out.append(f"## {c.name} ({c.group}{', ' + c.slice if c.slice else ''}): {len(by_cause[c.name])}\n")
        for d in by_cause[c.name][:per_cause]:
            where = ".".join(part for part in (d.scope.cls, d.scope.function) if part)
            out.append(f"{d.path}:{d.line}: {d.severity}[{d.rule}] {d.msg}\n")
            out.append(f"    | {d.text.strip()}{f'    ({where})' if where else ''}\n")
        out.append("\n")
    return "".join(out)


def summary(title: str, diagnostics: Iterable[tuple[str, str, str, str]]) -> str:
    """The cause × area table (with each cause's group and slice), the totals per group, the totals of errors and
    warnings, and the counts per rule and severity (sorted by name) of ``diagnostics``, given as (cause, area, rule,
    severity). Every cause and group gets a row, also when zero, so a diff of two summaries shows what moved where."""
    diagnostics = list(diagnostics)
    cells = collections.Counter((c, a) for c, a, _, _ in diagnostics)
    groups = collections.Counter((CAUSE_BY_NAME[c].group, a) for c, a, _, _ in diagnostics)
    severities = collections.Counter((s, a) for _, a, _, s in diagnostics)
    rules = collections.Counter((r, s) for _, _, r, s in diagnostics)

    def counts(row: str, cell: collections.Counter) -> str:
        values = [cell[row, a] for a in AREA_NAMES]
        return "".join(f"{n:>10}" for n in [*values, sum(values)]) + "\n"

    areas = "".join(f"{a:>10}" for a in [*AREA_NAMES, "total"]) + "\n"
    lines = [title + "\n", f"{'cause':<32}{'group':<22}{'slice':<6}" + areas]
    lines.extend(f"{c.name:<32}{c.group:<22}{c.slice or '-':<6}" + counts(c.name, cells) for c in REPORTED)
    lines.append("\n")
    lines.append(f"{'group':<60}" + areas)
    lines.extend(f"{g:<60}" + counts(g, groups) for g in GROUPS)
    lines.append(f"{'errors':<60}" + counts("error", severities))
    lines.append(f"{'warnings':<60}" + counts("warning", severities))
    lines.append("\n")
    lines.append(f"{'rule':<40}{'error':>8}{'warning':>8}\n")
    lines.extend(f"{r:<40}{rules[r, 'error']:>8}{rules[r, 'warning']:>8}\n" for r in sorted({r for r, _ in rules}))
    return "".join(lines)


def area(path: str) -> str:
    """The area of a path relative to the Blender source root (``/`` or ``\\`` separated)."""
    path = path.replace("\\", "/")
    for name, prefixes in AREAS:
        if path.startswith(prefixes):
            return name
    return "other"
