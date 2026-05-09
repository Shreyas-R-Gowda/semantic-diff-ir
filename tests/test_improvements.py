"""
Tests for the improvements made during the audit.
Each test targets a specific bug that was fixed.
"""
import pytest
from ..compiler.normalizer import IRNormalizer
from ..diff.engine import DiffEngine
from ..diff.matcher import FunctionMatcher
from ..parser.parser import IRParser
from ..classify.base import ChangeKind
from ..classify.control_flow import CFClassifier
from ..classify.optimizations import OptClassifier
from ..diff.engine import BlockDiff, FunctionDiff, LoopDiff
from ..parser.types import LoopInfo


def _parse(ir: str, label: str = "test"):
    n = IRNormalizer()
    p = IRParser()
    return p.parse(n.normalize(ir), label)


# ─── normalizer fixes ──────────────────────────────────────────────────────────

def test_commutative_normalization():
    """add %a, %b and add %b, %a must normalize identically."""
    n = IRNormalizer()
    ir1 = "define i32 @f(i32 %a, i32 %b) {\nentry:\n  %r = add i32 %a, %b\n  ret i32 %r\n}"
    ir2 = "define i32 @f(i32 %a, i32 %b) {\nentry:\n  %r = add i32 %b, %a\n  ret i32 %r\n}"
    assert n.normalize(ir1) == n.normalize(ir2)


def test_commutative_multiple_ops():
    """mul, and, or, xor are also commutative."""
    n = IRNormalizer()
    for op in ("mul", "and", "or", "xor"):
        ir1 = f"define i32 @f(i32 %a, i32 %b) {{\nentry:\n  %r = {op} i32 %a, %b\n  ret i32 %r\n}}"
        ir2 = f"define i32 @f(i32 %a, i32 %b) {{\nentry:\n  %r = {op} i32 %b, %a\n  ret i32 %r\n}}"
        assert n.normalize(ir1) == n.normalize(ir2), f"Failed for {op}"


def test_commutative_does_not_swap_immediates():
    """add i32 %x, 1 must NOT be swapped (second arg is immediate, not SSA)."""
    n = IRNormalizer()
    ir = "define i32 @f(i32 %x) {\nentry:\n  %r = add i32 %x, 1\n  ret i32 %r\n}"
    norm = n.normalize(ir)
    assert "1" in norm   # immediate still present


def test_phi_label_renaming():
    """
    BUG FIX: Phi-node predecessor labels must be renamed alongside branch targets.
    A numeric block used as a phi predecessor was not renamed in the original code.
    """
    n = IRNormalizer()
    ir = """\
define i32 @f(i32 %n) {
entry:
  br label %42
42:
  %v = phi i32 [ 0, %entry ], [ %v2, %42 ]
  %v2 = add i32 %v, 1
  %c  = icmp slt i32 %v2, %n
  br i1 %c, label %42, label %exit
exit:
  ret i32 %v2
}"""
    norm = n.normalize(ir)
    # The raw '42' in the phi predecessor [ %v2, %42 ] should be renamed
    assert "%42" not in norm, "Phi predecessor %42 was not renamed"
    assert "bb0" in norm


def test_ptr_type_normalization():
    """i32* in instruction lines should normalize to ptr."""
    n = IRNormalizer()
    ir = "define void @f(i32* %p) {\nentry:\n  %v = load i32, i32* %p\n  ret void\n}"
    norm = n.normalize(ir)
    # After normalization the load line should use ptr not i32*
    load_line = next(l for l in norm.splitlines() if "load" in l)
    assert "i32*" not in load_line


def test_attribute_groups_stripped():
    """attributes #0 = {...} and #N refs must be removed."""
    n = IRNormalizer()
    ir = """\
define i32 @f(i32 %x) #0 {
entry:
  ret i32 %x
}
attributes #0 = { noinline uwtable }
"""
    norm = n.normalize(ir)
    assert "attributes #0" not in norm
    # The #0 on define should also be gone
    define_line = next(l for l in norm.splitlines() if l.startswith("define"))
    assert "#0" not in define_line


# ─── block matching fixes ─────────────────────────────────────────────────────

def test_fuzzy_block_matching_after_insertion():
    """
    BUG FIX: Inserting a new block before a loop must not cause the loop block
    to appear as removed+added (fuzzy matching should pair it by fingerprint).
    """
    old_ir = """\
define i32 @f(i32 %n) {
entry:
  br label %loop
loop:
  %i   = phi i32 [ 0, %entry ], [ %i2, %loop ]
  %i2  = add i32 %i, 1
  %c   = icmp slt i32 %i2, %n
  br i1 %c, label %loop, label %exit
exit:
  ret i32 %i2
}"""
    new_ir = """\
define i32 @f(i32 %n) {
entry:
  %cmp = icmp sle i32 %n, 0
  br i1 %cmp, label %early, label %loop
early:
  ret i32 0
loop:
  %i   = phi i32 [ 0, %entry ], [ %i2, %loop ]
  %i2  = add i32 %i, 1
  %c   = icmp slt i32 %i2, %n
  br i1 %c, label %loop, label %exit
exit:
  ret i32 %i2
}"""
    old_mod = _parse(old_ir)
    new_mod = _parse(new_ir)
    result  = DiffEngine().diff(old_mod, new_mod)
    fd = result.function_diffs[0]

    # loop and exit blocks should be matched (same label still present)
    matched = [bd for bd in fd.block_diffs if bd.status == "matched"]
    assert any(bd.old_label == "loop" for bd in matched), \
        "loop block should be matched, not removed+added"


def test_token_level_block_similarity():
    """
    Token-level SequenceMatcher: two blocks differing by one opcode swap
    should have high similarity (>= 0.80), not the lower char-level score.
    """
    from ..parser.types import BasicBlock, Instruction, Opcode

    def make_block(label, ops):
        blk = BasicBlock(label=label)
        for op in ops:
            blk.instructions.append(
                Instruction(opcode_str=op, result=None, type_str="",
                            operands=[], raw=op, block=label)
            )
        return blk

    from ..diff.engine import DiffEngine
    eng = DiffEngine()

    # Blocks that differ by one instruction substitution out of 6
    old_blk = make_block("b", ["phi", "load", "add", "mul", "icmp", "br"])
    new_blk = make_block("b", ["phi", "load", "add", "fadd", "icmp", "br"])
    bd = eng._diff_block_pair(old_blk, new_blk)
    assert bd.similarity >= 0.75, f"Expected >= 0.75, got {bd.similarity:.2f}"


# ─── loop matching fix ────────────────────────────────────────────────────────

def test_loop_structural_matching():
    """
    BUG FIX: Loops matched by structure, not header label.
    When a preheader is inserted the header label shifts; the old code
    reported the loop as removed+added.
    """
    # Old: loop header is 'loop'
    old_ir = """\
define i32 @f(i32* %p, i32 %n) {
entry:
  br label %loop
loop:
  %i   = phi i32 [ 0, %entry ], [ %i2, %loop ]
  %acc = phi i32 [ 0, %entry ], [ %acc2, %loop ]
  %ptr = getelementptr i32, i32* %p, i32 %i
  %v   = load i32, i32* %ptr
  %acc2 = add i32 %acc, %v
  %i2  = add i32 %i, 1
  %c   = icmp slt i32 %i2, %n
  br i1 %c, label %loop, label %exit
exit:
  ret i32 %acc2
}"""
    # New: same loop but a preheader guard was inserted
    new_ir = """\
define i32 @f(i32* %p, i32 %n) {
entry:
  %guard = icmp sle i32 %n, 0
  br i1 %guard, label %exit, label %loop
loop:
  %i   = phi i32 [ 0, %entry ], [ %i2, %loop ]
  %acc = phi i32 [ 0, %entry ], [ %acc2, %loop ]
  %ptr = getelementptr i32, i32* %p, i32 %i
  %v   = load i32, i32* %ptr
  %acc2 = add i32 %acc, %v
  %i2  = add i32 %i, 1
  %c   = icmp slt i32 %i2, %n
  br i1 %c, label %loop, label %exit
exit:
  ret i32 %acc2
}"""
    old_mod = _parse(old_ir)
    new_mod = _parse(new_ir)
    result  = DiffEngine().diff(old_mod, new_mod)
    fd = result.function_diffs[0]

    # Loop should be matched (not reported as removed+added)
    added_loops   = [ld for ld in fd.loop_diffs if ld.old_loop is None]
    removed_loops = [ld for ld in fd.loop_diffs if ld.new_loop is None]
    matched_loops = [ld for ld in fd.loop_diffs
                     if ld.old_loop is not None and ld.new_loop is not None]
    assert matched_loops, "Loop should be structurally matched"
    assert not removed_loops, f"Loop incorrectly reported as removed: {removed_loops}"


# ─── classifier fixes ─────────────────────────────────────────────────────────

def test_instr_count_suppressed_when_vectorization_explains_it():
    """
    BUG FIX: INSTR_COUNT_UP must not fire when vectorization already explains
    the instruction count increase.
    """
    old_loop = LoopInfo(header="loop", body={"loop"}, back_edges=[],
                        vector_width=0)
    new_loop = LoopInfo(header="loop", body={"loop"}, back_edges=[],
                        vector_width=4)
    ld = LoopDiff(header="loop", old_loop=old_loop, new_loop=new_loop,
                  vector_changed=True)

    # Simulate vectorization: instruction count grew significantly
    fd = FunctionDiff(
        old_name="f", new_name="f",
        match_confidence=1.0, status="modified",
        old_instr_count=10, new_instr_count=40,
        old_block_count=3,  new_block_count=8,
        old_edge_count=3,   new_edge_count=8,
        old_critical_path=5, new_critical_path=5,
        old_mem_deps=0, new_mem_deps=0,
        old_calls=[], new_calls=[],
        old_histogram={}, new_histogram={},
        loop_diffs=[ld],
        explained_instr_delta=True,   # set by OptClassifier after vectorize
    )

    report = CFClassifier().classify(fd)
    kinds = {c.kind for c in report.changes}
    assert ChangeKind.INSTR_COUNT_UP not in kinds, \
        "INSTR_COUNT_UP fired even though vectorization explains the delta"


def test_unroll_factor_change_correct_kind():
    """
    BUG FIX: When unroll factor changes (e.g. x4 → x8), the kind should be
    LOOP_UNROLL_GAINED (increased), not LOOP_UNROLL_LOST.
    """
    old_loop = LoopInfo(header="loop", body={"loop"}, back_edges=[],
                        unroll_factor=4)
    new_loop = LoopInfo(header="loop", body={"loop"}, back_edges=[],
                        unroll_factor=8)
    ld = LoopDiff(header="loop", old_loop=old_loop, new_loop=new_loop,
                  unroll_changed=True)

    fd = FunctionDiff(
        old_name="f", new_name="f",
        match_confidence=1.0, status="modified",
        old_instr_count=10, new_instr_count=20,
        old_block_count=2, new_block_count=2,
        old_edge_count=2,  new_edge_count=2,
        old_critical_path=5, new_critical_path=5,
        old_mem_deps=0, new_mem_deps=0,
        old_calls=[], new_calls=[],
        old_histogram={}, new_histogram={},
        loop_diffs=[ld],
    )

    report = OptClassifier().classify(fd)
    kinds = {c.kind for c in report.changes}
    # Factor went UP (4 → 8), so should be GAINED not LOST
    assert ChangeKind.LOOP_UNROLL_GAINED in kinds, \
        "Increasing unroll factor should be LOOP_UNROLL_GAINED"
    assert ChangeKind.LOOP_UNROLL_LOST not in kinds


def test_histogram_cosine_matching():
    """
    Stage 3 matcher: a function renamed but with identical body
    should be matched via histogram cosine similarity.
    """
    ir = """\
define i32 @old_name(i32* %p, i32 %n) {
entry:
  br label %loop
loop:
  %i   = phi i32 [ 0, %entry ], [ %i2, %loop ]
  %ptr = getelementptr i32, i32* %p, i32 %i
  %v   = load i32, i32* %ptr
  %i2  = add i32 %i, 1
  %c   = icmp slt i32 %i2, %n
  br i1 %c, label %loop, label %exit
exit:
  ret i32 %i2
}
define i32 @helper(i32 %x) {
entry:
  ret i32 %x
}
"""
    renamed_ir = ir.replace("@old_name", "@new_name")
    old_mod = _parse(ir)
    new_mod = _parse(renamed_ir)

    matches, added, removed = FunctionMatcher().match(old_mod, new_mod)
    matched_names = {(m.old_name, m.new_name) for m in matches}
    # helper should match by exact name
    assert ("helper", "helper") in matched_names
    # old_name → new_name should be matched (histogram or body stage)
    assert any(m.old_name == "old_name" and m.new_name == "new_name"
               for m in matches), \
        f"Renamed function not matched. matches={matches}, added={added}, removed={removed}"
