"""Runs inside Blender: dump the RNA flags of the documented API, what the API docs say about them and
the runtime behaviour probed in this Blender build, as JSON.

Usage (see report_flags.py):
  blender --background --factory-startup --python scripts/blender/dump_rna_flags.py --       OUTPUT.json [--docs-kw-only] [--crashed CRASHED.txt]

The docs columns are computed with the same ``rna_info`` calls ``doc/python_api/sphinx_doc_gen.py``
uses. ``--docs-kw-only`` tells the script that this Blender version's ``sphinx_doc_gen.py`` writes a
``*`` before the first optional argument (older versions list all arguments positionally).

Probes never run an API function or operator: every probe call passes an extra unknown keyword
argument, and ``pyrna_func_vectorcall`` (``bpy_rna.cc``) rejects unknown keywords after converting
the arguments but before calling the function. A probe therefore only reports how the arguments were
parsed. Property probes assign the current value back (or ``None``, restoring the old value after).

Before each probe step ``OUTPUT.json.progress`` is overwritten with ``<path>:<step>``, so when a probe
crashes Blender the caller can add that line to ``CRASHED.txt`` and run the script again; crashed steps
are skipped and reported in the row's ``runtime.crashed``.
"""

import collections
import itertools
import json
import os
import sys
import traceback

import bpy

try:
    import _rna_info as rna_info
except ImportError:  # Blender < 4.4
    import rna_info

PROBE_KW = "__flag_probe__"
UNKNOWN_KW_MESSAGES = ("invalid keyword argument(s) (" + PROBE_KW,)
MAX_POOL_VISITS = 60000
MAX_COLLECTION_ITEMS = 3


# -----------------------------------------------------------------------------
# Instances to probe on


def seed_data():
    """Create data-blocks, modifiers, constraints, nodes... so the pool has instances of most types."""

    def attempt(fn):
        try:
            return fn()
        except Exception:
            return None

    scene = bpy.context.scene
    data = bpy.data

    def link(name, obdata):
        ob = data.objects.new(name, obdata)
        scene.collection.objects.link(ob)
        return ob

    for curve_type in ("CURVE", "SURFACE", "FONT"):
        curve = attempt(lambda: data.curves.new(curve_type.lower(), curve_type))
        if curve is not None:
            if curve_type != "FONT":
                attempt(lambda: curve.splines.new("BEZIER").bezier_points.add(1))
                attempt(lambda: curve.splines.new("NURBS").points.add(2))
            link(curve_type.lower(), curve)
    attempt(lambda: link("metaball", data.metaballs.new("metaball")).data.elements.new())
    attempt(lambda: link("lattice", data.lattices.new("lattice")))
    attempt(lambda: link("armature", data.armatures.new("armature")))
    attempt(lambda: link("speaker", data.speakers.new("speaker")))
    attempt(lambda: link("volume", data.volumes.new("volume")))
    attempt(lambda: link("pointcloud", data.pointclouds.new("pointcloud")))
    attempt(lambda: link("curves", data.hair_curves.new("curves")))
    attempt(lambda: link("grease_pencil", data.grease_pencils_v3.new("grease_pencil")))
    attempt(lambda: link("grease_pencil", data.grease_pencils.new("grease_pencil")))
    for light_type in ("POINT", "SUN", "SPOT", "AREA"):
        attempt(lambda: link(light_type, data.lights.new(light_type, light_type)))
    for probe_type in ("SPHERE", "PLANE", "VOLUME", "CUBEMAP", "PLANAR", "GRID"):
        attempt(lambda: link(probe_type, data.lightprobes.new(probe_type, probe_type)))
    tex_type_prop = bpy.types.Texture.bl_rna.properties["type"]
    for item in tex_type_prop.enum_items:
        attempt(lambda: data.textures.new(item.identifier, item.identifier))
    attempt(lambda: data.images.new("image", 4, 4))
    attempt(lambda: data.masks.new("mask").layers.new())
    attempt(lambda: data.palettes.new("palette").colors.new())
    attempt(lambda: data.actions.new("action"))
    attempt(lambda: data.particles.new("particles"))
    attempt(lambda: data.linestyles.new("linestyle"))
    attempt(lambda: data.texts.new("text"))
    attempt(lambda: data.fonts.load("<builtin>"))
    attempt(lambda: data.cache_files)
    attempt(lambda: scene.keying_sets.new())
    attempt(lambda: scene.timeline_markers.new("marker"))

    # Modifiers, constraints and visual effects of every type on a mesh object.
    mesh_ob = next((ob for ob in data.objects if ob.type == "MESH"), None) or link("mesh", data.meshes.new("mesh"))
    for item in bpy.types.Modifier.bl_rna.properties["type"].enum_items:
        attempt(lambda: mesh_ob.modifiers.new(item.identifier, item.identifier))
    for item in bpy.types.Constraint.bl_rna.properties["type"].enum_items:
        attempt(lambda: mesh_ob.constraints.new(item.identifier))
    attempt(lambda: mesh_ob.vertex_groups.new())
    attempt(lambda: mesh_ob.shape_key_add(name="Basis"))
    attempt(lambda: mesh_ob.data.uv_layers.new())
    attempt(lambda: mesh_ob.data.color_attributes.new("color", "FLOAT_COLOR", "POINT"))
    attempt(lambda: mesh_ob.particle_systems)
    attempt(lambda: mesh_ob.animation_data_create())
    attempt(lambda: mesh_ob.animation_data.drivers.new("location", index=0))

    # Strips.
    editor = attempt(lambda: scene.sequence_editor_create())
    if editor is not None:
        strips = getattr(editor, "strips", None) or getattr(editor, "sequences", None)
        for effect in ("COLOR", "ADJUSTMENT", "TEXT"):
            attempt(lambda: strips.new_effect(effect, effect, 1, frame_start=1, frame_end=10))

    # One node of every node type, in each kind of node tree that accepts it.
    trees = [
        attempt(lambda: data.node_groups.new(t, t))
        for t in ("ShaderNodeTree", "GeometryNodeTree", "CompositorNodeTree", "TextureNodeTree")
    ]
    trees = [t for t in trees if t is not None]
    node_types = [t for t in dir(bpy.types) if _is_subclass(t, "Node")]
    for node_type in node_types:
        for tree in trees:
            if attempt(lambda: tree.nodes.new(node_type)) is not None:
                break


def _is_subclass(identifier, base_identifier):
    rna = getattr(getattr(bpy.types, identifier, None), "bl_rna", None)
    while rna is not None:
        if rna.identifier == base_identifier:
            return True
        rna = rna.base
    return False


def build_pool(progress, crashed):
    """Map each struct identifier to an instance of it (or of a subclass), found by walking the data.

    Reads that crashed Blender in an earlier run (``pool <Struct>.<prop>:read`` in ``crashed``) are skipped.
    """
    pool = {}
    exact = set()

    def add(obj, rna):
        while rna is not None:
            pool.setdefault(rna.identifier, obj)
            rna = rna.base

    seen = set()
    roots = [bpy.data, bpy.context.window_manager, bpy.context.preferences, bpy.context.scene, bpy.context.view_layer]
    queue = collections.deque((root, 0) for root in roots if root is not None)
    visits = 0
    while queue and visits < MAX_POOL_VISITS:
        obj, depth = queue.popleft()
        try:
            rna = obj.bl_rna
        except (AttributeError, ReferenceError):
            continue
        try:
            key = (obj.as_pointer(), rna.identifier)
        except Exception:
            key = (id(obj), rna.identifier)
        if key in seen:
            continue
        seen.add(key)
        visits += 1
        # Exact types win over the subclass instances added for their bases.
        if rna.identifier not in exact:
            pool[rna.identifier] = obj
            exact.add(rna.identifier)
        add(obj, rna.base)
        if depth > 10:
            continue
        for prop in rna.properties:
            if prop.identifier == "rna_type" or prop.type not in {"POINTER", "COLLECTION"}:
                continue
            # Depsgraph iterators hand out temporary instances that are freed while walking.
            if prop.fixed_type is not None and prop.fixed_type.identifier.startswith("Depsgraph"):
                continue
            step = f"pool {rna.identifier}.{prop.identifier}:read"
            if step in crashed:
                continue
            progress(step)
            try:
                value = getattr(obj, prop.identifier)
            except Exception:
                continue
            if value is None:
                continue
            if prop.type == "POINTER":
                queue.append((value, depth + 1))
            else:
                if prop.srna is not None:
                    pool.setdefault(prop.srna.identifier, value)
                try:
                    items = list(itertools.islice(iter(value), MAX_COLLECTION_ITEMS))
                except Exception:
                    items = []
                queue.extend((item, depth + 1) for item in items)
    return pool


# -----------------------------------------------------------------------------
# Flags and docs


def prop_flags(rna_prop):
    array_dimensions = tuple(getattr(rna_prop, "array_dimensions", ()))
    while array_dimensions and array_dimensions[-1] == 0:
        array_dimensions = array_dimensions[:-1]
    return {
        "type": rna_prop.type,
        "subtype": getattr(rna_prop, "subtype", ""),
        "fixed_type": getattr(getattr(rna_prop, "fixed_type", None), "identifier", None),
        "is_required": rna_prop.is_required,
        "is_output": rna_prop.is_output,
        "is_never_none": rna_prop.is_never_none,
        "is_argument_optional": rna_prop.is_argument_optional,
        "is_readonly": rna_prop.is_readonly,
        "is_enum_flag": getattr(rna_prop, "is_enum_flag", False),
        "is_registered": rna_prop.is_registered,
        "is_registered_optional": rna_prop.is_registered_optional,
        "is_path_supports_blend_relative": getattr(rna_prop, "is_path_supports_blend_relative", False),
        "is_path_supports_templates": getattr(rna_prop, "is_path_supports_templates", False),
        "is_deprecated": getattr(rna_prop, "is_deprecated", False),
        "is_array": getattr(rna_prop, "is_array", False),
        "array_length": getattr(rna_prop, "array_length", 0),
        "array_dimensions": array_dimensions,
    }


def _top_level_union(type_str):
    parts, depth, current = [], 0, ""
    for char in type_str:
        depth += char in "[(" and 1 or char in "])" and -1 or 0
        if char == "|" and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += char
    return parts + [current.strip()]


def prop_docs(info_prop, **kwargs):
    """What the docs say: the type text, its qualifiers and the facts the report compares."""
    description = info_prop.get_type_description(**kwargs)
    if isinstance(description, tuple):
        type_str, type_info = description
        type_info = list(type_info)
        return {
            "type": type_str,
            "info": type_info,
            "none": "None" in _top_level_union(type_str),
            "set": type_str.startswith("set["),
            "readonly": "readonly" in type_info,
            "dynamic": any("dynamic array" in info for info in type_info),
        }
    # Blender < 4.4 writes prose such as "Object, (optional, never None)": pointers are taken to
    # allow None unless they say "never None".
    text = description
    type_info = []
    if text.endswith(")") and ", (" in text:
        type_info = [q.strip() for q in text[text.rindex(", (") + 3 : -1].split(",")]
    return {
        "type": text,
        "info": type_info,
        "none": info_prop.type == "pointer" and "never None" not in type_info,
        "set": " set in " in text,
        "readonly": "readonly" in type_info,
        "dynamic": "dynamic" in text,
    }


def func_flags(rna_func):
    return {
        "use_self": rna_func.use_self,
        "use_self_type": rna_func.use_self_type,
        "is_registered": rna_func.is_registered,
        "is_registered_optional": rna_func.is_registered_optional,
    }


# -----------------------------------------------------------------------------
# Probes


class _Unconvertible:
    """A value no RNA property type accepts."""


class Probe:
    def __init__(self, pool, progress, crashed):
        self.pool = pool
        self.progress = progress
        # Probe steps that crashed Blender in an earlier run: they're skipped and reported.
        self.crashed = crashed
        self.path = ""
        self.result = {}

    def start(self, path):
        self.path = path
        self.result = {}
        return self.result

    def guard(self, step):
        """Write the step to the progress file; return False if it crashed Blender before."""
        key = f"{self.path}:{step}"
        # "<prefix>*" skips every probe of a struct (or operator) whose data crashed when read.
        if key in self.crashed or any(c.endswith("*") and self.path.startswith(c[:-1]) for c in self.crashed):
            self.result.setdefault("crashed", []).append(step)
            return False
        self.progress(key)
        return True

    def sample(self, rna_prop):
        """A value that converts to ``rna_prop`` without errors, or raise LookupError."""
        ptype = rna_prop.type
        if ptype in {"BOOLEAN", "INT", "FLOAT"}:
            if getattr(rna_prop, "is_array", False) or rna_prop.array_length:
                dims = [d for d in rna_prop.array_dimensions if d] or [rna_prop.array_length]
                if not rna_prop.array_length:
                    return []
                flat = list(rna_prop.default_array)
                for dim in reversed(dims[1:]):
                    flat = [flat[i : i + dim] for i in range(0, len(flat), dim)]
                return flat
            return rna_prop.default
        if ptype == "STRING":
            return rna_prop.default or ""
        if ptype == "ENUM":
            if rna_prop.is_enum_flag:
                return set()
            items = [item.identifier for item in rna_prop.enum_items] or [
                item.identifier for item in rna_prop.enum_items_static
            ]
            if rna_prop.default in items:
                return rna_prop.default
            if items:
                return items[0]
            raise LookupError("enum without items")
        if ptype == "POINTER":
            value = self.pool.get(rna_prop.fixed_type.identifier)
            if value is None:
                raise LookupError(f"no {rna_prop.fixed_type.identifier} instance")
            return value
        if ptype == "COLLECTION":
            return []
        raise LookupError(ptype)

    def call(self, step, fn, args, kwargs):
        """Call a bpy_func with the probe keyword and return the TypeError message."""
        if not self.guard(step):
            return "CRASHED"
        try:
            fn(*args, **kwargs, **{PROBE_KW: 0})
        except TypeError as ex:
            return str(ex)
        except Exception as ex:  # Should not happen, the function is never run.
            return f"{type(ex).__name__}: {ex}"
        return "CALLED"

    def param_probes(self, fn, rna_func, inputs, index):
        """Probe parameter ``inputs[index]``. Returns a dict of results (missing keys: not probed)."""
        param = inputs[index]
        name = param.identifier
        result = self.result
        try:
            required_before = {p.identifier: self.sample(p) for p in inputs[:index] if p.is_required}
        except LookupError as ex:
            result["skipped"] = f"no value for an earlier parameter ({ex})"
            return result
        n_inputs = len(inputs)
        reached_end = lambda msg: PROBE_KW in msg and "invalid keyword" in msg

        # Required: leave the parameter out.
        msg = self.call("required", fn, (), required_before)
        if f'required parameter "{name}" not specified' in msg:
            result["required"] = True
        elif reached_end(msg):
            result["required"] = False
        else:
            result["required_inconclusive"] = msg

        if len(required_before) + 2 <= n_inputs:
            # None.
            msg = self.call("none", fn, (), {**required_before, name: None})
            if reached_end(msg):
                result["accepts_none"] = True
            elif f'keyword argument "{name}"' in msg:
                result["accepts_none"] = False
                result["none_error"] = msg.split(" - ", 1)[-1][:160]
            else:
                result["none_inconclusive"] = msg

            if param.type == "ENUM" and param.is_enum_flag:
                msg = self.call("enum_str", fn, (), {**required_before, name: "__probe_str__"})
                result["enum_flag_accepts_str"] = reached_end(msg)
                msg = self.call("enum_set", fn, (), {**required_before, name: set()})
                result["enum_flag_accepts_set"] = reached_end(msg)

            if param.type in {"BOOLEAN", "INT", "FLOAT"} and param.array_length:
                try:
                    value = self.sample(param)
                    longer = value + value[:1] if value else value
                    msg = self.call("length", fn, (), {**required_before, name: longer})
                    result["accepts_other_length"] = reached_end(msg)
                except LookupError:
                    pass

        if index + 2 <= n_inputs:
            # Positional: all earlier parameters and this one by position.
            try:
                args = [self.sample(p) for p in inputs[:index]] + [self.sample(param)]
            except LookupError:
                args = None
            if args is not None:
                msg = self.call("positional", fn, args, {})
                if reached_end(msg) or f'argument {index + 1}, "{name}"' in msg:
                    result["positional"] = True
                elif "to be a keyword argument" in msg:
                    result["positional"] = False
                else:
                    result["positional_inconclusive"] = msg
        return result

    def property_probes(self, obj, rna_prop):
        name = rna_prop.identifier
        result = self.result
        if not self.guard("read"):
            return result
        try:
            value = getattr(obj, name)
        except Exception as ex:
            result["skipped"] = f"getattr failed: {ex}"[:160]
            return result
        result["observed_none"] = value is None
        if type(obj).__name__ == "bpy_prop_collection":
            result["collection_wrapper"] = True
        if rna_prop.type == "COLLECTION":
            # Assigning to a collection replaces its items, so it's not probed.
            return result
        if not self.guard("write"):
            return result
        # pyrna_struct_setattro checks that the property is editable before converting the value,
        # so assigning a value of no supported type tells read-only from writable without writing.
        try:
            setattr(obj, name, _Unconvertible())
            result["write_error"] = "an unconvertible value was accepted"
        except AttributeError as ex:
            result["writable"] = "read-only" not in str(ex)
            if result["writable"]:
                result["write_error"] = str(ex)[:160]
        except TypeError:
            result["writable"] = True
        except Exception as ex:
            result["write_error"] = f"{type(ex).__name__}: {ex}"[:160]
        if result.get("writable") and self.guard("none"):
            try:
                setattr(obj, name, None)
                result["accepts_none"] = True
                try:
                    setattr(obj, name, value)
                except Exception:
                    pass
            except TypeError as ex:
                result["accepts_none"] = False
                result["none_error"] = str(ex)[:160]
            except Exception as ex:
                result["none_error"] = f"{type(ex).__name__}: {ex}"[:160]
        return result


# -----------------------------------------------------------------------------


def bound_function(pool, struct_id, rna_func):
    """A bpy_func for ``rna_func`` to probe with, preferring one bound to an instance."""
    candidates = []
    if struct_id in pool:
        candidates.append(pool[struct_id])
    candidates.append(getattr(bpy.types, struct_id, None))
    for owner in candidates:
        try:
            fn = getattr(owner, rna_func.identifier)
        except Exception:
            continue
        # Only RNA functions; a Python override with the same name would really run.
        if type(fn).__name__ == "bpy_func":
            return fn, owner is not candidates[-1]
    return None, False


def dump(docs_kw_only, progress, crashed):
    progress("seed data")
    seed_data()
    progress("instance pool")
    pool = build_pool(progress, crashed)
    probe = Probe(pool, progress, crashed)
    structs, _funcs, ops, _props = rna_info.BuildRNAInfo()

    rows = []
    for struct in sorted(structs.values(), key=lambda s: s.identifier):
        if struct.module_name != "bpy.types":
            continue
        struct_id = struct.identifier
        rna = struct.bl_rna
        progress(struct_id)
        rows.append(
            {
                "kind": "class",
                "path": struct_id,
                "base": struct.base.identifier if struct.base else None,
                "registerable": any(f.is_registered for f in rna.functions)
                or any(p.is_registered for p in rna.properties),
                "probed_instance": struct_id in pool,
            }
        )

        instance = pool.get(struct_id)
        for prop in struct.properties:
            rna_prop = prop.bl_prop
            row = {
                "kind": "property",
                "path": f"{struct_id}.{prop.identifier}",
                "flags": prop_flags(rna_prop),
                "docs": prop_docs(prop),
                "runtime": {},
            }
            if instance is not None and not rna_prop.is_registered:
                probe.start(row["path"])
                try:
                    row["runtime"] = probe.property_probes(instance, rna_prop)
                except Exception as ex:
                    row["runtime"] = {"skipped": f"{type(ex).__name__}: {ex}"[:160]}
            rows.append(row)

        for func in struct.functions:
            rna_func = func.bl_func
            path = f"{struct_id}.{func.identifier}"
            inputs = [p for p in rna_func.parameters if not p.is_output]
            outputs = [p for p in rna_func.parameters if p.is_output]
            kw_only_index = (
                next((i for i, p in enumerate(func.args) if not p.is_required), None) if docs_kw_only else None
            )
            rows.append(
                {
                    "kind": "function",
                    "path": path,
                    "flags": func_flags(rna_func),
                    "docs": {"kind": "classmethod" if func.is_classmethod else "method"},
                    "n_outputs": len(outputs),
                }
            )
            fn, bound_to_instance = (
                (None, False) if rna_func.is_registered else bound_function(pool, struct_id, rna_func)
            )
            info_args = {a.identifier: a for a in func.args}
            for index, param in enumerate(inputs):
                info = info_args[param.identifier]
                row = {
                    "kind": "parameter",
                    "path": f"{path}({param.identifier})",
                    "function": path,
                    "index": index,
                    "callback": rna_func.is_registered,
                    "flags": prop_flags(param),
                    "docs": {
                        **prop_docs(info, as_arg=True),
                        "signature": info.get_arg_default(force=False),
                        "kw_only": kw_only_index is not None and index >= kw_only_index,
                    },
                    "runtime": {},
                }
                if fn is not None:
                    probe.start(row["path"])
                    row["runtime"] = probe.param_probes(fn, rna_func, inputs, index)
                    row["runtime"]["bound_to_instance"] = bound_to_instance
                elif not rna_func.is_registered:
                    row["runtime"] = {"skipped": "no instance to call the function on"}
                rows.append(row)
            info_returns = {r.identifier: r for r in func.return_values}
            for index, param in enumerate(outputs):
                rows.append(
                    {
                        "kind": "return",
                        "path": f"{path} -> {param.identifier}",
                        "function": path,
                        "index": index,
                        "n_outputs": len(outputs),
                        "callback": rna_func.is_registered,
                        "flags": prop_flags(param),
                        "docs": prop_docs(info_returns[param.identifier], as_ret=True),
                    }
                )

    window_manager = bpy.context.window_manager
    for op in sorted(ops.values(), key=lambda o: (o.module_name, o.func_name)):
        path = f"bpy.ops.{op.module_name}.{op.func_name}"
        progress(path)
        rows.append({"kind": "operator", "path": path})
        try:
            properties = window_manager.operator_properties_last(op.identifier)
        except Exception:
            properties = None
        for prop in op.args:
            rna_prop = prop.bl_prop
            row = {
                "kind": "operator argument",
                "path": f"{path}({prop.identifier})",
                "function": path,
                "flags": prop_flags(rna_prop),
                "docs": {**prop_docs(prop, as_arg=True), "signature": prop.get_arg_default(force=True)},
                "runtime": {},
            }
            if properties is not None:
                probe.start(row["path"])
                try:
                    runtime = probe.property_probes(properties, rna_prop)
                    # Operator arguments are always assignable, readonly only affects the UI.
                    runtime.pop("writable", None)
                    row["runtime"] = runtime
                except Exception as ex:
                    row["runtime"] = {"skipped": f"{type(ex).__name__}: {ex}"[:160]}
            rows.append(row)

    return {
        "blender_version": bpy.app.version_string,
        "docs_kw_only": docs_kw_only,
        "pool_types": len(pool),
        "rows": rows,
    }


def main():
    argv = sys.argv[sys.argv.index("--") + 1 :]
    output = argv[0]
    docs_kw_only = "--docs-kw-only" in argv
    crashed = set()
    if "--crashed" in argv:
        with open(argv[argv.index("--crashed") + 1], encoding="utf-8") as fh:
            crashed = {line.strip() for line in fh if line.strip()}
    # The last item is written before each probe, so a crash names its culprit.
    progress_path = output + ".progress"
    with open(progress_path, "w", encoding="utf-8") as progress_file:

        def progress(item):
            progress_file.seek(0)
            progress_file.write(item + "\n")
            progress_file.truncate()
            progress_file.flush()

        try:
            result = dump(docs_kw_only, progress, crashed)
        except Exception:
            traceback.print_exc()
            sys.exit(1)
    with open(output, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=None)
    os.remove(progress_path)
    print(f"Wrote {len(result['rows'])} rows to {output}")


main()
