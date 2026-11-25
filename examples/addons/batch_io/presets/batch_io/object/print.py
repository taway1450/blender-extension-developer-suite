import bpy

# Blender runs a preset with the context of the panel that applies it: the Object tab has an object.
# demo: blender-assumed-preset-context
settings = bpy.context.object.batch_io

settings.enabled = True
settings.file_format = "STL"
