"""Cross-checks of the return classifier (``libclang/crosscheck.py``): LLVM's inferred ``nonnull`` returns and
Clang Static Analyzer paths to a NULL return."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from libclang.crosscheck import Probe, disagreements, failed_probes, nonnull_returns, probe_source, witnesses

LL = """
define internal fastcc noundef nonnull ptr @_ZN7blenderL17rna_Curve_spl_newEPNS_5CurveE(ptr noundef %0) #0 {
define internal fastcc noundef ptr @_ZN7blenderL21rna_Palette_color_newEPNS_7PaletteE(ptr noundef %0) #0 {
define internal fastcc void @_ZN7blenderL19rna_Object_shape_getEPNS_10PointerRNAE(ptr sret(%"struct.x") %0) #0 {
define dso_local noundef nonnull ptr @rna_extern_c(ptr noundef %0) #0 {
"""


def test_llvm_nonnull_return_attributes_are_read_per_function() -> None:
    names = ["rna_Curve_spl_new", "rna_Palette_color_new", "rna_Object_shape_get", "rna_extern_c", "rna_absent"]
    assert nonnull_returns(LL, names) == {
        "rna_Curve_spl_new": True,
        "rna_Palette_color_new": False,
        "rna_extern_c": True,
    }


def test_a_function_name_must_match_whole() -> None:
    """``rna_Curve_spl_new`` is not ``rna_Curve_spl_new_ex``, nor the other way around."""
    ll = "define internal nonnull ptr @_ZN7blenderL20rna_Curve_spl_new_exEPNS_5CurveE(ptr %0) {\n"
    assert nonnull_returns(ll, ["rna_Curve_spl_new"]) == {}


def test_the_probe_calls_each_function_with_its_non_null_arguments_and_dereferences_the_result() -> None:
    text, lines = probe_source(
        "/b/rna_palette_gen.cc",
        [
            Probe("blender::rna_Palette_color_new", 0b1, "pointer"),
            Probe("blender::rna_Palette_get", 0b10, "PointerRNA"),
        ],
    )
    # An error report ends the path: a NULL after it raises in Python and is no witness. ``BKE_reportf`` is
    # variadic, which the analyzer never inlines, so both become macros, defined after their declarations.
    src = text.splitlines()
    assert src[0] == '#include "BKE_report.hh"'
    assert "RPT_ERROR" in text and "__builtin_unreachable" in text
    report = next(n for n, line in enumerate(src) if line.startswith("#define BKE_reportf("))
    assert report < src.index('#include "/b/rna_palette_gen.cc"')
    src = text.splitlines()
    first = next(n for n, i in lines.items() if i == 0)
    assert "call<1ull>(&blender::rna_Palette_color_new)" in src[first - 1]
    second = next(n for n, i in lines.items() if i == 1)
    assert "call<2ull>(&blender::rna_Palette_get)" in src[second - 1] and ".data" in src[second - 1]


def test_null_dereferences_in_the_probes_are_witnesses() -> None:
    sarif = {
        "runs": [
            {
                "results": [
                    {
                        "ruleId": "core.NullDereference",
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "file:///p/probe.cc"},
                                    "region": {"startLine": 40},
                                }
                            }
                        ],
                    },
                    {
                        "ruleId": "core.NullDereference",
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "file:///b/rna_x.cc"},
                                    "region": {"startLine": 40},
                                }
                            }
                        ],
                    },
                    {
                        "ruleId": "core.DivideZero",
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "file:///p/probe.cc"},
                                    "region": {"startLine": 41},
                                }
                            }
                        ],
                    },
                ]
            }
        ]
    }
    assert witnesses(json.dumps(sarif), {40: 0, 41: 1}, "probe.cc") == {0}


def test_disagreements_are_the_findings_that_contradict_the_verdict() -> None:
    rows = [
        ("A.never_ok", "never", True, False),
        ("B.null_but_llvm_proves_nonnull", "null", True, False),
        ("C.unknown_but_llvm_proves_nonnull", "unknown", True, False),
        ("D.never_but_csa_path", "never", None, True),
        ("E.raises_but_csa_path", "raises", None, True),
        ("F.null_with_csa_path", "null", False, True),
    ]
    found = {name: why for name, why in disagreements(rows)}
    assert set(found) == {
        "B.null_but_llvm_proves_nonnull",
        "C.unknown_but_llvm_proves_nonnull",
        "D.never_but_csa_path",
        "E.raises_but_csa_path",
    }


def test_a_probe_that_does_not_compile_is_found_by_its_line() -> None:
    stderr = (
        "/w/rna_action_gen_probe.cc:42:62: error: no matching function for call to 'call'\n"
        "/w/rna_action_gen_probe.cc:33:58: note: candidate template ignored\n"
        "/b/rna_action.cc:10:1: error: something else\n"
    )
    assert failed_probes(stderr, "rna_action_gen_probe.cc", {41: 0, 42: 1, 33: 7}) == {1}
