"""
IR Normalization: remove differences that are semantically irrelevant.

Invariants we preserve:
  - Control flow structure
  - Instruction opcodes and their operand types
  - Memory access patterns
  - Call targets

Invariants we REMOVE:
  - Debug metadata (file names, line numbers, variable names)
  - Module-level ident/flags
  - Unnamed temporary numbering (%1, %2 → %v0, %v1 with stable re-numbering)
  - Phi-node label references to unnamed blocks (fixed: was not renaming these)
  - Attribute group details that change across compiler versions
  - Attribute group definitions (attributes #N = {...})
  - source_filename directive
  - Typed pointer syntax (i32*, void*) → opaque ptr for cross-version compat
  - Operand order in commutative ops (add/mul/and/or/xor)

The renaming of unnamed temporaries is the most important step.
When you add a local variable to a function, all subsequent %N values
get bumped by the number of new instructions.  This makes a naive text
diff report hundreds of changes for a 2-line edit.  By renaming to a
canonical sequence per-function (in dominance order), we absorb these shifts.

NOTE: Phi-node predecessors also use block labels in `[ val, %N ]` form.
The original normalizer handled `label %N` in branch targets but NOT
the phi form.  This is fixed here: we also rename `%N` in phi predecessors.
"""
from __future__ import annotations

import re
from typing import Dict, List

# ─── compiled regexes ────────────────────────────────────────────────────────

_RE_DBG_META_DEF = re.compile(
    r'^\s*!\d+\s*=\s*(?:distinct\s+)?'
    r'!(?:DI\w+|llvm\.loop|DebugLoc)',
    re.IGNORECASE,
)
_RE_DBG_ANNOT    = re.compile(r',?\s*!dbg\s+!\d+')
_RE_LOOP_META    = re.compile(r',?\s*!llvm\.loop\s+!\d+')
_RE_TBAA_META    = re.compile(r',?\s*!tbaa(?:\.struct)?\s+!\d+')
_RE_RANGE_META   = re.compile(r',?\s*!range\s+!\d+')
_RE_SOURCE_FILE  = re.compile(r'^source_filename\s*=.*$', re.MULTILINE)
_RE_IDENT        = re.compile(r'^!\s*llvm\.ident\s*=.*$', re.MULTILINE)
_RE_MODULE_FLAGS = re.compile(r'^!\s*llvm\.module\.flags\s*=.*$', re.MULTILINE)
_RE_ATTR_NOISE   = re.compile(
    r'"(?:frame-pointer|stack-protector-buffer-size|'
    r'min-legal-vector-width|no-trapping-math|target-cpu|target-features|'
    r'tune-cpu|uwtable)"\s*=\s*"[^"]*"'
)
_RE_FUNC_DEF      = re.compile(r'^define\b')
_RE_ATTR_GROUP    = re.compile(r'^attributes\s+#\d+\s*=\s*\{[^}]*\}', re.MULTILINE)
_RE_ATTR_REF      = re.compile(r'\s+#\d+\b')
_RE_TYPED_PTR     = re.compile(r'\b(i\d+|float|double|half|bfloat|void)\s*\*+')
_RE_COMMUTATIVE   = re.compile(
    r'(=\s*(?:add|mul|and|or|xor)\s+(?:nuw\s+)?(?:nsw\s+)?)'
    r'((?:i\d+|ptr)\s+)'
    r'(%[\w.$]+),\s*(%[\w.$]+)'
)


class IRNormalizer:
    """
    Stateless normalizer: call `normalize(ir_text)` and get back
    a cleaned IR string ready for parsing or text comparison.
    """

    def normalize(self, ir: str) -> str:
        ir = self._strip_metadata(ir)
        ir = self._strip_module_noise(ir)
        ir = self._strip_attr_noise(ir)
        ir = self._strip_attribute_groups(ir)
        ir = self._normalize_ptr_types(ir)
        ir = self._normalize_commutative(ir)
        ir = self._rename_unnamed(ir)
        ir = self._collapse_blank_lines(ir)
        return ir

    # ── metadata removal ──────────────────────────────────────────────────────

    def _strip_metadata(self, ir: str) -> str:
        out = []
        for line in ir.splitlines():
            if _RE_DBG_META_DEF.match(line):
                continue
            if "llvm.dbg.value" in line or "llvm.dbg.declare" in line:
                continue
            line = _RE_DBG_ANNOT.sub("", line)
            line = _RE_LOOP_META.sub("", line)
            line = _RE_TBAA_META.sub("", line)
            line = _RE_RANGE_META.sub("", line)
            line = re.sub(r',\s*!\d+\s*$', '', line)
            out.append(line)
        return "\n".join(out)

    def _strip_module_noise(self, ir: str) -> str:
        ir = _RE_SOURCE_FILE.sub("", ir)
        ir = _RE_IDENT.sub("", ir)
        ir = _RE_MODULE_FLAGS.sub("", ir)
        return ir

    def _strip_attr_noise(self, ir: str) -> str:
        return _RE_ATTR_NOISE.sub("", ir)

    # ── attribute groups ──────────────────────────────────────────────────────

    def _strip_attribute_groups(self, ir: str) -> str:
        """
        Remove 'attributes #N = { ... }' definitions and #N references in
        function signatures.  Attribute groups encode backend-specific
        properties (cpu target, frame pointer style, etc.) that change
        across compiler versions without changing semantics.
        """
        ir = _RE_ATTR_GROUP.sub("", ir)
        # Remove trailing #N on define/declare lines only (not inside bodies)
        lines = []
        for line in ir.splitlines():
            if line.startswith("define ") or line.startswith("declare "):
                line = _RE_ATTR_REF.sub("", line)
            lines.append(line)
        return "\n".join(lines)

    # ── pointer type normalization ─────────────────────────────────────────────

    def _normalize_ptr_types(self, ir: str) -> str:
        """
        Normalize typed pointers (LLVM ≤14) to opaque pointers (LLVM 15+).
        `i32*` → `ptr`, `float**` → `ptr`, `void*` → `ptr`.
        Only applies to instruction lines (indented) to avoid clobbering
        struct type definitions like `%struct.Foo = type { i32*, i8 }`.
        """
        lines = []
        for line in ir.splitlines():
            # Normalize pointer types on:
            #   - indented lines (instructions inside function bodies)
            #   - define/declare lines (normalizes parameter types)
            # Intentionally skips type definition lines like
            # `%struct.Foo = type { i32*, i8 }` (not indented, no define/declare).
            if (line != line.lstrip()
                    or line.startswith("define ")
                    or line.startswith("declare ")):
                line = _RE_TYPED_PTR.sub("ptr", line)
            lines.append(line)
        return "\n".join(lines)

    # ── commutative normalization ─────────────────────────────────────────────

    def _normalize_commutative(self, ir: str) -> str:
        """
        Canonicalize operand order for commutative integer ops so that
        `add i32 %a, %b` and `add i32 %b, %a` normalize identically.

        Only swaps when both operands are SSA values (not immediates),
        to avoid touching `add i32 %x, 1` where order is already canonical.
        Sorting is lexicographic on the value name.
        """
        def _swap_if_needed(m: re.Match) -> str:
            prefix = m.group(1)   # '= add ' or '= add nuw nsw ' etc.
            typ    = m.group(2)   # 'i32 ' or 'ptr '
            a      = m.group(3)   # '%foo'
            b      = m.group(4)   # '%bar'
            if a > b:
                a, b = b, a
            return f"{prefix}{typ}{a}, {b}"

        lines = []
        for line in ir.splitlines():
            lines.append(_RE_COMMUTATIVE.sub(_swap_if_needed, line))
        return "\n".join(lines)

    # ── unnamed value renaming ─────────────────────────────────────────────────

    def _rename_unnamed(self, ir: str) -> str:
        """
        Per-function sequential renaming of unnamed temporaries.

        Strategy: within each 'define ... { ... }' block, scan for all
        definitions of the form '%N =' and block labels 'N:', then remap
        them to %v0, %v1, ... (values) and bb0, bb1, ... (blocks).

        TWO passes per function:
          Pass 1: collect all definition sites → build old→new map
          Pass 2: apply substitutions (value references + block labels
                  in BOTH branch targets AND phi-node predecessors)

        Bug fix over original: phi-node predecessor refs like `[ val, %16 ]`
        are now renamed, not just `label %16` in branch instructions.
        """
        lines  = ir.splitlines()
        result: List[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if _RE_FUNC_DEF.match(line):
                body: List[str] = [line]
                i += 1
                while i < len(lines) and lines[i].strip() != "}":
                    body.append(lines[i])
                    i += 1
                body.append("}")
                result.extend(self._rename_function_body(body))
                i += 1
            else:
                result.append(line)
                i += 1
        return "\n".join(result)

    def _rename_function_body(self, lines: List[str]) -> List[str]:
        val_map:   Dict[str, str] = {}
        label_map: Dict[str, str] = {}
        val_ctr   = 0
        label_ctr = 0

        # Pass 1: collect definitions in order
        for line in lines[1:-1]:
            stripped = line.strip()

            # Block label definition: `42:` or `loop.body:` at column 0
            if not line.startswith((" ", "\t")):
                m = re.match(r'^([\w.$]+):', stripped)
                if m:
                    old_lbl = m.group(1)
                    if re.fullmatch(r'\d+', old_lbl):
                        label_map[old_lbl] = f"bb{label_ctr}"
                        label_ctr += 1
                    continue

            # Value definition: `  %42 = ...`
            m = re.match(r'^\s+(%\d+)\s*=', line)
            if m:
                old = m.group(1)
                if old not in val_map:
                    val_map[old] = f"%v{val_ctr}"
                    val_ctr += 1

        if not val_map and not label_map:
            return lines

        # Pre-build sorted lists (longest first to avoid partial matches)
        sorted_vals   = sorted(val_map.items(),   key=lambda x: -len(x[0]))
        sorted_labels = sorted(label_map.items(), key=lambda x: -len(x[0]))

        def apply(line: str) -> str:
            # Replace SSA value references: %42 → %v0
            for old, new in sorted_vals:
                # Word boundary avoids %420 matching %42
                line = re.sub(re.escape(old) + r'\b', new, line)

            for old, new in sorted_labels:
                # Branch targets: `label %42` or `label 42`
                line = re.sub(
                    r'\blabel\s+%?' + old + r'\b',
                    f'label %{new}', line
                )
                # Phi predecessors: `[ val, %42 ]`
                line = re.sub(
                    r'(,\s*)%' + old + r'\b',
                    r'\g<1>%' + new, line
                )
                # Block label definition line: `42:`
                line = re.sub(
                    r'^(\s*)' + old + r':',
                    r'\g<1>' + new + ':', line
                )
            return line

        return [lines[0]] + [apply(l) for l in lines[1:-1]] + [lines[-1]]

    def _collapse_blank_lines(self, ir: str) -> str:
        return re.sub(r'\n{3,}', '\n\n', ir)
