"""Run the source stub readers on a Blender source tree, then compare their stubs and audit a hand table.

``mise run probe:source-stubs <version>`` runs this. Each reader runs in its own ``uv`` process (libclang with
its pinned wheel) under the suite's machine-wide lock, which the readers inherit; a reader whose prerequisites
are missing (the makesrna build, a compile_commands.json) fails alone and the rest go on.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "scripts"))
from _resources import guarded

TOOLS = ("regex", "libclang", "makesrna")
PYTHON = ["uv", "run", "--no-project", "--python", "3.13"]
WHEELS = {"libclang": ["--with", "libclang==18.1.1"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("version", help="Version label for the outputs (e.g. 5.2)")
    parser.add_argument("--source", type=Path, help="Blender source tree (default: .cache/blender-src/<version>)")
    parser.add_argument("--tool", choices=(*TOOLS, "all"), default="all")
    args = parser.parse_args()
    tools = TOOLS if args.tool == "all" else (args.tool,)
    source = ["--source", str(args.source)] if args.source else []
    failed = []
    with guarded():
        for tool in tools:
            print(f"==> {tool}", flush=True)
            command = [*PYTHON, *WHEELS.get(tool, []), "python", str(HERE / tool / "run.py"), args.version, *source]
            if subprocess.run(command).returncode:
                failed.append(tool)
        for script in ("compare", "audit"):
            subprocess.run([*PYTHON, "python", str(HERE / "common" / f"{script}.py"), args.version])
    if failed:
        print(f"Failed: {', '.join(failed)}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
