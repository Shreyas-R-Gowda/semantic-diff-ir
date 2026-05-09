"""
Core semantic diff engine.

Key correctness fixes over the original:

1. Token-level block similarity
   SequenceMatcher was given the pipe-joined opcode string ("add|mul|ret")
   and compared it character-by-character.  We now pass a list of opcode
   tokens so each token is treated as an atomic unit.

2. Fuzzy block matching
   The original matched blocks only by exact label equality.  We now do a
   two-stage match: exact label first, then best-fingerprint for residuals
   above a similarity threshold, so inserted blocks don't cause mass
   false removed/added reports for all subsequent blocks.

3. Structural loop matching
   Loops are now matched by body_signature() rather than header label.
   After vectorization a preheader is inserted and the header label shifts;
   the old code would report every loop as removed+added.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx

from ..graphs.cfg import CFGBuilder
from ..graphs.dfg import DFGBuilder
from ..parser.types import BasicBlock, Function, IRModule, LoopInfo
from .matcher import FunctionMatcher

_BLOCK_FUZZY_THRESHOLD = 0.40


@dataclass
class BlockDiff:
    old_label:      Optional[str]
    new_label:      Optional[str]
    status:         str
    old_fp:         str = ""
    new_fp:         str = ""
    similarity:     float = 1.0
    added_instrs:   List[str] = field(default_factory=list)
    removed_instrs: List[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.status != "matched" or self.similarity < 1.0


@dataclass
class LoopDiff:
    header:              str
    old_loop:            Optional[LoopInfo]
    new_loop:            Optional[LoopInfo]
    unroll_changed:      bool = False
    vector_changed:      bool = False
    trip_cnt_changed:    bool = False
    runtime_check_added: bool = False
    iv_stride_changed:   bool = False


@dataclass
class FunctionDiff:
    old_name:         str
    new_name:         str
    match_confidence: float
    status:           str
    match_reason:     str = "exact"

    old_instr_count: int = 0
    new_instr_count: int = 0
    old_block_count: int = 0
    new_block_count: int = 0
    old_edge_count:  int = 0
    new_edge_count:  int = 0

    old_critical_path: int = 0
    new_critical_path: int = 0
    old_mem_deps:      int = 0
    new_mem_deps:      int = 0

    block_diffs:  List[BlockDiff] = field(default_factory=list)
    loop_diffs:   List[LoopDiff]  = field(default_factory=list)

    old_calls:     List[str] = field(default_factory=list)
    new_calls:     List[str] = field(default_factory=list)
    old_histogram: Dict[str, int] = field(default_factory=dict)
    new_histogram: Dict[str, int] = field(default_factory=dict)

    # Set True when loop/vector changes already account for the instr delta,
    # so CFClassifier can suppress redundant INSTR_COUNT_UP/DOWN noise.
    explained_instr_delta: bool = False

    @property
    def instr_delta(self) -> int:
        return self.new_instr_count - self.old_instr_count

    @property
    def critical_path_delta(self) -> int:
        return self.new_critical_path - self.old_critical_path

    @property
    def inlined_functions(self) -> List[str]:
        return [c for c in self.old_calls
                if c not in self.new_calls and not c.startswith("llvm.")]

    @property
    def deinlined_functions(self) -> List[str]:
        return [c for c in self.new_calls
                if c not in self.old_calls and not c.startswith("llvm.")]

    def has_loop_or_vector_change(self) -> bool:
        return any(ld.unroll_changed or ld.vector_changed for ld in self.loop_diffs)


@dataclass
class ModuleDiff:
    old_source:     str
    new_source:     str
    function_diffs: List[FunctionDiff] = field(default_factory=list)

    @property
    def changed_functions(self) -> List[FunctionDiff]:
        return [d for d in self.function_diffs if d.status != "unchanged"]


class DiffEngine:

    def __init__(self):
        self.cfg_builder = CFGBuilder()
        self.dfg_builder = DFGBuilder()
        self.matcher     = FunctionMatcher()

    def diff(self, old: IRModule, new: IRModule) -> ModuleDiff:
        result = ModuleDiff(old.source_file, new.source_file)
        matches, added, removed = self.matcher.match(old, new)

        for m in matches:
            fd = self._diff_function(
                old.functions[m.old_name],
                new.functions[m.new_name],
                m.confidence,
                m.reason,
            )
            result.function_diffs.append(fd)

        for name in added:
            f = new.functions[name]
            result.function_diffs.append(FunctionDiff(
                old_name="", new_name=name,
                match_confidence=0.0, status="added", match_reason="added",
                new_instr_count=f.total_instructions(),
                new_block_count=len(f.basic_blocks),
                new_calls=f.calls(),
                new_histogram=f.opcode_histogram(),
            ))

        for name in removed:
            f = old.functions[name]
            result.function_diffs.append(FunctionDiff(
                old_name=name, new_name="",
                match_confidence=0.0, status="removed", match_reason="removed",
                old_instr_count=f.total_instructions(),
                old_block_count=len(f.basic_blocks),
                old_calls=f.calls(),
                old_histogram=f.opcode_histogram(),
            ))

        return result

    # ── per-function diff ─────────────────────────────────────────────────────

    def _diff_function(
        self, old_f: Function, new_f: Function, confidence: float, reason: str
    ) -> FunctionDiff:
        old_cfg = self.cfg_builder.build(old_f)
        new_cfg = self.cfg_builder.build(new_f)
        old_dfg = self.dfg_builder.build(old_f)
        new_dfg = self.dfg_builder.build(new_f)

        block_diffs = self._diff_blocks(old_f, new_f)
        loop_diffs  = self._diff_loops(old_cfg, new_cfg)

        any_change = (
            any(bd.changed for bd in block_diffs)
            or old_f.total_instructions() != new_f.total_instructions()
            or len(old_f.basic_blocks) != len(new_f.basic_blocks)
        )

        fd = FunctionDiff(
            old_name=old_f.name,
            new_name=new_f.name,
            match_confidence=confidence,
            status="modified" if any_change else "unchanged",
            match_reason=reason,

            old_instr_count=old_f.total_instructions(),
            new_instr_count=new_f.total_instructions(),
            old_block_count=old_cfg.number_of_nodes(),
            new_block_count=new_cfg.number_of_nodes(),
            old_edge_count=old_cfg.number_of_edges(),
            new_edge_count=new_cfg.number_of_edges(),

            old_critical_path=old_dfg.graph.get("critical_path", 0),
            new_critical_path=new_dfg.graph.get("critical_path", 0),
            old_mem_deps=old_dfg.graph.get("mem_dep_count", 0),
            new_mem_deps=new_dfg.graph.get("mem_dep_count", 0),

            block_diffs=block_diffs,
            loop_diffs=loop_diffs,

            old_calls=old_f.calls(),
            new_calls=new_f.calls(),
            old_histogram=old_f.opcode_histogram(),
            new_histogram=new_f.opcode_histogram(),
        )
        fd.explained_instr_delta = fd.has_loop_or_vector_change()
        return fd

    # ── block diff ────────────────────────────────────────────────────────────

    def _diff_blocks(self, old_f: Function, new_f: Function) -> List[BlockDiff]:
        """Two-stage: exact label, then fuzzy fingerprint for residuals."""
        diffs: List[BlockDiff] = []
        matched_new: Set[str]  = set()
        old_blocks = old_f.basic_blocks
        new_blocks = new_f.basic_blocks

        # Stage 1: exact label
        unmatched_old: List[str] = []
        for lbl, old_blk in old_blocks.items():
            if lbl in new_blocks:
                diffs.append(self._diff_block_pair(old_blk, new_blocks[lbl]))
                matched_new.add(lbl)
            else:
                unmatched_old.append(lbl)

        unmatched_new = [lbl for lbl in new_blocks if lbl not in matched_new]

        # Stage 2: fuzzy match residuals
        used_old: Set[str] = set()
        used_new: Set[str] = set()
        if unmatched_old and unmatched_new:
            candidates: List[Tuple[float, str, str]] = []
            for old_lbl in unmatched_old:
                old_toks = old_blocks[old_lbl].opcode_tokens()
                for new_lbl in unmatched_new:
                    new_toks = new_blocks[new_lbl].opcode_tokens()
                    sim = SequenceMatcher(None, old_toks, new_toks).ratio()
                    if sim >= _BLOCK_FUZZY_THRESHOLD:
                        candidates.append((sim, old_lbl, new_lbl))

            candidates.sort(reverse=True)
            for sim, old_lbl, new_lbl in candidates:
                if old_lbl in used_old or new_lbl in used_new:
                    continue
                diffs.append(self._diff_block_pair(
                    old_blocks[old_lbl], new_blocks[new_lbl],
                    force_similarity=sim,
                ))
                used_old.add(old_lbl)
                used_new.add(new_lbl)

        for lbl in unmatched_old:
            if lbl not in used_old:
                diffs.append(BlockDiff(
                    old_label=lbl, new_label=None,
                    status="removed", old_fp=old_blocks[lbl].fingerprint(),
                ))
        for lbl in unmatched_new:
            if lbl not in used_new:
                diffs.append(BlockDiff(
                    old_label=None, new_label=lbl,
                    status="added", new_fp=new_blocks[lbl].fingerprint(),
                ))

        return diffs

    def _diff_block_pair(
        self,
        old_blk: BasicBlock,
        new_blk: BasicBlock,
        force_similarity: Optional[float] = None,
    ) -> BlockDiff:
        old_fp = old_blk.fingerprint()
        new_fp = new_blk.fingerprint()

        if old_fp == new_fp and force_similarity is None:
            return BlockDiff(
                old_label=old_blk.label, new_label=new_blk.label,
                status="matched", old_fp=old_fp, new_fp=new_fp, similarity=1.0,
            )

        # Token-level comparison (fix: original joined to string then compared chars)
        old_toks = old_blk.opcode_tokens()
        new_toks = new_blk.opcode_tokens()
        sim = force_similarity if force_similarity is not None else (
            SequenceMatcher(None, old_toks, new_toks).ratio()
        )

        added_instrs: List[str] = []
        removed_instrs: List[str] = []
        for tag, i1, i2, j1, j2 in SequenceMatcher(None, old_toks, new_toks).get_opcodes():
            if tag == "delete":
                removed_instrs.extend(old_toks[i1:i2])
            elif tag == "insert":
                added_instrs.extend(new_toks[j1:j2])
            elif tag == "replace":
                removed_instrs.extend(old_toks[i1:i2])
                added_instrs.extend(new_toks[j1:j2])

        return BlockDiff(
            old_label=old_blk.label, new_label=new_blk.label,
            status="matched",
            old_fp=old_fp, new_fp=new_fp,
            similarity=sim,
            added_instrs=added_instrs,
            removed_instrs=removed_instrs,
        )

    # ── loop diff ─────────────────────────────────────────────────────────────

    def _diff_loops(
        self, old_cfg: nx.DiGraph, new_cfg: nx.DiGraph
    ) -> List[LoopDiff]:
        """
        Match loops by structural signature (body_size, phi_count,
        vector_width, trip_count) instead of header label.  When labels
        shift due to inserted preheaders, this keeps the loop paired.
        """
        old_loops: List[LoopInfo] = old_cfg.graph.get("loops", [])
        new_loops: List[LoopInfo] = new_cfg.graph.get("loops", [])

        matched_new: Set[int] = set()
        loop_diffs: List[LoopDiff] = []

        new_by_sig: Dict[tuple, List[int]] = defaultdict(list)
        for idx, lo in enumerate(new_loops):
            new_by_sig[lo.body_signature()].append(idx)

        for old_lo in old_loops:
            sig = old_lo.body_signature()
            candidates = [i for i in new_by_sig.get(sig, []) if i not in matched_new]

            if len(candidates) == 1:
                new_lo = new_loops[candidates[0]]
                matched_new.add(candidates[0])
            elif len(candidates) > 1:
                best = min(
                    candidates,
                    key=lambda i: abs(len(new_loops[i].body) - len(old_lo.body))
                )
                matched_new.add(best)
                new_lo = new_loops[best]
            else:
                # Fallback: body-size proximity among all unmatched
                remaining = [(i, lo) for i, lo in enumerate(new_loops)
                             if i not in matched_new]
                new_lo = None
                if remaining:
                    best_i, best_lo = min(
                        remaining,
                        key=lambda x: abs(len(x[1].body) - len(old_lo.body))
                    )
                    if abs(len(best_lo.body) - len(old_lo.body)) <= 2:
                        matched_new.add(best_i)
                        new_lo = best_lo

                if new_lo is None:
                    loop_diffs.append(LoopDiff(
                        header=old_lo.header, old_loop=old_lo, new_loop=None
                    ))
                    continue

            loop_diffs.append(self._compare_loops(old_lo.header, old_lo, new_lo))

        for i, new_lo in enumerate(new_loops):
            if i not in matched_new:
                loop_diffs.append(LoopDiff(
                    header=new_lo.header, old_loop=None, new_loop=new_lo
                ))

        return loop_diffs

    def _compare_loops(
        self, header: str, old_lo: LoopInfo, new_lo: LoopInfo
    ) -> LoopDiff:
        ld = LoopDiff(header=header, old_loop=old_lo, new_loop=new_lo)
        ld.unroll_changed      = old_lo.unroll_factor != new_lo.unroll_factor
        ld.vector_changed      = old_lo.vector_width  != new_lo.vector_width
        ld.trip_cnt_changed    = old_lo.trip_count    != new_lo.trip_count
        ld.iv_stride_changed   = old_lo.iv_stride     != new_lo.iv_stride
        ld.runtime_check_added = (
            not old_lo.has_runtime_check and new_lo.has_runtime_check
        )
        return ld
