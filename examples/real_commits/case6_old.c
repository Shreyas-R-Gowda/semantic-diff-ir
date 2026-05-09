/* BEFORE: only reads one field */
typedef struct { int id; int flags; int value; } Row;

int process(const Row *r) {
    return r->value * 2;
}
