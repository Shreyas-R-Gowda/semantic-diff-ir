; ModuleID = 'examples/real_commits/case2_new.c'
source_filename = "examples/real_commits/case2_new.c"
target datalayout = "e-m:o-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-n32:64-S128-Fn32"
target triple = "arm64-apple-macosx26.0.0"

; Function Attrs: mustprogress nofree norecurse nosync nounwind ssp willreturn memory(argmem: read) uwtable(sync)
define i32 @compute(ptr noundef readonly captures(none) %a, ptr noundef readonly captures(none) %b) local_unnamed_addr #0 {
entry:
  %0 = load i32, ptr %a, align 4, !tbaa !6
  %arrayidx1.i = getelementptr inbounds nuw i8, ptr %a, i64 4
  %1 = load i32, ptr %arrayidx1.i, align 4, !tbaa !6
  %arrayidx2.i = getelementptr inbounds nuw i8, ptr %a, i64 8
  %2 = load i32, ptr %arrayidx2.i, align 4, !tbaa !6
  %arrayidx4.i = getelementptr inbounds nuw i8, ptr %a, i64 12
  %3 = load i32, ptr %arrayidx4.i, align 4, !tbaa !6
  %4 = load i32, ptr %b, align 4, !tbaa !6
  %arrayidx1.i2 = getelementptr inbounds nuw i8, ptr %b, i64 4
  %5 = load i32, ptr %arrayidx1.i2, align 4, !tbaa !6
  %arrayidx2.i4 = getelementptr inbounds nuw i8, ptr %b, i64 8
  %6 = load i32, ptr %arrayidx2.i4, align 4, !tbaa !6
  %arrayidx4.i6 = getelementptr inbounds nuw i8, ptr %b, i64 12
  %7 = load i32, ptr %arrayidx4.i6, align 4, !tbaa !6
  %add.i3 = add i32 %1, %0
  %add3.i5 = add i32 %add.i3, %2
  %add5.i7 = add i32 %add3.i5, %3
  %add.i = add i32 %add5.i7, %4
  %add3.i = add i32 %add.i, %5
  %add5.i = add i32 %add3.i, %6
  %add = add i32 %add5.i, %7
  ret i32 %add
}

attributes #0 = { mustprogress nofree norecurse nosync nounwind ssp willreturn memory(argmem: read) uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "probe-stack"="__chkstk_darwin" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+bti,+ccdp,+ccidx,+ccpp,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8.5a,+v8a" }

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
