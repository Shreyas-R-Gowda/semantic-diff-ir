from __future__ import annotations

import json
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..eval.benchmark import (
    benchmark_to_dict,
    builtin_benchmark_cases,
    render_benchmark_text,
    run_benchmark,
)
from ..pipeline import PipelineConfig, SemanticDiffPipeline
from ..report.renderer import ReportRenderer


class DiffRequest(BaseModel):
    old_ir: str = Field(min_length=1)
    new_ir: str = Field(min_length=1)
    old_label: str = "old.ll"
    new_label: str = "new.ll"
    show_unchanged: bool = False


class DiffResponse(BaseModel):
    report: Dict[str, Any]
    text: str


def create_app() -> FastAPI:
    app = FastAPI(title="Semantic Diff API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/examples")
    def examples() -> List[Dict[str, Any]]:
        return [
            {
                "id": case.id,
                "project": case.project,
                "commit_description": case.commit_description,
                "old_ir": case.old_ir,
                "new_ir": case.new_ir,
                "expected_kinds": sorted(
                    {
                        kind.name
                        for truth in case.ground_truth
                        for kind in truth.expected_kinds
                    }
                ),
            }
            for case in builtin_benchmark_cases()
        ]

    @app.post("/api/diff", response_model=DiffResponse)
    def diff_ir(payload: DiffRequest) -> DiffResponse:
        try:
            pipeline = SemanticDiffPipeline(
                PipelineConfig(show_unchanged=payload.show_unchanged)
            )
            diff_report = pipeline.run_ir_text(
                payload.old_ir,
                payload.new_ir,
                payload.old_label,
                payload.new_label,
            )
            renderer_json = ReportRenderer(show_unchanged=payload.show_unchanged)
            renderer_rich = ReportRenderer(show_unchanged=payload.show_unchanged)
            json_str = renderer_json.render_json(
                diff_report.module_diff,
                diff_report.func_reports,
            )
            rich_str = renderer_rich.render_rich(
                diff_report.module_diff,
                diff_report.func_reports,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return DiffResponse(
            report=json.loads(json_str),
            text=rich_str,
        )

    @app.get("/api/benchmark")
    def benchmark() -> Dict[str, Any]:
        result = run_benchmark()
        out = benchmark_to_dict(result)
        out["text"] = render_benchmark_text(result)
        return out

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run(
        "semantic_diff.web.api:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
