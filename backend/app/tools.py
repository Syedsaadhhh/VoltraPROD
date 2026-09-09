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
        clean_ids = [aid.strip().replace("'", "") for aid in exclude_asset_ids if aid.strip()]
        if clean_ids:
            escaped_ids = ", ".join(f"'{aid}'" for aid in clean_ids)
            where_clauses.append(f"asset_id NOT IN ({escaped_ids})")

    if tags:
        clean_tags = [t.strip().replace("'", "") for t in tags if t.strip()]
        if clean_tags:
            tag_list_str = ", ".join(f"'{t}'" for t in clean_tags)
            where_clauses.append(f"hasAny(tags, [{tag_list_str}])")

    where_sql = " AND ".join(where_clauses)
    query = (
        f"SELECT asset_id, source_path, sha256, duration_ms, sample_rate, channels, tags, "
        f"rights_note, available "
        f"FROM {settings.CLICKHOUSE_DATABASE}.sound_assets "
        f"WHERE {where_sql} "
        f"ORDER BY asset_id ASC "
        f"LIMIT {min(max(1, limit), 50)}"
    )

    try:
        res = await clickhouse_mcp.execute_query(query)
        candidates = []
        raw_output = res.get("output", "").strip()
        if raw_output:
            try:
                parsed = json.loads(raw_output)
                if isinstance(parsed, dict) and "columns" in parsed and "rows" in parsed:
                    cols = parsed["columns"]
                    for r in parsed["rows"]:
                        candidates.append(dict(zip(cols, r)))
                elif isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict):
                            candidates.append(item)
                elif isinstance(parsed, dict):
                    candidates.append(parsed)
            except Exception:
                # Fallback to newline-delimited JSON
                for line in raw_output.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        candidates.append(json.loads(line))
                    except Exception:
                        pass

        # Normalize source_path
        for row in candidates:
            sp = row.get("source_path", "")
            if sp and not sp.startswith("/") and not sp.startswith("http"):
                sp = f"/{sp}"
            row["source_path"] = sp

        return {
            "status": "success",
            "query": query,
            "count": len(candidates),
            "candidates": candidates,
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
        events = []
        raw_output = res.get("output", "").strip()
        if raw_output:
            try:
                parsed = json.loads(raw_output)
                if isinstance(parsed, dict) and "columns" in parsed and "rows" in parsed:
                    cols = parsed["columns"]
                    for r in parsed["rows"]:
                        events.append(dict(zip(cols, r)))
                elif isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict):
                            events.append(item)
            except Exception:
                for line in raw_output.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except Exception:
                        pass

        return {
            "status": "success",
            "query": query,
            "count": len(events),
            "events": events,
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

