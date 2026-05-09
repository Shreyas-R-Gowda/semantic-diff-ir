"""Unit tests for semantic change classifiers."""
import pytest
from ..classify.base import ChangeKind
from ..classify.control_flow import CFClassifier
from ..classify.memory import MemClassifier
from ..classify.optimizations import OptClassifier
from ..diff.engine import BlockDiff, FunctionDiff, LoopDiff
from ..parser.types import LoopInfo


def _make_fd(**kwargs) -> FunctionDiff:
    defaults = dict(
        old_name="f", new_name="f",
        match_confidence=1.0, status="modified",
        old_instr_count=10, new_instr_count=10,
        old_block_count=2,  new_block_count=2,
        old_edge_count=2,   new_edge_count=2,
        old_critical_path=5, new_critical_path=5,
        old_mem_deps=0, new_mem_deps=0,
        old_calls=[], new_calls=[],
        old_histogram={}, new_histogram={},
    )
    defaults.update(kwargs)
    return FunctionDiff(**defaults)


# ── OptClassifier ─────────────────────────────────────────────────────────────

def test_vectorize_gained():
    old_loop = LoopInfo(header="loop", body={"loop"}, back_edges=[], vector_width=0)
    new_loop = LoopInfo(header="loop", body={"loop"}, back_edges=[], vector_width=4)
    ld = LoopDiff(header="loop", old_loop=old_loop, new_loop=new_loop,
                  vector_changed=True)
    fd = _make_fd(loop_diffs=[ld])
    report = OptClassifier().classify(fd)
    kinds = {c.kind for c in report.changes}
    assert ChangeKind.VECTORIZE_GAINED in kinds


def test_vectorize_lost():
    old_loop = LoopInfo(header="loop", body={"loop"}, back_edges=[], vector_width=8)
    new_loop = LoopInfo(header="loop", body={"loop"}, back_edges=[], vector_width=0)
    ld = LoopDiff(header="loop", old_loop=old_loop, new_loop=new_loop,
                  vector_changed=True)
    fd = _make_fd(loop_diffs=[ld])
    report = OptClassifier().classify(fd)
    kinds = {c.kind for c in report.changes}
    assert ChangeKind.VECTORIZE_LOST in kinds


def test_unroll_gained():
    old_loop = LoopInfo(header="loop", body={"loop"}, back_edges=[], unroll_factor=None)
    new_loop = LoopInfo(header="loop", body={"loop"}, back_edges=[], unroll_factor=4)
    ld = LoopDiff(header="loop", old_loop=old_loop, new_loop=new_loop,
                  unroll_changed=True)
    fd = _make_fd(loop_diffs=[ld])
    report = OptClassifier().classify(fd)
    kinds = {c.kind for c in report.changes}
    assert ChangeKind.LOOP_UNROLL_GAINED in kinds


def test_inlining_detected():
    fd = _make_fd(old_calls=["helper"], new_calls=[])
    report = OptClassifier().classify(fd)
    kinds = {c.kind for c in report.changes}
    assert ChangeKind.INLINING_ADDED in kinds


def test_dead_code_eliminated():
    removed_bd = BlockDiff(old_label="dead", new_label=None, status="removed")
    fd = _make_fd(
        old_instr_count=20, new_instr_count=15,
        block_diffs=[removed_bd],
    )
    report = OptClassifier().classify(fd)
    kinds = {c.kind for c in report.changes}
    assert ChangeKind.DEAD_CODE_ELIMINATED in kinds


# ── CFClassifier ──────────────────────────────────────────────────────────────

def test_branch_added():
    fd = _make_fd(
        old_histogram={"br": 1},
        new_histogram={"br": 3},
    )
    report = CFClassifier().classify(fd)
    kinds = {c.kind for c in report.changes}
    assert ChangeKind.BRANCH_ADDED in kinds


def test_branch_removed():
    fd = _make_fd(
        old_histogram={"br": 4},
        new_histogram={"br": 1},
    )
    report = CFClassifier().classify(fd)
    kinds = {c.kind for c in report.changes}
    assert ChangeKind.BRANCH_REMOVED in kinds


def test_cfg_complexity_up():
    fd = _make_fd(
        old_edge_count=5, new_edge_count=10,
        old_block_count=4, new_block_count=8,
    )
    report = CFClassifier().classify(fd)
    kinds = {c.kind for c in report.changes}
    assert ChangeKind.CFG_COMPLEXITY_UP in kinds


def test_instr_count_up():
    fd = _make_fd(old_instr_count=10, new_instr_count=20)
    report = CFClassifier().classify(fd)
    kinds = {c.kind for c in report.changes}
    assert ChangeKind.INSTR_COUNT_UP in kinds


def test_critical_path_longer():
    fd = _make_fd(old_critical_path=5, new_critical_path=15)
    report = CFClassifier().classify(fd)
    kinds = {c.kind for c in report.changes}
    assert ChangeKind.CRITICAL_PATH_LONGER in kinds


# ── MemClassifier ─────────────────────────────────────────────────────────────

def test_load_count_changed():
    fd = _make_fd(
        old_histogram={"load": 2},
        new_histogram={"load": 8},
    )
    report = MemClassifier().classify(fd)
    kinds = {c.kind for c in report.changes}
    assert ChangeKind.LOAD_COUNT_CHANGED in kinds


def test_store_count_changed():
    fd = _make_fd(
        old_histogram={"store": 5},
        new_histogram={"store": 1},
    )
    report = MemClassifier().classify(fd)
    kinds = {c.kind for c in report.changes}
    assert ChangeKind.STORE_COUNT_CHANGED in kinds


def test_alloca_changed():
    fd = _make_fd(
        old_histogram={"alloca": 0},
        new_histogram={"alloca": 3},
    )
    report = MemClassifier().classify(fd)
    kinds = {c.kind for c in report.changes}
    assert ChangeKind.ALLOCA_CHANGED in kinds


def test_mem_deps_changed():
    fd = _make_fd(old_mem_deps=1, new_mem_deps=8)
    report = MemClassifier().classify(fd)
    kinds = {c.kind for c in report.changes}
    assert ChangeKind.MEM_DEP_CHANGED in kinds


def test_no_false_positives_on_unchanged():
    fd = _make_fd(
        status="unchanged",
        old_histogram={"br": 2, "load": 3, "store": 2},
        new_histogram={"br": 2, "load": 3, "store": 2},
    )
    for clf in [OptClassifier(), CFClassifier(), MemClassifier()]:
        report = clf.classify(fd)
        # unchanged function with same histograms should produce no changes
        assert not report.has_changes, f"{clf.__class__.__name__} produced false positive"
