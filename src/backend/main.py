"""MindFlow Backend API.

FastAPI server for AI-powered text generation.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from .intent_classifier import classify, Intent
from .context_manager import ContextManager
from .llm_client import LLMClient


# Global instances
context_manager: Optional[ContextManager] = None
llm_client: Optional[LLMClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global context_manager, llm_client
    context_manager = ContextManager()
    try:
        llm_client = LLMClient()
    except ValueError as e:
        print(f"Warning: {e}")
        print("Set ANTHROPIC_API_KEY to enable LLM generation")
    yield
    # Cleanup if needed


app = FastAPI(
    title="MindFlow API",
    description="AI-powered input method backend",
    version="0.1.0",
    lifespan=lifespan
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    text: str
    intent: Optional[str] = None
    context: Optional[dict] = None


class GenerateResponse(BaseModel):
    candidate: str
    confidence: float
    model: str = "claude"


class HealthResponse(BaseModel):
    status: str
    llm_available: bool


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        llm_available=llm_client is not None
    )


@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    """Generate text continuation.

    Args:
        request: GenerateRequest with text, optional intent, and optional context

    Returns:
        GenerateResponse with candidate text and confidence
    """
    if llm_client is None:
        raise HTTPException(
            status_code=503,
            detail="LLM not available. Set ANTHROPIC_API_KEY."
        )

    # Parse intent
    parsed = classify(request.text)
    intent = parsed.intent

    # Get context
    ctx = context_manager.get_context() if context_manager else {}
    if request.context:
        ctx.update(request.context)

    # Add target_lang for translate intent
    if intent == Intent.TRANSLATE and parsed.extra:
        ctx["target_lang"] = parsed.extra

    try:
        result = await llm_client.generate(
            text=parsed.text,
            intent=intent,
            context=ctx
        )

        # Record this turn in context
        if context_manager:
            context_manager.add_turn(
                user=request.text,
                assistant=result["candidate"],
                intent=intent.value
            )

        return GenerateResponse(
            candidate=result["candidate"],
            confidence=result["confidence"],
            model=result.get("model", "claude")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/context")
async def update_context(app_type: Optional[str] = None,
                         language: Optional[str] = None,
                         project: Optional[str] = None,
                         topic: Optional[str] = None):
    """Update session context."""
    if context_manager:
        context_manager.update_session(
            app_type=app_type,
            language=language,
            project=project,
            topic=topic
        )
    return {"status": "ok"}


@app.post("/forget")
async def forget(scope: str = "session"):
    """Clear memory.

    Args:
        scope: "session" or "all"
    """
    if context_manager:
        context_manager.forget(scope)
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
