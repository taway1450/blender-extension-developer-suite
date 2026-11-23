"""Feature test: context pointers Blender's C code sets together (Pointer aliases).

- context.particle_system is provided by the Properties editor only (buttons_context.cc), from a context path that
  goes through an object (buttons_context_path_particle): context.object is then set. Pinned particle settings give
  particle_settings, not particle_system.
- context.active_strip is the active strip of CTX_data_sequencer_scene (screen_ctx_active_strip in
  screen_context.cc), so context.sequencer_scene, the same scene, is set.

Not aliased: context.active_pose_bone and context.active_object. The 3D viewport leaves active_object None for a
hidden object in object mode (view3d_context.cc), while active_pose_bone may be a bone of the armature in pose mode
that deforms such a mesh (BKE_object_pose_armature_get).

The assert_type calls in the bodies are no-ops at runtime."""

from typing import assert_type

import bpy
from bpy.types import Object, Operator, Panel, Scene


class PTR_CONTEXT_PT_particles(Panel):
    bl_label = "Particles"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "particle"

    @classmethod
    def poll(cls, context):
        return context.particle_system is not None

    def draw(self, context):
        self.layout.label(text=context.particle_system.name)  # ty: ignore[blender-narrowed-by-poll]
        assert_type(context.object, Object)  # oracle-skip: a Pointer alias, silent


class PTR_CONTEXT_OT_strip(Operator):
    bl_idname = "ptr_context.strip"
    bl_label = "Strip"

    @classmethod
    def poll(cls, context):
        return context.active_strip is not None

    def execute(self, context):
        assert_type(context.sequencer_scene, Scene)  # oracle-skip: a Pointer alias, silent
        return {"FINISHED"}


class PTR_CONTEXT_OT_pose_bone(Operator):
    bl_idname = "ptr_context.pose_bone"
    bl_label = "Pose bone"

    @classmethod
    def poll(cls, context):
        return context.active_pose_bone is not None

    def execute(self, context):
        assert_type(context.active_object, Object | None)  # bare-ok: the 3D viewport may hide the active object
        return {"FINISHED"}


classes = (PTR_CONTEXT_PT_particles, PTR_CONTEXT_OT_strip, PTR_CONTEXT_OT_pose_bone)
register, unregister = bpy.utils.register_classes_factory(classes)
