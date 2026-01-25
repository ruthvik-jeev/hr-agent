"""
HR Agent API Server

A FastAPI-based REST API for the HR Agent, enabling integration with
web frontends, Slack bots, Microsoft Teams, and other applications.
"""

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
import uvicorn
import uuid

from ..core.agent import HRAgent, get_requester_context
from ..core.memory import get_memory_store
from ..seed import seed_if_needed
from ..infrastructure.config import settings
from ..infrastructure.security import rate_limiter, audit_logger, AuditAction
from ..infrastructure.observability import logger, metrics
from ..infrastructure.errors import HRAgentError, RateLimitError


# ============================================================================
# API MODELS
# ============================================================================


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""

    message: str = Field(..., description="The user's message/question")
    session_id: Optional[str] = Field(
        None, description="Session ID for conversation continuity"
    )


class ChatResponse(BaseModel):
    """Response body for chat endpoint."""

    response: str = Field(..., description="The agent's response")
    session_id: str = Field(..., description="Session ID for follow-up messages")
    timestamp: str = Field(..., description="Response timestamp")


class SessionInfo(BaseModel):
    """Session information response."""

    session_id: str
    user_email: str
    created_at: str
    turn_count: int
    has_pending_confirmation: bool


class UserContext(BaseModel):
    """User context information."""

    employee_id: int
    name: str
    email: str
    role: str
    direct_reports_count: int


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: str
    version: str = "2.0.0"


# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="HR Agent API",
    description="An intelligent HR assistant API for ACME Corporation",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for web frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# MIDDLEWARE
# ============================================================================


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    """Add request tracking, logging, and rate limiting."""
    request_id = str(uuid.uuid4())
    start_time = datetime.utcnow()

    # Set request context for logging
    logger.set_context(request_id=request_id)

    # Log request
    logger.info(
        "Request started",
        method=request.method,
        path=request.url.path,
    )

    try:
        response = await call_next(request)

        # Calculate duration
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Log response
        logger.info(
            "Request completed",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        # Record metrics
        metrics.histogram(
            "api.latency_ms", duration_ms, tags={"path": request.url.path}
        )
        metrics.increment(
            "api.requests",
            tags={"path": request.url.path, "status": str(response.status_code)},
        )

        # Add headers
        response.headers["X-Request-ID"] = request_id

        return response
    except Exception as e:
        logger.error("Request failed", error=str(e))
        raise


# ============================================================================
# ERROR HANDLERS
# ============================================================================


@app.exception_handler(HRAgentError)
async def hr_agent_error_handler(_request: Request, exc: HRAgentError):
    """Handle custom HR Agent errors."""
    return JSONResponse(
        status_code=_get_status_code(exc),
        content=exc.to_dict(),
    )


@app.exception_handler(RateLimitError)
async def rate_limit_error_handler(_request: Request, exc: RateLimitError):
    """Handle rate limit errors with proper headers."""
    return JSONResponse(
        status_code=429,
        content=exc.to_dict(),
        headers={"Retry-After": str(exc.details.get("retry_after_seconds", 60))},
    )


def _get_status_code(exc: HRAgentError) -> int:
    """Map exception types to HTTP status codes."""
    from ..infrastructure.errors import (
        AuthorizationError,
        ValidationError,
        ResourceNotFoundError,
    )

    if isinstance(exc, AuthorizationError):
        return 403
    elif isinstance(exc, ValidationError):
        return 400
    elif isinstance(exc, ResourceNotFoundError):
        return 404
    return 500


# ============================================================================
# AUTHENTICATION (Simplified for demo)
# ============================================================================


async def get_current_user(
    request: Request, x_user_email: str = Header(..., alias="X-User-Email")
) -> dict:
    """
    Extract the current user from the request header.
    With rate limiting and audit logging.
    """
    # Rate limit check
    allowed, _info = rate_limiter.is_allowed(x_user_email)
    if not allowed:
        raise RateLimitError("API", retry_after=60)

    try:
        context = get_requester_context(x_user_email)

        # Audit login/access
        audit_logger.log(
            action=AuditAction.LOGIN,
            user_email=x_user_email,
            resource_type="api",
            ip_address=request.client.host if request.client else None,
        )

        return context
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except (TypeError, KeyError) as e:
        raise HTTPException(
            status_code=500, detail=f"Authentication error: {str(e)}"
        ) from e


# ============================================================================
# STARTUP EVENT
# ============================================================================


@app.on_event("startup")
async def startup_event():
    """Initialize the database on startup."""
    seed_if_needed()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def create_session(user_email: str) -> str:
    """Create a new conversation session and return its ID."""
    session_id = str(uuid.uuid4())
    memory_store = get_memory_store()
    memory_store.get_or_create_session(session_id, user_email)
    return session_id


# ============================================================================
# ENDPOINTS
# ============================================================================


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check the health of the API."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
    )


@app.get("/me", response_model=UserContext, tags=["User"])
async def get_my_info(user: dict = Depends(get_current_user)):
    """Get the current user's context information."""
    return UserContext(
        employee_id=user["employee_id"],
        name=user["name"],
        email=user["user_email"],
        role=user["role"],
        direct_reports_count=len(user.get("direct_reports", [])),
    )


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest, user: dict = Depends(get_current_user)):
    """
    Send a message to the HR Agent and get a response.

    Supports multi-turn conversations using session_id.
    """
    try:
        agent = HRAgent(user["user_email"], request.session_id)
        response = agent.chat(request.message)

        return ChatResponse(
            response=response,
            session_id=agent.session_id,
            timestamp=datetime.now().isoformat(),
        )
    except (ValueError, TypeError, KeyError) as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}") from e


@app.post("/sessions", response_model=SessionInfo, tags=["Sessions"])
async def create_new_session(user: dict = Depends(get_current_user)):
    """Create a new conversation session."""
    session_id = create_session(user["user_email"])
    memory_store = get_memory_store()
    session = memory_store.get_session(session_id)

    if not session:
        raise HTTPException(status_code=500, detail="Failed to create session")

    return SessionInfo(
        session_id=session_id,
        user_email=user["user_email"],
        created_at=session.created_at.isoformat(),
        turn_count=0,
        has_pending_confirmation=False,
    )


@app.get("/sessions/{session_id}", response_model=SessionInfo, tags=["Sessions"])
async def get_session_info(session_id: str, user: dict = Depends(get_current_user)):
    """Get information about a conversation session."""
    memory_store = get_memory_store()
    session = memory_store.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_email != user["user_email"]:
        raise HTTPException(status_code=403, detail="Access denied to this session")

    return SessionInfo(
        session_id=session.session_id,
        user_email=session.user_email,
        created_at=session.created_at.isoformat(),
        turn_count=len(session.turns),
        has_pending_confirmation=session.has_pending_confirmation(),
    )


@app.delete("/sessions/{session_id}", tags=["Sessions"])
async def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    """Delete a conversation session."""
    memory_store = get_memory_store()
    session = memory_store.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_email != user["user_email"]:
        raise HTTPException(status_code=403, detail="Access denied to this session")

    memory_store.delete_session(session_id)
    return {"message": "Session deleted successfully"}


@app.get("/sessions", response_model=list[SessionInfo], tags=["Sessions"])
async def list_my_sessions(user: dict = Depends(get_current_user)):
    """List all sessions for the current user."""
    memory_store = get_memory_store()
    sessions = memory_store.list_sessions(user["user_email"])

    return [
        SessionInfo(
            session_id=s.session_id,
            user_email=s.user_email,
            created_at=s.created_at.isoformat(),
            turn_count=len(s.turns),
            has_pending_confirmation=s.has_pending_confirmation(),
        )
        for s in sessions
    ]


# ============================================================================
# METRICS ENDPOINT
# ============================================================================


@app.get("/metrics", tags=["System"])
async def get_metrics():
    """Get current metrics (for Prometheus scraping or debugging)."""
    return metrics.get_stats()


@app.get("/health/detailed", tags=["System"])
async def detailed_health_check():
    """Detailed health check with dependency status."""
    from ..infrastructure.db import get_engine

    health = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "checks": {},
    }

    # Check database
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health["checks"]["database"] = {"status": "healthy"}
    except (SQLAlchemyError, OSError) as e:
        health["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
        health["status"] = "degraded"

    # Check LLM (optional - don't fail if unavailable)
    try:
        from ..core.llm import get_client

        get_client()  # Verify client can be created
        health["checks"]["llm"] = {"status": "configured", "model": settings.llm_model}
    except (ImportError, ValueError, OSError) as e:
        health["checks"]["llm"] = {"status": "unavailable", "error": str(e)}

    return health


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


def main():
    """Run the API server."""
    uvicorn.run(
        "hr_agent.api:app",
        host=settings.api_host if hasattr(settings, "api_host") else "0.0.0.0",
        port=settings.api_port if hasattr(settings, "api_port") else 8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
