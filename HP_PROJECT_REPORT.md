# Semantic Diff for Compiler IR
### HP Compiler Design Project — Final Report

---

**Student:** Shreyasr
**Date:** May 31, 2026
**Project:** Semantic Diff for Compiler IR
**Partner:** HP Inc.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [System Architecture](#3-system-architecture)
4. [Pipeline Stages](#4-pipeline-stages)
5. [Key Algorithms](#5-key-algorithms)
6. [Change Classification System](#6-change-classification-system)
7. [Evaluation & Benchmark Results](#7-evaluation--benchmark-results)
8. [Realistic Commit-Pattern Case Studies](#8-realistic-commit-pattern-case-studies)
9. [Web UI & Tooling](#9-web-ui--tooling)
10. [Deliverables Checklist](#10-deliverables-checklist)
11. [Conclusion](#11-conclusion)

---

## 1. Executive Summary

This project delivers a working **Semantic Diff tool for LLVM Intermediate Representation (IR)**, which compares two versions of a C/C++ program — or two pre-compiled `.ll` files — and reports *semantic* changes at the IR level rather than raw textual differences.

Unlike a plain `diff`, the tool answers the question: *"What did the compiler actually change about the behavior of this code?"* It detects vectorization, loop unrolling, inlining, dead code elimination, branch folding, memory access changes, and critical-path shifts — each classified with severity (PERF / WARN / INFO) and a plain-English explanation.

**Key results:**
- Benchmark evaluation: **10/10 cases passed, F1 = 100%**
- Unit test suite: **54 tests, all passing**
- Source-pair demo: **7 realistic LLVM/application optimization scenarios**
- Deliverables: **core pipeline complete; publication-grade real-commit evaluation remains future work**

---

## 2. Problem Statement

Compiler developers and performance engineers routinely ask:

> *"What changed semantically when we applied this optimization pass?"*

A line-level diff of LLVM IR is noisy and hard to interpret — unnamed temporaries (`%1`, `%2`) shift with every edit, basic-block labels renumber, and metadata lines swamp the signal. Existing tools either show raw diffs (git, `diff`) or require full compiler expertise to interpret IR manually.

This tool bridges the gap: it normalizes away surface noise, structurally matches functions and blocks across revisions, and classifies changes into human-readable categories with actionable severity labels.

---

## 3. System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Input Layer                               │
│   C/C++ source files  ──OR──  Pre-compiled .ll IR files          │
└──────────────────┬───────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                   Compiler Extractor                             │
│   clang -O{level} -S -emit-llvm → raw .ll text                  │
│   opt -mem2reg -sroa (optional promotion pass)                   │
└──────────────────┬───────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                     IR Normalizer                                │
│   • Strip debug metadata, module flags, source_filename          │
│   • Rename unnamed temporaries (%0, %1 → %t0, %t1)              │
│   • Normalize pointer syntax (i8* → ptr)                         │
│   • Canonicalize commutative ops (add, mul, and, or, xor)        │
│   • Remove !tbaa, !range, !dbg annotations                       │
└──────────────────┬───────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                       IR Parser                                  │
│   • Parse functions, basic blocks, instructions                  │
│   • Build CFG (control-flow graph) per function                  │
│   • Build DFG (data-flow graph / use-def chains)                 │
│   • Identify loops (back-edges in CFG)                           │
│   • Detect vector types (<N x T>), unroll factors, IV strides    │
└──────────────────┬───────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Diff Engine                                 │
│   Function Matcher (4-stage):                                    │
│     1. Exact name match                                          │
│     2. Signature match (return type + arg types)                 │
│     3. Histogram cosine similarity (instruction type counts)     │
│     4. Body fingerprint (hashed instruction sequence)            │
│   Block Matcher (2-stage):                                       │
│     1. Exact label match                                         │
│     2. Fuzzy fingerprint (Jaccard on instruction set)            │
│   Produces: ModuleDiff → [FunctionDiff → [BlockDiff]]            │
└──────────────────┬───────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                   Change Classifiers (3 modules)                 │
│                                                                  │
│  OptClassifier      CFClassifier       MemClassifier             │
│  ─────────────      ────────────       ─────────────             │
│  VECTORIZE_*        BRANCH_*           LOAD_COUNT_CHANGED        │
│  LOOP_UNROLL_*      LOOP_*             STORE_COUNT_CHANGED       │
│  INLINING_*         CFG_COMPLEXITY_*   ALLOCA_CHANGED            │
│  DEAD_CODE_*        CRITICAL_PATH_*    MEM_DEP_CHANGED           │
└──────────────────┬───────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Report Renderer                               │
│   Rich (colored terminal)  ──OR──  JSON  ──OR──  .dot (CFG)     │
│   Severity: PERF (green) / WARN (yellow) / INFO (cyan)          │
└──────────────────────────────────────────────────────────────────┘
```

**Technology stack:**

| Layer | Technology |
|-------|-----------|
| Core engine | Python 3.10+, NetworkX (CFG/DFG graphs) |
| Compiler integration | clang, opt (LLVM toolchain) |
| Web backend | FastAPI, Pydantic, Uvicorn |
| Web frontend | React 19, TypeScript, Vite |
| CFG visualization | Cytoscape.js |
| PDF export | jsPDF |
| Testing | pytest |

---

## 4. Pipeline Stages

### Stage 1 — IR Extraction (Source Mode)

When given C/C++ source files, the tool invokes:

```bash
clang -O{level} [-std=...] -S -emit-llvm -o out.ll input.c
opt -mem2reg -sroa out.ll -S -o out.ll     # optional: promote allocas
```

This produces human-readable LLVM IR text that is then passed through the normalizer. In `--ir` mode, this stage is skipped and `.ll` files are used directly.

### Stage 2 — Normalization

The normalizer is critical for reducing false positives. Without it, every trivially renamed temporary register (`%1` vs `%2`) would appear as a change. Normalization steps:

1. **Strip noise lines:** `source_filename`, `target datalayout`, `target triple`, `!llvm.*` metadata lines, `attributes #N` blocks
2. **Rename unnamed temporaries:** Sequential scan assigns `%t0`, `%t1`, … in order of first appearance — making both sides comparable
3. **Normalize pointer types:** Replaces legacy `i8*`, `i32*` etc. with opaque `ptr` (LLVM 15+ style), handles `getelementptr inbounds` → `getelementptr`
4. **Canonicalize commutative ops:** For `add`, `mul`, `and`, `or`, `xor` — sort operands alphabetically so `add %a, %b` and `add %b, %a` match

### Stage 3 — Parsing

The parser builds a structured in-memory model from normalized IR text:

- **Module:** list of `Function` objects
- **Function:** list of `BasicBlock` objects + parameter signature
- **BasicBlock:** list of `Instruction` objects + label
- **Instruction:** opcode, operands, result register, type annotations
- **CFG:** `networkx.DiGraph` where nodes are block labels, edges are branch targets
- **DFG:** `networkx.DiGraph` where edges are use-def dependencies (result register → consuming instruction)
- **Loop detection:** back-edges in CFG (DFS-based), with induction variable and stride extraction
- **Vector detection:** regex scan for `<N x T>` type annotations → width extraction

### Stage 4 — Diff Engine

The diff engine performs **hierarchical structural matching**:

**Function matching** uses a 4-stage waterfall:
1. Exact name → direct pair
2. Renamed functions → match by signature similarity
3. Instruction histogram cosine similarity (normalized over opcode frequencies)
4. Body fingerprint hash for final tie-breaking

**Block matching** within matched function pairs:
1. Exact label match
2. Fuzzy fingerprint: Jaccard similarity on the set of instruction opcodes per block

Each matched pair gets a `similarity` score (0.0–1.0). Blocks below threshold are flagged added/removed.

### Stage 5 — Classification

Three independent classifier modules analyze `FunctionDiff` objects:

| Classifier | Module | What it detects |
|-----------|--------|----------------|
| `OptClassifier` | `classify/optimizations.py` | Vectorization, unrolling, inlining, dead code |
| `CFClassifier` | `classify/control_flow.py` | Branch count, loop count, CFG complexity, critical path |
| `MemClassifier` | `classify/memory.py` | Load/store counts, alloca changes, memory dependencies |

Each classifier emits `SemanticChange` objects with a `ChangeKind` enum value, severity (`perf`/`warn`/`info`), description, and optional detail line.

### Stage 6 — Reporting

- **Rich mode:** ANSI-colored terminal output with severity-coded badges
- **JSON mode:** Structured JSON for programmatic consumption or UI display
- **DOT mode:** One `.dot` file per modified function, color-coded by block status (green=added, red=removed, yellow=modified) — renderable with Graphviz

---

## 5. Key Algorithms

### 5.1 Function Histogram Similarity

For fuzzy-matching renamed functions, the tool computes a cosine similarity between instruction frequency histograms:

```
hist(f) = { opcode: count }  for all instructions in function f
cosine(old, new) = (old · new) / (|old| × |new|)
```

This is robust to local renaming and small structural edits while correctly distinguishing functions that do fundamentally different work.

### 5.2 Block Fingerprint (Jaccard)

For block matching, each block is represented as the *multiset* of instruction opcodes it contains. Jaccard similarity:

```
J(A, B) = |A ∩ B| / |A ∪ B|
```

A threshold of 0.3 is used for fuzzy matching — low enough to handle heavily modified blocks, high enough to avoid spurious matches.

### 5.3 Critical Path Computation

The critical path is the length of the longest chain through the data-flow graph (use-def edges). This models the minimum latency of the function on an ideal out-of-order processor:

```
critical_path(f) = max path length in DFG(f) using BFS/topological sort
```

`CRITICAL_PATH_LONGER` / `CRITICAL_PATH_SHORTER` are emitted when this value changes between old and new.

### 5.4 Loop Detection

Loops are identified by back-edges in the CFG (edges from a later block to an earlier block in DFS order). For each loop:
- **Induction variable (IV):** phi node with a constant-stride increment
- **Stride:** the constant added to IV per iteration
- **Unroll factor:** estimated from stride or multiple IV phi nodes
- **Vectorization width:** number of lanes in `<N x T>` typed instructions in the loop body
- **Trip count:** static value if the loop bound is a compile-time constant

---

## 6. Change Classification System

### 6.1 Change Kinds (24 total)

| Category | Kind | Severity | Meaning |
|----------|------|----------|---------|
| **Vectorization** | `VECTORIZE_GAINED` | PERF | Loop now uses SIMD lanes |
| | `VECTORIZE_LOST` | WARN | Loop lost SIMD — check aliasing |
| | `VECTORIZE_WIDTH_CHANGE` | INFO | SIMD width changed (e.g. 4→8) |
| **Loop Unrolling** | `LOOP_UNROLL_GAINED` | PERF | Loop body now unrolled |
| | `LOOP_UNROLL_LOST` | WARN | Loop no longer unrolled |
| **Inlining** | `INLINING_ADDED` | PERF | Call site inlined |
| | `INLINING_REMOVED` | WARN | Previously inlined call re-outlined |
| **Dead Code** | `DEAD_CODE_ELIMINATED` | INFO | Unreachable code removed |
| | `DEAD_CODE_REINTRODUCED` | WARN | New dead/speculative path added |
| **Branches** | `BRANCH_ADDED` | WARN | New conditional branch |
| | `BRANCH_REMOVED` | INFO | Branch folded (branchless) |
| **Loops** | `LOOP_ADDED` | INFO | New loop structure |
| | `LOOP_REMOVED` | INFO | Loop fully unrolled or eliminated |
| **CFG** | `CFG_COMPLEXITY_UP` | WARN | More edges/blocks |
| | `CFG_COMPLEXITY_DOWN` | INFO | CFG simplified |
| **Memory** | `LOAD_COUNT_CHANGED` | WARN/INFO | Load instruction count changed |
| | `STORE_COUNT_CHANGED` | WARN/INFO | Store instruction count changed |
| | `ALLOCA_CHANGED` | INFO | Stack allocation changed |
| | `MEM_DEP_CHANGED` | INFO | Store→load dependency changed |
| **Instructions** | `INSTR_COUNT_UP` | WARN | More instructions total |
| | `INSTR_COUNT_DOWN` | INFO | Fewer instructions total |
| **Latency** | `CRITICAL_PATH_LONGER` | PERF | Longer serial dep chain |
| | `CRITICAL_PATH_SHORTER` | PERF | Shorter critical path |
| **Runtime** | `RUNTIME_CHECK_ADDED` | INFO | Aliasing/bounds check added |

### 6.2 Severity Mapping

| Severity | Color | Meaning |
|----------|-------|---------|
| `PERF` | Green | Direct performance improvement expected |
| `WARN` | Yellow | Regression risk — investigate |
| `INFO` | Cyan | Neutral structural change — informational |

### 6.3 Performance Impact Score

The web UI computes a composite **Performance Impact Score** (0–100) from the classified changes:

```
score = min(PERF changes, 2) × 25
      + min(WARN changes, 2) × 15
      + min(INFO changes, 4) × 5
      = min(raw_score, 100)
```

Color coding: green (0–20, low) → amber (21–50, medium) → orange (51–80, high) → red (81–100, critical).

---

## 7. Evaluation & Benchmark Results

### 7.1 Benchmark Design

The built-in benchmark (`semantic_diff.eval`) consists of 10 hand-crafted LLVM IR fixture pairs drawn from real optimization scenarios in LLVM, SQLite, PostgreSQL, Redis, and OpenSSL. Each fixture has:
- A commit-style description
- Old and new IR snippets
- Ground-truth `ChangeKind` labels

The evaluator computes **Precision**, **Recall**, and **F1** per case and reports aggregate scores.

### 7.2 Results

```
Benchmark cases passed = 10/10    average F1 = 100.00%
```

| Case ID | Project | Description | Expected | Found | Result |
|---------|---------|-------------|----------|-------|--------|
| llvm-loop-vectorize-gained | LLVM | Fixed-stride loop gets vector IR | `LOOP_UNROLL_GAINED`, `VECTORIZE_GAINED` | ✓ exact | **PASS** |
| llvm-loop-vectorize-lost | LLVM | Aliasing change breaks vectorization | `LOOP_UNROLL_LOST`, `VECTORIZE_LOST` | ✓ exact | **PASS** |
| llvm-inline-added | LLVM | Small helper becomes profitable to inline | `INLINING_ADDED` | ✓ exact | **PASS** |
| llvm-inline-removed | LLVM | Helper grows past inline threshold | `INLINING_REMOVED` | ✓ exact | **PASS** |
| llvm-branch-added | LLVM | Fast-path guard adds conditional branch | `BRANCH_ADDED`, `CFG_COMPLEXITY_UP`, `DEAD_CODE_REINTRODUCED`, `INSTR_COUNT_UP` | ✓ exact | **PASS** |
| llvm-branch-removed | LLVM | Branch folded into select | `BRANCH_REMOVED`, `CFG_COMPLEXITY_DOWN`, `DEAD_CODE_ELIMINATED`, `INSTR_COUNT_DOWN` | ✓ exact | **PASS** |
| sqlite-loads-added | SQLite | New predicate reads extra row field | `INSTR_COUNT_UP`, `LOAD_COUNT_CHANGED` | ✓ exact | **PASS** |
| postgres-stores-removed | PostgreSQL | Redundant state write eliminated | `INSTR_COUNT_DOWN`, `STORE_COUNT_CHANGED` | ✓ exact | **PASS** |
| redis-memdeps-added | Redis | Update path adds store-load reuse | `INSTR_COUNT_UP`, `LOAD_COUNT_CHANGED`, `MEM_DEP_CHANGED`, `STORE_COUNT_CHANGED` | ✓ exact | **PASS** |
| openssl-critical-path-longer | OpenSSL | Hardened arithmetic adds serial deps | `CRITICAL_PATH_LONGER`, `INSTR_COUNT_UP` | ✓ exact | **PASS** |

### 7.3 Unit Test Coverage

```
54 tests across 6 modules — all passing
```

| Test Module | Tests | Coverage Area |
|-------------|-------|---------------|
| `test_normalizer.py` | 6 | Metadata stripping, temp renaming, pointer normalization, commutative canonicalization |
| `test_parser.py` | 10 | Function/block/instruction parsing, CFG construction, loop detection, vector type extraction |
| `test_diff.py` | 9 | Function matching (exact, fuzzy, added/removed), block matching, similarity scoring |
| `test_classifier.py` | 15 | All 24 ChangeKind cases, severity assignment, description accuracy |
| `test_benchmark.py` | 2 | Full pipeline end-to-end via benchmark suite |
| `test_improvements.py` | 12 | Regression tests for all fixes applied during development |

---

## 8. Realistic Commit-Pattern Case Studies

Seven source pairs model IR-level effects inspired by LLVM and application optimization commit patterns, including SQLite/PostgreSQL-style data access changes and an OpenSSL-style hardening scenario. Each pair consists of `.c` source files. The included `run_demo.sh` script generates `.ll` IR and `.json` reports locally; generated outputs are intentionally excluded from version control.

### Case 1 — `__restrict` Enables Vectorization (LLVM LoopVectorize)

**Commit pattern:** Adding `__restrict` qualifiers to pointer parameters tells the compiler the pointers cannot alias. Without `__restrict`, the vectorizer must insert a runtime aliasing check or bail to scalar code. With `__restrict`, it emits clean SIMD.

**Old IR:** Scalar loop — `load float`, `fmul float`, `store float` per iteration
**New IR:** Vectorized loop — `load <4 x float>`, `fmul <4 x float>`, `store <4 x float>`

**Tool output:**
```
[PERF] Loop 'for.body': vectorization GAINED (width=4)
[PERF] Loop 'for.body': unrolling ADDED (factor ×4)
```
**Tags:** `VECTORIZE_GAINED`, `LOOP_UNROLL_GAINED`

---

### Case 2 — Unrolled Callee Crosses Inline Threshold (LLVM Inliner)

**Commit pattern:** Rewriting or fully unrolling a small fixed-trip-count loop makes the helper easier to inline. The helper body becomes straight-line code and can be expanded at its call sites.

**Tool output:**
```
[INFO] Loop at block 'for.body.i' REMOVED
[INFO] Loop at block 'for.body.i2' REMOVED
[INFO] 3 branch(es) REMOVED
[INFO] CFG complexity DECREASED
[PERF] Critical path LONGER: -1→8 (+9 use-def hops)
```
**Tags:** `LOOP_REMOVED`, `BRANCH_REMOVED`, `CFG_COMPLEXITY_DOWN`, `CRITICAL_PATH_LONGER`

---

### Case 3 — Diamond CFG → Select Instruction (LLVM SimplifyCFG)

**Commit pattern:** A diamond-shaped control flow graph (two `br` paths merging at a `phi`) is folded by SimplifyCFG into branchless `select` instructions — removing 5 basic blocks and all branch instructions.

**Old IR:** 6 blocks (`entry`, `ret.lo`, `check.hi`, `ret.hi`, `ret.x`, `exit`), 5 branch instructions
**New IR:** 1 block, 0 branches, 2 `select` instructions

**Tool output:**
```
[INFO] 5 block(s) eliminated (4 fewer instructions)
[INFO] 5 branch(es) REMOVED
[INFO] CFG complexity DECREASED: edges 7→0 (-100%), blocks 6→1
[INFO] Instruction count DOWN: 9→5 (-4)
```
**Tags:** `BRANCH_REMOVED`, `CFG_COMPLEXITY_DOWN`, `DEAD_CODE_ELIMINATED`, `INSTR_COUNT_DOWN`

---

### Case 4 — Fixed Trip Count Enables Loop Unrolling (LLVM LoopUnroll)

**Commit pattern:** Changing a variable loop bound to a compile-time constant allows the LoopUnroll pass to fully unroll the loop — eliminating the back-edge, IV phi, and branch entirely.

**Tool output:**
```
[INFO] 3 loop(s) REMOVED
[INFO] 7 branch(es) REMOVED
[INFO] CFG complexity DECREASED
[INFO] Instruction count DOWN
[WARN] LOAD count DOWN: 8 → 4 (-4, 50%)
```
**Tags:** `LOOP_REMOVED`, `BRANCH_REMOVED`, `CFG_COMPLEXITY_DOWN`, `INSTR_COUNT_DOWN`, `LOAD_COUNT_CHANGED`

---

### Case 5 — Dead Store Eliminated (LLVM DSE)

**Commit pattern:** A store to a pointer followed immediately by another store to the same pointer (the first value is never read) is a *dead store*. DSE removes it, reducing instruction count and memory pressure.

**Old IR:** `store i32 0` (dead) → `load` → `store i32 %x` (live)
**New IR:** `load` → `store i32 %x` only

**Tool output:**
```
[INFO] Instruction count DOWN: 10→8 (-2)
[INFO] LOAD count DOWN: 3→2 (-1, 33%)
[INFO] STORE count DOWN: 4→3 (-1, 25%)
[INFO] Memory dependencies DOWN: 3→2 (-1, 33%)
```
**Tags:** `INSTR_COUNT_DOWN`, `LOAD_COUNT_CHANGED`, `STORE_COUNT_CHANGED`, `MEM_DEP_CHANGED`

---

### Case 6 — New Struct Field Read Adds Load (Application)

**Commit pattern:** A new predicate (e.g. a permission check or version field) is added to a struct. Reading it adds a `load` instruction, a new branch, and introduces a new execution path.

**Tool output:**
```
[WARN] DEAD_CODE_REINTRODUCED: new speculative path added
[WARN] 2 branch(es) ADDED
[WARN] CFG complexity INCREASED
[WARN] Instruction count UP: +3
[WARN] LOAD count UP: 2→4 (+2, 100%)
```
**Tags:** `LOAD_COUNT_CHANGED`, `BRANCH_ADDED`, `CFG_COMPLEXITY_UP`, `INSTR_COUNT_UP`, `DEAD_CODE_REINTRODUCED`

---

### Case 7 — Chained Arithmetic Lengthens Critical Path (OpenSSL)

**Commit pattern:** A security hardening change adds chained arithmetic operations (e.g. blinding, masking) that create a new serial data-dependency chain — increasing the minimum latency even if instruction count increases only slightly.

**Old IR:** 3 independent arithmetic ops, critical path = 3
**New IR:** 6 chained ops, critical path = 6

**Tool output:**
```
[PERF] Critical path LONGER: 3→6 (+3 use-def hops)
[INFO] Instruction count UP: 9→12 (+3)
```
**Tags:** `CRITICAL_PATH_LONGER`, `INSTR_COUNT_UP`

---

## 9. Web UI & Tooling

### 9.1 Web Application

A full-stack web application provides a browser-based interface to the tool.

**Backend:** FastAPI server (`semantic_diff.web.api`) exposes:
- `POST /api/diff` — accepts old/new IR text + options, returns JSON diff + rich text report
- `GET /api/benchmark` — runs the 10-case benchmark suite and returns structured results
- `GET /api/health` — service liveness check

**Frontend:** React + TypeScript SPA with:

| Feature | Description |
|---------|-------------|
| IR Input Panels | Dual text editors for old/new IR with LLVM syntax highlighting (opcodes, registers, types, vectors) |
| IR Diff Viewer | Side-by-side diff with line-level red/green highlighting and line numbers |
| CFG Visualizer | Interactive Cytoscape.js graph — nodes colored by status (green=added, red=removed, yellow=modified) |
| Performance Score | Animated 0–100 gauge computed from classified changes, color-coded by severity |
| Report Tabs | Rich text / JSON / raw text views of the diff report |
| Benchmark Panel | One-click run of all 10 benchmark cases with pass/fail badges and F1 display |
| PDF Export | HP-branded PDF report with summary table, function cards, change details, and page footer |
| Keyboard Shortcuts | `Ctrl+Enter` / `Cmd+Enter` to trigger diff |
| HP Branding | HP Enterprise gradient header, HP blue (`#0096D6`) / dark blue (`#003087`) color scheme |

### 9.2 CLI Tool

```bash
# Compare two C source files at O2
semantic-diff old.c new.c --opt O2

# Specify C++ standard
semantic-diff old.cpp new.cpp --opt O2 --std c++17

# Diff pre-compiled LLVM IR
semantic-diff --ir old.ll new.ll --format json

# Write report to file
semantic-diff old.c new.c -o report.txt

# Write per-function CFG .dot files
semantic-diff old.c new.c --dot ./cfg_diffs/

# Run benchmark evaluation
semantic-diff-eval
semantic-diff-eval --format json
```

### 9.3 DOT CFG Export

The `DotRenderer` writes one `.dot` file per modified function. Each file is a Graphviz digraph with:
- **Green** nodes — blocks added in the new version
- **Red** nodes — blocks removed from the old version
- **Yellow** nodes — blocks present in both but modified (similarity < 100%)
- **Dashed gray edges** — matched block pairs across revisions

Render with: `dot -Tpng scale.dot -o scale.png`

---

## 10. Deliverables Checklist

| Deliverable | Description | Status |
|-------------|-------------|--------|
| **D1** | IR Normalization — strip metadata, rename temporaries, normalize pointers, canonicalize commutative ops | ✅ Complete |
| **D2** | IR Parsing — functions, blocks, instructions, CFG, DFG, loop detection, vector type extraction | ✅ Complete |
| **D3** | Diff Engine — 4-stage function matcher, 2-stage block matcher, similarity scoring, ModuleDiff structure | ✅ Complete |
| **D4** | Change Classification — 24 ChangeKind values across OptClassifier, CFClassifier, MemClassifier | ✅ Complete |
| **D5** | Evaluation — 10-case offline benchmark suite, Precision/Recall/F1 metrics, and 7 realistic source-pair demos. Exact commit-hash extraction is still needed for publication-grade validation. | ⚠ Offline suite complete |
| **Bonus** | Web UI with CFG visualizer, IR diff viewer, PDF export, Performance Score, HP branding | ✅ Complete |
| **Bonus** | Full unit test suite (54 tests) | ✅ Complete |
| **Bonus** | CLI flags: `--std`, `--output`, `--dot`, `--show-unchanged`, `--no-mem2reg` | ✅ Complete |

---

## 11. Conclusion

This project implements a complete **semantic differencing pipeline for LLVM IR** — from raw C/C++ source to classified, human-readable change reports. The tool supports 24 categories of compiler optimization changes, achieves a perfect F1 score on a 10-case offline benchmark suite covering LLVM, SQLite, PostgreSQL, Redis, and OpenSSL patterns, and includes 7 realistic source-pair demos.

The web interface makes the tool accessible without command-line expertise, providing interactive CFG visualization, side-by-side IR diffing, and a one-click PDF export suitable for sharing with a compiler team.

**The tool is a working prototype for compiler pass development workflows** — developers can paste IR before and after applying a pass, see which optimizations fired and which regressions to investigate, and export a branded PDF report for team review. A publication-grade evaluation should add IR extracted from exact real commit hashes and compare findings against commit descriptions manually.

---

*Report generated for HP Inc. Compiler Design Project, May 2026.*
*Tool source: `semantic-diff-ir` v0.1.0 — FastAPI + React + LLVM*
