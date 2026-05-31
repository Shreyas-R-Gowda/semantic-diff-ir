# Demo Quick Start

This demo path does not require LLVM, `clang`, or `opt`. It uses the committed
LLVM IR fixtures in `examples/real_commits/` and runs the tool in `--ir` mode.

## 1. Install Base Dependencies

```bash
pip install -r requirements.txt
pip install -e .
```

## 2. Run A Semantic Diff On Existing IR

```bash
semantic-diff --ir \
  examples/real_commits/case3_old.ll \
  examples/real_commits/case3_new.ll || true
```

## 3. Save A JSON Report

```bash
semantic-diff --ir --format json \
  examples/real_commits/case3_old.ll \
  examples/real_commits/case3_new.ll \
  -o case3_report.json || true
```

## 4. Run The Offline Benchmark

```bash
semantic-diff-eval
```

## 5. Try Other Included IR Pairs

```bash
semantic-diff --ir \
  examples/real_commits/case1_old.ll \
  examples/real_commits/case1_new.ll || true

semantic-diff --ir \
  examples/real_commits/case7_old.ll \
  examples/real_commits/case7_new.ll || true
```

Source-mode commands such as `semantic-diff old.c new.c --opt O2` require a
local LLVM toolchain. The commands above avoid that requirement. `semantic-diff`
returns exit code 1 when differences are found, so the demo commands use
`|| true` to keep copy-paste shell sessions moving after a successful diff.
