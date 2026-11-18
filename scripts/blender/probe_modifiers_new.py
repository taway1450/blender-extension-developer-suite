"""Check that the shipped callers of ``modifiers.new()`` handle a rejected modifier (run by
scripts/probe_modifiers_new.py, #139).

Usage (inside Blender):
  blender --background --factory-startup --python probe_modifiers_new.py -- <output json> <fbx test dir>

``ObjectModifiers.new()`` returns None, with only a warning, when the object rejects the modifier type. Each check
starts from the factory-startup scene (the default cube selected and active):

- ``api_empty_subsurf``: an empty rejects ``SUBSURF``, and ``new()`` returns None instead of raising.
- ``<operator>_adds``: the quick-effects operator, run through ``bpy.ops`` on the cube, finishes and adds its
  modifiers (Quick Smoke and Liquid only in a build with the fluid modifier).
- ``<operator>_rejected[_<where>]``: the operator's ``execute`` runs with a context whose objects reject every
  modifier: the selected objects (``flow``), or the object the operator creates and reads back as the active object
  (``domain``, and Quick Fur's curves). Every quick-effects operator only takes meshes, which accept all of its
  modifiers, so the rejection is emulated: a stand-in object returns None from ``modifiers.new()`` and passes
  everything else to the real one. The operator must return ``{'CANCELLED'}`` with an error report naming the object,
  and leave the scene as it was: the same objects, modifiers, display types and selection (all but Quick Explode,
  which adds a particle system before its modifier and leaves it behind).
- ``<operator>_rejected_second``: the same with a second cube selected, where only the second object rejects (the
  second cube's flow, or the curves object Quick Fur makes for it), so the operator has changed the first object
  before it cancels and must take that back.
- ``fbx_import_<file>``: the FBX importer (Python) adds the armature and subdivision modifiers to the meshes.

The JSON holds each check's result (``ok``, and ``value`` or ``error``, or ``skipped``); the driver reads it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import bpy
from bpy.types import Object

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _recorder import check, script_args, write_results

# The objects that rejected a modifier in the current check (an operator may delete them before it cancels).
REJECTED: list[str] = []

FBX_FILES = {
    "bl_cube_skinned.fbx": "ARMATURE",
    "ufbx_blender_293x_nonmanifold_subsurf_74b.fbx": "SUBSURF",
}


def reset() -> None:
    bpy.ops.wm.read_homefile(use_factory_startup=True)


def unwrap(value):
    return value._obj if isinstance(value, RejectingObject) else value


class RejectingModifiers:
    """An object's modifiers that reject every new modifier, as ``ObjectModifiers.new()`` does for an object that
    does not support the type."""

    def __init__(self, obj: bpy.types.Object) -> None:
        self._obj = obj

    def new(self, name: str, type: str) -> None:
        REJECTED.append(self._obj.name)

    def __iter__(self):
        return iter(self._obj.modifiers)

    def __len__(self) -> int:
        return len(self._obj.modifiers)

    def __getattr__(self, name: str):
        return getattr(self._obj.modifiers, name)


class RejectingObject:
    """A stand-in for an object whose modifiers reject every new modifier; everything else is the real object."""

    def __init__(self, obj: bpy.types.Object) -> None:
        object.__setattr__(self, "_obj", obj)

    @property
    def modifiers(self) -> RejectingModifiers:
        return RejectingModifiers(self._obj)

    def __getattr__(self, name: str):
        return getattr(self._obj, name)

    def __setattr__(self, name: str, value) -> None:
        setattr(self._obj, name, value)

    def __eq__(self, other) -> bool:
        return self._obj == unwrap(other)

    def __hash__(self) -> int:
        return hash(self._obj)


def every(obj: Object) -> bool:
    return True


def never(obj: Object) -> bool:
    return False


class ProbeContext:
    """The real context, with the selected objects or the active object replaced by rejecting stand-ins where
    ``reject_selected`` / ``reject_active`` say so for the object."""

    def __init__(self, context: bpy.types.Context, *, reject_selected=never, reject_active=never) -> None:
        self._context = context
        self._reject_selected = reject_selected
        self._reject_active = reject_active

    @property
    def selected_objects(self):
        return [RejectingObject(o) if self._reject_selected(o) else o for o in self._context.selected_objects]

    @property
    def active_object(self):
        obj = self._context.active_object
        return RejectingObject(obj) if obj is not None and self._reject_active(obj) else obj

    def temp_override(self, **kwargs):
        def real(value):
            return [unwrap(v) for v in value] if isinstance(value, list) else unwrap(value)

        return self._context.temp_override(**{key: real(value) for key, value in kwargs.items()})

    def __getattr__(self, name: str):
        return getattr(self._context, name)


class ProbeOperator:
    """Stands in for the operator instance: its properties at their defaults, and the reports it makes."""

    def __init__(self, idname: str) -> None:
        for prop in getattr(bpy.ops.object, idname).get_rna_type().properties:
            if prop.type not in {"POINTER", "COLLECTION"}:
                setattr(self, prop.identifier, prop.default)
        self.reports: list[tuple[list[str], str]] = []

    def report(self, type: set[str], message: str) -> None:
        self.reports.append((sorted(type), message))


def operator_class(idname: str) -> type:
    from bl_operators import object_quick_effects

    return {
        "quick_fur": object_quick_effects.QuickFur,
        "quick_explode": object_quick_effects.QuickExplode,
        "quick_smoke": object_quick_effects.QuickSmoke,
        "quick_liquid": object_quick_effects.QuickLiquid,
    }[idname]


def needs_fluid(idname: str) -> bool:
    return idname in {"quick_smoke", "quick_liquid"} and not bpy.app.build_options.fluid


def run_adds(idname: str) -> dict:
    reset()
    before = {o.name for o in bpy.data.objects}
    result = getattr(bpy.ops.object, idname)()
    if result != {"FINISHED"}:
        raise AssertionError(f"bpy.ops.object.{idname}() returned {sorted(result)}")
    added = {o.name: sorted(m.type for m in o.modifiers) for o in bpy.data.objects if o.modifiers}
    if not added:
        raise AssertionError(f"bpy.ops.object.{idname}() added no modifier")
    return {"modifiers": added, "new_objects": sorted({o.name for o in bpy.data.objects} - before)}


def scene_state() -> dict:
    """What a cancelled operator must leave as it was: the objects, their modifiers, display types and selection."""
    active = bpy.context.view_layer.objects.active
    objects = {
        o.name: {"modifiers": [m.type for m in o.modifiers], "display_type": o.display_type, "selected": o.select_get()}
        for o in bpy.data.objects
    }
    return {"objects": objects, "active": active.name if active else None}


def add_second_cube() -> None:
    """Select a second cube beside the default one, which stays active."""
    cube = bpy.context.active_object
    bpy.ops.mesh.primitive_cube_add(location=(3.0, 0.0, 0.0))
    cube.select_set(True)
    bpy.context.view_layer.objects.active = cube


def second_cube(obj: Object) -> bool:
    return obj.name == "Cube.001"


def second_curves(obj: Object) -> bool:
    """The curves object Quick Fur adds for the second cube (the first one's exists by then)."""
    return obj.type == "CURVES" and sum(o.type == "CURVES" for o in bpy.data.objects) > 1


def run_rejected(
    idname: str, *, reject_selected=never, reject_active=never, second: bool = False, unchanged: bool = True
) -> dict:
    reset()
    if second:
        add_second_cube()
    REJECTED.clear()
    before = scene_state()
    cls = operator_class(idname)
    op = ProbeOperator(idname)
    context = ProbeContext(bpy.context, reject_selected=reject_selected, reject_active=reject_active)
    result = cls.execute(op, context)
    rejected = sorted(set(REJECTED))
    if result != {"CANCELLED"}:
        raise AssertionError(f"{cls.__name__}.execute returned {result!r} (reports {op.reports})")
    if not rejected:
        raise AssertionError(f"{cls.__name__}.execute never asked a rejecting object for a modifier")
    errors = [message for types, message in op.reports if types == ["ERROR"]]
    if not any(name in message for message in errors for name in rejected):
        raise AssertionError(f"{cls.__name__}.execute reported no error naming {rejected}: {op.reports}")
    if unchanged and (after := scene_state()) != before:
        raise AssertionError(f"{cls.__name__}.execute cancelled but changed the scene:\n{before}\n->\n{after}")
    return {"rejected": rejected, "reports": op.reports}


def api_empty_subsurf() -> str:
    reset()
    empty = bpy.data.objects.new("ProbeEmpty", None)
    bpy.context.scene.collection.objects.link(empty)
    modifier = empty.modifiers.new("Subdivision", "SUBSURF")
    if modifier is not None:
        raise AssertionError(f"an empty accepted a SUBSURF modifier: {modifier!r}")
    return "None"


def fbx_import(path: Path, modifier_type: str) -> dict:
    bpy.ops.wm.read_homefile(use_factory_startup=True, use_empty=True)
    result = bpy.ops.import_scene.fbx(filepath=str(path), use_subsurf=True)
    if result != {"FINISHED"}:
        raise AssertionError(f"import_scene.fbx returned {sorted(result)}")
    found = {o.name: [m.type for m in o.modifiers] for o in bpy.data.objects if o.modifiers}
    if not any(modifier_type in types for types in found.values()):
        raise AssertionError(f"no {modifier_type} modifier after the import: {found}")
    return found


def main() -> None:
    args = script_args()
    out, fbx_dir = args[0], Path(args[1])
    results: dict = {}
    check(results, "api_empty_subsurf", api_empty_subsurf)
    no_fluid = "built without the fluid modifier"
    for idname in ("quick_fur", "quick_explode", "quick_smoke", "quick_liquid"):
        skip = no_fluid if needs_fluid(idname) else ""
        check(results, f"{idname}_adds", lambda: run_adds(idname), skip=skip)
    check(results, "quick_fur_rejected", lambda: run_rejected("quick_fur", reject_active=every))
    check(
        results,
        "quick_fur_rejected_second",
        lambda: run_rejected("quick_fur", reject_active=second_curves, second=True),
    )
    check(
        results,
        "quick_explode_rejected",
        # Quick Explode adds the particle system first, so a rejected Explode modifier leaves it behind.
        lambda: run_rejected("quick_explode", reject_selected=every, reject_active=every, unchanged=False),
    )
    for idname in ("quick_smoke", "quick_liquid"):
        skip = no_fluid if needs_fluid(idname) else ""
        check(results, f"{idname}_rejected_flow", lambda: run_rejected(idname, reject_selected=every), skip=skip)
        check(
            results,
            f"{idname}_rejected_second",
            lambda: run_rejected(idname, reject_selected=second_cube, second=True),
            skip=skip,
        )
        check(results, f"{idname}_rejected_domain", lambda: run_rejected(idname, reject_active=every), skip=skip)
    for name, modifier_type in FBX_FILES.items():
        check(results, f"fbx_import_{Path(name).stem}", lambda: fbx_import(fbx_dir / name, modifier_type))
    write_results(out, results)


main()
