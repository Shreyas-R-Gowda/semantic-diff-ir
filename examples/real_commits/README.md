# Real Commit Examples

Seven source pairs that reproduce IR-level effects of real LLVM optimization commits.

## How to run

```bash
# Install the tool first
pip install -e ".[test]"

# Compile IR and run semantic diff on all 7 cases
bash examples/real_commits/run_demo.sh
```

Requires clang (version 12+). Install with:

```bash
# macOS
brew install llvm

# Ubuntu
apt install clang
```

## Cases

| Case | Commit Pattern | Tool Output |
|------|---------------|-------------|
| 1 | `__restrict` enables vectorization | `VECTORIZE_GAINED`, `LOOP_UNROLL_GAINED` |
| 2 | Unrolled callee crosses inline threshold | `LOOP_REMOVED`, `BRANCH_REMOVED`, `CFG_COMPLEXITY_DOWN`, `CRITICAL_PATH_LONGER` |
| 3 | Diamond CFG -> select instruction | `BRANCH_REMOVED`, `CFG_COMPLEXITY_DOWN`, `INSTR_COUNT_DOWN` |
| 4 | Fixed trip count enables loop unroll | `LOOP_REMOVED`, `BRANCH_REMOVED`, `CFG_COMPLEXITY_DOWN`, `INSTR_COUNT_DOWN` |
| 5 | Dead store eliminated | `STORE_COUNT_CHANGED`, `LOAD_COUNT_CHANGED`, `MEM_DEP_CHANGED`, `INSTR_COUNT_DOWN` |
| 6 | New struct field read adds load | `LOAD_COUNT_CHANGED`, `BRANCH_ADDED`, `CFG_COMPLEXITY_UP`, `INSTR_COUNT_UP` |
| 7 | Chained arithmetic lengthens critical path | `CRITICAL_PATH_LONGER`, `INSTR_COUNT_UP` |

## Output files generated after running

- `case{N}_old.ll` / `case{N}_new.ll` - compiled LLVM IR
- `case{N}_output.json` - semantic diff report in JSON
- `case{N}_cfg/*.dot` - CFG diff graphs (render with graphviz)
