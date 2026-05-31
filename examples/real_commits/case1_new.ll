; Case 1 NEW: vectorized loop - __restrict confirms no aliasing, SIMD enabled
; Models: LLVM LoopVectorize - __restrict enables clean vector path
target datalayout = "e-m:o-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-n32:64-S128-Fn32"
target triple = "arm64-apple-macosx26.0.0"

define void @scale(ptr noalias %out, ptr noalias %in, float %factor, i32 %n) {
entry:
  %cmp = icmp sgt i32 %n, 0
  br i1 %cmp, label %vector.ph, label %for.end

vector.ph:
  %n64 = sext i32 %n to i64
  %splatinsert = insertelement <4 x float> poison, float %factor, i32 0
  %splat = shufflevector <4 x float> %splatinsert, <4 x float> poison, <4 x i32> zeroinitializer
  br label %vector.body

vector.body:
  %i.vec = phi i64 [ 0, %vector.ph ], [ %i.vec.next, %vector.body ]
  %in.ptr = getelementptr float, ptr %in, i64 %i.vec
  %val = load <4 x float>, ptr %in.ptr, align 4
  %mul = fmul <4 x float> %val, %splat
  %out.ptr = getelementptr float, ptr %out, i64 %i.vec
  store <4 x float> %mul, ptr %out.ptr, align 4
  %i.vec.next = add nuw nsw i64 %i.vec, 4
  %cond = icmp slt i64 %i.vec.next, %n64
  br i1 %cond, label %vector.body, label %for.end

for.end:
  ret void
}
