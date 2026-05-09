/* AFTER: fixed trip count 4 - compiler fully unrolls */
int dot(const int *a, const int *b) {
    int s = 0;
    for (int i = 0; i < 4; i++)
        s += a[i] * b[i];
    return s;
}
