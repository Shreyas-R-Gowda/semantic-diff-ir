/* AFTER: loop fully unrolled - helper small enough to inline */
static int sum4(const int *a) {
    return a[0] + a[1] + a[2] + a[3];
}

int compute(const int *a, const int *b) {
    return sum4(a) + sum4(b);
}
