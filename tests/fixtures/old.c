/* old.c — baseline: simple loop with load/store, no optimizations */
#include <stddef.h>

int sum_array(const int *arr, int n) {
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

static int helper(int x) {
    return x * x + 1;
}

int compute(int x, int y) {
    return helper(x) + helper(y);
}
