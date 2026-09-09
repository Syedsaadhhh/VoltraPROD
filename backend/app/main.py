"""FastAPI Application Entry Point for Sound Rehearsal.

Serves REST endpoints, runs the MCP lifecycle, and delivers the built React UI.
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.models import (
    Session,
    EditBatch,
    ToolResult,
    PlaybackAck,
    AuditionFeedback,
    ToolResultStatus,
)
from app.auth import verify_user, assert_session_ownership
from app.firestore_store import firestore_store
from app.mcp_client import clickhouse_mcp
from app.event_sink import record_playback_ack, record_audition_feedback

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("sound_rehearsal")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle context manager handling startup and graceful shutdown."""
    logger.info("Starting Sound Rehearsal Backend...")
    yield
    logger.info("Shutting down Sound Rehearsal Backend; cleaning up MCP connections...")
    await clickhouse_mcp.close()


app = FastAPI(
    title="Sound Rehearsal API",
    description="Browser sound-design rehearsal agent with Gemini, ClickHouse MCP, and Firestore",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def health_check() -> Dict[str, Any]:
    """Public health endpoint required for container and deployment liveness probes."""
    return {
        "status": "ok",
        "app": "sound-rehearsal",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/api/status", tags=["system"])
async def system_status() -> Dict[str, Any]:
    """Detailed diagnostic status of all backend integrations without exposing secret values."""
    status_report = settings.get_credential_status()

    # Add runtime availability states
    status_report["gemini"]["available"] = settings.is_gemini_configured
    status_report["clickhouse"]["available"] = settings.is_clickhouse_configured
    status_report["firestore"]["available"] = firestore_store.is_available

    return {
        "app": "sound-rehearsal",
        "version": "0.1.0",
        "integrations": status_report,
    }


@app.post("/api/sessions", tags=["sessions"], response_model=Session)
async def create_session(
    session: Session,
    current_uid: str = Depends(verify_user),
) -> Session:
    """Create a new authoritative rehearsal session."""
    session.owner_uid = current_uid
    try:
        created = await firestore_store.create_session(session)
        return created
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}",
        )


@app.get("/api/sessions/{session_id}", tags=["sessions"], response_model=Session)
async def get_session(
    session_id: str,
    current_uid: str = Depends(verify_user),
) -> Session:
    """Fetch current rehearsal session state."""
    try:
        session = await firestore_store.get_session(session_id)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' not found",
            )
        assert_session_ownership(session.owner_uid, current_uid)
        return session
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read session: {str(e)}",
        )


@app.post("/api/sessions/{session_id}/edits", tags=["sessions"], response_model=ToolResult)
async def apply_edits(
    session_id: str,
    batch: EditBatch,
    current_uid: str = Depends(verify_user),
) -> ToolResult:
    """Apply an atomic edit batch enforcing optimistic revision checks and idempotency."""
    if batch.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path session_id '{session_id}' does not match batch session_id '{batch.session_id}'",
        )
    return await firestore_store.apply_edit_batch(batch, owner_uid=current_uid)


@app.post("/api/sessions/{session_id}/playback-ack", tags=["events"])
async def acknowledge_playback(
    session_id: str,
    ack: PlaybackAck,
    current_uid: str = Depends(verify_user),
) -> Dict[str, Any]:
    """Record browser playback and media decode acknowledgement."""
    recorded = await record_playback_ack(ack, session_id=session_id)
    return {"status": "received", "recorded_in_clickhouse": recorded}


@app.post("/api/sessions/{session_id}/feedback", tags=["events"])
async def submit_audition_feedback(
    session_id: str,
    feedback: AuditionFeedback,
    current_uid: str = Depends(verify_user),
) -> Dict[str, Any]:
    """Record director audition feedback."""
    if feedback.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mismatched session_id")
    recorded = await record_audition_feedback(feedback)
    return {"status": "received", "recorded_in_clickhouse": recorded}


# Frontend static files serving
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "frontend", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dist, "index.html"))
