from __future__ import annotations
import os
from typing import List
from ..classify.base import FunctionReport
from ..diff.engine import BlockDiff, FunctionDiff, ModuleDiff


class DotRenderer:
    def render(
        self,
        module_diff: ModuleDiff,
        func_reports: List[FunctionReport],
        out_dir: str,
    ) -> List[str]:
        """
        Write one .dot file per modified/added/removed function to out_dir.
        Returns list of file paths written.
        """
        os.makedirs(out_dir, exist_ok=True)
        written = []
        for fd in module_diff.function_diffs:
            if fd.status == "unchanged":
                continue
            dot = self._render_function(fd)
            name = fd.new_name or fd.old_name
            safe_name = name.replace(".", "_").replace("@", "")
            path = os.path.join(out_dir, f"{safe_name}.dot")
            with open(path, "w") as f:
                f.write(dot)
            written.append(path)
        return written

    def _render_function(self, fd: FunctionDiff) -> str:
        func_name = fd.new_name or fd.old_name
        lines = [
            f'digraph "{func_name}" {{',
            "  node [shape=box fontname=monospace fontsize=10];",
            "  edge [fontsize=9];",
            "",
        ]
        # Build a map of block label -> status and similarity from block_diffs
        block_status: dict = {}
        for bd in fd.block_diffs:
            if bd.status == "added":
                block_status[bd.new_label] = ("added", 1.0)
            elif bd.status == "removed":
                block_status[bd.old_label] = ("removed", 1.0)
            else:
                lbl = bd.new_label or bd.old_label
                block_status[lbl] = ("matched", bd.similarity)
        # Emit nodes
        all_labels = set(block_status.keys()) - {None}
        for lbl in sorted(all_labels):
            status, sim = block_status.get(lbl, ("unchanged", 1.0))
            if status == "added":
                color = "palegreen"
            elif status == "removed":
                color = "lightcoral"
            elif status == "matched" and sim < 1.0:
                color = "lightyellow"
            else:
                color = "white"
            pct = f"{sim:.0%}" if status == "matched" and sim < 1.0 else status
            lines.append(
                f'  "{lbl}" [label="{lbl}\\n{pct}" style=filled fillcolor="{color}"];'
            )
        # Emit edges from block_diffs (matched pairs)
        for bd in fd.block_diffs:
            src = bd.old_label
            dst = bd.new_label
            if src and dst and src != dst:
                lines.append(f'  "{src}" -> "{dst}" [style=dashed color=gray];')
        lines.append("}")
        return "\n".join(lines)
