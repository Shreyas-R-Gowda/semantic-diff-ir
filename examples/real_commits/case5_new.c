/* AFTER: dead store removed - only the meaningful write remains */
void init(int *p, int x) {
    *p = x;
}
