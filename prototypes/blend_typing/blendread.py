"""PROTOTYPE, throwaway: a dependency-free reader of .blend files (header, blocks, SDNA), from the research probe.

See docs/research/blend-file-typing.md. Not production code: no error handling beyond what the prototype needs.
"""
import ctypes
import ctypes.util
import gzip
import re
import struct
import sys
import time
from collections import Counter, defaultdict


def zstd_decompress(raw):
    lib = ctypes.CDLL(ctypes.util.find_library("zstd") or "libzstd.so.1")

    class Buf(ctypes.Structure):
        _fields_ = [("src", ctypes.c_void_p), ("size", ctypes.c_size_t), ("pos", ctypes.c_size_t)]

    lib.ZSTD_createDStream.restype = ctypes.c_void_p
    lib.ZSTD_decompressStream.restype = ctypes.c_size_t
    lib.ZSTD_decompressStream.argtypes = [ctypes.c_void_p, ctypes.POINTER(Buf), ctypes.POINTER(Buf)]
    lib.ZSTD_isError.argtypes = [ctypes.c_size_t]
    lib.ZSTD_freeDStream.argtypes = [ctypes.c_void_p]
    ds = lib.ZSTD_createDStream()
    src = ctypes.create_string_buffer(raw, len(raw))
    inb = Buf(ctypes.cast(src, ctypes.c_void_p), len(raw), 0)
    chunk = 1 << 22
    dst = ctypes.create_string_buffer(chunk)
    out = []
    while inb.pos < inb.size:
        outb = Buf(ctypes.cast(dst, ctypes.c_void_p), chunk, 0)
        ret = lib.ZSTD_decompressStream(ds, ctypes.byref(outb), ctypes.byref(inb))
        if lib.ZSTD_isError(ret):
            raise RuntimeError("zstd error")
        out.append(dst.raw[: outb.pos])
    lib.ZSTD_freeDStream(ds)
    return b"".join(out)


class Blend:
    def __init__(self, data):
        self.d = data
        if data[7:8] in (b"-", b"_"):
            self.ptr = 8 if data[7:8] == b"-" else 4
            self.le = data[8:9] == b"v"
            self.version = int(data[9:12])
            self.fmt = 0
            hdr = 12
            e = "<" if self.le else ">"
            self.bh = struct.Struct(e + ("4siQii" if self.ptr == 8 else "4siIii"))
            self.bh_order = ("code", "len", "old", "sdna", "nr")
        else:
            assert data[7:9] == b"17"
            self.ptr, self.le, self.fmt = 8, True, int(data[10:12])
            self.version = int(data[13:17])
            hdr = 17
            self.bh = struct.Struct("<4siQqq")
            self.bh_order = ("code", "sdna", "old", "len", "nr")
        self.e = "<" if self.le else ">"
        self.blocks = []  # (code, sdna, old, len, nr, offset)
        pos = hdr
        while True:
            vals = dict(zip(self.bh_order, self.bh.unpack_from(data, pos)))
            code = vals["code"].rstrip(b"\0")
            pos += self.bh.size
            self.blocks.append((code, vals["sdna"], vals["old"], vals["len"], vals["nr"], pos))
            if code == b"ENDB":
                break
            pos += vals["len"]
        self.by_old = {b[2]: b for b in self.blocks if b[0] != b"ENDB"}

    def decode_sdna(self):
        dna = next(b for b in self.blocks if b[0] == b"DNA1")
        d, p, e = self.d, dna[5], self.e
        base = dna[5]
        al = lambda q: base + ((q - base + 3) & ~3)
        assert d[p : p + 4] == b"SDNA"
        p += 4

        def strings(p):
            assert d[p : p + 4] in (b"NAME", b"TYPE")
            n = struct.unpack_from(e + "i", d, p + 4)[0]
            p += 8
            out = []
            for _ in range(n):
                q = d.index(b"\0", p)
                out.append(d[p:q].decode())
                p = q + 1
            return out, al(p)

        self.names, p = strings(p)
        self.types, p = strings(p)
        assert d[p : p + 4] == b"TLEN"
        self.tlen = struct.unpack_from(e + "%dh" % len(self.types), d, p + 4)
        p += 4 + 2 * len(self.types)
        p = al(p)
        assert d[p : p + 4] == b"STRC"
        n = struct.unpack_from(e + "i", d, p + 4)[0]
        p += 8
        self.structs = []
        self.struct_by_name = {}
        for i in range(n):
            t, nf = struct.unpack_from(e + "hh", d, p)
            fields = struct.unpack_from(e + "%dh" % (2 * nf), d, p + 4)
            p += 4 + 4 * nf
            off = 0
            layout = {}
            for k in range(nf):
                ft, fn = fields[2 * k], fields[2 * k + 1]
                name = self.names[fn]
                is_ptr = name.startswith("*") or name.startswith("(*")
                dims = [int(x) for x in re.findall(r"\[(\d+)\]", name)]
                count = 1
                for x in dims:
                    count *= x
                size = (self.ptr if is_ptr else self.tlen[ft]) * count
                bare = re.sub(r"[\*\(\)]|\[\d+\]", "", name).split("(")[0]
                layout[bare] = (off, self.types[ft], is_ptr, size, name)
                off += size
            self.structs.append((self.types[t], layout))
            self.struct_by_name[self.types[t]] = i

    def field(self, struct_name, path):
        off = 0
        sname = struct_name
        for part in path.split("."):
            layout = self.structs[self.struct_by_name[sname]][1]
            o, t, is_ptr, size, _ = layout[part]
            off += o
            sname = t
        return off, sname, is_ptr, size

    def read(self, base, struct_name, path):
        off, t, is_ptr, size = self.field(struct_name, path)
        p = base + off
        if is_ptr:
            return struct.unpack_from(self.e + ("Q" if self.ptr == 8 else "I"), self.d, p)[0]
        if t == "char":
            raw = self.d[p : p + size]
            return raw.split(b"\0", 1)[0].decode("utf-8", "replace")
        fmt = {"short": "h", "int": "i", "char": "b", "float": "f", "int16_t": "h", "int8_t": "b",
               "uchar": "B", "ushort": "H", "uint": "I", "int64_t": "q", "uint64_t": "Q"}.get(t)
        if fmt is None:
            return self.d[p : p + size]
        return struct.unpack_from(self.e + fmt, self.d, p)[0]

    def sname(self, block):
        return self.structs[block[1]][0]

    def listbase(self, base, struct_name, path, item_struct=None):
        first = self.read(base, struct_name, path + ".first")
        seen = 0
        while first and seen < 100000:
            b = self.by_old.get(first)
            if b is None:
                return
            yield b
            first = self.read(b[5], item_struct or self.sname(b), "next")
            seen += 1


def open_blend(path):
    raw = open(path, "rb").read()
    if raw[:4] == b"\x28\xb5\x2f\xfd":
        raw = zstd_decompress(raw)
    elif raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    blend = Blend(raw)
    blend.decode_sdna()
    return blend
