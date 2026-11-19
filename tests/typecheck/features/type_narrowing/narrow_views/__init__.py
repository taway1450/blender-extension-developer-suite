"""Feature test: a Type tag also tells the type of a sibling pointer. An object whose type is 'MESH' has a Mesh as
its data, a text object ('FONT') a TextCurve, and a fluid modifier whose fluid_type is 'DOMAIN' has domain
settings. Writing that tag allocates the settings it implies, so after `fluid.fluid_type = 'DOMAIN'` in the same block
the modifier has domain settings too. The assert_type calls in the bodies are no-ops at runtime."""

from typing import Literal, assert_type

from bpy.types import FluidDomainSettings, FluidModifier, Mesh, Modifier, Object, TextCurve


def vertex_count(ob: Object) -> int:
    if ob.type == 'MESH':
        assert_type(ob.data, Mesh)
        ob.update_tag()
        assert_type(ob.data, Mesh)  # a call does not undo the test
        return len(ob.data.vertices)
    return 0


def body_text(ob: Object) -> str:
    if ob.type != 'FONT':
        return ''
    assert_type(ob.data, TextCurve)  # the curve of a text object is refined again
    return ob.data.body


def selected_meshes(objects: list[Object]) -> list[Mesh]:
    meshes = [ob.data for ob in objects if ob.type == 'MESH']
    assert_type(meshes, list[Mesh])  # the test in a comprehension
    return meshes


def data_name(ob: Object) -> str:
    match ob.type:
        case 'MESH':
            assert_type(ob.data, Mesh)  # a match on the tag
            return ob.data.name
    return ''


def domain_resolution(md: Modifier) -> int:
    if md.type == 'FLUID' and md.fluid_type == 'DOMAIN':
        assert_type(md.domain_settings, FluidDomainSettings)
        return md.domain_settings.resolution_max
    return 0


def make_domain(fluid: FluidModifier, other: FluidModifier) -> None:
    fluid.fluid_type = 'DOMAIN'
    assert_type(fluid.domain_settings, FluidDomainSettings)  # the setter allocates the domain settings
    fluid.domain_settings.use_noise = True
    fluid = other
    assert_type(fluid.domain_settings, FluidDomainSettings | None)  # bare-ok: bound again after the write


def maybe_domain(fluid: FluidModifier, domain: bool) -> None:
    if domain:
        fluid.fluid_type = 'DOMAIN'
    assert_type(fluid.domain_settings, FluidDomainSettings | None)  # bare-ok: the write is in a branch


def domain_then_kind(fluid: FluidModifier, kind: Literal['FLOW', 'EFFECTOR']) -> None:
    fluid.fluid_type = 'DOMAIN'
    fluid.name = "Domain"
    assert_type(fluid.domain_settings, FluidDomainSettings)  # a write of another attribute keeps the view
    fluid.fluid_type = kind
    assert_type(fluid.domain_settings, FluidDomainSettings | None)  # bare-ok: the last tag write is not a literal


def domain_in_loop(fluid: FluidModifier, kinds: list[Literal['FLOW', 'EFFECTOR']]) -> None:
    fluid.fluid_type = 'DOMAIN'
    for kind in kinds:
        assert_type(fluid.domain_settings, FluidDomainSettings | None)  # bare-ok: the loop writes the tag after it
        fluid.fluid_type = kind


def register():
    pass


def unregister():
    pass
