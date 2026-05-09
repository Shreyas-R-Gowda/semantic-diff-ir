"""Unit tests for IR parser."""
import pytest
from ..parser.parser import IRParser
from ..parser.types import Opcode

_SIMPLE_IR = """\
define i32 @add(i32 %a, i32 %b) {
entry:
  %sum = add i32 %a, %b
  ret i32 %sum
}
"""

_LOOP_IR = """\
define i32 @sum(i32* %arr, i32 %n) {
entry:
  br label %loop

loop:
  %i = phi i32 [ 0, %entry ], [ %i.next, %loop ]
  %acc = phi i32 [ 0, %entry ], [ %acc.next, %loop ]
  %ptr = getelementptr i32, i32* %arr, i32 %i
  %val = load i32, i32* %ptr
  %acc.next = add i32 %acc, %val
  %i.next = add i32 %i, 1
  %cond = icmp slt i32 %i.next, %n
  br i1 %cond, label %loop, label %exit

exit:
  ret i32 %acc.next
}
"""

_MULTI_FUNC_IR = """\
declare i32 @printf(i8*, ...)

define i32 @foo(i32 %x) {
entry:
  %r = mul i32 %x, %x
  ret i32 %r
}

define void @bar() {
entry:
  ret void
}
"""


def test_parse_simple_function():
    mod = IRParser().parse(_SIMPLE_IR, "test")
    assert "add" in mod.functions
    f = mod.functions["add"]
    assert not f.is_declaration
    assert f.return_type == "i32"
    assert len(f.params) == 2


def test_parse_instructions():
    mod = IRParser().parse(_SIMPLE_IR, "test")
    f = mod.functions["add"]
    instrs = list(f.all_instructions())
    opcodes = [i.opcode for i in instrs]
    assert Opcode.ADD in opcodes
    assert Opcode.RET in opcodes


def test_parse_loop_ir():
    mod = IRParser().parse(_LOOP_IR, "test")
    f = mod.functions["sum"]
    assert "loop" in f.basic_blocks
    assert "exit" in f.basic_blocks
    loop_blk = f.basic_blocks["loop"]
    phi_count = sum(1 for i in loop_blk.instructions if i.opcode == Opcode.PHI)
    assert phi_count >= 2


def test_cfg_wiring():
    mod = IRParser().parse(_LOOP_IR, "test")
    f = mod.functions["sum"]
    loop_blk = f.basic_blocks["loop"]
    assert "exit" in loop_blk.successors or "loop" in loop_blk.successors


def test_declaration_parsed():
    mod = IRParser().parse(_MULTI_FUNC_IR, "test")
    assert "printf" in mod.functions
    assert mod.functions["printf"].is_declaration


def test_defined_functions():
    mod = IRParser().parse(_MULTI_FUNC_IR, "test")
    defs = mod.defined_functions()
    assert "foo" in defs
    assert "bar" in defs
    assert "printf" not in defs


def test_opcode_histogram():
    mod = IRParser().parse(_LOOP_IR, "test")
    hist = mod.functions["sum"].opcode_histogram()
    assert hist.get("load", 0) >= 1
    assert hist.get("icmp", 0) >= 1


def test_total_instructions():
    mod = IRParser().parse(_SIMPLE_IR, "test")
    f = mod.functions["add"]
    assert f.total_instructions() == 2   # add + ret


def test_calls_list():
    ir = """\
define void @caller() {
entry:
  call void @callee()
  ret void
}
"""
    mod = IRParser().parse(ir, "test")
    assert "callee" in mod.functions["caller"].calls()


def test_calls_list_allows_dollar_names():
    ir = """\
define void @caller() {
entry:
  call void @ns$callee()
  ret void
}
"""
    mod = IRParser().parse(ir, "test")
    assert "ns$callee" in mod.functions["caller"].calls()
