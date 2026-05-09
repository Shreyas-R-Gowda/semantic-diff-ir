from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


class Opcode(str, Enum):
    # Memory
    LOAD     = "load"
    STORE    = "store"
    ALLOCA   = "alloca"
    GEP      = "getelementptr"
    # Control
    BR       = "br"
    RET      = "ret"
    SWITCH   = "switch"
    INVOKE   = "invoke"
    UNREACHABLE = "unreachable"
    # Calls
    CALL     = "call"
    # Integer arithmetic
    ADD      = "add"
    SUB      = "sub"
    MUL      = "mul"
    SDIV     = "sdiv"
    UDIV     = "udiv"
    SREM     = "srem"
    UREM     = "urem"
    # Float arithmetic
    FADD     = "fadd"
    FSUB     = "fsub"
    FMUL     = "fmul"
    FDIV     = "fdiv"
    FREM     = "frem"
    FNEG     = "fneg"
    # Bitwise
    SHL      = "shl"
    LSHR     = "lshr"
    ASHR     = "ashr"
    AND      = "and"
    OR       = "or"
    XOR      = "xor"
    # Compare
    ICMP     = "icmp"
    FCMP     = "fcmp"
    # SSA / select
    PHI      = "phi"
    SELECT   = "select"
    # Casts
    TRUNC    = "trunc"
    ZEXT     = "zext"
    SEXT     = "sext"
    FPTRUNC  = "fptrunc"
    FPEXT    = "fpext"
    FPTOUI   = "fptoui"
    FPTOSI   = "fptosi"
    UITOFP   = "uitofp"
    SITOFP   = "sitofp"
    BITCAST  = "bitcast"
    PTRTOINT = "ptrtoint"
    INTTOPTR = "inttoptr"
    ADDRSPACECAST = "addrspacecast"
    # Aggregate
    EXTRACTVALUE  = "extractvalue"
    INSERTVALUE   = "insertvalue"
    # Vector
    EXTRACTELEMENT = "extractelement"
    INSERTELEMENT  = "insertelement"
    SHUFFLEVECTOR  = "shufflevector"
    # Atomic
    ATOMICRMW  = "atomicrmw"
    CMPXCHG    = "cmpxchg"
    FENCE      = "fence"
    # Misc
    LANDINGPAD = "landingpad"
    RESUME     = "resume"
    OTHER      = "_other"

    @classmethod
    def from_str(cls, s: str) -> "Opcode":
        s = s.lower().split()[0]   # strip "tail"/"musttail" prefix
        for member in cls:
            if member.value == s:
                return member
        return cls.OTHER

    @property
    def is_memory(self) -> bool:
        return self in (Opcode.LOAD, Opcode.STORE, Opcode.ALLOCA, Opcode.GEP)

    @property
    def is_terminator(self) -> bool:
        return self in (
            Opcode.BR, Opcode.RET, Opcode.SWITCH, Opcode.INVOKE,
            Opcode.UNREACHABLE, Opcode.RESUME,
        )

    @property
    def is_call(self) -> bool:
        return self in (Opcode.CALL, Opcode.INVOKE)

    @property
    def is_arith(self) -> bool:
        return self in (
            Opcode.ADD, Opcode.SUB, Opcode.MUL,
            Opcode.SDIV, Opcode.UDIV, Opcode.SREM, Opcode.UREM,
            Opcode.FADD, Opcode.FSUB, Opcode.FMUL, Opcode.FDIV,
        )

    @property
    def is_commutative(self) -> bool:
        return self in (
            Opcode.ADD, Opcode.MUL, Opcode.AND, Opcode.OR, Opcode.XOR,
            Opcode.FADD, Opcode.FMUL,
        )

    @property
    def is_vector_op(self) -> bool:
        return self in (
            Opcode.EXTRACTELEMENT, Opcode.INSERTELEMENT, Opcode.SHUFFLEVECTOR,
        )


@dataclass
class Instruction:
    opcode_str: str           # raw opcode string (may have prefix like "tail")
    result:     Optional[str] # LHS %name or None for void
    type_str:   str           # LLVM type string
    operands:   List[str]     # value references extracted from RHS
    raw:        str           # verbatim source line (stripped)
    block:      str = ""      # owning block label (set by parser)

    @property
    def opcode(self) -> Opcode:
        return Opcode.from_str(self.opcode_str)

    @property
    def is_vector(self) -> bool:
        import re
        return bool(re.search(r'<\d+\s*x\s*\w+>', self.type_str + self.raw))

    @property
    def vector_width(self) -> int:
        import re
        m = re.search(r'<(\d+)\s*x\s*\w+>', self.type_str + self.raw)
        return int(m.group(1)) if m else 0

    @property
    def callee(self) -> Optional[str]:
        """Return callee name for call instructions."""
        import re
        if self.opcode.is_call:
            m = re.search(r'@([\w.$]+)\s*\(', self.raw)
            return m.group(1) if m else None
        return None

    def opcode_fingerprint(self) -> str:
        """Type-erased fingerprint for similarity comparison."""
        base = self.opcode.value
        if self.is_vector:
            base += f"<{self.vector_width}>"
        return base


@dataclass
class BasicBlock:
    label:        str
    instructions: List[Instruction] = field(default_factory=list)
    successors:   List[str]         = field(default_factory=list)
    predecessors: List[str]         = field(default_factory=list)

    @property
    def terminator(self) -> Optional[Instruction]:
        return self.instructions[-1] if self.instructions else None

    def instr_count(self) -> int:
        return len(self.instructions)

    def count_opcode(self, op: Opcode) -> int:
        return sum(1 for i in self.instructions if i.opcode == op)

    def vector_width(self) -> int:
        widths = [i.vector_width for i in self.instructions if i.is_vector]
        return max(widths, default=0)

    def fingerprint(self) -> str:
        """Opcode-sequence fingerprint, order-preserving."""
        return "|".join(i.opcode_fingerprint() for i in self.instructions)

    def opcode_tokens(self) -> List[str]:
        """Fingerprint as list of tokens (for token-level SequenceMatcher)."""
        return [i.opcode_fingerprint() for i in self.instructions]

    def structural_key(self) -> tuple:
        """
        A lightweight key for fuzzy block matching.
        Uses (terminator opcode, successor count, total instrs, phi count).
        """
        term_op = self.terminator.opcode.value if self.terminator else "none"
        phi_cnt = self.count_opcode(Opcode.PHI)
        return (term_op, len(self.successors), self.instr_count(), phi_cnt)


@dataclass
class LoopInfo:
    header:        str
    body:          Set[str]
    back_edges:    List[Tuple[str, str]]
    depth:         int            = 0
    trip_count:    Optional[int]  = None
    unroll_factor: Optional[int]  = None
    vector_width:  int            = 0
    has_runtime_check: bool       = False
    # IV analysis
    iv_stride:     int            = 1    # induction variable increment per iteration
    phi_count:     int            = 0    # phi nodes in header

    def body_signature(self) -> tuple:
        """
        Structural signature for loop matching across function versions.
        Stable even when block labels change due to code insertion.
        Uses (body_size, phi_count, vector_width, trip_count).
        """
        return (len(self.body), self.phi_count, self.vector_width, self.trip_count)


@dataclass
class Function:
    name:          str
    return_type:   str
    params:        List[Tuple[str, str]]   # [(type, name), ...]
    basic_blocks:  Dict[str, BasicBlock]   = field(default_factory=dict)
    attributes:    List[str]               = field(default_factory=list)
    is_declaration: bool                   = False

    @property
    def entry_block(self) -> Optional[BasicBlock]:
        return next(iter(self.basic_blocks.values()), None)

    def total_instructions(self) -> int:
        return sum(b.instr_count() for b in self.basic_blocks.values())

    def all_instructions(self):
        for b in self.basic_blocks.values():
            yield from b.instructions

    def count_opcode(self, op: Opcode) -> int:
        return sum(b.count_opcode(op) for b in self.basic_blocks.values())

    def calls(self) -> List[str]:
        return [i.callee for i in self.all_instructions()
                if i.opcode.is_call and i.callee]

    def has_vector_ops(self) -> bool:
        return any(i.is_vector for i in self.all_instructions())

    def opcode_histogram(self) -> Dict[str, int]:
        hist: Dict[str, int] = {}
        for i in self.all_instructions():
            hist[i.opcode.value] = hist.get(i.opcode.value, 0) + 1
        return hist


@dataclass
class IRModule:
    source_file:  str
    functions:    Dict[str, Function] = field(default_factory=dict)
    global_vars:  List[str]           = field(default_factory=list)
    raw_ir:       str                 = ""

    def defined_functions(self) -> Dict[str, Function]:
        return {n: f for n, f in self.functions.items() if not f.is_declaration}
