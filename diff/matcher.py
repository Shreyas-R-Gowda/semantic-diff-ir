"""
Function-level matching between two IRModule versions.

Matching stages (in order, first match wins):
  1. Exact name          → confidence 1.0
  2. Signature score     ≥ SIG_THRESHOLD
  3. Histogram cosine    ≥ HIST_THRESHOLD  (new: catches renamed functions
                                           with same opcode distribution)
  4. Body fingerprint    ≥ BODY_THRESHOLD

Thresholds are conservative: we prefer false negatives (unmatched)
over false positives (wrongly-matched functions).

Histogram cosine similarity (stage 3) is the key new addition.
Two functions that do the same computation but got renamed (e.g., during
a refactor that adds a namespace prefix) will have nearly identical opcode
distributions and should be matched.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, List, Set, Tuple

from ..parser.types import Function, IRModule


@dataclass
class FunctionMatch:
    old_name:   str
    new_name:   str
    confidence: float
    reason:     str   # 'exact' | 'signature' | 'histogram' | 'body'


MatchResult = Tuple[List[FunctionMatch], List[str], List[str]]


class FunctionMatcher:

    SIG_THRESHOLD  = 0.70
    HIST_THRESHOLD = 0.90   # high bar: histogram alone is a weak signal
    BODY_THRESHOLD = 0.60

    def match(self, old: IRModule, new: IRModule) -> MatchResult:
        old_defs = old.defined_functions()
        new_defs = new.defined_functions()

        matches:     List[FunctionMatch] = []
        matched_old: Set[str]            = set()
        matched_new: Set[str]            = set()

        # Stage 1: exact name
        for name in old_defs:
            if name in new_defs:
                matches.append(FunctionMatch(name, name, 1.0, "exact"))
                matched_old.add(name)
                matched_new.add(name)

        # Stage 2: signature similarity
        rem_old = {n: f for n, f in old_defs.items() if n not in matched_old}
        rem_new = {n: f for n, f in new_defs.items() if n not in matched_new}
        self._match_stage(rem_old, rem_new, matched_old, matched_new,
                          matches, self._sig_score, self.SIG_THRESHOLD, "signature")

        # Stage 3: histogram cosine similarity (catches renamed functions)
        rem_old = {n: f for n, f in old_defs.items() if n not in matched_old}
        rem_new = {n: f for n, f in new_defs.items() if n not in matched_new}
        self._match_stage(rem_old, rem_new, matched_old, matched_new,
                          matches, self._hist_score, self.HIST_THRESHOLD, "histogram")

        # Stage 4: body fingerprint
        rem_old = {n: f for n, f in old_defs.items() if n not in matched_old}
        rem_new = {n: f for n, f in new_defs.items() if n not in matched_new}
        self._match_stage(rem_old, rem_new, matched_old, matched_new,
                          matches, self._body_score, self.BODY_THRESHOLD, "body")

        added   = [n for n in new_defs if n not in matched_new]
        removed = [n for n in old_defs if n not in matched_old]
        return matches, added, removed

    # ── scoring ───────────────────────────────────────────────────────────────

    def _sig_score(self, a: Function, b: Function) -> float:
        score = 0.0
        if a.return_type == b.return_type:
            score += 0.35
        if len(a.params) == len(b.params):
            score += 0.35
            if a.params:
                hits = sum(
                    1 for (ta, _), (tb, _) in zip(a.params, b.params) if ta == tb
                )
                score += 0.20 * (hits / len(a.params))
        old_sz, new_sz = a.total_instructions(), b.total_instructions()
        if old_sz + new_sz:
            score += 0.10 * min(old_sz, new_sz) / max(old_sz, new_sz)
        return score

    def _hist_score(self, a: Function, b: Function) -> float:
        """
        Cosine similarity of opcode frequency vectors.
        Invariant to function size (normalized).  High cosine means the
        two functions perform the same kinds of operations in similar
        proportions — a strong (though not sufficient) match signal.
        """
        ha = a.opcode_histogram()
        hb = b.opcode_histogram()
        if not ha or not hb:
            return 0.0
        keys = set(ha) | set(hb)
        dot  = sum(ha.get(k, 0) * hb.get(k, 0) for k in keys)
        na   = math.sqrt(sum(v*v for v in ha.values()))
        nb   = math.sqrt(sum(v*v for v in hb.values()))
        if na == 0 or nb == 0:
            return 0.0
        cosine = dot / (na * nb)
        # Also require similar total instruction counts (within 30%)
        old_sz, new_sz = a.total_instructions(), b.total_instructions()
        if old_sz + new_sz == 0:
            return 0.0
        size_ratio = min(old_sz, new_sz) / max(old_sz, new_sz)
        if size_ratio < 0.70:
            cosine *= size_ratio   # penalize large size mismatch
        return cosine

    def _body_score(self, a: Function, b: Function) -> float:
        return SequenceMatcher(None, self._fp_tokens(a), self._fp_tokens(b)).ratio()

    def _fp_tokens(self, f: Function) -> List[str]:
        return [
            i.opcode.value
            for blk in f.basic_blocks.values()
            for i in blk.instructions
        ]

    # ── helpers ───────────────────────────────────────────────────────────────

    def _match_stage(
        self,
        old: Dict[str, Function],
        new: Dict[str, Function],
        matched_old: Set[str],
        matched_new: Set[str],
        out: List[FunctionMatch],
        score_fn,
        threshold: float,
        reason: str,
    ):
        used_new: Set[str] = set()
        candidates = []
        for on, of in old.items():
            for nn, nf in new.items():
                if nn in used_new:
                    continue
                s = score_fn(of, nf)
                if s >= threshold:
                    candidates.append((s, on, nn))

        candidates.sort(reverse=True)
        for s, on, nn in candidates:
            if on in matched_old or nn in matched_new or nn in used_new:
                continue
            out.append(FunctionMatch(on, nn, s, reason))
            matched_old.add(on)
            matched_new.add(nn)
            used_new.add(nn)
