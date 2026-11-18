"""List every FUNC_REGISTER function in Blender's makesrna sources: struct, flags, inputs, outputs."""
import re, sys, pathlib

root = pathlib.Path(sys.argv[1]) / "source/blender/makesrna/intern"
files = ["rna_animation.cc", "rna_node_socket.cc", "rna_node_tree_interface.cc", "rna_nodetree.cc",
         "rna_render.cc", "rna_rna.cc", "rna_ui.cc", "rna_wm_api.cc", "rna_wm_gizmo.cc", "rna_wm.cc",
         "rna_userdef.cc", "rna_asset.cc", "rna_usd.cc", "rna_space.cc"]

for name in files:
    p = root / name
    if not p.exists():
        continue
    struct = None
    cfunc = None
    cur = None
    results = []
    raw = p.read_text(encoding="utf-8", errors="replace").splitlines()
    lines = []
    buf = ""
    for l in raw:
        s = l.rstrip()
        if buf:
            buf += " " + s.strip()
            if s.endswith(";") or s.endswith("{") or s.endswith("}"):
                lines.append(buf); buf = ""
            else:
                lines.append("")
            continue
        if re.search(r"RNA_def_\w+\($|RNA_def_\w+\(\s*func,?$|= RNA_def_\w+\(.*[,(]$", s):
            buf = s; continue
        lines.append(s)

    def flush():
        if cur and "FUNC_REGISTER" in cur["flags"]:
            results.append(cur)

    for i, line in enumerate(lines, 1):
        m = re.match(r"^(?:static )?void (\w+)\(", line)
        if m:
            flush(); cur = None
            cfunc = m.group(1)
            struct = None
        m = re.search(r'RNA_def_struct\(\s*brna,\s*"(\w+)"', line)
        if m:
            struct = m.group(1)
        m = re.search(r'RNA_def_function\(\s*srna,\s*"(\w+)"', line)
        if m:
            flush()
            cur = {"struct": struct or f"<{cfunc}>", "name": m.group(1), "line": i, "flags": "",
                   "params": [], "file": name}
            continue
        if cur is None:
            continue
        m = re.search(r"RNA_def_function_flag\(func,\s*([^;]+)\);", line)
        if m:
            cur["flags"] += m.group(1)
        # parameter definitions
        m = re.search(r'RNA_def_(?!function)\w+\(\s*func,\s*"(\w+)"', line)
        if m:
            cur["params"].append({"name": m.group(1), "opt": False, "out": False})
        m2 = re.search(r'RNA_def_function_return\(func,\s*RNA_def_\w+\(func,\s*"(\w+)"', line)
        if m2:
            cur["params"][-1]["out"] = True
        if re.search(r"RNA_def_function_(return|output)\(func,\s*\w+\)", line):
            cur["params"][-1]["out"] = True
        if "PARM_PYFUNC_REGISTER_OPTIONAL" in line and cur["params"]:
            cur["params"][-1]["opt"] = True
    flush()
    for r in results:
        ins = [x for x in r["params"] if not x["out"]]
        outs = [x["name"] for x in r["params"] if x["out"]]
        no_self = "FUNC_NO_SELF" in r["flags"]
        self_type = "FUNC_USE_SELF_TYPE" in r["flags"]
        kind = "classmethod" if no_self and not self_type else ("function(cls-arg)" if no_self else "function")
        required = "FUNC_REGISTER_OPTIONAL" not in r["flags"]
        base = 0 if (no_self and not self_type) else 1
        maxc = base + len(ins) + (1 if kind == "classmethod" else 0)
        first_opt = next((k for k, x in enumerate(ins) if x["opt"]), None)
        minc = maxc if first_opt is None else base + first_opt + (1 if kind == "classmethod" else 0)
        args = ", ".join(x["name"] + ("?" if x["opt"] else "") for x in ins)
        print(f'{r["file"]}:{r["line"]}\t{r["struct"]}.{r["name"]}\t{kind}\t'
              f'{"REQUIRED" if required else "optional"}\tpos={minc if minc==maxc else f"{minc}-{maxc}"}\t'
              f'({args}) -> {outs}')
