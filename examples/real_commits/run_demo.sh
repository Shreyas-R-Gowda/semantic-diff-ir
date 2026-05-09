#!/usr/bin/env bash
# Requires: clang (any version >= 12), semantic-diff installed via pip install -e .
# To make this script executable manually, run:
#   chmod +x examples/real_commits/run_demo.sh
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOL="python3 -m semantic_diff.cli"

echo "=== Compiling IR ==="
for case in 1 2 3; do
    clang -O2 -S -emit-llvm -fno-discard-value-names \
        "$SCRIPT_DIR/case${case}_old.c" -o "$SCRIPT_DIR/case${case}_old.ll"
    clang -O2 -S -emit-llvm -fno-discard-value-names \
        "$SCRIPT_DIR/case${case}_new.c" -o "$SCRIPT_DIR/case${case}_new.ll"
    echo "  case${case}: IR generated"
done

echo ""
echo "=== Case 1: __restrict enables vectorization ==="
$TOOL --ir "$SCRIPT_DIR/case1_old.ll" "$SCRIPT_DIR/case1_new.ll" \
    || true

echo ""
echo "=== Case 2: Inlining gained after loop unrolling ==="
$TOOL --ir "$SCRIPT_DIR/case2_old.ll" "$SCRIPT_DIR/case2_new.ll" \
    || true

echo ""
echo "=== Case 3: Branch eliminated by select conversion ==="
$TOOL --ir "$SCRIPT_DIR/case3_old.ll" "$SCRIPT_DIR/case3_new.ll" \
    || true

echo ""
echo "=== Saving JSON outputs ==="
for case in 1 2 3; do
    $TOOL --ir --format json \
        "$SCRIPT_DIR/case${case}_old.ll" \
        "$SCRIPT_DIR/case${case}_new.ll" \
        -o "$SCRIPT_DIR/case${case}_output.json" \
        || true
    echo "  case${case}: saved to case${case}_output.json"
done

echo ""
echo "=== Saving DOT CFG diffs ==="
for case in 1 2 3; do
    $TOOL --ir \
        "$SCRIPT_DIR/case${case}_old.ll" \
        "$SCRIPT_DIR/case${case}_new.ll" \
        --dot "$SCRIPT_DIR/case${case}_cfg/" \
        || true
    echo "  case${case}: dot files in case${case}_cfg/"
done

echo ""
echo "Done. To render a CFG graph:"
echo "  dot -Tpng examples/real_commits/case3_cfg/clamp.dot -o clamp.png"

echo ""
echo "=== Compiling IR for cases 4-7 ==="
for case in 4 5 6 7; do
    clang -O2 -S -emit-llvm -fno-discard-value-names \
        "$SCRIPT_DIR/case${case}_old.c" -o "$SCRIPT_DIR/case${case}_old.ll"
    clang -O2 -S -emit-llvm -fno-discard-value-names \
        "$SCRIPT_DIR/case${case}_new.c" -o "$SCRIPT_DIR/case${case}_new.ll"
    echo "  case${case}: IR generated"
done

echo ""
echo "=== Case 4: Loop unroll gained (fixed trip count) ==="
$TOOL --ir "$SCRIPT_DIR/case4_old.ll" "$SCRIPT_DIR/case4_new.ll" \
    || true

echo ""
echo "=== Case 5: Redundant store eliminated ==="
$TOOL --ir "$SCRIPT_DIR/case5_old.ll" "$SCRIPT_DIR/case5_new.ll" \
    || true

echo ""
echo "=== Case 6: Extra load from new struct field ==="
$TOOL --ir "$SCRIPT_DIR/case6_old.ll" "$SCRIPT_DIR/case6_new.ll" \
    || true

echo ""
echo "=== Case 7: Serial dependency chain lengthened ==="
$TOOL --ir "$SCRIPT_DIR/case7_old.ll" "$SCRIPT_DIR/case7_new.ll" \
    || true

echo ""
echo "=== Saving JSON outputs for cases 4-7 ==="
for case in 4 5 6 7; do
    $TOOL --ir --format json \
        "$SCRIPT_DIR/case${case}_old.ll" \
        "$SCRIPT_DIR/case${case}_new.ll" \
        -o "$SCRIPT_DIR/case${case}_output.json" \
        || true
    echo "  case${case}: saved to case${case}_output.json"
done

echo ""
echo "=== Saving DOT CFG diffs for cases 4-7 ==="
for case in 4 5 6 7; do
    $TOOL --ir \
        "$SCRIPT_DIR/case${case}_old.ll" \
        "$SCRIPT_DIR/case${case}_new.ll" \
        --dot "$SCRIPT_DIR/case${case}_cfg/" \
        || true
    echo "  case${case}: dot files in case${case}_cfg/"
done

echo ""
echo "All 7 cases complete."
