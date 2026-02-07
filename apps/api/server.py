"""
HR Agent API Server

A FastAPI-based REST API for the HR Agent, enabling integration with
web frontends, Slack bots, Microsoft Teams, and other applications.

Built with LangGraph for agent orchestration.
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

from hr_agent.agent.langgraph_agent import HRAgentLangGraph, run_hr_agent
from hr_agent.seed import seed_if_needed
from hr_agent.configs.config import settings
from hr_agent.utils.security import rate_limiter, audit_logger, AuditAction
from hr_agent.tracing.observability import logger, metrics
from hr_agent.utils.errors import HRAgentError, RateLimitError
from hr_agent.repositories.employee import EmployeeRepository


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
    description="An intelligent HR assistant API powered by LangGraph",
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
# SESSION STORAGE (In-memory for demo, use Redis in production)
# ============================================================================

_sessions: dict[str, dict] = {}


def get_or_create_session(session_id: str | None, user_email: str) -> tuple[str, dict]:
    """Get or create a session for the user."""
    if session_id and session_id in _sessions:
        session = _sessions[session_id]
        if session["user_email"] == user_email:
            return session_id, session

    # Create new session
    new_session_id = session_id or str(uuid.uuid4())
    _sessions[new_session_id] = {
        "user_email": user_email,
        "created_at": datetime.utcnow(),
        "turns": [],
        "pending_confirmation": None,
    }
    return new_session_id, _sessions[new_session_id]


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
    from hr_agent.utils.errors import (
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


def get_requester_context(user_email: str) -> dict:
    """Get the context for the requesting user."""
    employee_repo = EmployeeRepository()
    employee = employee_repo.get_by_email(user_email)

    if not employee:
        raise ValueError(f"User {user_email} not found")

    direct_reports = employee_repo.get_direct_reports(employee["employee_id"])

    return {
        "employee_id": employee["employee_id"],
        "user_email": employee["email"],
        "name": employee["preferred_name"] or employee.get("legal_name", "Unknown"),
        "role": employee["title"],
        "department": employee["department"],
        "direct_reports": [r["employee_id"] for r in direct_reports],
        "is_manager": len(direct_reports) > 0,
    }


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
    Uses LangGraph for agent orchestration.
    """
    try:
        session_id, session = get_or_create_session(
            request.session_id, user["user_email"]
        )

        # Run the LangGraph agent
        response = run_hr_agent(
            user_email=user["user_email"],
            question=request.message,
        )

        # Store the turn
        session["turns"].append(
            {
                "query": request.message,
                "response": response,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        return ChatResponse(
            response=response,
            session_id=session_id,
            timestamp=datetime.now().isoformat(),
        )
    except (ValueError, TypeError, KeyError) as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}") from e


@app.post("/sessions", response_model=SessionInfo, tags=["Sessions"])
async def create_new_session(user: dict = Depends(get_current_user)):
    """Create a new conversation session."""
    session_id, session = get_or_create_session(None, user["user_email"])

    return SessionInfo(
        session_id=session_id,
        user_email=user["user_email"],
        created_at=session["created_at"].isoformat(),
        turn_count=0,
        has_pending_confirmation=False,
    )


@app.get("/sessions/{session_id}", response_model=SessionInfo, tags=["Sessions"])
async def get_session_info(session_id: str, user: dict = Depends(get_current_user)):
    """Get information about a conversation session."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = _sessions[session_id]
    if session["user_email"] != user["user_email"]:
        raise HTTPException(status_code=403, detail="Access denied to this session")

    return SessionInfo(
        session_id=session_id,
        user_email=session["user_email"],
        created_at=session["created_at"].isoformat(),
        turn_count=len(session["turns"]),
        has_pending_confirmation=session["pending_confirmation"] is not None,
    )


@app.delete("/sessions/{session_id}", tags=["Sessions"])
async def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    """Delete a conversation session."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = _sessions[session_id]
    if session["user_email"] != user["user_email"]:
        raise HTTPException(status_code=403, detail="Access denied to this session")

    del _sessions[session_id]
    return {"message": "Session deleted successfully"}


@app.get("/sessions", response_model=list[SessionInfo], tags=["Sessions"])
async def list_my_sessions(user: dict = Depends(get_current_user)):
    """List all sessions for the current user."""
    user_sessions = [
        SessionInfo(
            session_id=sid,
            user_email=s["user_email"],
            created_at=s["created_at"].isoformat(),
            turn_count=len(s["turns"]),
            has_pending_confirmation=s["pending_confirmation"] is not None,
        )
        for sid, s in _sessions.items()
        if s["user_email"] == user["user_email"]
    ]
    return user_sessions


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
    from hr_agent.utils.db import get_engine

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

    # Check LLM
    health["checks"]["llm"] = {
        "status": "configured",
        "model": settings.llm_model,
        "provider": settings.llm_provider,
    }

    # Check Langfuse tracing
    if settings.langfuse_enabled and settings.langfuse_public_key:
        health["checks"]["langfuse"] = {
            "status": "enabled",
            "host": settings.langfuse_host,
        }
    else:
        health["checks"]["langfuse"] = {"status": "disabled"}

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
