/* AFTER: also reads flags field for a new guard check */
typedef struct { int id; int flags; int value; } Row;

int process(const Row *r) {
    if (r->flags == 0) return 0;
    return r->value * 2;
}
