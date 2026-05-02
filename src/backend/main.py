"""MindFlow Backend API.

FastAPI application providing AI-powered text generation endpoints.
Designed for low-latency interaction with the macOS input method frontend.

Endpoints:
    GET  /health          - Health check
    POST /generate        - Single-shot text generation
    POST /generate/stream - Streaming text generation via Server-Sent Events
    POST /context         - Update session context
    POST /forget          - Clear session or all memory
"""

import json
import logging
import sys
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from .config import settings
from .context_manager import ContextManager
from .intent_classifier import classify, Intent
from .llm_client import (
    LLMClient,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMGenerationError,
)

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("mindflow")


# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

context_manager: Optional[ContextManager] = None
llm_client: Optional[LLMClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize and tear down shared resources."""
    global context_manager, llm_client

    logger.info("Starting MindFlow backend (host=%s, port=%d)", settings.server_host, settings.server_port)

    context_manager = ContextManager()

    if settings.anthropic_api_key:
        try:
            llm_client = LLMClient(
                api_key=settings.anthropic_api_key,
                context_manager=context_manager,
            )
            logger.info("LLM client ready (model=%s)", settings.model_name)
        except LLMAuthenticationError as exc:
            logger.warning("LLM client unavailable: %s", exc)
    else:
        logger.warning(
            "ANTHROPIC_API_KEY not set. LLM generation will be unavailable. "
            "Set ANTHROPIC_API_KEY or MINDFLOW_ANTHROPIC_API_KEY to enable."
        )

    yield

    # Cleanup
    logger.info("MindFlow backend shutting down")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="MindFlow API",
    description="AI-powered input method backend",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS: restrict to localhost origins only (frontend runs locally)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8765",
        "http://127.0.0.1:8765",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "tauri://localhost",  # For potential Tauri-based frontends
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    """Request body for generation endpoints.

    Attributes:
        text: The raw user input (may include ;; trigger prefix).
        intent: Optional explicit intent override (bypasses classifier).
        context: Optional additional context to merge into the session.
    """

    text: str
    intent: Optional[str] = None
    context: Optional[dict] = None


class GenerateResponse(BaseModel):
    """Response body for the non-streaming /generate endpoint."""

    candidate: str
    confidence: float
    model: str = "claude"


class HealthResponse(BaseModel):
    """Response body for the /health endpoint."""

    status: str
    llm_available: bool
    model: Optional[str] = None


class ContextRequest(BaseModel):
    """Request body for the /context endpoint."""

    app_type: Optional[str] = None
    language: Optional[str] = None
    project: Optional[str] = None
    topic: Optional[str] = None


class ForgetRequest(BaseModel):
    """Request body for the /forget endpoint."""

    scope: str = "session"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check returning server status and LLM availability."""
    return HealthResponse(
        status="ok",
        llm_available=llm_client is not None,
        model=settings.model_name if llm_client else None,
    )


@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    """Generate a complete text response (non-streaming).

    The input text is classified by intent, context is gathered from the
    session, and a single response is returned.
    """
    if llm_client is None:
        raise HTTPException(
            status_code=503,
            detail="LLM service unavailable. Set ANTHROPIC_API_KEY.",
        )

    # Classify intent
    parsed = classify(request.text)
    intent = parsed.intent

    # Gather context
    ctx = await context_manager.get_context() if context_manager else {}
    if request.context:
        ctx.update(request.context)

    # Handle target_lang for translate
    if intent == Intent.TRANSLATE and parsed.extra:
        ctx["target_lang"] = parsed.extra

    try:
        result = await llm_client.generate(
            text=parsed.text,
            intent=intent,
            context=ctx,
        )
    except LLMAuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid API key")
    except LLMRateLimitError:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please retry.")
    except LLMGenerationError as exc:
        logger.error("Generation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Generation failed")

    # Record this turn in context history
    if context_manager:
        await context_manager.add_turn(
            user=request.text,
            assistant=result["candidate"],
            intent=intent.value,
        )

    logger.info(
        "Generated response: intent=%s, chars=%d",
        intent.value,
        len(result["candidate"]),
    )

    return GenerateResponse(
        candidate=result["candidate"],
        confidence=result["confidence"],
        model=result.get("model", "claude"),
    )


@app.post("/generate/stream")
async def generate_stream(request: GenerateRequest):
    """Stream text generation via Server-Sent Events.

    Each SSE event contains a JSON payload with either a text chunk or
    a completion signal. Event types:
        - 'chunk': {"text": "..."} -- a partial text fragment
        - 'done':  {"text": "...", "model": "..."} -- final assembled result

    The client should concatenate all 'chunk' payloads to build the full
    response, or use the 'done' event for the complete text.
    """
    if llm_client is None:
        raise HTTPException(
            status_code=503,
            detail="LLM service unavailable. Set ANTHROPIC_API_KEY.",
        )

    # Classify intent
    parsed = classify(request.text)
    intent = parsed.intent

    # Gather context
    ctx = await context_manager.get_context() if context_manager else {}
    if request.context:
        ctx.update(request.context)

    if intent == Intent.TRANSLATE and parsed.extra:
        ctx["target_lang"] = parsed.extra

    async def event_generator():
        """Yield SSE events from the LLM stream."""
        full_text = []
        try:
            async for chunk in llm_client.generate_stream(
                text=parsed.text,
                intent=intent,
                context=ctx,
            ):
                full_text.append(chunk)
                yield {
                    "event": "chunk",
                    "data": json.dumps({"text": chunk}, ensure_ascii=False),
                }

            assembled = "".join(full_text)

            # Record the completed turn
            if context_manager:
                await context_manager.add_turn(
                    user=request.text,
                    assistant=assembled,
                    intent=intent.value,
                )

            yield {
                "event": "done",
                "data": json.dumps(
                    {"text": assembled, "model": settings.model_name},
                    ensure_ascii=False,
                ),
            }

            logger.info(
                "Streamed response: intent=%s, chars=%d",
                intent.value,
                len(assembled),
            )

        except LLMAuthenticationError:
            yield {
                "event": "error",
                "data": json.dumps({"error": "Invalid API key"}),
            }
        except LLMRateLimitError:
            yield {
                "event": "error",
                "data": json.dumps({"error": "Rate limit exceeded"}),
            }
        except LLMGenerationError as exc:
            logger.error("Stream generation failed: %s", exc)
            yield {
                "event": "error",
                "data": json.dumps({"error": "Generation failed"}),
            }

    return EventSourceResponse(event_generator())


@app.post("/context")
async def update_context(request: ContextRequest):
    """Update session context metadata.

    Accepts app_type, language, project, and topic fields.
    Only non-null fields are applied.
    """
    if context_manager:
        await context_manager.update_session(
            app_type=request.app_type,
            language=request.language,
            project=request.project,
            topic=request.topic,
        )
    return {"status": "ok"}


@app.post("/forget")
async def forget(request: ForgetRequest):
    """Clear memory.

    Accepts a scope: 'session' (default) clears the current session,
    'all' clears both session and long-term memory.
    """
    if context_manager:
        await context_manager.forget(request.scope)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Entrypoint for direct execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
        log_level="info",
    )
