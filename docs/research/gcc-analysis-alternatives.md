# Analysing Blender's source with GCC instead of libclang

Research note, 2026-11-20.

**Question.** The libclang reader (`prototypes/source_stubs/libclang/`, see
[source-stub-generators.md](source-stub-generators.md)) does two jobs on Blender 5.2's C/C++:

1. **Define-time facts**: it runs the `RNA_def_*` call sequences, operators, context callbacks, node declarations
   and the C tables. This needs the source's shape: the original call arguments, macro-expanded strings, enum names,
   types and global initializers.
2. **Nullable returns** (`returns.py`): a path-sensitive walk over each RNA function's runtime body and its callees,
   with the verdicts never / null / raises / unknown.

Could GCC do either job instead, and how do all the candidate approaches compare?

**Method.**
- Primary sources:
  - The GCC manual, plugin docs and analyzer internals, read as texinfo from the `gcc-mirror/gcc` GitHub mirror for
    `releases/gcc-13` and `master` (17.0.0). gcc.gnu.org did not resolve from this session.
  - The clang docs, read from `llvm-project` on GitHub. clang.llvm.org did not resolve either.
  - Each tool's own repository.
- Small experiments with the installed gcc 13.3 and clang 18.1.3, in the session scratchpad (`gcc-research/`):
  - a 45-line RNA-like file;
  - a minimal GCC plugin, built against `gcc-13-plugin-dev` headers that were extracted, not installed;
  - two real Blender units compiled with GCC, using the flags from `compile_commands.json`: `rna_palette.cc`
    (define-time) and `blenkernel/intern/deform.cc`.
- No build was run, and no mise tasks. Claims are marked **verified** (an experiment or a primary source) or
  **inferred**.

## 1. Answer

1. **GCC can do both jobs, but not as a drop-in for libclang.** GCC has no stable, high-level API to its AST like
   libclang's C API. The real choices are:
   - **text dumps**, which are for debugging and lose the source's shape;
   - **a GCC plugin in C++**, built for one exact GCC version;
   - **`-fanalyzer`**, whose manual says it is "only suitable for use on C code", both for GCC 13 and on master.
2. **For job 1, GCC is worse than libclang.**
   - By the time any dump is written, the C++ front end has already folded `PROP_EDITABLE | PROP_NEVER_NULL` to
     `262145`, dropped an `if` whose condition is a `const int`, and lost the enum names. **Verified**:
     `-fdump-tree-original`, `-fdump-tree-gimple` and LLVM IR all do this.
   - Global initializers do not appear in the function dumps. These are the `EnumPropertyItem`, `PyMethodDef`,
     `PyTypeObject` and `BMOpDefine` tables.
   - A call that names an undeclared identifier is dropped whole. Clang keeps it as a `RecoveryExpr` with its string
     arguments.
   - A plugin hooked at `PLUGIN_PRE_GENERICIZE` does see the unfolded tree (`bit_ior_expr`, the enum `const_decl`,
     `if_stmt`). It would mean rewriting `lower.py` (653 lines of Python) as a C++ plugin against GCC's unstable
     internals, to gain nothing libclang does not already give.
3. **For job 2, GCC adds options but does not replace our walk.**
   - GIMPLE/SSA gives a lowered CFG with every call, `0B` for NULL, line numbers and explicit temporaries. That is a
     simpler IR to walk than the AST, but it reaches us as unstable text or through a plugin.
   - `-fanalyzer` found the NULL path through a callee and wrote it as a SARIF `codeFlow`. It was also wrong in ways
     that matter here:
     - it stayed silent on an unknown callee, so `unknown` reads as `never`;
     - it warned that `new Object()` may be NULL;
     - on the real `deform.cc` its only 4 warnings were false positives on placement-`new` lambdas in `BLI_any.hh`.

     It is a bug finder, unsound by design. It can show that a function returns NULL, never that it does not.
4. **The known problems are mostly not about clang.**
   - Missing generated files, borrowed header flags, files parsed apart that Blender compiles together inside
     `rna_X_gen.cc`, and missing optional libraries: GCC would hit every one of these on the same partial build.
     It would also fail harder: with an error in the unit, no pass after gimplification runs (no SSA dump, no
     analyzer). **Verified.**
   - GCC fixes only the libclang-18-vs-libstdc++-13 mismatch, because GCC is the compiler that headers is for.
     Blender's release builds use GCC 14.2.1 (`build_files/config/pipeline_config.yaml`).
5. **Recommendation:** keep libclang for both jobs, and fix the inputs, not the compiler.
   - **Run the codegen.** The partial build already has `bin/makesrna`. One run of it writes the real
     `RNA_prototypes.hh` and all 75 `rna_*_gen.cc`. Building the other `CUSTOM_COMMAND` outputs (shader and DNA
     headers) removes the shim. Then parse the runtime halves as `rna_X_gen.cc` units, as Blender compiles them.
   - **Add an independent check for job 2.** The cheapest is LLVM's own `nonnull` and `returned` return attributes
     from `clang -O1 -emit-llvm`. In the experiment they marked a `&global` return, a `new` and a checked fallback as
     non-null, and stayed silent on NULL and unknown returns, which is the conservative direction.
   - **Use the Clang Static Analyzer (or GCC's analyzer, for C units) only as a witness finder for `null`.** That is,
     as evidence for a verdict, not as the verdict.
   - Section 5 has the details.

## 2. GCC-based options

### 2.1 Tree and GIMPLE dumps (`-fdump-tree-*`, `-fdump-lang-*`, `-fdump-ipa-*`, `-fcallgraph-info`)

What exists (GCC 13 and master manuals; experiments with GCC 13.3):

| Dump | What it is | Kept | Lost |
|---|---|---|---|
| `-fdump-lang-raw` | the C++ front end's whole tree as a node graph (`@N function_decl name: @M ...`). It is the successor of `-fdump-translation-unit`, which GCC 13 rejects ("unrecognized command-line option") | every declaration, `CONST_DECL` names, string constants, decl locations (`srcp:`), function bodies after front-end folding | expression line numbers. Size: 25 MB and 405k lines for a file that includes only `<string> <vector> <map> <memory>` |
| `-fdump-tree-original[-raw]` | GENERIC per function, C-like or raw | calls, strings concatenated and macro-expanded, `if`/loops lowered to `goto`s | enum names (`262145`), `if` on a `const int` (folded away), unused expressions like `(void)ob->type` |
| `-fdump-tree-gimple[-lineno\|-raw]` | three-address GIMPLE before SSA. `-raw` prints tuples (`gimple_call <RNA_def_property, prop, srna, "parent", 4, 0>`) | `file:line:col` for every statement and string argument, temporaries, `return`, `0B` for NULL | as above. No types on call arguments, though the locals' types appear in each `bind` |
| `-fdump-tree-ssa`, `-einline`, `-fdump-ipa-*` | later passes | SSA form. With `-O1`, early inlining had already folded `find_mesh` into its caller | the source's call structure, once callees are inlined |
| `-fdump-ipa-cgraph`, `-fcallgraph-info` | call graph. `.ci` files are in VCG text format | mangled and demangled names, the definition location, every call site's location | indirect targets. Inlined callees vanish (`find_mesh` had no edge at `-O1`) |
| `-fdump-tree-*-graph` | GraphViz CFG per function | the CFG | — |
| `-fdump-go-spec`, `-aux-info` | declaration dumps | `-fdump-go-spec` prints C++ function prototypes (with mangled names) and macro constants | anonymous enums. `-aux-info` "is silently ignored in any language other than C" (it wrote an empty file for C++) |
| `-fsave-optimization-record`, `-fdump-analyzer-json` | JSON | optimization remarks; the analyzer's internals | the manual: "the format ... is subject to change" (both) |

On Blender (**verified**):
- `rna_palette.cc` compiled to GIMPLE with GCC 13 in 1.8 s, with the partial build's flags (clang-only `-Xclang` and
  `-W` flags removed) and no errors.
- Its GIMPLE is a flat, readable call sequence: `RNA_def_property (srna, "color", 2, 20)`,
  `RNA_def_property_flag (prop, 65536)`, `RNA_def_property_update (prop, 84869120, "rna_PaletteColor_color_update")`.
  Enum and notifier values arrive as numbers.

- **Job 1:** partial at best.
  - Call sequences, strings and arithmetic are fine.
  - Enum names have to be mapped back from values, which needs another reader for the enums.
  - Global data tables are not in any per-function dump. They exist only in `-fdump-lang-raw`, which is far too big
    for 800 units, or in the assembly.
  - Folding loses information the readers record today: for example the speculative both-branch runs on a
    `const`-folded condition.
- **Job 2:** usable.
  - GIMPLE before SSA, with `-lineno`, is the easiest IR in this list to walk: explicit `if (ob == 0B) goto`, one
    operation per statement, every call resolved to a declaration.
  - But C++ EH regions, `try/finally` cleanups and aggregate returns (`PointerRNA` written through `<retval>`) all
    have to be parsed out of text.
- **Stability:** these are debugging dumps; the manual says nothing about keeping their format. The analyzer
  internals page says GCC 16 changed the supergraph's layout. Our parser would follow GCC releases.
  **Inferred**: the text format churns across major versions.
- **Build needed:** every unit has to compile without errors. In the experiment, a unit with errors still wrote
  `.original` and `.gimple`, but with the failing statements dropped (`<<< error >>>`). It wrote no SSA, IPA or
  analyzer output. So this needs the generated headers (section 4.2) and every optional library's headers.
- **Effort (inferred):** a GIMPLE-text parser plus a new walk. About 1,500–2,500 lines of Python, replacing
  `lower.py` and parts of `returns.py`. A second reader would still be needed for job 1.

### 2.2 A GCC plugin (C++, `-fplugin=`)

The plugin API (`plugins.texi`) has these events:
- `PLUGIN_FINISH_DECL`, `PLUGIN_FINISH_TYPE`, `PLUGIN_PRE_GENERICIZE` ("allows to see low level AST in C and C++
  frontends"), `PLUGIN_FINISH_UNIT`;
- pass registration through `PLUGIN_PASS_MANAGER_SETUP`, so a GIMPLE or IPA pass can be inserted anywhere;
- `PLUGIN_INCLUDE_FILE`.

Requirements:
- Every plugin must define `plugin_is_GPL_compatible`. This repo is GPL-3.0, so that is no obstacle.
- The recommended `plugin_default_version_check` compares `basever`, `datestamp`, `devphase`, `revision` and
  `configuration_arguments`, so a plugin is bound to one exact GCC build.

**Verified:**
- A 45-line plugin built in 0.7 s against `gcc-13-plugin-dev` 13.3.0. It also needed `gmp.h` from `libgmp-dev`;
  neither package is installed here.
- At `PRE_GENERICIZE` it printed, for the test file:
  - `RNA_def_property_flag @22: <var_decl> <bit_ior_expr>`: the `|` is not folded yet;
  - `BKE_report @40: <parm_decl> <const_decl> "no mesh"`: the enum constant is a declaration with its name;
  - `if_stmt` nodes, and `SIZE` still a `var_decl`.

  This is close to what libclang's cursors give. Statement locations are there.
- Under errors, `PRE_GENERICIZE` still ran for every function. The call naming an undeclared `RNA_Object` was simply
  missing, with no recovery node.

What we would write (**inferred**):
- a plugin of about 1,500–3,000 lines of C++ that serializes `PRE_GENERICIZE` trees into the JSON `lower.py`
  produces today. `interp.py`, `rna.py` and `returns.py` (about 3,000 lines) would stay as they are. That JSON is
  the seam: GCC would be a second lowerer behind it.
- for job 2, optionally a GIMPLE pass after `cfg`/`ssa` that writes a CFG per function.

Costs:
- The C++ front end's tree codes (`cp/cp-tree.def`) and accessor macros are internal and change between majors.
  GCC 13 locally, 14.2 for Blender releases and 16 current means one rebuild and some porting per version.
- Users need the matching `gcc-N-plugin-dev` package.
- Macro spellings are reachable only through line-map APIs (`-ftrack-macro-expansion`, on by default). This is
  **inferred** and was not tried.

- **Job 1:** as good as libclang on a clean unit, worse on a broken one, and a lot of C++ to own.
- **Job 2:** the best GCC route. A pass can see GIMPLE/SSA with GCC's own CFG and call graph.
  - Across units it needs either our own summary merge (as today) or `-flto` with the plugin loaded into `lto1`.
  - LTO of all of Blender is a full build plus a whole-program link: **inferred** to be beyond 15 GB of RAM in
    practice.

**Python plugin frameworks:**
- **gcc-python-plugin** (David Malcolm) is effectively dead. Its README calls it "experimental proof-of-concept" and
  lists testing up to GCC 8. Its last commit, on 19 Sep 2020, was "Don't include params.h if building with GCC 10".
  It would need porting to GCC 13/14 before use.
- **GCC MELT** (a Lisp-like plugin DSL) has been discontinued since about 2016. **Unverified**: its site could not
  be reached.

No maintained Python binding to GCC internals was found.

### 2.3 `-fanalyzer` (static analyzer, SARIF output)

From the manual:
- It does "coverage-guided symbolic execution" over GIMPLE-SSA, interprocedurally within a unit, with call strings
  and optional call summaries (`-fanalyzer-call-summaries`).
- Whole-program analysis goes through LTO. The internals doc chose GIMPLE-SSA "in the hopes of making it easy to work
  with LTO".
- SARIF via `-fdiagnostics-format=sarif-file`. Graphs via `-fdump-analyzer-supergraph` / `-exploded-graph`.
- Extension: `PLUGIN_ANALYZER_INIT` (GCC 13 `plugin.def`) lets a plugin register *known functions*, and
  `gcc.dg/plugin/analyzer_known_fns_plugin.c` is the example.
- GCC 13's and master's manuals both say: "The analyzer is only suitable for use on C code in this release."

**Verified with GCC 13.3:**

| Test | Result |
|---|---|
| `int use(Main *m) { Object *ob = find_mesh(m); return ob->type; }`, where `find_mesh` loops and returns `nullptr` | `-Wanalyzer-null-dereference`, a 6-event SARIF `codeFlow` through the callee |
| Probe `sink = f_raises(m, r)->type;` (NULL after `BKE_report`) | warned, so `raises` cannot be told from `null` unless `BKE_report` is modelled |
| Probe on `f_unknown` (calls a function with no body) | silent: `unknown` looks like `never` |
| Probe on `f_alloc() { return new Object(); }` | false positive: "dereference of possibly-NULL `operator new(16)`" |
| `blenkernel/intern/deform.cc`, real flags, `-O0 -fanalyzer` | 8.3 s; 4 warnings, all `-Wanalyzer-null-argument` false positives on placement-`new` lambdas in `BLI_any.hh:46-52`; none about `deform.cc` itself |
| A unit with errors | the analyzer did not run |

- **Job 2:**
  - A witness finder. Generate a probe per RNA function (`sink = f(args)->field;`) in a TU that `#include`s the
    `rna_X.cc` runtime half, then read the SARIF results.
  - A known-function plugin could make `BKE_report(..., RPT_ERROR...)` end the path, which separates `raises` from
    `null`.
  - It cannot give `never`, because silence also means "gave up" (exploded-graph limits) or "unknown callee".
  - It is officially C-only, and its C++ false positives in GCC 13 fall right on our verdicts (`new`).
- **Job 1:** nothing.
- **Effort (inferred):** a probe generator in Python (about 300 lines) plus a SARIF reader. A known-function plugin
  is about 200 lines of C++ against analyzer internals, which are unstable.

### 2.4 CastXML and GCC-XML

- **GCC-XML** was a patched GCC front end. It is archived (2024) with the note "GCC-XML has been succeeded by
  CastXML".
- **CastXML** parses "as complete translation units using an internal Clang compiler".
  - `--castxml-cc-gnu g++` only makes Clang's predefined macros and target match GCC's.
  - **Verified**: Ubuntu's `castxml` 0.6.3 links `libclang-cpp.so.17` and `libLLVM-17`.
  - It writes declarations (types, functions, fields) as XML.
- It is not a GCC route and writes no function bodies (**inferred** from the manual, which describes only "a subset
  of the AST"). So it gives no `RNA_def_*` sequences and no return analysis. It offers nothing libclang lacks.

### 2.5 Other GCC pieces

- **libgccjit** is "an API for embedding GCC inside programs": you build IR through it and GCC compiles it. It has
  no front end for reading source.
- **LTO IR** (GIMPLE bytecode in `.o` files) can only be read back by `lto1`, which means a plugin again.
- **`-fsyntax-only` with diagnostics** gives errors and warnings, not facts.
- **`-fgimple`** (a C front end that reads GIMPLE) is for testing passes. It does not help with reading.

## 3. Clang/LLVM-based options

### 3.1 libclang (current)

- `Tooling.md`: "LibClang is a stable high level C interface to clang ... Use LibClang when you ... need a stable
  interface that takes care to be backwards compatible ... want to interface with clang from other languages than
  C++."
- **Job 1:** the best of all options. `clang_Cursor_Evaluate`, `RecoveryExpr` for broken calls (**verified**: the
  undeclared-`RNA_Object` call keeps `"parent"`), types, USRs, global initializers.
- **Job 2:** works today (section 5.1 of the stubs note). We own the walk.
- **Limits:**
  - PyPI `libclang` is stuck at 18.1.1 (June 2024; **verified** on pypi.org). The bindings-only `clang` package is at
    21.1.7 but needs a system `libclang.so` of the same version.
  - The libstdc++ errors (`<ratio>`) are **inferred** to come from the mismatch of the wheel's clang 18 resource
    headers and flags, since the same clang 18 compiled `makesrna` in the build. A newer libclang through the
    `clang` bindings is the likely fix.

### 3.2 Improvements to the libclang inputs (no new tool)

1. **Codegen-only full-config build.**
   - `.cache/blender-build/5.2-src` already contains `bin/makesrna` (**verified**).
   - `makesrna/intern/CMakeLists.txt` produces all of `GENSRC` (the `rna_*_gen.cc` and `RNA_prototypes.hh`) in one
     `add_custom_command` that runs that binary. The stubs note measured the makesrna run at about 1 s.
   - `build.ninja` has 3,859 `CUSTOM_COMMAND` outputs, mostly shader sources and infos, icons and DNA files.
     Building only those, with Ninja given the generated files as targets, makes every generated header real.
   - Cost (**inferred**): minutes, since the tools (`datatoc`, `makesdna`, glsl preprocessors) are small. No object
     files of Blender itself are built.
   - This removes the shim and should clear most of the 69 error units (missing generated declarations, shim
     mistakes).
2. **Parse `rna_X_gen.cc` directly** (it `#include`s `rna_X.cc` with `RNA_RUNTIME`). That is exactly how Blender
   compiles the runtime halves, which fixes "files parsed separately that Blender compiles together".
3. **Headers without their own compile command** keep borrowing a unit's flags. This is the same for every
   compiler-based approach.
4. **Optional libraries** (fftw3, MaterialX): configure with the precompiled `lib/` dependencies, or accept the
   `#ifdef`'d-out code. This is also the same for every compiler.

### 3.3 LibTooling, AST matchers, `-ast-dump=json`, Clang plugins

- LibTooling and AST matchers are C++ with full AST control. `Tooling.md` warns "Do not use LibTooling when you ...
  want a stable interface". `clang-query` (installed) lets you try matchers interactively.
- `-Xclang -ast-dump=json`:
  - Complete, and has `expansionLoc`/`spellingLoc` (**verified**).
  - Size: 55 KB for one function with `-ast-dump-filter`, but 262 MB for the 4-STL-header file without a filter
    (**verified**).
  - It works per unit with a filter on the functions we need. Its JSON shape follows clang's internal AST, with no
    stability promise.
- **Job 1 / job 2:** the same information as libclang, with more control (`CFG` building, `ASTContext`) but a C++
  codebase that follows every LLVM release. Worth it only if libclang's cursor API blocks something. Nothing in
  `lower.py` suggests it does.

### 3.4 Clang Static Analyzer (CSA)

- C++-mature path-sensitive symbolic execution.
- Checkers: `core.NullDereference`, and `nullability.*` (mostly ObjC; `NullReturnedFromNonnull` covers C/C++ but
  needs `_Nonnull`).
- Cross-TU inlining through `clang-extdef-mapping` (installed) and `ctu-dir`.
- Custom checkers in C++.
- Budgets: `max-nodes` 75,000 per top-level function by default.

**Verified, on the same probe file as GCC:**
- With defaults it did *not* report the NULL from `f_raises`. `suppress-null-return-paths` (default `true`, "a
  heuristic for avoiding bug reports with paths that go through inlined functions that are more defensive than
  their callers") hides exactly the paths we want.
- With `-analyzer-config suppress-null-return-paths=false` (and `suppress-inlined-defensive-checks=false`) it
  reported `core.NullDereference` at the probe.
- No false positive on `new`.
- Silent on the unknown callee.
- Annotating returns with `_Nonnull` did not add a `NullReturnedFromNonnull` report for the same function.

Assessment:
- **Job 2:** a better witness finder than `-fanalyzer` for C++. It has the same blind spot: no proof of `never`.
  `raises` needs a small checker that makes the path a sink after `BKE_report` with an error level.
- **Job 1:** nothing.
- **Effort (inferred):** a probe generator plus a `plist`/SARIF reader, about 300 lines of Python. Optionally a
  checker of about 150 lines of C++ for `raises`, built against LLVM 18 (`clang-tools-18` is installed).

### 3.5 LLVM IR (`clang -emit-llvm`)

**Verified:**
- `-O0 -g` IR keeps every call with its string constants (`@.str.3 = "Parent object"`), debug locations, and all
  global initializers (tables).
- It folds constants, and drops the constant `if` and the enum names, as GCC does.
- Since LLVM 17 pointers are opaque (`ptr`), so struct types survive only in debug info.

The useful find for job 2:
- At `-O1`, LLVM's own attribute inference marks provably non-null returns: `f_addr` (`&global`) and `f_new`
  (`new`) got `nonnull`, and `f_checked` (`o ? o : &g`) got `nonnull` too.
- `f_deref(ob)` got `returned` on its parameter, so the caller's nullness carries through.
- `find_mesh` (can return NULL) and `f_unknown` got nothing.

This is a sound-direction check for `never` (only what LLVM can prove), within one unit. With `llvm-link` of the
relevant units' bitcode it would cover callees too (**inferred**). It does not know `raises`. Its idea of "non-null"
includes UB-based reasoning: a dereferenced pointer is assumed non-null, which is the same rule `returns.py` uses.

- **Effort (inferred):** `clang -O1 -emit-llvm -S` over the runtime units, then a grep of `define ... nonnull ptr
  @...` and `returned` arguments. About 100 lines of Python, no new dependency.
- **Use:** cross-check `never` verdicts and find missed ones.

## 4. Other analyzers

| Tool | Realistic for Blender C++20? | Why |
|---|---|---|
| **Infer** (Pulse) | possible, heavy | MIT. C/C++ "Yes". Pulse is interprocedural with per-function summaries, and reports a NULL dereference only when it is *manifest* ("Errors are only reported when all conditions on the erroneous path are true regardless of input"). Conditional NULLs stay *latent* and unreported. It captures the build through its own bundled clang (`facebook-clang-plugins` in the repo). Answering "can it return NULL" would mean reading summaries (`infer debug --procedures-summary`), whose format is internal. Install and capture time on 4 CPUs: **unverified**, but large. |
| **CodeQL** | licence-limited | `codeql-cli-binaries` licence: analysis is allowed only on an "Open Source Codebase". Blender is GPL, so allowed, but the CLI cannot be redistributed and needs a CodeQL database built from a traced compile. Has good C++ dataflow and nullness libraries. Whether `build-mode: none` covers C/C++: **unverified** (docs.github.com did not resolve). |
| **Frama-C** | no | C only. Its C++ front end Frama-Clang is a separate, experimental plugin (**unverified**: frama-c.com did not resolve). |
| **cppcheck** | no for these jobs | Its own tokenizer and simplecpp preprocessor. It finds bugs (`nullPointer`) but exposes no facts or summaries. |
| **Joern** (code property graphs) | no | A fuzzy C/C++ parser, without types or macro expansion of the real build (**inferred** from its README, which uses gcc only to find system headers). |
| **srcML**, **tree-sitter** | no for job 2, weak for job 1 | Syntax only: no preprocessing, no name resolution. The regex reader already covers what syntax gives. |
| **Coccinelle** | no | C-focused semantic patching, with limited C++ (**unverified**). |

## 5. Comparison and recommendation

### 5.1 Comparison

Build column: "clean" means each unit must compile without errors for the output to exist.

| Approach | Job 1 (define-time facts) | Job 2 (nullable returns) | Build needed | Language, size (inferred) | Stability | Fixes known problems? |
|---|---|---|---|---|---|---|
| libclang (now) | best: recovery, eval, initializers | works (our walk) | configure + partial | Python, exists | stable C API; wheel stuck at 18 | — |
| **libclang + codegen + `_gen.cc` units** | best | works, fewer `unknown` | configure + codegen only (minutes) | Python, small change | as above | missing generated files, shim, `_gen.cc` grouping |
| GCC dumps (GIMPLE text) | poor: folded, no enum names, no tables | usable IR, text parsing | clean units: codegen + all optional libs | Python, 1.5–2.5k | debugging format | only libstdc++; a new failure mode on errors |
| GCC plugin | good (`PRE_GENERICIZE`), no recovery | best GCC route (GIMPLE pass) | clean units + plugin-dev | C++, 1.5–3k + rebuild per GCC | internal API, exact version | libstdc++ only |
| GCC `-fanalyzer` | none | witnesses for `null` only; C++ false positives | clean units | Python 300 + optional C++ plugin | SARIF stable; analyzer C-only | no |
| CastXML / GCC-XML | declarations only | none | configure | — | — | no (clang inside) |
| LibTooling / JSON AST | = libclang | = libclang | as libclang | C++ or huge JSON | unstable | no |
| Clang Static Analyzer | none | witnesses for `null` (C++-mature) | as libclang | Python 300 + optional C++ checker | stable CLI, unstable checker API | no |
| LLVM IR attributes | poor (folded) | cheap proof of `never` within a unit | clean units | Python ~100 | `nonnull` attribute stable | no |
| Infer Pulse | none | manifest NULLs only; summaries internal | full capture | OCaml tool, config | moderate | no |
| CodeQL | possible (queries) | good dataflow | traced compile | QL | stable | no; licence constraints |

### 5.2 Recommendation

1. **Do not move to GCC.**
   - For job 1, every GCC route either loses facts (dumps) or means a C++ plugin that recreates libclang's view
     without its error recovery.
   - For job 2, GCC's one ready-made tool is officially C-only and gave C++ false positives on exactly the
     allocations that decide `never`.
   - The one problem GCC would fix (the libstdc++ mismatch) has a cheaper fix: newer libclang bindings, or matching
     flags.
2. **Fix the inputs:** run the codegen (`makesrna` and the other `CUSTOM_COMMAND` outputs), and parse the runtime
   halves as `rna_X_gen.cc` units. This targets most of the 69 error units directly. Measure the error count before
   and after.
3. **Hybrid for job 2:** keep `returns.py` as the verdict, and add two independent checks.
   - LLVM's inferred `nonnull`/`returned` attributes confirm `never` cheaply.
   - CSA probes with `suppress-null-return-paths=false` give a concrete path for `null`. A disagreement with the walk
     is a lead to inspect.
   - Keep GCC's analyzer in reserve for pure-C units if the CSA probes prove noisy.
4. **Revisit a GCC plugin** only if the project needs results that match the release compiler exactly (GCC 14.2).
   Even then, emit the existing lowered JSON so the interpreter stays the same.

### 5.3 Verified versus inferred

- **Verified here:**
  - every dump behaviour in 2.1;
  - the plugin's view at `PRE_GENERICIZE`;
  - the `-fanalyzer` results, including `deform.cc`;
  - GCC's behaviour on units with errors;
  - clang's `RecoveryExpr`;
  - the JSON AST sizes;
  - CSA's suppression default and its probe results;
  - LLVM's attribute inference;
  - CastXML's clang linkage;
  - `bin/makesrna` existing in the partial build, and the counts of `CUSTOM_COMMAND` outputs and `rna_*_gen.cc`;
  - Blender's release GCC version;
  - PyPI libclang's version;
  - the gcc-python-plugin and GCC-XML status.
- **Inferred, not measured:**
  - all line counts and effort;
  - the codegen-only build time and how many of the 69 error units it fixes;
  - the cause of the libstdc++ errors;
  - LTO memory;
  - GIMPLE format churn;
  - the costs of Infer and CodeQL.
- **Unverified (sources unreachable):** MELT's status; Frama-Clang's maturity; CodeQL's C/C++ `build-mode: none`;
  Coccinelle's C++ support.

## 6. Sources

GCC (the manual's texinfo source, read from the GitHub mirror because gcc.gnu.org did not resolve):

- Invocation manual (dump, analyzer, `-aux-info`, `-fdump-go-spec`, `-fcallgraph-info`, `-fsave-optimization-record`
  and SARIF options): [GCC 13](https://github.com/gcc-mirror/gcc/blob/releases/gcc-13/gcc/doc/invoke.texi),
  [master](https://github.com/gcc-mirror/gcc/blob/master/gcc/doc/invoke.texi) (`gcc/BASE-VER` 17.0.0)
- Plugins (events, `plugin_is_GPL_compatible`, version check):
  [plugins.texi](https://github.com/gcc-mirror/gcc/blob/master/gcc/doc/plugins.texi)
- `PLUGIN_ANALYZER_INIT`: [plugin.def (GCC 13)](https://github.com/gcc-mirror/gcc/blob/releases/gcc-13/gcc/plugin.def)
- Known-function plugin example:
  [analyzer_known_fns_plugin.c](https://github.com/gcc-mirror/gcc/blob/releases/gcc-13/gcc/testsuite/gcc.dg/plugin/analyzer_known_fns_plugin.c)
- Analyzer internals: [analyzer.texi](https://github.com/gcc-mirror/gcc/blob/master/gcc/doc/analyzer.texi)
- libgccjit: [jit/docs/index.rst](https://github.com/gcc-mirror/gcc/blob/master/gcc/jit/docs/index.rst)

Plugin frameworks and declaration dumpers:

- gcc-python-plugin: [repository](https://github.com/davidmalcolm/gcc-python-plugin),
  [commits](https://github.com/davidmalcolm/gcc-python-plugin/commits/master)
- GCC-XML: [repository](https://github.com/gccxml/gccxml)
- CastXML: [manual](https://github.com/CastXML/CastXML/blob/master/doc/manual/castxml.1.rst), and Ubuntu noble's
  `castxml` 0.6.3 package (inspected with `ldd`)

Clang and LLVM (the docs source on GitHub, because clang.llvm.org did not resolve):

- [Tooling.md](https://github.com/llvm/llvm-project/blob/main/clang/docs/Tooling.md)
- [analyzer/checkers.md](https://github.com/llvm/llvm-project/blob/main/clang/docs/analyzer/checkers.md)
- [AnalyzerOptions.def](https://github.com/llvm/llvm-project/blob/main/clang/include/clang/StaticAnalyzer/Core/AnalyzerOptions.def)
- [CrossTranslationUnit.md](https://github.com/llvm/llvm-project/blob/main/clang/docs/analyzer/user-docs/CrossTranslationUnit.md)
- PyPI: [libclang](https://pypi.org/project/libclang/), [clang](https://pypi.org/project/clang/)

Other tools:

- Infer: [README](https://github.com/facebook/infer/blob/main/README.md),
  [Pulse](https://github.com/facebook/infer/blob/main/website/docs/checker-pulse.md)
- [CodeQL CLI licence](https://github.com/github/codeql-cli-binaries/blob/main/LICENSE.md)
- [Joern](https://github.com/joernio/joern), [cppcheck](https://github.com/danmar/cppcheck),
  [srcML](https://github.com/srcML/srcML)

Blender 5.2 (`.cache/blender-src/5.2-src`):

- `build_files/config/pipeline_config.yaml` (buildbot `gcc` `14.2.1`), and
  `build_files/build_environment/linux/linux_rocky8_setup.sh` (`gcc-toolset-14`)
- `source/blender/makesrna/intern/CMakeLists.txt` (the `GENSRC` custom command)
- `.cache/blender-build/5.2-src/build.ninja` and `bin/makesrna`

Not reachable from this session: gcc.gnu.org, clang.llvm.org, docs.github.com, fbinfer.com, frama-c.com.
