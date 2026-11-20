"""Context members: what each editor's context callback answers for a member name, and with which RNA type.

Two shapes are run by the interpreter:

- ``int X_context(const bContext *C, const char *member, bContextDataResult *result)`` callbacks: inside
  ``if (CTX_data_equals(member, "x") || ...)`` the then-branch defines the members named there;
- the screen context's ``map.add("scene", screen_ctx_scene)`` table: each callback is run with its member name.

A setter's RNA type comes from clang's types, not from names: ``CTX_data_id_pointer_set(result, &ob->id)`` has
``ob`` typed ``Object *``, so the DNA struct is ``Object``, which RNA maps to the struct whose ``RNA_def_struct_sdna``
is ``Object``. ``CTX_data_pointer_set(result, id, &RNA_X, data)`` and ``PointerRNA`` values built with
``RNA_pointer_create_discrete(id, &RNA_X, data)`` give ``X`` directly. The ``*_context_dir[]`` arrays list members.
"""

from __future__ import annotations

from common.model import ContextMember

from .interp import UNKNOWN, GlobalRef, Interp, MemberTest, Obj


class Context:
    def __init__(self, interp: Interp, rna, model) -> None:
        self.i = interp
        self.rna = rna
        self.model = model
        self.members: dict[str, ContextMember] = {}
        self.dna_to_rna: dict[str, str] = {}
        I = interp.intrinsics
        I["CTX_data_equals"] = self.equals
        I["CTX_data_dir"] = lambda i, a, e, c: False
        I["CTX_data_id_pointer_set"] = self.id_pointer_set
        I["CTX_data_pointer_set"] = self.pointer_set
        I["CTX_data_pointer_set_ptr"] = self.pointer_set_ptr
        I["CTX_data_id_list_add"] = self.id_list_add
        I["CTX_data_list_add"] = self.list_add
        I["CTX_data_list_add_ptr"] = self.list_add_ptr
        I["CTX_data_type_set"] = self.type_set
        I["CTX_data_prop_set"] = self.prop_set
        I["CTX_data_dir_set"] = lambda i, a, e, c: None
        for name in ("RNA_pointer_create_discrete", "RNA_pointer_create_with_parent", "RNA_pointer_create",
                     "RNA_pointer_create_id_subdata"):
            I[name] = self.pointer_create
        I["RNA_id_pointer_create"] = self.id_pointer_create
        I["RNA_main_pointer_create"] = lambda i, a, e, c: Obj("ptr", "BlendData")

    # ----------------------------------------------------------------------------------------------------------------
    def rna_for_dna(self, dna: str) -> str:
        if not self.dna_to_rna:
            for ident, d in self.rna.dna_of.items():
                if d == ident or d not in self.dna_to_rna:
                    self.dna_to_rna[d] = ident
            # A DNA struct shared by several RNA structs maps to the one named like it, else to the base-most one.
            for ident, d in self.rna.dna_of.items():
                cur = self.dna_to_rna.get(d)
                if cur != d and ident in self.rna.structs:
                    s = self.rna.structs[ident]
                    if s.base and self.rna.dna_of.get(s.base) == d:
                        self.dna_to_rna[d] = s.base
        return self.dna_to_rna.get(dna, dna if dna in self.rna.structs else "")

    def id_type(self, expr) -> str:
        """The DNA struct of an ``ID *`` argument: ``&ob->id`` -> ``Object``; ``ID *`` stays ``ID``."""
        if not expr:
            return ""
        if expr[0] == "u" and expr[1] == "&" and expr[2] and expr[2][0] == "m" and expr[2][2] == "id":
            return expr[2][3]
        if expr[0] == "m":
            return expr[5] if len(expr) > 5 else ""
        if expr[0] in ("v",):
            return expr[3] if len(expr) > 3 else ""
        if expr[0] == "u" and len(expr) > 4:
            return expr[4]
        if expr[0] == "c":
            return ""
        return ""

    def member(self, name: str) -> ContextMember:
        m = self.members.get(name)
        if m is None:
            m = ContextMember(name=name, src="")
            self.members[name] = m
        return m

    def record(self, rna_type: str, collection: bool, kind: str | None = None, call=None) -> None:
        if not self.i.where.startswith("source/blender/editors/"):
            return
        for name in self.i.ctx_members:
            m = self.member(name)
            entry = (rna_type, collection)
            if entry not in m.types:
                m.types.append(entry)
            if kind:
                m.kind = kind
            elif collection:
                m.kind = "collection"
            editor = self.i.where
            if editor and editor not in m.editors:
                m.editors.append(editor)
            if not m.src and call is not None:
                m.src = self.i.src(call[4])

    # ----------------------------------------------------------------------------------------------------------------
    def equals(self, i, a, e, call):
        if len(a) > 1 and isinstance(a[1], str):
            return MemberTest(frozenset([a[1]]))
        return UNKNOWN

    def _struct_arg(self, value) -> str:
        if isinstance(value, GlobalRef) and value.name.startswith("RNA_"):
            return value.name[4:]
        return ""

    def id_pointer_set(self, i, a, e, call):
        dna = self.id_type(e[1]) if len(e) > 1 else ""
        self.record(self.rna_for_dna(dna) or dna or "ID", False, call=call)

    def pointer_set(self, i, a, e, call):
        self.record(self._struct_arg(a[2]) if len(a) > 2 else "", False, call=call)

    def pointer_set_ptr(self, i, a, e, call):
        ptr = a[1] if len(a) > 1 else None
        self.record(ptr.data if isinstance(ptr, Obj) and ptr.kind == "ptr" else "", False, call=call)

    def id_list_add(self, i, a, e, call):
        dna = self.id_type(e[1]) if len(e) > 1 else ""
        self.record(self.rna_for_dna(dna) or dna or "ID", True, call=call)

    def list_add(self, i, a, e, call):
        self.record(self._struct_arg(a[2]) if len(a) > 2 else "", True, call=call)

    def list_add_ptr(self, i, a, e, call):
        ptr = a[1] if len(a) > 1 else None
        self.record(ptr.data if isinstance(ptr, Obj) and ptr.kind == "ptr" else "", True, call=call)

    def type_set(self, i, a, e, call):
        if not self.i.where.startswith("source/blender/editors/"):
            return  # e.g. bpy_interface.cc's Python fall-back, reached through CTX_wm_window()
        names = getattr(a[1], "names", ()) if len(a) > 1 else ()
        for name in self.i.ctx_members:
            m = self.member(name)
            if "Collection" in names:
                m.kind = "collection"
                m.types = [(t, True) for t, _ in m.types] or m.types
            elif "Property" in names:
                m.kind = "property"
            elif "Pointer" in names and m.kind == "pointer":
                pass

    def prop_set(self, i, a, e, call):
        self.record("", False, kind="property", call=call)

    def pointer_create(self, i, a, e, call):
        for v in a:
            t = self._struct_arg(v)
            if t:
                return Obj("ptr", t)
        return UNKNOWN

    def id_pointer_create(self, i, a, e, call):
        dna = self.id_type(e[0]) if e else ""
        return Obj("ptr", self.rna_for_dna(dna) or dna or "ID")

    # ----------------------------------------------------------------------------------------------------------------
    def run(self, files: set[str]) -> None:
        fns = [f for f in self.i.p.functions.values() if f.file in files and f.file.startswith("source/blender/editors/")]
        for fn in fns:
            names = [p[0] for p in fn.params]
            if "member" in names and any("bContextDataResult" in p[1] for p in fn.params):
                args = [UNKNOWN] * len(fn.params)
                args[names.index("member")] = UNKNOWN
                self.i.call_function(fn, args)
        # ``map.add("name", callback)`` tables (screen context): run each callback for its member.
        for fn in fns:
            for name, target in _map_adds(fn.body):
                callee = self.i.p.functions.get(target)
                if callee is None:
                    continue
                saved = self.i.ctx_members
                self.i.ctx_members = frozenset([name])
                try:
                    self.i.call_function(callee, [UNKNOWN] * len(callee.params))
                finally:
                    self.i.ctx_members = saved
                m = self.member(name)
                editor = callee.file
                if editor not in m.editors:
                    m.editors.append(editor)
                m.src = m.src or f"{callee.file}:{callee.line}"
        # ``*_context_dir[]`` arrays: every listed member exists, typed or not.
        for usr, g in self.i.p.globals.items():
            if g["file"] in files and g["name"].endswith("context_dir"):
                value = self.i.global_value(usr, g["name"])
                if isinstance(value, list):
                    for v in value:
                        if isinstance(v, str):
                            m = self.member(v)
                            if g["file"] not in m.editors:
                                m.editors.append(g["file"])
                            m.src = m.src or f"{g['file']}:{g['line']}"
        for m in self.members.values():
            if not m.types and m.kind == "pointer":
                m.kind = "unknown"
            if any(c for _, c in m.types):
                m.kind = "collection"
        self.model.context.extend(sorted(self.members.values(), key=lambda m: m.name))


def _map_adds(body):
    stack = [body]
    while stack:
        x = stack.pop()
        if not isinstance(x, list):
            continue
        if len(x) > 3 and x[0] == "mc" and x[1] in ("add", "add_new", "add_overwrite") and len(x[3]) == 2:
            a, b = x[3]
            if a and a[0] == "ctor" and len(a[2]) == 1:  # StringRef("scene")
                a = a[2][0]
            if a and b and a[0] == "s" and b[0] == "fn":
                yield a[1], b[1]
        stack.extend(y for y in x if isinstance(y, list))
