"""Unit tests for IR normalizer."""
import pytest
from ..compiler.normalizer import IRNormalizer

_IR_WITH_DEBUG = """\
source_filename = "/tmp/foo.c"
define i32 @add(i32 %0, i32 %1) !dbg !5 {
  %3 = add i32 %0, %1, !dbg !6, !tbaa !7
  ret i32 %3, !dbg !8
}
!5 = distinct !DISubprogram(name: "add")
!6 = !DILocation(line: 2)
!7 = !{!"tbaa"}
!8 = !DILocation(line: 3)
"""

_IR_UNNAMED = """\
define i32 @f(i32 %0) {
entry:
  %1 = add i32 %0, 1
  %2 = mul i32 %1, 2
  ret i32 %2
}
"""

_IR_UNNAMED2 = """\
define i32 @f(i32 %0) {
entry:
  %1 = add i32 %0, 1
  %2 = mul i32 %1, 2
  %3 = sub i32 %2, 1
  ret i32 %3
}
"""


def test_strip_debug_metadata():
    norm = IRNormalizer().normalize(_IR_WITH_DEBUG)
    assert "!dbg" not in norm
    assert "!DISubprogram" not in norm
    assert "!DILocation" not in norm
    assert "source_filename" not in norm


def test_strip_tbaa():
    norm = IRNormalizer().normalize(_IR_WITH_DEBUG)
    assert "!tbaa" not in norm


def test_unnamed_renaming_stable():
    n = IRNormalizer()
    norm1 = n.normalize(_IR_UNNAMED)
    norm2 = n.normalize(_IR_UNNAMED2)
    # Both have %v0 as the first renamed value
    assert "%v0" in norm1
    assert "%v0" in norm2


def test_unnamed_renaming_no_shift():
    n = IRNormalizer()
    # Adding an instruction in the middle should NOT shift names of later instrs
    # (they get new stable names, but common prefix stays the same)
    norm1 = n.normalize(_IR_UNNAMED)
    norm2 = n.normalize(_IR_UNNAMED2)
    # Both start with add → %v0
    lines1 = [l for l in norm1.splitlines() if "add" in l]
    lines2 = [l for l in norm2.splitlines() if "add" in l]
    assert lines1 and lines2
    # Same name for the add result in both
    assert lines1[0].split("=")[0].strip() == lines2[0].split("=")[0].strip()


def test_no_blank_line_explosion():
    ir = "define void @f() {\nentry:\n  ret void\n}\n\n\n\n\n"
    norm = IRNormalizer().normalize(ir)
    assert "\n\n\n" not in norm


def test_module_noise_removed():
    ir = """\
; ModuleID = 'foo.c'
source_filename = "foo.c"
!llvm.ident = !{!0}
!llvm.module.flags = !{!1}
define void @f() {
entry:
  ret void
}
"""
    norm = IRNormalizer().normalize(ir)
    assert "llvm.ident" not in norm
    assert "llvm.module.flags" not in norm
