; Case 3 OLD: diamond CFG with explicit branches (if/else clamp)
; Models: SimplifyCFG - diamond CFG -> select instruction
target datalayout = "e-m:o-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-n32:64-S128-Fn32"
target triple = "arm64-apple-macosx26.0.0"

define i32 @clamp(i32 %x, i32 %lo, i32 %hi) {
entry:
  %cmp.lo = icmp slt i32 %x, %lo
  br i1 %cmp.lo, label %ret.lo, label %check.hi

ret.lo:
  br label %exit

check.hi:
  %cmp.hi = icmp sgt i32 %x, %hi
  br i1 %cmp.hi, label %ret.hi, label %ret.x

ret.hi:
  br label %exit

ret.x:
  br label %exit

exit:
  %result = phi i32 [ %lo, %ret.lo ], [ %hi, %ret.hi ], [ %x, %ret.x ]
  ret i32 %result
}
