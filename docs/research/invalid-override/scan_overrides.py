"""Apply the proposed callback table to every class body in the feature tests (by base *names*, syntactic).

Prints each def that Blender would reject, so we can see which lines blender-invalid-override would hit.
"""
import ast, pathlib, sys

F, C = "function", "classmethod"
# root -> name -> (kind, min, max) counts include self/cls
T = {
    "Operator": {"poll": (C, 2, 2), "execute": (F, 2, 2), "check": (F, 2, 2), "invoke": (F, 3, 3),
                 "modal": (F, 3, 3), "draw": (F, 2, 2), "cancel": (F, 2, 2), "description": (C, 3, 3)},
    "Macro": {"poll": (C, 2, 2), "draw": (F, 2, 2)},
    "Panel": {"poll": (C, 2, 2), "draw": (F, 2, 2), "draw_header": (F, 2, 2), "draw_header_preset": (F, 2, 2)},
    "Menu": {"poll": (C, 2, 2), "draw": (F, 2, 2)},
    "Header": {"draw": (F, 2, 2)},
    "UIList": {"draw_item": (F, 7, 10), "draw_filter": (F, 3, 3), "filter_items": (F, 6, 6)},
    "Node": {"poll": (C, 2, 2), "poll_instance": (F, 2, 2), "update": (F, 1, 1), "insert_link": (F, 2, 2),
             "init": (F, 2, 2), "copy": (F, 2, 2), "free": (F, 1, 1), "draw_buttons": (F, 3, 3),
             "draw_buttons_ext": (F, 3, 3), "draw_label": (F, 1, 1)},
    "NodeTree": {"poll": (C, 2, 2), "update": (F, 1, 1), "get_from_context": (C, 2, 2),
                 "valid_socket_type": (C, 2, 2)},
    "NodeSocket": {"draw": (F, 5, 5), "draw_color": (F, 3, 3), "draw_color_simple": (C, 1, 1)},
}

if len(sys.argv) > 2:  # the table extracted from makesrna (rna_callbacks.py output)
    T = {}
    for line in open(sys.argv[2]):
        loc, qual, kind, req, pos, *_ = line.rstrip("\n").split("\t")
        owner, fname = qual.split(".")
        owner = {"<RNA_api_operator>": "Operator", "<RNA_api_macro>": "Macro"}.get(owner, owner)
        if owner == "NodeSocketStandard":
            continue
        lo, _, hi = pos[4:].partition("-")
        T.setdefault(owner, {})[fname] = (C if kind == "classmethod" else F, int(lo), int(hi or lo))

root = pathlib.Path(sys.argv[1])
classes = {}
for path in root.rglob("*.py"):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.setdefault(node.name, []).append((path, node))


def base_names(node):
    for b in node.bases:
        yield b.attr if isinstance(b, ast.Attribute) else getattr(b, "id", None)


def root_of(node, seen=()):
    for name in base_names(node):
        if name in T:
            return name
        for p, other in classes.get(name, []):
            if other is not node and name not in seen:
                r = root_of(other, seen + (name,))
                if r:
                    return r
    return None


hits = 0
for name, defs in classes.items():
    for path, node in defs:
        r = root_of(node)
        if not r:
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.FunctionDef) or stmt.name not in T[r]:
                continue
            kind, lo, hi = T[r][stmt.name]
            decos = [getattr(d, "id", None) for d in stmt.decorator_list]
            have = C if "classmethod" in decos else ("static" if "staticmethod" in decos else F)
            n = len(stmt.args.posonlyargs) + len(stmt.args.args)
            problem = None
            if kind == C and have != C:
                problem = "must be a classmethod"
            elif kind == F and have == C:
                problem = "must not be a classmethod"
            elif not (lo <= n <= hi):
                problem = f"{n} positional, Blender wants {lo}" + (f"-{hi}" if hi != lo else "")
            if problem:
                hits += 1
                print(f"{path.relative_to(root)}:{stmt.lineno}: {r}.{stmt.name}: {problem}")
print("hits:", hits)
