from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List


class ChangeKind(Enum):
    LOOP_UNROLL_GAINED      = auto()
    LOOP_UNROLL_LOST        = auto()
    VECTORIZE_GAINED        = auto()
    VECTORIZE_LOST          = auto()
    VECTORIZE_WIDTH_CHANGE  = auto()
    RUNTIME_CHECK_ADDED     = auto()
    INLINING_ADDED          = auto()
    INLINING_REMOVED        = auto()
    DEAD_CODE_ELIMINATED    = auto()
    DEAD_CODE_REINTRODUCED  = auto()
    BRANCH_ADDED            = auto()
    BRANCH_REMOVED          = auto()
    LOOP_ADDED              = auto()
    LOOP_REMOVED            = auto()
    CFG_COMPLEXITY_UP       = auto()
    CFG_COMPLEXITY_DOWN     = auto()
    LOAD_COUNT_CHANGED      = auto()
    STORE_COUNT_CHANGED     = auto()
    ALLOCA_CHANGED          = auto()
    MEM_DEP_CHANGED         = auto()
    INSTR_COUNT_UP          = auto()
    INSTR_COUNT_DOWN        = auto()
    CRITICAL_PATH_LONGER    = auto()
    CRITICAL_PATH_SHORTER   = auto()


@dataclass
class SemanticChange:
    kind:      ChangeKind
    description: str
    severity:  str = "info"
    details:   str = ""


@dataclass
class FunctionReport:
    func_name: str
    changes:   List[SemanticChange] = field(default_factory=list)

    def add(self, kind: ChangeKind, desc: str,
            severity: str = "info", details: str = ""):
        self.changes.append(SemanticChange(kind, desc, severity, details))

    @property
    def has_changes(self) -> bool:
        return bool(self.changes)
