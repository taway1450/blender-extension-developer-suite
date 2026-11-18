"""What the probe drivers (``probe_*.py``) share: their command line, running their script in Blender and reading
the checks it recorded (with ``scripts/blender/_recorder.py``)."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from _common import CACHE_DIR, StepError, blender_script_command, validate_version


def probe_parser(doc: str | None) -> argparse.ArgumentParser:
    """A parser for the version to probe and the Blender binary to use; a probe adds its own options."""
    parser = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("version", type=validate_version, help="Blender version (X.Y) or build name (e.g. main)")
    parser.add_argument("--blender", type=Path, help="Blender binary (or its directory) to use")
    return parser


def probe_dir(name: str, version: str) -> Path:
    """``.cache/<name>/<version>``, created, where a probe writes its results and Blender's output."""
    out = CACHE_DIR / name / version
    out.mkdir(parents=True, exist_ok=True)
    return out


def run_blender(
    blender: Path, script: Path, *args: str | Path, log_path: Path, options: tuple[str, ...] = ()
) -> tuple[int, str]:
    """Run ``script`` with ``args`` in background Blender, write its output to ``log_path``; the exit code and the
    output."""
    command = blender_script_command(blender, script, *args, options=options)
    proc = subprocess.run(command, capture_output=True, text=True)
    output = proc.stdout + proc.stderr
    log_path.write_text(output, encoding="utf-8")
    return proc.returncode, output


def run_probe(
    blender: Path,
    script: Path,
    out: Path,
    *args: str | Path,
    log_path: Path | None = None,
    options: tuple[str, ...] = (),
) -> tuple[dict, str]:
    """Run the probe ``script`` in background Blender with the results file ``out`` and then ``args`` after
    ``--``; the results it wrote and Blender's output, which goes to ``log_path`` (default ``blender.log`` next to
    ``out``). Fails when Blender fails or writes no results."""
    log_path = log_path or out.parent / "blender.log"
    out.unlink(missing_ok=True)
    code, output = run_blender(blender, script, out, *args, log_path=log_path, options=options)
    if code or not out.exists():
        raise StepError(f"Blender failed with exit code {code} (see {log_path}):\n{output[-3000:]}")
    return json.loads(out.read_text(encoding="utf-8")), output


def failed_checks(results: dict, *, prefix: str = "", verb: str = "failed") -> list[str]:
    """One message per check the probe recorded as not ok, with its error."""
    return [f"{prefix}{name} {verb}:\n{r['error']}" for name, r in results.items() if not r["ok"]]
