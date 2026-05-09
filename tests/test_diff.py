"""Unit tests for diff engine and function matcher."""
import pytest
from ..parser.parser import IRParser
from ..compiler.normalizer import IRNormalizer
from ..diff.engine import DiffEngine
from ..diff.matcher import FunctionMatcher

_OLD_IR = """\
define i32 @sum(i32* %arr, i32 %n) {
entry:
  br label %loop
loop:
  %i   = phi i32 [ 0, %entry ], [ %i.next, %loop ]
  %acc = phi i32 [ 0, %entry ], [ %acc.next, %loop ]
  %ptr = getelementptr i32, i32* %arr, i32 %i
  %val = load i32, i32* %ptr
  %acc.next = add i32 %acc, %val
  %i.next   = add i32 %i, 1
  %cond = icmp slt i32 %i.next, %n
  br i1 %cond, label %loop, label %exit
exit:
  ret i32 %acc.next
}

define i32 @helper(i32 %x) {
entry:
  %r = mul i32 %x, %x
  ret i32 %r
}
"""

_NEW_IR = """\
define i32 @sum(i32* %arr, i32 %n) {
entry:
  %cmp = icmp sle i32 %n, 0
  br i1 %cmp, label %early_exit, label %loop
early_exit:
  ret i32 0
loop:
  %i   = phi i32 [ 0, %entry ], [ %i.next, %loop ]
  %acc = phi i32 [ 0, %entry ], [ %acc.next, %loop ]
  %ptr = getelementptr i32, i32* %arr, i32 %i
  %val = load i32, i32* %ptr
  %acc.next = add i32 %acc, %val
  %i.next   = add i32 %i, 1
  %cond = icmp slt i32 %i.next, %n
  br i1 %cond, label %loop, label %exit
exit:
  ret i32 %acc.next
}

define i32 @helper(i32 %x) {
entry:
  %r = mul i32 %x, %x
  ret i32 %r
}
"""


def _parse(ir):
    n = IRNormalizer()
    p = IRParser()
    return p.parse(n.normalize(ir), "test")


def test_unchanged_function_detected():
    old_mod = _parse(_OLD_IR)
    new_mod = _parse(_NEW_IR)
    result  = DiffEngine().diff(old_mod, new_mod)
    helper_diff = next(
        (fd for fd in result.function_diffs if fd.old_name == "helper"), None
    )
    assert helper_diff is not None
    assert helper_diff.status == "unchanged"


def test_modified_function_detected():
    old_mod = _parse(_OLD_IR)
    new_mod = _parse(_NEW_IR)
    result  = DiffEngine().diff(old_mod, new_mod)
    sum_diff = next(
        (fd for fd in result.function_diffs if fd.old_name == "sum"), None
    )
    assert sum_diff is not None
    assert sum_diff.status == "modified"


def test_added_block_reported():
    old_mod = _parse(_OLD_IR)
    new_mod = _parse(_NEW_IR)
    result  = DiffEngine().diff(old_mod, new_mod)
    sum_diff = next(fd for fd in result.function_diffs if fd.old_name == "sum")
    added_blocks = [bd for bd in sum_diff.block_diffs if bd.status == "added"]
    assert len(added_blocks) >= 1


def test_instr_delta_positive():
    old_mod = _parse(_OLD_IR)
    new_mod = _parse(_NEW_IR)
    result  = DiffEngine().diff(old_mod, new_mod)
    sum_diff = next(fd for fd in result.function_diffs if fd.old_name == "sum")
    assert sum_diff.instr_delta > 0


def test_function_matcher_exact():
    old_mod = _parse(_OLD_IR)
    new_mod = _parse(_NEW_IR)
    matches, added, removed = FunctionMatcher().match(old_mod, new_mod)
    exact = [m for m in matches if m.reason == "exact"]
    names = {m.old_name for m in exact}
    assert "sum" in names
    assert "helper" in names


def test_diff_preserves_match_reason():
    renamed = _OLD_IR.replace("@helper", "@helper_renamed")
    old_mod = _parse(_OLD_IR)
    new_mod = _parse(renamed)
    result = DiffEngine().diff(old_mod, new_mod)
    helper_diff = next(
        fd for fd in result.function_diffs if fd.old_name == "helper"
    )
    assert helper_diff.new_name == "helper_renamed"
    assert helper_diff.match_reason in {"histogram", "body", "signature"}


def test_module_diff_changed_functions():
    old_mod = _parse(_OLD_IR)
    new_mod = _parse(_NEW_IR)
    result  = DiffEngine().diff(old_mod, new_mod)
    changed = result.changed_functions
    assert any(fd.old_name == "sum" for fd in changed)
    assert not any(fd.old_name == "helper" for fd in changed)


def test_added_function():
    extra_ir = _NEW_IR + """
define i32 @new_func(i32 %x) {
entry:
  ret i32 %x
}
"""
    old_mod = _parse(_OLD_IR)
    new_mod = _parse(extra_ir)
    result  = DiffEngine().diff(old_mod, new_mod)
    added = [fd for fd in result.function_diffs if fd.status == "added"]
    assert any(fd.new_name == "new_func" for fd in added)


def test_removed_function():
    old_extra = _OLD_IR + """
define i32 @to_remove(i32 %x) {
entry:
  ret i32 %x
}
"""
    old_mod = _parse(old_extra)
    new_mod = _parse(_NEW_IR)
    result  = DiffEngine().diff(old_mod, new_mod)
    removed = [fd for fd in result.function_diffs if fd.status == "removed"]
    assert any(fd.old_name == "to_remove" for fd in removed)
