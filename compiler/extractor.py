from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple


class CompilationError(Exception):
    pass


class IRExtractor:
    def __init__(self, clang: str = "clang", opt: str = "opt"):
        self.clang = clang
        self.opt   = opt
        self._check_tools()

    def _check_tools(self):
        missing = [t for t in (self.clang, self.opt) if not shutil.which(t)]
        if missing:
            raise RuntimeError(
                f"Required tools not found: {missing}\n"
                "Install with:  brew install llvm  |  apt install clang llvm"
            )

    def extract(
        self,
        source: str,
        opt_level: str = "O0",
        extra_cflags: Optional[List[str]] = None,
        promote_mem: bool = True,
    ) -> str:
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(source)

        with tempfile.TemporaryDirectory() as td:
            ir_path = os.path.join(td, "out.ll")
            self._compile(path, ir_path, opt_level, extra_cflags or [])
            if promote_mem:
                promoted = os.path.join(td, "promoted.ll")
                self._run_opt(ir_path, promoted, ["mem2reg", "sroa", "early-cse"])
                ir_path = promoted
            return Path(ir_path).read_text()

    def extract_pair(
        self,
        old_src: str,
        new_src: str,
        opt_level: str = "O0",
    ) -> Tuple[str, str]:
        return (
            self.extract(old_src, opt_level),
            self.extract(new_src, opt_level),
        )

    def _compile(self, src: Path, out: str, opt_level: str, extra: List[str]):
        lang = self._detect_lang(src)
        cmd = [
            self.clang,
            f"-{opt_level}",
            "-S", "-emit-llvm",
            "-fno-discard-value-names",
            *(["-x", lang] if lang else []),
            str(src),
            "-o", out,
            *extra,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            raise CompilationError(f"clang failed on {src}:\n{r.stderr}")

    def _run_opt(self, src: str, dst: str, passes: List[str]):
        pass_arg = ",".join(passes)
        for argv in [
            [self.opt, f"-passes={pass_arg}", "-S", src, "-o", dst],
            [self.opt, *[f"-{p}" for p in passes], "-S", src, "-o", dst],
        ]:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=120)
            if r.returncode == 0:
                return
        shutil.copy(src, dst)

    @staticmethod
    def _detect_lang(path: Path) -> Optional[str]:
        return {
            ".c":   "c",
            ".cpp": "c++", ".cc": "c++", ".cxx": "c++",
        }.get(path.suffix.lower())
