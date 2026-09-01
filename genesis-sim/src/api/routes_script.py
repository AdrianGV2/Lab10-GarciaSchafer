"""Endpoints for running the Python written in the editor's Python tab."""

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/script", tags=["python_script"])


class ScriptBody(BaseModel):
    source: str


def _runner(request: Request):
    runner = getattr(request.app.state, "script_runner", None)
    if runner is None:
        raise HTTPException(
            status_code=503, detail="Script execution is disabled on this server."
        )
    return runner


@router.post("/run")
def run_script(request: Request, body: ScriptBody):
    try:
        _runner(request).run(body.source)
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error))
    return {"status": "running"}


@router.post("/stop")
def stop_script(request: Request):
    _runner(request).stop()
    return {"status": "stopped"}


@router.get("/output")
def script_output(request: Request, since: int = 0):
    return _runner(request).poll(since)
