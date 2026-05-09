/* AFTER: chained operations - intentionally serial critical path */
int hash(int a, int b, int c) {
    int x = a * 2654435761;
    int y = (x + b) * 2246822519;
    int z = (y + c) * 3266489917;
    return x ^ y ^ z;
}
