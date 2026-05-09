/* BEFORE: helper has a loop - too large to inline */
static int sum4(const int *a) {
    int s = 0;
    for (int i = 0; i < 4; i++) s += a[i];
    return s;
}

int compute(const int *a, const int *b) {
    return sum4(a) + sum4(b);
}
