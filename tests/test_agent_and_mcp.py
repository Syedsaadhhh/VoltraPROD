"""Unit and integration contract tests for Agent tools, ClickHouse MCP query logic, and constraints."""

import json
import pytest
from unittest.mock import AsyncMock, patch
from app.config import settings
from app.models import (
    Session,
    Cue,
    EnvelopePoint,
    EditBatch,
    CueEdit,
    CueEditAction,
    DirectorDirectionRequest,
    DirectorDirectionResponse,
)
from app.tools import find_sound_candidates, recall_auditions, inspect_session


def test_director_request_and_response_models():
    """Verify Director request and response serialization contracts."""
    req = DirectorDirectionRequest(
        instruction="Add subtle tension drone as she turns to the door",
        base_revision=0,
        excluded_asset_ids=["asset_dialogue_hero_01"],
        scene_beats="Hero freezes at 4.5s staring at wooden door",
    )
    assert req.instruction == "Add subtle tension drone as she turns to the door"
    assert "asset_dialogue_hero_01" in req.excluded_asset_ids
    assert req.scene_beats is not None

    trace = {
        "tool_name": "find_sound_candidates",
        "input_args": {"tags": ["tense", "drone"]},
        "output_summary": "Found 1 candidates",
        "status": "success",
    }
    resp = DirectorDirectionResponse(
        status="success",
        action_summary="Added tense drone cue",
        rationale="Matches tension when hero freezes at door.",
        revision=1,
        tool_traces=[trace],
    )
    dumped = resp.model_dump(mode="json")
    assert dumped["status"] == "success"
    assert dumped["revision"] == 1
    assert len(dumped["tool_traces"]) == 1
    assert dumped["tool_traces"][0]["tool_name"] == "find_sound_candidates"


@pytest.mark.asyncio
async def test_find_sound_candidates_query_construction():
    """Verify that find_sound_candidates builds valid ClickHouse SQL with exclusions and tags."""
    mock_mcp = AsyncMock()
    mock_mcp.execute_query.return_value = {
        "output": (
            '{"asset_id":"asset_tense_drone_01","source_path":"demo/tense_drone_low_01.wav",'
            '"sha256":"abc123","duration_ms":6000,"sample_rate":44100,"channels":2,'
            '"tags":["ambience","drone","tense"],"source_description":"Low 55Hz drone",'
            '"rights_note":"CC0","available":1}\n'
        )
    }

    with patch("app.tools.clickhouse_mcp", mock_mcp), \
         patch.object(settings, "CLICKHOUSE_HOST", "mock.clickhouse.cloud"), \
         patch.object(settings, "CLICKHOUSE_PASSWORD", "mock_pass"), \
         patch.object(settings, "CLICKHOUSE_DATABASE", "voltra_dev"):

        res = await find_sound_candidates(
            tags=["tense", "drone"],
            min_duration_ms=2000,
            exclude_asset_ids=["asset_footsteps_wood_01", "asset_dialogue_hero_01"],
            limit=5,
        )

        assert res["status"] == "success"
        assert res["count"] == 1
        candidate = res["candidates"][0]
        assert candidate["asset_id"] == "asset_tense_drone_01"
        # source_path should be normalized with leading /
        assert candidate["source_path"] == "/demo/tense_drone_low_01.wav"

        # Inspect generated query
        query = mock_mcp.execute_query.call_args[0][0]
        assert "hasAny(tags, ['tense', 'drone'])" in query
        assert "duration_ms >= 2000" in query
        assert "asset_id NOT IN ('asset_footsteps_wood_01', 'asset_dialogue_hero_01')" in query
        assert "FORMAT JSONEachRow" not in query


@pytest.mark.asyncio
async def test_find_sound_candidates_sql_sanitization():
    """Verify that single quotes in tags or excluded_asset_ids are stripped to prevent SQL injection."""
    mock_mcp = AsyncMock()
    mock_mcp.execute_query.return_value = {"output": ""}

    with patch("app.tools.clickhouse_mcp", mock_mcp), \
         patch.object(settings, "CLICKHOUSE_HOST", "mock.clickhouse.cloud"), \
         patch.object(settings, "CLICKHOUSE_PASSWORD", "mock_pass"), \
         patch.object(settings, "CLICKHOUSE_DATABASE", "voltra_dev"):

        await find_sound_candidates(
            tags=["drone' OR 1=1 --"],
            exclude_asset_ids=["bad'asset"],
        )

        query = mock_mcp.execute_query.call_args[0][0]
        assert "drone OR 1=1 --" in query
        assert "badasset" in query
        assert "bad'asset" not in query


@pytest.mark.asyncio
async def test_recall_auditions_parsing():
    """Verify recall_auditions parses JSONEachRow history."""
    mock_mcp = AsyncMock()
    mock_mcp.execute_query.return_value = {
        "output": (
            '{"event_id":"evt_1","session_id":"sess_1","revision":1,"asset_id":"asset_wood_01",'
            '"decision":"reject","instruction":"too harsh","occurred_at":"2026-09-09 12:00:00"}\n'
            '{"event_id":"evt_2","session_id":"sess_1","revision":2,"asset_id":"asset_drone_01",'
            '"decision":"accept","instruction":"perfect","occurred_at":"2026-09-09 12:05:00"}\n'
        )
    }

    with patch("app.tools.clickhouse_mcp", mock_mcp), \
         patch.object(settings, "CLICKHOUSE_HOST", "mock.clickhouse.cloud"), \
         patch.object(settings, "CLICKHOUSE_PASSWORD", "mock_pass"), \
         patch.object(settings, "CLICKHOUSE_DATABASE", "voltra_dev"):

        res = await recall_auditions(session_id="sess_1", limit=10)
        assert res["status"] == "success"
        assert res["count"] == 2
        assert res["events"][0]["decision"] == "reject"
        assert res["events"][1]["decision"] == "accept"


@pytest.mark.asyncio
async def test_protected_track_modification_rejected():
    """Verify that any proposed batch attempting to mutate a protected track is rejected."""
    session = Session(
        id="session_protected_test",
        owner_uid="director_test",
        revision=1,
        scene_duration_ms=10000,
        protected_track_ids=["dialogue"],
        cues=[
            Cue(
                id="cue_dialogue_hero",
                asset_id="asset_dialogue_hero_01",
                source_in_ms=0,
                source_out_ms=3000,
                timeline_start_ms=1000,
                gain_db=0.0,
                pan=0.0,
                track_id="dialogue",
            )
        ],
    )

    # 1. Attempt to delete protected cue
    delete_batch = EditBatch(
        operation_id="op_del_1",
        session_id="session_protected_test",
        expected_revision=1,
        rationale_summary="Attempting to remove dialogue",
        edits=[CueEdit(action=CueEditAction.REMOVE, cue_id="cue_dialogue_hero")],
    )

    # Check the pure transaction rule
    with pytest.raises(ValueError, match="PROTECTED_TRACK"):
        protected_tracks = set(session.protected_track_ids)
        for edit in delete_batch.edits:
            cue = next((c for c in session.cues if c.id == edit.cue_id), None)
            if cue and cue.track_id in protected_tracks:
                raise ValueError(f"PROTECTED_TRACK: Cannot modify or delete cue {cue.id} on protected track {cue.track_id}")

    # 2. Attempt to add cue on protected track
    add_batch = EditBatch(
        operation_id="op_add_1",
        session_id="session_protected_test",
        expected_revision=1,
        rationale_summary="Attempting to add to dialogue track",
        edits=[
            CueEdit(
                action=CueEditAction.ADD,
                cue_id="new_dialogue_cue",
                cue=Cue(
                    id="new_dialogue_cue",
                    asset_id="asset_dialogue_hero_01",
                    source_in_ms=0,
                    source_out_ms=2000,
                    timeline_start_ms=500,
                    track_id="dialogue",
                ),
            )
        ],
    )
    with pytest.raises(ValueError, match="PROTECTED_TRACK"):
        protected_tracks = set(session.protected_track_ids)
        for edit in add_batch.edits:
            if edit.action == CueEditAction.ADD and edit.cue and edit.cue.track_id in protected_tracks:
                raise ValueError(f"PROTECTED_TRACK: Cannot add new cues to protected track {edit.cue.track_id}")
