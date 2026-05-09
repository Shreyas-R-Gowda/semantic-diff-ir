/* AFTER: __restrict tells compiler pointers never alias - clean vectorization */
void scale(float * __restrict out, float * __restrict in, float factor, int n) {
    for (int i = 0; i < n; i++) {
        out[i] = in[i] * factor;
    }
}
