from typing import assert_type

import bpy
from bpy.types import FluidDomainSettings

# The fluid presets apply from the Viscosity panel, which shows only for a fluid domain.
domain = bpy.context.fluid.domain_settings  # ty: ignore[blender-assumed-preset-context]
assert_type(domain, FluidDomainSettings)  # oracle-skip: stock ty keeps the stub type
domain.viscosity_base = 3.0
