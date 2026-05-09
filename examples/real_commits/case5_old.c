/* BEFORE: first store is dead - overwritten before any read */
void init(int *p, int x) {
    *p = 0;       /* dead store - immediately overwritten */
    *p = x;
}
