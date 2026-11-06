"""Feature test: a Type tag also tells the type of a sibling pointer. An object whose type is 'MESH' has a Mesh as
its data, a text object ('FONT') a TextCurve, and a fluid modifier whose fluid_type is 'DOMAIN' has domain
settings. The assert_type calls in the bodies are no-ops at runtime."""

from typing import assert_type

from bpy.types import FluidDomainSettings, Mesh, Modifier, Object, TextCurve


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


def register():
    pass


def unregister():
    pass
