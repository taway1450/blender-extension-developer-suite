"""PROTOTYPE, throwaway. Build the .blend files of the example add-ons in ``examples/``, inside Blender.

Runs in background Blender (``mise run probe:blend-typing main --make``):

    blender --background --factory-startup --python make_examples.py -- EXAMPLES_DIR

- ``asset_pack/assets.blend``: what an asset add-on ships and appends from: a material ``Rust`` (Principled BSDF
  with a noise texture), a geometry node group ``Scatter Points`` and a mesh object ``Rock`` with a Bevel modifier.
- ``scene_template/startup.blend``: the scene an app-template-like add-on runs against: a camera ``Camera``, an area
  light ``Key Light``, a mesh ``Cube`` with a Subdivision modifier and the material ``Ground``, and an IDProperty
  ``scene["shot"]``.

Both are saved compressed, so they stay small enough to commit.
"""

import os
import sys

import bmesh
import bpy


def empty_file():
    bpy.ops.wm.read_homefile(use_empty=True)


def mesh_object(name, make):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    make(bm)
    bm.to_mesh(mesh)
    bm.free()
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def principled_material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    return mat


def asset_pack(path):
    empty_file()
    rust = principled_material("Rust")
    nodes = rust.node_tree.nodes
    texture = nodes.new("ShaderNodeTexNoise")
    texture.name = "Rust Noise"
    rust.node_tree.links.new(texture.outputs["Color"], nodes["Principled BSDF"].inputs["Base Color"])
    rust.use_fake_user = True

    tree = bpy.data.node_groups.new("Scatter Points", "GeometryNodeTree")
    tree.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    tree.interface.new_socket("Density", in_out="INPUT", socket_type="NodeSocketFloat")
    tree.interface.new_socket("Points", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    group_in = tree.nodes.new("NodeGroupInput")
    group_out = tree.nodes.new("NodeGroupOutput")
    distribute = tree.nodes.new("GeometryNodeDistributePointsOnFaces")
    tree.links.new(group_in.outputs["Geometry"], distribute.inputs["Mesh"])
    tree.links.new(group_in.outputs["Density"], distribute.inputs["Density"])
    tree.links.new(distribute.outputs["Points"], group_out.inputs["Points"])
    tree.use_fake_user = True

    rock = mesh_object("Rock", lambda bm: bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0))
    rock.data.materials.append(rust)
    bevel = rock.modifiers.new("Bevel", "BEVEL")
    bevel.width = 0.05
    rock.use_fake_user = True
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)


def scene_template(path):
    empty_file()
    scene = bpy.context.scene
    scene["shot"] = "010"
    camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    scene.collection.objects.link(camera)
    scene.camera = camera
    light = bpy.data.objects.new("Key Light", bpy.data.lights.new("Key Light", "AREA"))
    scene.collection.objects.link(light)
    cube = mesh_object("Cube", lambda bm: bmesh.ops.create_cube(bm, size=2.0))
    cube.modifiers.new("Subdivision", "SUBSURF")
    cube.data.materials.append(principled_material("Ground"))
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)


def main():
    examples = sys.argv[sys.argv.index("--") + 1]
    asset_pack(os.path.join(examples, "asset_pack", "assets.blend"))
    scene_template(os.path.join(examples, "scene_template", "startup.blend"))
    print("blend-typing: made the example files")


main()
