/* BEFORE: pointer aliasing unknown - vectorizer adds runtime check or bails */
void scale(float *out, float *in, float factor, int n) {
    for (int i = 0; i < n; i++) {
        out[i] = in[i] * factor;
    }
}
