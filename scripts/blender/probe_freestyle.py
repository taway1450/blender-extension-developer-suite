"""Render the factory-startup scene with Freestyle (run by scripts/probe_freestyle.py, #136).

Usage (inside Blender):
  blender --background --factory-startup --python probe_freestyle.py -- <output json>

Three renders with Cycles at a small size:

- ``script`` twice: a style module (``SCRIPT`` mode) that sorts the chains with ``pyShuffleBP1D`` and colours the
  strokes with ``pyRandomColorShader(7)``, then records each stroke's colour. Seeded, both renders give the same
  colours.
- ``parameter_editor``: a line set whose line style uses the noise modifiers (``Noise.rand`` /
  ``turbulence_smooth``) and the geometry modifiers that call ``stroke_normal`` (sinus displacement, 2D offset).

Afterwards ``random.seed(0)`` must still be callable. The JSON holds each check's result; the driver reads it.
"""

from __future__ import annotations

import os
import random
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _recorder import check, script_args, write_results

STYLE_MODULE = """
import bpy
from freestyle.chainingiterators import ChainSilhouetteIterator
from freestyle.predicates import NotUP1D, QuantitativeInvisibilityUP1D, TrueUP1D, pyShuffleBP1D
from freestyle.shaders import ConstantThicknessShader, SamplingShader, pyRandomColorShader
from freestyle.types import Operators, StrokeShader


class RecordColorShader(StrokeShader):
    def shade(self, stroke):
        color = stroke[0].attribute.color
        bpy.app.driver_namespace["freestyle_probe_colors"].append(tuple(round(c, 6) for c in color))


Operators.select(QuantitativeInvisibilityUP1D(0))
Operators.bidirectional_chain(ChainSilhouetteIterator(), NotUP1D(QuantitativeInvisibilityUP1D(0)))
Operators.sort(pyShuffleBP1D())
shaders = [SamplingShader(5.0), ConstantThicknessShader(3), pyRandomColorShader(7), RecordColorShader()]
Operators.create(TrueUP1D(), shaders)
"""


def setup_scene() -> bpy.types.Scene:
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 1
    scene.cycles.device = "CPU"
    scene.render.resolution_x = 96
    scene.render.resolution_y = 72
    scene.render.resolution_percentage = 100
    scene.render.use_freestyle = True
    return scene


def render_script(scene: bpy.types.Scene) -> list[tuple[float, ...]]:
    settings = bpy.context.view_layer.freestyle_settings
    settings.mode = "SCRIPT"
    if not settings.modules:
        text = bpy.data.texts.new("probe_style.py")
        text.from_string(STYLE_MODULE)
        settings.modules.new().script = text
    bpy.app.driver_namespace["freestyle_probe_colors"] = []
    bpy.ops.render.render()
    return list(bpy.app.driver_namespace["freestyle_probe_colors"])


def render_parameter_editor(scene: bpy.types.Scene) -> None:
    settings = bpy.context.view_layer.freestyle_settings
    settings.mode = "EDITOR"
    lineset = settings.linesets.active or settings.linesets.new("LineSet")
    linestyle = lineset.linestyle
    linestyle.thickness_modifiers.new("Noise", "NOISE")
    linestyle.alpha_modifiers.new("Noise", "NOISE")
    linestyle.color_modifiers.new("Tangent", "TANGENT")
    linestyle.geometry_modifiers.new("Sinus", "SINUS_DISPLACEMENT")
    linestyle.geometry_modifiers.new("Offset", "2D_OFFSET")
    linestyle.geometry_modifiers.new("Noise", "PERLIN_NOISE_1D")
    bpy.ops.render.render()


def main() -> None:
    out = script_args()[0]
    scene = setup_scene()
    results: dict = {}
    check(results, "script_first", lambda: render_script(scene))
    check(results, "script_second", lambda: render_script(scene))
    check(results, "parameter_editor", lambda: render_parameter_editor(scene))
    check(results, "random_seed_callable", lambda: random.seed(0))
    write_results(out, results)


main()
