"""
CFG construction and analysis.

Unroll detection improvements:
  - IV stride analysis: `add i32 %iv, 4` → unroll_factor=4 (most reliable)
  - Excess phi-node heuristic: >6 phis in header → likely unrolled
  - GEP offset heuristic: only fires when IV stride also hints unrolling
    (guards against struct-field false positives in the original code)
  - Trip count now also checks the latch block, not just the header
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx

from ..parser.types import BasicBlock, Function, LoopInfo, Opcode


class CFGBuilder:

    def build(self, func: Function) -> nx.DiGraph:
        cfg = nx.DiGraph(func_name=func.name)
        if not func.basic_blocks:
            return cfg

        for lbl, blk in func.basic_blocks.items():
            cfg.add_node(lbl, block=blk, loop_depth=0, vector_width=0)

        for lbl, blk in func.basic_blocks.items():
            for s in blk.successors:
                if s in func.basic_blocks:
                    cfg.add_edge(lbl, s, kind="forward")

        entry = next(iter(func.basic_blocks))
        self._prune_unreachable(cfg, entry)
        dominators = self._idom(cfg, entry)
        cfg.graph["dominators"] = dominators
        loops = self._find_loops(cfg, func, dominators)
        self._assign_loop_depth(cfg, loops)
        self._annotate_vectors(cfg, func)
        cfg.graph["loops"] = loops
        return cfg

    # ── dominators ────────────────────────────────────────────────────────────

    def _idom(self, cfg: nx.DiGraph, entry: str) -> Dict[str, str]:
        try:
            return nx.immediate_dominators(cfg, entry)
        except Exception:
            return {n: n for n in cfg.nodes()}

    def _dominates(self, a: str, b: str, idom: Dict[str, str]) -> bool:
        visited: Set[str] = set()
        cur = b
        while cur not in visited:
            if cur == a:
                return True
            visited.add(cur)
            nxt = idom.get(cur)
            if nxt is None or nxt == cur:
                break
            cur = nxt
        return a == cur

    # ── loops ─────────────────────────────────────────────────────────────────

    def _find_loops(
        self, cfg: nx.DiGraph, func: Function, idom: Dict[str, str]
    ) -> List[LoopInfo]:
        loops: List[LoopInfo] = []
        back_edges: List[Tuple[str, str]] = []

        for src, dst in cfg.edges():
            if self._dominates(dst, src, idom):
                back_edges.append((src, dst))
                cfg[src][dst]["kind"] = "back"

        for tail, header in back_edges:
            body = self._loop_body(cfg, header, tail)
            info = LoopInfo(header=header, body=body, back_edges=[(tail, header)])
            self._detect_trip_count(func, info)
            self._detect_iv_stride(func, info)
            self._detect_unroll(func, info)
            self._detect_vectorize(func, info)
            self._count_header_phis(func, info)
            loops.append(info)

        for i, lo in enumerate(loops):
            lo.depth = sum(
                1 for j, other in enumerate(loops)
                if i != j and lo.header in other.body and lo.body < other.body
            )
        return loops

    def _loop_body(self, cfg: nx.DiGraph, header: str, tail: str) -> Set[str]:
        body: Set[str] = {header}
        stack = [tail]
        while stack:
            n = stack.pop()
            if n in body:
                continue
            body.add(n)
            stack.extend(cfg.predecessors(n))
        return body

    # ── loop annotations ──────────────────────────────────────────────────────

    def _detect_trip_count(self, func: Function, loop: LoopInfo):
        """Check both header AND latch for the loop-exit comparison."""
        candidates = [loop.header, loop.back_edges[0][0]]
        for blk_lbl in candidates:
            blk = func.basic_blocks.get(blk_lbl)
            if not blk:
                continue
            for instr in blk.instructions:
                if instr.opcode in (Opcode.ICMP, Opcode.FCMP):
                    m = re.search(
                        r'(?:slt|ult|sle|ule|ne|eq)\s+\S+\s+%[\w.]+,\s*(\d+)',
                        instr.raw,
                    )
                    if m:
                        loop.trip_count = int(m.group(1))
                        return

    def _count_header_phis(self, func: Function, loop: LoopInfo):
        hdr = func.basic_blocks.get(loop.header)
        if hdr:
            loop.phi_count = hdr.count_opcode(Opcode.PHI)

    def _detect_iv_stride(self, func: Function, loop: LoopInfo):
        """
        Find the induction variable increment.  A stride > 1 is the
        primary indicator that the compiler merged multiple iterations.
        Pattern: `%iv.next = add [nuw] [nsw] i<N> %iv_phi, <stride>`
        """
        hdr = func.basic_blocks.get(loop.header)
        if not hdr:
            return
        iv_names: Set[str] = set()
        for instr in hdr.instructions:
            if instr.opcode == Opcode.PHI and instr.result:
                iv_names.add(instr.result)

        for lbl in loop.body:
            blk = func.basic_blocks.get(lbl)
            if not blk:
                continue
            for instr in blk.instructions:
                if instr.opcode == Opcode.ADD:
                    m = re.search(
                        r'add\s+(?:nuw\s+)?(?:nsw\s+)?i\d+\s+'
                        r'(%[\w.$]+),\s*(\d+)',
                        instr.raw,
                    )
                    if m and m.group(1) in iv_names:
                        stride = int(m.group(2))
                        if stride > loop.iv_stride:
                            loop.iv_stride = stride
                        # Do NOT return early: scan all adds to find the max stride.
                        # Unrolled loops emit intermediate increments (stride 1, 2, ...)
                        # followed by the final outer increment (stride N = unroll factor).

    def _detect_unroll(self, func: Function, loop: LoopInfo):
        """
        Three-signal unroll detection (see module docstring).
        Signals tried in order of reliability:
          0. Explicit metadata (rare after optimization, but unambiguous)
          1. IV stride > 1  ← most reliable
          2. Excess phi nodes in header  ← reliable for large unroll factors
          3. GEP consecutive offsets  ← only when stride also hints unrolling
        """
        # Signal 0: explicit metadata
        for lbl in loop.body:
            blk = func.basic_blocks.get(lbl)
            if not blk:
                continue
            for instr in blk.instructions:
                if "llvm.loop.unroll.count" in instr.raw:
                    m = re.search(r'i32\s+(\d+)', instr.raw)
                    if m:
                        loop.unroll_factor = int(m.group(1))
                        return

        # Signal 1: IV stride
        if loop.iv_stride > 1 and loop.iv_stride in (2, 4, 8, 16, 32):
            loop.unroll_factor = loop.iv_stride
            return

        # Signal 2: excess phi nodes
        hdr = func.basic_blocks.get(loop.header)
        phi_count = hdr.count_opcode(Opcode.PHI) if hdr else 0
        if phi_count >= 6:
            raw_factor = max(2, phi_count // 2)
            for f in (32, 16, 8, 4, 2):
                if raw_factor >= f:
                    loop.unroll_factor = f
                    return

        # Signal 3: GEP consecutive offsets — guarded by stride check
        if loop.iv_stride == 1:
            return   # avoid struct false positives

        gep_offsets: List[int] = []
        for lbl in loop.body:
            blk = func.basic_blocks.get(lbl)
            if not blk:
                continue
            for instr in blk.instructions:
                if instr.opcode == Opcode.GEP:
                    for off in re.findall(r'i\d+\s+(\d+)', instr.raw):
                        gep_offsets.append(int(off))

        if len(gep_offsets) >= 4:
            unique = sorted(set(gep_offsets))
            strides_gep = [unique[k+1] - unique[k] for k in range(len(unique)-1)]
            if strides_gep and len(set(strides_gep)) == 1 and strides_gep[0] > 0:
                factor = len(unique)
                if factor in (2, 4, 8, 16, 32):
                    loop.unroll_factor = factor

    def _detect_vectorize(self, func: Function, loop: LoopInfo):
        for lbl in loop.body:
            blk = func.basic_blocks.get(lbl)
            if not blk:
                continue
            for instr in blk.instructions:
                if "llvm.loop.vectorize.width" in instr.raw:
                    m = re.search(r'i32\s+(\d+)', instr.raw)
                    if m:
                        loop.vector_width = int(m.group(1))
                if instr.is_vector:
                    loop.vector_width = max(loop.vector_width, instr.vector_width)

        if loop.vector_width > 0:
            hdr_blk = func.basic_blocks.get(loop.header, BasicBlock(label="x"))
            for pred in hdr_blk.predecessors:
                blk = func.basic_blocks.get(pred)
                if blk is None:
                    continue
                raw_text = " ".join(i.raw.lower() for i in blk.instructions)
                if re.search(r'memcheck|smax|smin|umax|umin', raw_text):
                    loop.has_runtime_check = True
                    break

    # ── helpers ───────────────────────────────────────────────────────────────

    def _prune_unreachable(self, cfg: nx.DiGraph, entry: str):
        reachable = nx.descendants(cfg, entry) | {entry}
        cfg.remove_nodes_from([n for n in list(cfg.nodes()) if n not in reachable])

    def _assign_loop_depth(self, cfg: nx.DiGraph, loops: List[LoopInfo]):
        for node in cfg.nodes():
            cfg.nodes[node]["loop_depth"] = sum(
                1 for lo in loops if node in lo.body
            )

    def _annotate_vectors(self, cfg: nx.DiGraph, func: Function):
        for lbl in cfg.nodes():
            blk = func.basic_blocks.get(lbl)
            if blk:
                cfg.nodes[lbl]["vector_width"] = blk.vector_width()
