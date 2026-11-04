# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""Query ty's language server at the markers in ``tests/typecheck/`` and compare with the recorded results.

Checks what an editor shows people using the bpy stubs: hover text, signature help, completions and
deprecation. Markers are comment lines below the code they query, with a caret at the column
(see ``tests/typecheck/README.md``):

    obj.location
    #   ^hover-contains "Location of the object"

They live in ``ide_*.py`` files in ``tests/typecheck/features/<feature>/`` and ``tests/typecheck/ide/<feature>/``.
All results, passes and failures alike, are written to ``tests/typecheck/expected/<generator>/<version>.ide.md``;
the task fails when that file would change, and ``--update`` rewrites it. The raw LSP responses go to
``.cache/typecheck-results/<version>/<generator>/ide.json``.

Usage:
  uv run scripts/check_ide.py main
  uv run scripts/check_ide.py 5.2 hover_rna_props --generator fake-bpy-module
  uv run scripts/check_ide.py main --update
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from typing import Any

from _common import CACHE_DIR, TYPECHECK_TESTS_DIR, StepError, log, main_wrapper
from build_ty import build_ty
from generate_stubs import (
    add_stubs_arguments,
    blender_python_version,
    ensure_worktree,
    generate_stubs,
    resolve_generators,
)

SEARCH_DIRS = (TYPECHECK_TESTS_DIR / "features", TYPECHECK_TESTS_DIR / "ide")
EXPECTED_DIR = TYPECHECK_TESTS_DIR / "expected"
RESULTS_DIR = CACHE_DIR / "typecheck-results"
REQUEST_TIMEOUT = 120  # seconds; the first request loads the stubs

MARKER = re.compile(r"^\s*#.*?\^(?P<kind>[a-z][a-z-]*)(?:\s+(?P<arg>.*?))?\s*$")
KINDS = ("hover", "hover-contains", "hover-none", "signature", "signature-param", "completion", "deprecated")
MAX_LINES = 40  # longer hover/signature texts are cut in the golden file


# --- LSP client -----------------------------------------------------------------------------------------------


class LspError(StepError):
    pass


class LspClient:
    """A minimal JSON-RPC client for a language server on stdio: requests, notifications, and null replies to
    the server's own requests (we advertise no capabilities that need real answers)."""

    def __init__(self, cmd: list[str], cwd: Path) -> None:
        self.process = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL)
        self.next_id = 0
        self.responses: dict[int, Queue[dict[str, Any]]] = {}
        self.lock = threading.Lock()
        self.reader = threading.Thread(target=self._read_loop, daemon=True)
        self.reader.start()

    def _read_message(self) -> dict[str, Any] | None:
        assert self.process.stdout is not None
        length = None
        while True:
            header = self.process.stdout.readline()
            if not header:
                return None
            header = header.strip()
            if not header:
                break
            name, _, value = header.decode("ascii").partition(":")
            if name.lower() == "content-length":
                length = int(value)
        if length is None:
            raise LspError("Language server sent a message without Content-Length")
        return json.loads(self.process.stdout.read(length).decode("utf-8"))

    def _read_loop(self) -> None:
        while (message := self._read_message()) is not None:
            if "id" in message and "method" in message:  # a request from the server
                self._send({"jsonrpc": "2.0", "id": message["id"], "result": None})
            elif "id" in message:
                with self.lock:
                    queue = self.responses.get(message["id"])
                if queue is not None:
                    queue.put(message)

    def _send(self, message: dict[str, Any]) -> None:
        assert self.process.stdin is not None
        body = json.dumps(message).encode("utf-8")
        with self.lock:
            self.process.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
            self.process.stdin.flush()

    def request(self, method: str, params: Any) -> Any:
        queue: Queue[dict[str, Any]] = Queue()
        with self.lock:
            self.next_id += 1
            request_id = self.next_id
            self.responses[request_id] = queue
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        try:
            response = queue.get(timeout=REQUEST_TIMEOUT)
        except Empty:
            raise LspError(f"No response to {method} within {REQUEST_TIMEOUT}s") from None
        finally:
            with self.lock:
                del self.responses[request_id]
        if "error" in response:
            raise LspError(f"{method} failed: {response['error']}")
        return response.get("result")

    def notify(self, method: str, params: Any) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def close(self) -> None:
        try:
            self.request("shutdown", None)
            self.notify("exit", None)
            self.process.wait(timeout=10)
        except Exception:
            self.process.kill()


def start_server(ty: Path, stubs: Path, python_version: str) -> LspClient:
    client = LspClient([str(ty), "server"], cwd=TYPECHECK_TESTS_DIR)
    markdown_first = ["markdown", "plaintext"]
    client.request("initialize", {
        "processId": None,
        "rootUri": TYPECHECK_TESTS_DIR.as_uri(),
        "workspaceFolders": [{"uri": TYPECHECK_TESTS_DIR.as_uri(), "name": "typecheck"}],
        "capabilities": {
            "textDocument": {
                "hover": {"contentFormat": markdown_first},
                "completion": {"completionItem": {"documentationFormat": markdown_first, "tagSupport": {"valueSet": [1]}}},
                "signatureHelp": {"signatureInformation": {"documentationFormat": markdown_first,
                                                           "parameterInformation": {"labelOffsetSupport": True}}},
                "diagnostic": {},
            },
            "general": {"positionEncodings": ["utf-16"]},
        },
        # ty reads these like a ty.toml; the [rules] and [environment] root come from tests/typecheck/ty.toml.
        "initializationOptions": {"configuration": {"environment": {
            "extra-paths": [str(stubs)], "python-version": python_version}}},
    })
    client.notify("initialized", {})
    return client


# --- markers ----------------------------------------------------------------------------------------------------


@dataclass
class Marker:
    path: Path
    line: int  # 0-based line of the queried code
    character: int  # 0-based column of the caret
    kind: str
    arg: str | None
    source: str  # the queried code line

    @property
    def rel(self) -> str:
        return self.path.relative_to(TYPECHECK_TESTS_DIR).as_posix()

    @property
    def title(self) -> str:
        arg = f" {self.arg}" if self.arg else ""
        return f"{self.rel}:{self.line + 1}:{self.character + 1} ^{self.kind}{arg}"


def feature_dirs() -> dict[str, Path]:
    dirs = {}
    for base in SEARCH_DIRS:
        if base.is_dir():
            for path in sorted(base.iterdir()):
                if any(path.glob("ide_*.py")):
                    dirs[path.name] = path
    return dirs


def find_markers(path: Path) -> list[Marker]:
    text = path.read_text(encoding="utf-8")
    if not text.isascii():
        # LSP positions count UTF-16 code units; with ASCII they equal the column of the caret.
        raise StepError(f"{path} contains non-ASCII characters; IDE test files must be ASCII")
    lines = text.splitlines()
    markers = []
    target = None
    for number, line in enumerate(lines):
        match = MARKER.match(line)
        if match is None:
            if line.strip() and not line.lstrip().startswith("#"):
                target = number
            continue
        if match["kind"] not in KINDS:
            raise StepError(f"{path}:{number + 1}: unknown marker ^{match['kind']} (known: {', '.join(KINDS)})")
        if target is None:
            raise StepError(f"{path}:{number + 1}: marker without a code line above it")
        markers.append(Marker(path, target, line.index("^"), match["kind"], match["arg"], lines[target].strip()))
    return markers


def quoted(arg: str | None) -> str:
    if not arg or not (len(arg) >= 2 and arg[0] == arg[-1] == '"'):
        raise StepError(f'expected a quoted string after the marker, got {arg!r}')
    return arg[1:-1]


# --- rendering ---------------------------------------------------------------------------------------------------


def normalize(text: str, stubs: Path) -> str:
    """Make rendered Markdown stable and readable in a diff (see the research note, section 4.3)."""
    text = text.replace("  \n", "<HB>\n").replace("&nbsp;", "·")
    for spelling in {str(stubs), stubs.as_posix(), stubs.as_uri()}:
        text = text.replace(spelling, "<stubs>")
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def plain(markdown: str) -> str:
    """Markdown as the text a reader sees, for -contains assertions: no escapes, entities or code fences."""
    text = re.sub(r"\\([\\`*_{}\[\]()#+\-.!<>|])", r"\1", markdown)
    text = text.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    text = re.sub(r"```\w*", "", text).replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def cut(text: str) -> str:
    lines = text.splitlines()
    if len(lines) <= MAX_LINES:
        return text
    return "\n".join(lines[:MAX_LINES] + [f"[... {len(lines) - MAX_LINES} more lines]"])


def doc_text(doc: Any) -> str:
    if doc is None:
        return ""
    return doc["value"] if isinstance(doc, dict) else str(doc)


def hover_markdown(hover: Any) -> str | None:
    if not hover:
        return None
    contents = hover["contents"]
    if isinstance(contents, list):
        return "\n\n".join(c if isinstance(c, str) else c["value"] for c in contents)
    return contents if isinstance(contents, str) else contents["value"]


def contains(haystack: str, needle: str) -> str:
    return "PASS" if needle in haystack else f'FAIL: does not contain "{needle}"'


def render(marker: Marker, response: Any, stubs: Path) -> str:
    """The golden-file text for one marker."""
    kind = marker.kind
    if kind.startswith("hover"):
        markdown = hover_markdown(response)
        if kind == "hover":
            return "(no hover)" if markdown is None else cut(normalize(markdown, stubs))
        if kind == "hover-none":
            return "PASS" if markdown is None else "FAIL: hover is not empty\n" + cut(normalize(markdown, stubs))
        return "FAIL: no hover" if markdown is None else contains(plain(markdown), quoted(marker.arg))

    if kind.startswith("signature"):
        if not response or not response.get("signatures"):
            return "(no signature help)" if kind == "signature" else "FAIL: no signature help"
        signature = response["signatures"][response.get("activeSignature") or 0]
        active = signature.get("activeParameter", response.get("activeParameter"))
        params = signature.get("parameters") or []
        if kind == "signature-param":
            if active is None or active >= len(params):
                return "FAIL: no active parameter"
            return contains(plain(doc_text(params[active].get("documentation"))), quoted(marker.arg))
        lines = [f"label: {normalize(signature['label'], stubs)}", f"active parameter: {active}", "parameters:"]
        for param in params:
            label = param["label"]
            name = signature["label"][label[0]:label[1]] if isinstance(label, list) else label
            documentation = normalize(doc_text(param.get("documentation")), stubs)
            lines.append(f"- {name}: {documentation or '(no documentation)'}")
        documentation = normalize(doc_text(signature.get("documentation")), stubs)
        lines += ["documentation:", cut(documentation) if documentation else "(none)"]
        return "\n".join(lines)

    if kind == "completion":
        items = response["items"] if isinstance(response, dict) else (response or [])
        by_label = {item["label"]: item for item in items}
        lines = []
        for label in (marker.arg or "").split():
            item = by_label.get(label)
            if item is None:
                lines.append(f"- {label}: FAIL: not offered")
                continue
            deprecated = 1 in (item.get("tags") or []) or item.get("deprecated")
            documentation = normalize(doc_text(item.get("documentation")), stubs).splitlines()
            lines.append(f"- {label}: detail: {normalize(item.get('detail') or '', stubs) or '(none)'}"
                         f"{' [deprecated]' if deprecated else ''}")
            lines.append(f"  documentation: {documentation[0] if documentation else '(none)'}")
        return "\n".join(lines)

    if kind == "deprecated":
        for diagnostic in (response or {}).get("items", []):
            start, end = diagnostic["range"]["start"], diagnostic["range"]["end"]
            on_marker = start["line"] <= marker.line <= end["line"] and (
                start["line"] < marker.line or start["character"] <= marker.character) and (
                end["line"] > marker.line or marker.character < end["character"])
            if on_marker and (diagnostic.get("code") == "deprecated" or 2 in (diagnostic.get("tags") or [])):
                return "PASS: " + diagnostic["message"]
        return "FAIL: no deprecated diagnostic at the caret"

    raise AssertionError(kind)


def query(client: LspClient, marker: Marker) -> Any:
    document = {"uri": marker.path.as_uri()}
    position = {"line": marker.line, "character": marker.character}
    if marker.kind.startswith("hover"):
        return client.request("textDocument/hover", {"textDocument": document, "position": position})
    if marker.kind.startswith("signature"):
        return client.request("textDocument/signatureHelp", {"textDocument": document, "position": position})
    if marker.kind == "completion":
        return client.request("textDocument/completion", {"textDocument": document, "position": position})
    if marker.kind == "deprecated":
        return client.request("textDocument/diagnostic", {"textDocument": document})
    raise AssertionError(marker.kind)


# --- golden file -------------------------------------------------------------------------------------------------


def golden_file(generator: str, version: str) -> Path:
    return EXPECTED_DIR / generator / f"{version}.ide.md"


def parse_golden(path: Path) -> dict[str, str]:
    """Sections of a golden file by title (the `## ` line)."""
    sections: dict[str, str] = {}
    if not path.is_file():
        return sections
    title = None
    body: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if title is not None:
                sections[title] = "\n".join(body).strip()
            title, body = line[3:], []
        elif title is not None:
            body.append(line)
    if title is not None:
        sections[title] = "\n".join(body).strip()
    return sections


def section_body(marker: Marker, result: str) -> str:
    return f"`{marker.source}`\n\n````text\n{result}\n````"


def write_golden(path: Path, generator: str, version: str, sections: dict[str, str]) -> None:
    def key(title: str) -> tuple[str, int, int, str]:
        location, _, rest = title.partition(" ")
        file, line, col = location.rsplit(":", 2)
        return file, int(line), int(col), rest

    out = [f"# IDE results, {generator} stubs, Blender {version}", "",
           f"Written by `mise run check:ide {version} --update`; the task fails when this file would change.",
           "Each section is one marker: the queried code line, then what ty's language server returned for it."]
    for title in sorted(sections, key=key):
        out += ["", f"## {title}", "", sections[title]]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


# --- main ------------------------------------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_stubs_arguments(parser)
    parser.add_argument("features", nargs="*", help="Feature directory names in tests/typecheck/features/ or "
                                                    "tests/typecheck/ide/ that have ide_*.py files (default: all)")
    parser.add_argument("--debug", action="store_true", help="Use a debug build of ty")
    parser.add_argument("--update", action="store_true", help="Rewrite the golden files instead of comparing")
    args = parser.parse_args()

    available = feature_dirs()
    unknown = set(args.features) - set(available)
    if unknown:
        raise StepError(f"Unknown features {', '.join(sorted(unknown))} (with ide_*.py files: {', '.join(available)})")
    selected = {name: available[name] for name in (args.features or available)}
    markers = [m for directory in selected.values() for f in sorted(directory.glob("ide_*.py")) for m in find_markers(f)]
    selected_prefixes = tuple(f"{d.relative_to(TYPECHECK_TESTS_DIR).as_posix()}/" for d in selected.values())

    generators = resolve_generators(args.version, args.ref, args.generator)
    all_stubs = {g: generate_stubs(args.version, generator=g, ref=args.ref, blender=args.blender, force=args.force)
                 for g in generators}
    python_version = blender_python_version(ensure_worktree(args.version, args.ref))
    ty = build_ty(args.debug)

    changed = False
    for generator, stubs in all_stubs.items():
        log(f"Querying ty's language server (Python {python_version}, Blender {args.version}, {generator} stubs) "
            f"at {len(markers)} markers in {len(selected)} features")
        client = start_server(ty, stubs, python_version)
        raw = []
        sections = {}
        try:
            for path in sorted({m.path for m in markers}):
                client.notify("textDocument/didOpen", {"textDocument": {
                    "uri": path.as_uri(), "languageId": "python", "version": 1,
                    "text": path.read_text(encoding="utf-8")}})
            for marker in markers:
                response = query(client, marker)
                raw.append({"marker": marker.title, "response": response})
                sections[marker.title] = section_body(marker, render(marker, response, stubs))
        finally:
            client.close()

        results_dir = RESULTS_DIR / args.version / generator
        results_dir.mkdir(parents=True, exist_ok=True)
        (results_dir / "ide.json").write_text(json.dumps(raw, indent=1), encoding="utf-8")
        failures = sum("FAIL" in body for body in sections.values())
        log(f"{len(sections) - failures} of {len(sections)} markers without a FAIL; raw responses: "
            f"{results_dir / 'ide.json'}")

        path = golden_file(generator, args.version)
        recorded = parse_golden(path)
        expected = {t: b for t, b in recorded.items() if t.startswith(selected_prefixes)}
        if args.update:
            others = {t: b for t, b in recorded.items() if not t.startswith(selected_prefixes)}
            write_golden(path, generator, args.version, {**others, **sections})
            log(f"Wrote {path}")
            continue
        if not path.is_file():
            log(f"No recorded results in {path}; run with --update to record them")
            changed = True
            continue
        if expected == sections:
            log(f"Results match {path.relative_to(TYPECHECK_TESTS_DIR.parent.parent)}")
            continue
        changed = True
        log(f"Results changed against {path.relative_to(TYPECHECK_TESTS_DIR.parent.parent)} (--update records them):")
        for title in sorted(set(expected) | set(sections)):
            if expected.get(title) == sections.get(title):
                continue
            print(f"    ## {title}", flush=True)
            diff = difflib.unified_diff((expected.get(title) or "").splitlines(), (sections.get(title) or "").splitlines(),
                                        "recorded", "now", lineterm="", n=1)
            for line in list(diff)[2:]:
                print(f"    {line}", flush=True)
    return 1 if changed else 0


if __name__ == "__main__":
    main_wrapper(main)
