; Case 1 OLD: scalar loop - aliased pointers prevent vectorization
; Models: LLVM LoopVectorize - __restrict enables clean vector path
target datalayout = "e-m:o-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-n32:64-S128-Fn32"
target triple = "arm64-apple-macosx26.0.0"

define void @scale(ptr %out, ptr %in, float %factor, i32 %n) {
entry:
  %cmp = icmp sgt i32 %n, 0
  br i1 %cmp, label %for.body, label %for.end

for.body:
  %i = phi i64 [ 0, %entry ], [ %i.next, %for.body ]
  %in.ptr = getelementptr float, ptr %in, i64 %i
  %val = load float, ptr %in.ptr, align 4
  %mul = fmul float %val, %factor
  %out.ptr = getelementptr float, ptr %out, i64 %i
  store float %mul, ptr %out.ptr, align 4
  %i.next = add nuw nsw i64 %i, 1
  %n64 = sext i32 %n to i64
  %cond = icmp slt i64 %i.next, %n64
  br i1 %cond, label %for.body, label %for.end

for.end:
  ret void
}
