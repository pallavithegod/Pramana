"""Local chat API with streamed tool telemetry and disconnect cancellation."""

import asyncio
import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pramana.agent import AgentRuntime, readiness
from pramana.config import Settings
from pramana.errors import PramanaError
from pramana.replay import replay_evidence
from pramana.store import SignalStore
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/api/chat", tags=["Pramana agent"])
REPO_ROOT = Path(__file__).resolve().parents[4]


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=8000)
    history: list[Message] = Field(default_factory=list, max_length=12)


@lru_cache(maxsize=1)
def runtime() -> AgentRuntime:
    settings = Settings.from_env()
    db = settings.runtime_db
    if not db.is_absolute():
        db = REPO_ROOT / db
    return AgentRuntime(settings, SignalStore(db))


@lru_cache(maxsize=1)
def chat_slots() -> asyncio.Semaphore:
    return asyncio.Semaphore(runtime().settings.max_concurrent_chats)


async def acquire_slot():
    slots = chat_slots()
    try:
        await asyncio.wait_for(slots.acquire(), timeout=0.1)
    except TimeoutError:
        raise HTTPException(
            429, detail={"code": "SERVER_BUSY", "message": "Local model is busy; retry shortly"}
        ) from None
    try:
        yield
    finally:
        slots.release()


async def check_ready(agent: AgentRuntime) -> None:
    status = await readiness(agent.settings)
    if status["ollama"] != "ready":
        raise HTTPException(503, detail={"code": "OLLAMA_NOT_READY", "readiness": status})
    if status["serpapi"] != "configured":
        raise HTTPException(503, detail={"code": "MISSING_SERPAPI_KEY", "readiness": status})


@router.get("/status")
async def status() -> dict:
    return await readiness(runtime().settings)


@router.post("", dependencies=[Depends(acquire_slot)])
async def chat(body: ChatRequest) -> dict:
    agent = runtime()
    await check_ready(agent)
    try:
        return await agent.chat(body.message, [m.model_dump() for m in body.history])
    except PramanaError as exc:
        raise HTTPException(
            504 if exc.code == "RUN_TIMEOUT" else 503, detail=exc.as_dict()["error"]
        ) from None


@router.post("/stream")
async def stream(body: ChatRequest, request: Request) -> StreamingResponse:
    agent = runtime()
    await check_ready(agent)
    # Hold the semaphore inside the generator for its entire lifetime. Dependency
    # finalization semantics vary by FastAPI version; don't rely on them for SSE.
    slots = chat_slots()
    try:
        await asyncio.wait_for(slots.acquire(), timeout=0.1)
    except TimeoutError:
        raise HTTPException(429, detail={"code": "SERVER_BUSY"}) from None

    async def events():
        try:
            async for event in agent.events(body.message, [m.model_dump() for m in body.history]):
                if await request.is_disconnected():
                    break
                yield (
                    "event: "
                    + event["type"]
                    + "\ndata: "
                    + json.dumps(event, ensure_ascii=False, allow_nan=False)
                    + "\n\n"
                )
        finally:
            slots.release()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/reports/{run_id}")
def report(run_id: str) -> dict:
    data = runtime().store.report(run_id)
    if data is None:
        raise HTTPException(404, detail={"code": "REPORT_NOT_FOUND"})
    return data


@router.get("/reports/{run_id}/replay")
def replay(run_id: str) -> dict:
    """Recompute saved filter/decision evidence without Ollama or SerpApi calls."""
    data = report(run_id)
    if "evidence" not in data:
        raise HTTPException(
            409,
            detail={"code": "REPLAY_UNAVAILABLE", "message": "This report predates replay capture"},
        )
    try:
        return {"run_id": run_id, **replay_evidence(data["evidence"])}
    except (ValueError, TypeError, KeyError):
        raise HTTPException(409, detail={"code": "INVALID_REPLAY_EVIDENCE"}) from None
