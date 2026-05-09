/* new.c — refactored: helper inlined, sum adds early-exit branch */
#include <stddef.h>

int sum_array(const int *arr, int n) {
    if (n <= 0) return 0;   /* early-exit branch added */
    int total = 0;
    for (int i = 0; i < n; i++) {
        total += arr[i];
    }
    return total;
}

int dot_product(const int *a, const int *b, int n) {
    int result = 0;
    for (int i = 0; i < n; i++) {
        result += a[i] * b[i];
    }
    return result;
}

/* helper inlined into compute — no longer a separate function */
int compute(int x, int y) {
    return (x * x + 1) + (y * y + 1);
}
