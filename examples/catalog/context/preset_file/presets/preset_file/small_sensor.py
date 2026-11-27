import bpy

camera = bpy.context.camera  # ty: ignore[blender-assumed-preset-context]
camera.sensor_width = 13.2
camera.sensor_fit = "HORIZONTAL"
