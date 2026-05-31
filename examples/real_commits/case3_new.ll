; Case 3 NEW: branchless select - SimplifyCFG folds diamond into selects
; Models: SimplifyCFG - diamond CFG -> select instruction
target datalayout = "e-m:o-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-n32:64-S128-Fn32"
target triple = "arm64-apple-macosx26.0.0"

define i32 @clamp(i32 %x, i32 %lo, i32 %hi) {
entry:
  %cmp.lo = icmp slt i32 %x, %lo
  %clamp.lo = select i1 %cmp.lo, i32 %lo, i32 %x
  %cmp.hi = icmp sgt i32 %clamp.lo, %hi
  %result = select i1 %cmp.hi, i32 %hi, i32 %clamp.lo
  ret i32 %result
}
