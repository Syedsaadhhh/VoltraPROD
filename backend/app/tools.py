"""Domain tool implementations for the Sound Rehearsal agent.

Connects Gemini agent decisions to ClickHouse MCP retrieval and Firestore state.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from app.config import settings
from app.mcp_client import clickhouse_mcp
from app.firestore_store import firestore_store
from app.models import Session, EditBatch, ToolResult, ToolResultStatus

logger = logging.getLogger(__name__)


async def find_sound_candidates(
    tags: Optional[List[str]] = None,
    min_duration_ms: int = 0,
    exclude_asset_ids: Optional[List[str]] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """Retrieve sound assets from ClickHouse catalogue matching search criteria via official MCP."""
    if not settings.is_clickhouse_configured:
        return {
            "status": "unavailable",
            "error": "ClickHouse MCP is unavailable: database credentials are not configured.",
            "candidates": [],
        }

    where_clauses = ["available = 1"]
    if min_duration_ms > 0:
        where_clauses.append(f"duration_ms >= {int(min_duration_ms)}")

    if exclude_asset_ids:
        escaped_ids = ", ".join(f"'{aid}'" for aid in exclude_asset_ids if aid.isalnum() or "-" in aid or "_" in aid)
        if escaped_ids:
            where_clauses.append(f"asset_id NOT IN ({escaped_ids})")

    # In ClickHouse array hasAny or hasAll for tags
    if tags:
        tag_list_str = ", ".join(f"'{t}'" for t in tags)
        where_clauses.append(f"hasAny(tags, [{tag_list_str}])")

    where_sql = " AND ".join(where_clauses)
    query = (
        f"SELECT asset_id, source_path, sha256, duration_ms, sample_rate, channels, tags, "
        f"source_description, rights_note, available "
        f"FROM {settings.CLICKHOUSE_DATABASE}.sound_assets "
        f"WHERE {where_sql} "
        f"ORDER BY asset_id ASC "
        f"LIMIT {min(max(1, limit), 50)}"
    )

    try:
        res = await clickhouse_mcp.execute_query(query)
        return {
            "status": res.get("status", "success"),
            "query": query,
            "data": res.get("output", ""),
        }
    except Exception as e:
        logger.error(f"Error querying sound candidates: {e}")
        return {
            "status": "error",
            "error": str(e),
            "candidates": [],
        }


async def recall_auditions(
    session_id: str,
    limit: int = 10,
) -> Dict[str, Any]:
    """Recall prior audition feedback and decisions from ClickHouse event store."""
    if not settings.is_clickhouse_configured:
        return {
            "status": "unavailable",
            "error": "ClickHouse MCP is unavailable: database credentials are not configured.",
            "events": [],
        }

    clean_sid = session_id.replace("'", "")
    query = (
        f"SELECT event_id, session_id, revision, asset_id, decision, instruction, occurred_at "
        f"FROM {settings.CLICKHOUSE_DATABASE}.audition_events "
        f"WHERE session_id = '{clean_sid}' "
        f"ORDER BY occurred_at DESC "
        f"LIMIT {min(max(1, limit), 50)}"
    )

    try:
        res = await clickhouse_mcp.execute_query(query)
        return {
            "status": res.get("status", "success"),
            "query": query,
            "data": res.get("output", ""),
        }
    except Exception as e:
        logger.error(f"Error recalling auditions: {e}")
        return {
            "status": "error",
            "error": str(e),
            "events": [],
        }


async def inspect_session(session_id: str) -> Dict[str, Any]:
    """Read the authoritative current session and cue state from Firestore."""
    if not settings.is_firestore_configured:
        return {
            "status": "unavailable",
            "error": "Firestore is unavailable: Firebase credentials not configured.",
            "session": None,
        }

    session = await firestore_store.get_session(session_id)
    if session is None:
        return {
            "status": "not_found",
            "session_id": session_id,
        }

    return {
        "status": "success",
        "session": session.model_dump(mode="json"),
    }
