/* BEFORE: independent additions - short critical path */
int hash(int a, int b, int c) {
    int x = a * 2654435761;
    int y = b * 2246822519;
    int z = c * 3266489917;
    return x ^ y ^ z;
}
