from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from .types import BasicBlock, Function, Instruction, IRModule, Opcode

_RE_FUNC_DEF = re.compile(
    r'^define\s+'
    r'(?:(?:private|internal|available_externally|linkonce|weak|'
    r'common|appending|extern_weak|linkonce_odr|weak_odr|external)\s+)?'
    r'(?:(?:default|hidden|protected)\s+)?'
    r'(?:(?:unnamed_addr|local_unnamed_addr)\s+)?'
    r'(?:(?:dso_local|dso_preemptable)\s+)?'
    r'(?P<ret>[^@]+?)\s+'
    r'@(?P<name>[\w.$]+)\s*'
    r'\((?P<params>[^)]*)\)'
    r'(?P<tail>[^{]*)\{'
)
_RE_FUNC_DECL   = re.compile(r'^declare\s+.*?@(?P<name>[\w.$]+)\s*\(')
_RE_BLOCK_LABEL = re.compile(r'^([\w.$]+):\s*(?:;.*)?$')
_RE_INSTR       = re.compile(
    r'^\s+'
    r'(?:(?P<result>%[\w.$]+)\s*=\s*)?'
    r'(?P<tail_call>(?:tail|musttail|notail)\s+)?'
    r'(?P<opcode>[\w.]+)'
    r'(?P<rest>.*)$'
)
_RE_VALUE_REF = re.compile(r'([%@][\w.$]+)')
_RE_TYPE      = re.compile(r'^([^%@,\[{(]+)')


class IRParser:
    def parse(self, ir_text: str, source_file: str = "") -> IRModule:
        module = IRModule(source_file=source_file, raw_ir=ir_text)
        lines = ir_text.splitlines()
        idx = 0
        while idx < len(lines):
            line = lines[idx].rstrip()
            if not line or line.lstrip().startswith(";"):
                idx += 1
                continue

            decl_m = _RE_FUNC_DECL.match(line)
            if decl_m and line.startswith("declare"):
                func = Function(
                    name=decl_m.group("name"),
                    return_type="",
                    params=[],
                    is_declaration=True,
                )
                module.functions[func.name] = func
                idx += 1
                continue

            def_m = _RE_FUNC_DEF.match(line)
            if def_m:
                func, idx = self._parse_function(lines, idx, def_m)
                module.functions[func.name] = func
                continue

            if re.match(r'^@[\w.$]+\s*=', line):
                module.global_vars.append(line)

            idx += 1

        for func in module.functions.values():
            if not func.is_declaration:
                self._wire_cfg(func)

        return module

    def _parse_function(
        self, lines: List[str], start: int, m: re.Match
    ) -> Tuple[Function, int]:
        func = Function(
            name=m.group("name"),
            return_type=m.group("ret").strip(),
            params=self._parse_params(m.group("params") or ""),
            attributes=self._parse_attrs(m.group("tail") or ""),
        )
        idx = start + 1
        current: Optional[BasicBlock] = None
        first_instr_seen = False

        while idx < len(lines):
            raw = lines[idx].rstrip()

            if raw.strip() == "}":
                if current and current.instructions:
                    func.basic_blocks[current.label] = current
                return func, idx + 1

            stripped = raw.strip()
            if not stripped or stripped.startswith(";"):
                idx += 1
                continue

            lbl_m = _RE_BLOCK_LABEL.match(stripped)
            if (lbl_m
                    and not stripped.startswith("%")
                    and not stripped.startswith(" ")
                    and not stripped.startswith("\t")):
                if current and current.instructions:
                    func.basic_blocks[current.label] = current
                current = BasicBlock(label=lbl_m.group(1))
                idx += 1
                continue

            instr_m = _RE_INSTR.match(raw)
            if instr_m:
                if not first_instr_seen:
                    if current is None:
                        current = BasicBlock(label="entry")
                    first_instr_seen = True
                if current is not None:
                    instr = self._parse_instr(instr_m, current.label)
                    current.instructions.append(instr)

            idx += 1

        if current and current.instructions:
            func.basic_blocks[current.label] = current
        return func, idx

    def _parse_instr(self, m: re.Match, block_label: str) -> Instruction:
        opcode_str = ((m.group("tail_call") or "") + m.group("opcode")).strip()
        rest       = m.group("rest") or ""
        result     = m.group("result")

        operands = _RE_VALUE_REF.findall(rest)

        type_str = ""
        type_m = _RE_TYPE.match(rest.lstrip())
        if type_m:
            candidate = type_m.group(1).strip().rstrip(",")
            if re.search(r'\b(i\d+|float|double|ptr|\*)', candidate):
                type_str = candidate

        return Instruction(
            opcode_str=opcode_str,
            result=result,
            type_str=type_str,
            operands=operands,
            raw=m.string.strip(),
            block=block_label,
        )

    def _wire_cfg(self, func: Function):
        blocks = func.basic_blocks
        for label, block in blocks.items():
            term = block.terminator
            if term is None:
                continue
            targets = re.findall(r'label\s+%?([\w.$]+)', term.raw)
            for t in targets:
                if t in blocks:
                    if t not in block.successors:
                        block.successors.append(t)
                    if label not in blocks[t].predecessors:
                        blocks[t].predecessors.append(label)

    def _parse_params(self, s: str) -> List[Tuple[str, str]]:
        if not s.strip():
            return []
        result = []
        depth = 0
        buf = ""
        for ch in s:
            if ch in "<([{":
                depth += 1
            elif ch in ">)]}":
                depth -= 1
            if ch == "," and depth == 0:
                result.append(self._parse_one_param(buf.strip()))
                buf = ""
            else:
                buf += ch
        if buf.strip():
            result.append(self._parse_one_param(buf.strip()))
        return result

    def _parse_one_param(self, s: str) -> Tuple[str, str]:
        tokens = s.split()
        name = next((t for t in reversed(tokens) if t.startswith("%")), "")
        skip = {"noundef", "nocapture", "readonly", "writeonly",
                "nonnull", "returned", "sret", name}
        type_parts = [t for t in tokens if t not in skip]
        return (" ".join(type_parts), name)

    def _parse_attrs(self, s: str) -> List[str]:
        return re.findall(
            r'#\d+|\b(?:noinline|alwaysinline|optsize|cold|hot)\b', s
        )
