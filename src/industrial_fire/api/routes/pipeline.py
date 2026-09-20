from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from industrial_fire.api.dependencies import get_continuous_pipeline
from industrial_fire.api.schemas.pipeline import PipelineStatusResponse
from industrial_fire.application.pipeline.continuous_pipeline import ContinuousPipeline

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get("/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    pipeline: Annotated[ContinuousPipeline, Depends(get_continuous_pipeline)],
) -> PipelineStatusResponse:
    """Console readout for the dashboard: last poll time, hotspots processed, last error."""
    return PipelineStatusResponse(**pipeline.status.snapshot())
