# Example addons

Blender extensions used as type-checking targets for ty (`mise run check:addons <version>`).
They are written the way Blender addons are usually written (property annotations such as
`count: IntProperty(...)`, `bpy.types.Scene.x = PointerProperty(...)`, ...), so they show which
Blender idioms ty does not understand yet.
