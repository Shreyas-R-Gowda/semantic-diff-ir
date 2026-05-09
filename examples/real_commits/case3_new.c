/* AFTER: branchless using ternary - compiler emits select instructions */
int clamp(int x, int lo, int hi) {
    x = x < lo ? lo : x;
    x = x > hi ? hi : x;
    return x;
}
