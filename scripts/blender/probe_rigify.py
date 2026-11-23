"""Generate Rigify rigs from its metarigs and rig samples (run by scripts/probe_gltf_rigify.py, #137).

Usage (inside Blender):
  blender --background --factory-startup --python probe_rigify.py -- <output json>

Enables Rigify, then for each case starts from an empty file, builds a metarig and runs
``bpy.ops.pose.rigify_generate()``:

- ``metarig:<name>``: every metarig Rigify registers an add operator for (human, basic human / quadruped, the animals);
- ``metarig:human_upgraded_face``: the human metarig after ``pose.rigify_upgrade_face``, which replaces the legacy
  ``faces.super_face`` with the skin rigs (``skin_eye``, ``skin_jaw``, ``glue``, ``anchor``, ``basic_chain``, ...);
- ``sample:<rig type>``: every rig type with a ``create_sample``, in its own armature. A sample has no bone collection
  with a UI row, so the first collection (or a new one) gets one, as Generate asks for. ``skin.glue`` is left out: its
  sample is a lone glue bone with no skin chain to attach to, which Rigify rejects; the upgraded face covers it.

The operator catches generation errors and only reports them, so a case passes when the metarig's target rig exists
afterwards and has bones. The JSON maps each case to its result; the driver reads it.
"""

from __future__ import annotations

import os
import sys

import addon_utils
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _recorder import check, script_args, write_results

# Rig types whose sample cannot generate on its own.
NOT_STANDALONE = {"skin.glue"}


def empty_file() -> None:
    bpy.ops.wm.read_homefile(use_empty=True)


def generate(metarig: bpy.types.Object) -> int:
    """Generate the rig of ``metarig``; the number of bones in the generated rig."""
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.objects.active = metarig
    if not any(bcoll.rigify_ui_row > 0 for bcoll in metarig.data.collections_all):
        bcolls = metarig.data.collections_all
        (bcolls[0] if len(bcolls) else metarig.data.collections.new("Sample")).rigify_ui_row = 1
    result = bpy.ops.pose.rigify_generate()
    target = metarig.data.rigify_target_rig
    if result != {"FINISHED"} or target is None or not target.data.bones:
        raise RuntimeError(f"rigify_generate returned {result} and generated no rig (see blender.log)")
    return len(target.data.bones)


def metarig_case(operator: str) -> int:
    empty_file()
    category, name = operator.split(".")
    getattr(getattr(bpy.ops, category), name)()
    return generate(bpy.context.active_object)


def upgraded_face_case() -> int:
    empty_file()
    bpy.ops.object.armature_human_metarig_add()
    metarig = bpy.context.active_object
    bpy.ops.object.mode_set(mode="POSE")
    if bpy.ops.pose.rigify_upgrade_face() != {"FINISHED"}:
        raise RuntimeError("rigify_upgrade_face did not finish")
    return generate(metarig)


def sample_case(rig_type: str) -> int:
    empty_file()
    armature = bpy.data.armatures.new("metarig")
    obj = bpy.data.objects.new("metarig", armature)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.armature.metarig_sample_add(metarig_type=rig_type)
    return generate(obj)


def main() -> None:
    out = script_args()[0]
    addon_utils.enable("rigify", default_set=True, handle_error=None)
    from rigify import metarig_menu, rig_lists

    results: dict = {}
    for ops in metarig_menu.metarig_ops.values():
        for op_type, name in ops:
            check(results, f"metarig:{name}", lambda op=op_type.bl_idname: metarig_case(op))
    check(results, "metarig:human_upgraded_face", upgraded_face_case)
    for rig_type, entry in sorted(rig_lists.rigs.items()):
        if hasattr(entry["module"], "create_sample") and rig_type not in NOT_STANDALONE:
            check(results, f"sample:{rig_type}", lambda t=rig_type: sample_case(t))
    write_results(out, results)


main()
