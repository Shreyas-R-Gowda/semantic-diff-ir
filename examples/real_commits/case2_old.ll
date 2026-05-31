; ModuleID = 'examples/real_commits/case2_old.c'
source_filename = "examples/real_commits/case2_old.c"
target datalayout = "e-m:o-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-n32:64-S128-Fn32"
target triple = "arm64-apple-macosx26.0.0"

; Function Attrs: nofree norecurse nosync nounwind ssp memory(argmem: read) uwtable(sync)
define i32 @compute(ptr noundef readonly captures(none) %a, ptr noundef readonly captures(none) %b) local_unnamed_addr #0 {
entry:
  br label %for.body.i

for.body.i:                                       ; preds = %for.body.i, %entry
  %indvars.iv.i = phi i64 [ 0, %entry ], [ %indvars.iv.next.i, %for.body.i ]
  %s.04.i = phi i32 [ 0, %entry ], [ %add.i, %for.body.i ]
  %arrayidx.i = getelementptr inbounds nuw i32, ptr %a, i64 %indvars.iv.i
  %0 = load i32, ptr %arrayidx.i, align 4, !tbaa !6
  %add.i = add nsw i32 %0, %s.04.i
  %indvars.iv.next.i = add nuw nsw i64 %indvars.iv.i, 1
  %exitcond.not.i = icmp eq i64 %indvars.iv.next.i, 4
  br i1 %exitcond.not.i, label %for.body.i2, label %for.body.i, !llvm.loop !10

for.body.i2:                                      ; preds = %for.body.i, %for.body.i2
  %indvars.iv.i3 = phi i64 [ %indvars.iv.next.i7, %for.body.i2 ], [ 0, %for.body.i ]
  %s.04.i4 = phi i32 [ %add.i6, %for.body.i2 ], [ 0, %for.body.i ]
  %arrayidx.i5 = getelementptr inbounds nuw i32, ptr %b, i64 %indvars.iv.i3
  %1 = load i32, ptr %arrayidx.i5, align 4, !tbaa !6
  %add.i6 = add nsw i32 %1, %s.04.i4
  %indvars.iv.next.i7 = add nuw nsw i64 %indvars.iv.i3, 1
  %exitcond.not.i8 = icmp eq i64 %indvars.iv.next.i7, 4
  br i1 %exitcond.not.i8, label %sum4.exit9, label %for.body.i2, !llvm.loop !10

sum4.exit9:                                       ; preds = %for.body.i2
  %add = add nsw i32 %add.i6, %add.i
  ret i32 %add
}

attributes #0 = { nofree norecurse nosync nounwind ssp memory(argmem: read) uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "probe-stack"="__chkstk_darwin" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+bti,+ccdp,+ccidx,+ccpp,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a" }

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
!10 = distinct !{!10, !11, !12}
!11 = !{!"llvm.loop.mustprogress"}
!12 = !{!"llvm.loop.unroll.disable"}
