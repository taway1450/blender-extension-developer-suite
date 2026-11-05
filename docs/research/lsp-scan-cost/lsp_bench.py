# /// script
# requires-python = ">=3.12"
# dependencies = ["psutil"]
# ///
"""Time ty's language server (open-files mode) on one scenario; print one JSON line per run.

Scenario (all edits in memory, full-text didChange):
  1. open READER-1, pull diagnostics           -> first_diag_cold   (stubs load + check)
  2. hover a registered-property read there     -> hover
  3. open READER-2, pull diagnostics           -> first_diag_warm
  4. comment edit in READER-2, pull its diags  -> recheck_noreg
  5. open REGISTRAR, add one registration line, pull READER-2 diags -> recheck_reg
  6. comment edit in READER-1, pull its diags  -> recheck_noreg_heavy
Peak working set and final RSS of the server process are read with psutil.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from queue import Queue

import psutil


class Lsp:
    def __init__(self, cmd, cwd):
        self.p = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.next = 0
        self.q: dict[int, Queue] = {}
        self.lock = threading.Lock()
        threading.Thread(target=self._loop, daemon=True).start()

    def _read(self):
        length = None
        while True:
            h = self.p.stdout.readline()
            if not h:
                return None
            h = h.strip()
            if not h:
                break
            k, _, v = h.decode().partition(":")
            if k.lower() == "content-length":
                length = int(v)
        return json.loads(self.p.stdout.read(length))

    def _loop(self):
        while (m := self._read()) is not None:
            if "id" in m and "method" in m:
                self._send({"jsonrpc": "2.0", "id": m["id"], "result": None})
            elif "id" in m:
                with self.lock:
                    q = self.q.get(m["id"])
                if q:
                    q.put(m)

    def _send(self, m):
        b = json.dumps(m).encode()
        with self.lock:
            self.p.stdin.write(f"Content-Length: {len(b)}\r\n\r\n".encode() + b)
            self.p.stdin.flush()

    def req(self, method, params):
        q: Queue = Queue()
        with self.lock:
            self.next += 1
            i = self.next
            self.q[i] = q
        self._send({"jsonrpc": "2.0", "id": i, "method": method, "params": params})
        r = q.get(timeout=600)
        if "error" in r:
            raise RuntimeError(f"{method}: {r['error']}")
        return r.get("result")

    def note(self, method, params):
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def timed(self, method, params):
        t = time.perf_counter()
        r = self.req(method, params)
        return (time.perf_counter() - t) * 1000, r


def main():
    cfg = json.loads(Path(sys.argv[1]).read_text())
    ty, ws, stubs = cfg["ty"], Path(cfg["workspace"]), cfg["stubs"]
    s = Lsp([ty, "server"], ws)
    s.req("initialize", {
        "processId": None, "rootUri": ws.as_uri(),
        "workspaceFolders": [{"uri": ws.as_uri(), "name": "ws"}],
        "capabilities": {"textDocument": {"hover": {"contentFormat": ["plaintext"]}, "diagnostic": {}},
                         "general": {"positionEncodings": ["utf-16"]}},
        "initializationOptions": {"configuration": {"environment": {"extra-paths": [stubs], "python-version": "3.13"}}},
    })
    s.note("initialized", {})
    proc = psutil.Process(s.p.pid)
    docs: dict[str, list] = {}

    def uri(rel):
        return (ws / rel).as_uri()

    def open_(rel):
        text = (ws / rel).read_text(encoding="utf-8")
        docs[rel] = [text, 1]
        s.note("textDocument/didOpen", {"textDocument": {"uri": uri(rel), "languageId": "python", "version": 1, "text": text}})

    def change(rel, text):
        docs[rel][0] = text
        docs[rel][1] += 1
        s.note("textDocument/didChange", {"textDocument": {"uri": uri(rel), "version": docs[rel][1]},
                                          "contentChanges": [{"text": text}]})

    def diag(rel):
        ms, r = s.timed("textDocument/diagnostic", {"textDocument": {"uri": uri(rel)}})
        return ms, len(r.get("items", [])) if r else None

    out = {"ty": Path(ty).stem, "workspace": ws.name}
    r1, r2, reg = cfg["reader1"], cfg["reader2"], cfg["registrar"]
    open_(r1)
    out["first_diag_cold"], out["n_diag_r1"] = diag(r1)
    line, attr = cfg["hover"]
    col = docs[r1][0].splitlines()[line].rindex(attr)
    out["hover"], h = s.timed("textDocument/hover", {"textDocument": {"uri": uri(r1)}, "position": {"line": line, "character": col}})
    out["hover_text"] = (h or {}).get("contents", {}).get("value", "")[:60] if h else None
    open_(r2)
    out["first_diag_warm"], out["n_diag_r2"] = diag(r2)
    change(r2, docs[r2][0] + "\n# bench edit\n")
    out["recheck_noreg"], _ = diag(r2)
    if reg != r1:
        open_(reg)
    anchor, new = cfg["reg_edit"]
    text = docs[reg][0]
    i = text.index(anchor) + len(anchor)
    change(reg, text[:i] + "\n" + new + text[i:])
    out["recheck_reg"], _ = diag(r2)
    out["recheck_reg_registrar"], _ = diag(reg)
    change(r1, docs[r1][0] + "\n# bench edit 2\n")
    out["recheck_noreg_heavy"], _ = diag(r1)
    mi = proc.memory_info()
    out["peak_mb"] = round(getattr(mi, "peak_wset", mi.rss) / 2**20)
    out["rss_mb"] = round(mi.rss / 2**20)
    for k, v in out.items():
        if isinstance(v, float):
            out[k] = round(v, 1)
    print(json.dumps(out), flush=True)
    try:
        s.req("shutdown", None)
        s.note("exit", None)
        s.p.wait(10)
    except Exception:
        s.p.kill()


main()
