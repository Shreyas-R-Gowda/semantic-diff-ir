from __future__ import annotations

from typing import Dict, List, Tuple

import networkx as nx

from ..parser.types import Function, Instruction, Opcode


class DFGBuilder:

    def build(self, func: Function) -> nx.DiGraph:
        dfg = nx.DiGraph(func_name=func.name)
        def_map: Dict[str, Instruction] = {}

        for blk in func.basic_blocks.values():
            for instr in blk.instructions:
                if instr.result:
                    dfg.add_node(
                        instr.result,
                        opcode=instr.opcode.value,
                        block=instr.block,
                        is_vector=instr.is_vector,
                    )
                    def_map[instr.result] = instr

        for blk in func.basic_blocks.values():
            for instr in blk.instructions:
                if not instr.result:
                    continue
                for op in instr.operands:
                    if op in def_map and dfg.has_node(instr.result):
                        if not dfg.has_edge(op, instr.result):
                            dfg.add_edge(op, instr.result)

        self._critical_path(dfg)
        dfg.graph["mem_dep_count"] = self._count_mem_deps(func)
        return dfg

    def _critical_path(self, dfg: nx.DiGraph):
        try:
            order = list(nx.topological_sort(dfg))
        except nx.NetworkXUnfeasible:
            dfg.graph["critical_path"] = -1
            return

        depth: Dict[str, int] = {n: 0 for n in dfg.nodes()}
        for n in order:
            for pred in dfg.predecessors(n):
                depth[n] = max(depth[n], depth[pred] + 1)
            dfg.nodes[n]["depth"] = depth[n]

        dfg.graph["critical_path"] = max(depth.values(), default=0)

    def _count_mem_deps(self, func: Function) -> int:
        stores: Dict[str, int] = {}
        loads:  Dict[str, int] = {}
        for blk in func.basic_blocks.values():
            for instr in blk.instructions:
                ptr = instr.operands[-1] if instr.operands else ""
                if instr.opcode == Opcode.STORE:
                    stores[ptr] = stores.get(ptr, 0) + 1
                elif instr.opcode == Opcode.LOAD:
                    loads[ptr] = loads.get(ptr, 0) + 1
        return sum(
            stores[p] * loads[p]
            for p in set(stores) & set(loads)
        )
