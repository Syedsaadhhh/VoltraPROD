"""ClickHouse event ingestion sink for playback and audition events.

Uses clickhouse-connect with separate writer/admin credentials if available,
or logs events if writer credentials are not configured.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from app.config import settings
from app.models import PlaybackAck, AuditionFeedback

logger = logging.getLogger(__name__)

_ch_client = None


def get_writer_client():
    """Get clickhouse-connect client for inserting events."""
    global _ch_client
    if _ch_client is not None:
        return _ch_client

    if not settings.is_clickhouse_configured:
        return None

    try:
        import clickhouse_connect

        user = settings.CLICKHOUSE_ADMIN_USER or settings.CLICKHOUSE_USER
        password = settings.CLICKHOUSE_ADMIN_PASSWORD or settings.CLICKHOUSE_PASSWORD

        _ch_client = clickhouse_connect.get_client(
            host=settings.CLICKHOUSE_HOST,
            port=settings.CLICKHOUSE_PORT,
            username=user,
            password=password,
            database=settings.CLICKHOUSE_DATABASE,
            secure=settings.CLICKHOUSE_SECURE,
            verify=settings.CLICKHOUSE_VERIFY,
            connect_timeout=settings.CLICKHOUSE_CONNECT_TIMEOUT,
        )
        return _ch_client
    except Exception as e:
        logger.warning(f"Could not connect to ClickHouse for event writing: {e}")
        return None


async def record_playback_ack(ack: PlaybackAck, session_id: str) -> bool:
    """Record client playback acknowledgement event into ClickHouse."""
    client = get_writer_client()
    if client is None:
        logger.info(f"[PlaybackAck Event] session={session_id} op={ack.operation_id} status={ack.status}")
        return False

    import uuid

    try:
        event_id = str(uuid.uuid4())
        client.insert(
            "playback_events",
            [[
                event_id,
                session_id,
                ack.operation_id,
                ack.applied_revision,
                ack.status.value,
                ack.error_code or "",
                ack.observed_at,
            ]],
            column_names=["event_id", "session_id", "operation_id", "revision", "status", "error_code", "occurred_at"],
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to record playback event: {e}")
        return False


async def record_audition_feedback(feedback: AuditionFeedback) -> bool:
    """Record director audition feedback event into ClickHouse."""
    client = get_writer_client()
    if client is None:
        logger.info(f"[AuditionFeedback Event] session={feedback.session_id} decision={feedback.accepted_or_rejected_or_unrated}")
        return False

    try:
        first_asset = feedback.asset_ids[0] if feedback.asset_ids else ""
        client.insert(
            "audition_events",
            [[
                feedback.event_id,
                feedback.session_id,
                feedback.revision,
                first_asset,
                feedback.accepted_or_rejected_or_unrated.value,
                feedback.director_text or "",
                feedback.observed_at,
            ]],
            column_names=["event_id", "session_id", "revision", "asset_id", "decision", "instruction", "occurred_at"],
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to record audition feedback: {e}")
        return False
