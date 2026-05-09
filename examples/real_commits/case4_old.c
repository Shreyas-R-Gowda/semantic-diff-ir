/* BEFORE: variable trip count - compiler cannot unroll */
int dot(const int *a, const int *b, int n) {
    int s = 0;
    for (int i = 0; i < n; i++)
        s += a[i] * b[i];
    return s;
}
