"""Unit tests for domain models, validation constraints, and revision logic."""

import pytest
from pydantic import ValidationError

from app.models import (
    Asset,
    Cue,
    EnvelopePoint,
    Session,
    SessionStatus,
    EditBatch,
    CueEdit,
    CueEditAction,
    ToolResult,
    ToolResultStatus,
)


def test_asset_validation():
    """Verify Asset validation passes with valid attributes."""
    asset = Asset(
        id="test_footsteps_01",
        source_path="demo/footsteps_wood.wav",
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        duration_ms=1500,
        sample_rate=48000,
        channels=2,
        tags=["footsteps", "surface:wood"],
        source_description="Sneaker steps on hardwood",
        rights_note="CC0",
        available=True,
    )
    assert asset.duration_ms == 1500
    assert asset.sample_rate == 48000
    assert asset.channels == 2


def test_cue_numeric_constraints():
    """Verify pan in [-1, 1], gain in [-60, 0], and non-negative offsets."""
    # Valid cue
    cue = Cue(
        id="cue_1",
        asset_id="test_footsteps_01",
        source_in_ms=0,
        source_out_ms=1000,
        timeline_start_ms=500,
        gain_db=-12.0,
        pan=0.5,
        envelope_points=[
            EnvelopePoint(offset_ms=0, level=0.0),
            EnvelopePoint(offset_ms=200, level=1.0),
            EnvelopePoint(offset_ms=1000, level=0.0),
        ],
        track_id="foley",
    )
    assert cue.duration_ms == 1000
    assert cue.timeline_end_ms == 1500

    # Invalid pan > 1.0
    with pytest.raises(ValidationError):
        Cue(
            id="cue_bad_pan",
            asset_id="test_footsteps_01",
            source_in_ms=0,
            source_out_ms=1000,
            timeline_start_ms=0,
            pan=1.5,
        )

    # Invalid gain > 0.0
    with pytest.raises(ValidationError):
        Cue(
            id="cue_bad_gain",
            asset_id="test_footsteps_01",
            source_in_ms=0,
            source_out_ms=1000,
            timeline_start_ms=0,
            gain_db=6.0,
        )

    # Invalid source_out <= source_in
    with pytest.raises(ValidationError):
        Cue(
            id="cue_bad_times",
            asset_id="test_footsteps_01",
            source_in_ms=500,
            source_out_ms=500,
            timeline_start_ms=0,
        )

    # Unordered envelope points
    with pytest.raises(ValidationError):
        Cue(
            id="cue_bad_env",
            asset_id="test_footsteps_01",
            source_in_ms=0,
            source_out_ms=1000,
            timeline_start_ms=0,
            envelope_points=[
                EnvelopePoint(offset_ms=300, level=1.0),
                EnvelopePoint(offset_ms=100, level=0.5),
            ],
        )


def test_session_scene_bounds():
    """Verify cues cannot exceed scene_duration_ms."""
    valid_cue = Cue(
        id="cue_ok",
        asset_id="test_01",
        source_in_ms=0,
        source_out_ms=2000,
        timeline_start_ms=10000,
        track_id="foley",
    )
    session = Session(
        id="session_1",
        owner_uid="user_123",
        revision=0,
        scene_duration_ms=20000,
        cues=[valid_cue],
    )
    assert len(session.cues) == 1

    # Cue ending past scene duration (start 19000 + duration 2000 = 21000 > 20000)
    overrunning_cue = Cue(
        id="cue_over",
        asset_id="test_01",
        source_in_ms=0,
        source_out_ms=2000,
        timeline_start_ms=19000,
        track_id="foley",
    )
    with pytest.raises(ValidationError):
        Session(
            id="session_2",
            owner_uid="user_123",
            revision=0,
            scene_duration_ms=20000,
            cues=[overrunning_cue],
        )
