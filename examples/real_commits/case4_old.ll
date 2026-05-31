; ModuleID = 'examples/real_commits/case4_old.c'
source_filename = "examples/real_commits/case4_old.c"
target datalayout = "e-m:o-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-n32:64-S128-Fn32"
target triple = "arm64-apple-macosx26.0.0"

; Function Attrs: nofree norecurse nosync nounwind ssp memory(argmem: read) uwtable(sync)
define i32 @dot(ptr noundef readonly captures(none) %a, ptr noundef readonly captures(none) %b, i32 noundef %n) local_unnamed_addr #0 {
entry:
  %cmp7 = icmp sgt i32 %n, 0
  br i1 %cmp7, label %iter.check, label %for.cond.cleanup

iter.check:                                       ; preds = %entry
  %wide.trip.count = zext nneg i32 %n to i64
  %min.iters.check = icmp ult i32 %n, 4
  br i1 %min.iters.check, label %for.body.preheader, label %vector.main.loop.iter.check

for.body.preheader:                               ; preds = %vec.epilog.iter.check, %vec.epilog.middle.block, %iter.check
  %indvars.iv.ph = phi i64 [ 0, %iter.check ], [ %n.vec, %vec.epilog.iter.check ], [ %n.vec25, %vec.epilog.middle.block ]
  %s.08.ph = phi i32 [ 0, %iter.check ], [ %17, %vec.epilog.iter.check ], [ %24, %vec.epilog.middle.block ]
  br label %for.body

vector.main.loop.iter.check:                      ; preds = %iter.check
  %min.iters.check11 = icmp ult i32 %n, 16
  br i1 %min.iters.check11, label %vec.epilog.ph, label %vector.ph

vector.ph:                                        ; preds = %vector.main.loop.iter.check
  %n.vec = and i64 %wide.trip.count, 2147483632
  br label %vector.body

vector.body:                                      ; preds = %vector.body, %vector.ph
  %index = phi i64 [ 0, %vector.ph ], [ %index.next, %vector.body ]
  %vec.phi = phi <4 x i32> [ zeroinitializer, %vector.ph ], [ %12, %vector.body ]
  %vec.phi12 = phi <4 x i32> [ zeroinitializer, %vector.ph ], [ %13, %vector.body ]
  %vec.phi13 = phi <4 x i32> [ zeroinitializer, %vector.ph ], [ %14, %vector.body ]
  %vec.phi14 = phi <4 x i32> [ zeroinitializer, %vector.ph ], [ %15, %vector.body ]
  %0 = getelementptr inbounds nuw i32, ptr %a, i64 %index
  %1 = getelementptr inbounds nuw i8, ptr %0, i64 16
  %2 = getelementptr inbounds nuw i8, ptr %0, i64 32
  %3 = getelementptr inbounds nuw i8, ptr %0, i64 48
  %wide.load = load <4 x i32>, ptr %0, align 4, !tbaa !6
  %wide.load15 = load <4 x i32>, ptr %1, align 4, !tbaa !6
  %wide.load16 = load <4 x i32>, ptr %2, align 4, !tbaa !6
  %wide.load17 = load <4 x i32>, ptr %3, align 4, !tbaa !6
  %4 = getelementptr inbounds nuw i32, ptr %b, i64 %index
  %5 = getelementptr inbounds nuw i8, ptr %4, i64 16
  %6 = getelementptr inbounds nuw i8, ptr %4, i64 32
  %7 = getelementptr inbounds nuw i8, ptr %4, i64 48
  %wide.load18 = load <4 x i32>, ptr %4, align 4, !tbaa !6
  %wide.load19 = load <4 x i32>, ptr %5, align 4, !tbaa !6
  %wide.load20 = load <4 x i32>, ptr %6, align 4, !tbaa !6
  %wide.load21 = load <4 x i32>, ptr %7, align 4, !tbaa !6
  %8 = mul nsw <4 x i32> %wide.load18, %wide.load
  %9 = mul nsw <4 x i32> %wide.load19, %wide.load15
  %10 = mul nsw <4 x i32> %wide.load20, %wide.load16
  %11 = mul nsw <4 x i32> %wide.load21, %wide.load17
  %12 = add <4 x i32> %8, %vec.phi
  %13 = add <4 x i32> %9, %vec.phi12
  %14 = add <4 x i32> %10, %vec.phi13
  %15 = add <4 x i32> %11, %vec.phi14
  %index.next = add nuw i64 %index, 16
  %16 = icmp eq i64 %index.next, %n.vec
  br i1 %16, label %middle.block, label %vector.body, !llvm.loop !10

middle.block:                                     ; preds = %vector.body
  %bin.rdx = add <4 x i32> %13, %12
  %bin.rdx22 = add <4 x i32> %14, %bin.rdx
  %bin.rdx23 = add <4 x i32> %15, %bin.rdx22
  %17 = tail call i32 @llvm.vector.reduce.add.v4i32(<4 x i32> %bin.rdx23)
  %cmp.n = icmp eq i64 %n.vec, %wide.trip.count
  br i1 %cmp.n, label %for.cond.cleanup, label %vec.epilog.iter.check

vec.epilog.iter.check:                            ; preds = %middle.block
  %n.vec.remaining = and i64 %wide.trip.count, 12
  %min.epilog.iters.check = icmp eq i64 %n.vec.remaining, 0
  br i1 %min.epilog.iters.check, label %for.body.preheader, label %vec.epilog.ph

vec.epilog.ph:                                    ; preds = %vec.epilog.iter.check, %vector.main.loop.iter.check
  %vec.epilog.resume.val = phi i64 [ %n.vec, %vec.epilog.iter.check ], [ 0, %vector.main.loop.iter.check ]
  %bc.merge.rdx = phi i32 [ %17, %vec.epilog.iter.check ], [ 0, %vector.main.loop.iter.check ]
  %n.vec25 = and i64 %wide.trip.count, 2147483644
  %18 = insertelement <4 x i32> <i32 poison, i32 0, i32 0, i32 0>, i32 %bc.merge.rdx, i64 0
  br label %vec.epilog.vector.body

vec.epilog.vector.body:                           ; preds = %vec.epilog.vector.body, %vec.epilog.ph
  %index26 = phi i64 [ %vec.epilog.resume.val, %vec.epilog.ph ], [ %index.next30, %vec.epilog.vector.body ]
  %vec.phi27 = phi <4 x i32> [ %18, %vec.epilog.ph ], [ %22, %vec.epilog.vector.body ]
  %19 = getelementptr inbounds nuw i32, ptr %a, i64 %index26
  %wide.load28 = load <4 x i32>, ptr %19, align 4, !tbaa !6
  %20 = getelementptr inbounds nuw i32, ptr %b, i64 %index26
  %wide.load29 = load <4 x i32>, ptr %20, align 4, !tbaa !6
  %21 = mul nsw <4 x i32> %wide.load29, %wide.load28
  %22 = add <4 x i32> %21, %vec.phi27
  %index.next30 = add nuw i64 %index26, 4
  %23 = icmp eq i64 %index.next30, %n.vec25
  br i1 %23, label %vec.epilog.middle.block, label %vec.epilog.vector.body, !llvm.loop !14

vec.epilog.middle.block:                          ; preds = %vec.epilog.vector.body
  %24 = tail call i32 @llvm.vector.reduce.add.v4i32(<4 x i32> %22)
  %cmp.n31 = icmp eq i64 %n.vec25, %wide.trip.count
  br i1 %cmp.n31, label %for.cond.cleanup, label %for.body.preheader

for.cond.cleanup:                                 ; preds = %for.body, %middle.block, %vec.epilog.middle.block, %entry
  %s.0.lcssa = phi i32 [ 0, %entry ], [ %17, %middle.block ], [ %24, %vec.epilog.middle.block ], [ %add, %for.body ]
  ret i32 %s.0.lcssa

for.body:                                         ; preds = %for.body.preheader, %for.body
  %indvars.iv = phi i64 [ %indvars.iv.next, %for.body ], [ %indvars.iv.ph, %for.body.preheader ]
  %s.08 = phi i32 [ %add, %for.body ], [ %s.08.ph, %for.body.preheader ]
  %arrayidx = getelementptr inbounds nuw i32, ptr %a, i64 %indvars.iv
  %25 = load i32, ptr %arrayidx, align 4, !tbaa !6
  %arrayidx2 = getelementptr inbounds nuw i32, ptr %b, i64 %indvars.iv
  %26 = load i32, ptr %arrayidx2, align 4, !tbaa !6
  %mul = mul nsw i32 %26, %25
  %add = add nsw i32 %mul, %s.08
  %indvars.iv.next = add nuw nsw i64 %indvars.iv, 1
  %exitcond.not = icmp eq i64 %indvars.iv.next, %wide.trip.count
  br i1 %exitcond.not, label %for.cond.cleanup, label %for.body, !llvm.loop !15
}

; Function Attrs: nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare i32 @llvm.vector.reduce.add.v4i32(<4 x i32>) #1

attributes #0 = { nofree norecurse nosync nounwind ssp memory(argmem: read) uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "probe-stack"="__chkstk_darwin" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+bti,+ccdp,+ccidx,+ccpp,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a" }
attributes #1 = { nocallback nofree nosync nounwind speculatable willreturn memory(none) }

!llvm.module.flags = !{!0, !1, !2, !3, !4}
!llvm.ident = !{!5}

!0 = !{i32 2, !"SDK Version", [2 x i32] [i32 26, i32 4]}
!1 = !{i32 1, !"wchar_size", i32 4}
!2 = !{i32 8, !"PIC Level", i32 2}
!3 = !{i32 7, !"uwtable", i32 1}
!4 = !{i32 7, !"frame-pointer", i32 1}
!5 = !{!"Apple clang version 21.0.0 (clang-2100.0.123.102)"}
!6 = !{!7, !7, i64 0}
!7 = !{!"int", !8, i64 0}
!8 = !{!"omnipotent char", !9, i64 0}
!9 = !{!"Simple C/C++ TBAA"}
!10 = distinct !{!10, !11, !12, !13}
!11 = !{!"llvm.loop.mustprogress"}
!12 = !{!"llvm.loop.isvectorized", i32 1}
!13 = !{!"llvm.loop.unroll.runtime.disable"}
!14 = distinct !{!14, !11, !12, !13}
!15 = distinct !{!15, !11, !13, !12}
