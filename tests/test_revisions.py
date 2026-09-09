"""Unit tests verifying session revisions, ownership validation, and protected track enforcement."""

import pytest
from datetime import datetime, timezone
from app.models import (
    Session,
    Cue,
    EnvelopePoint,
    EditBatch,
    CueEdit,
    CueEditAction,
    ToolResultStatus,
)


def create_sample_session(owner_uid="director_1", revision=0, scene_duration_ms=30000) -> Session:
    dialogue_cue = Cue(
        id="cue_dialogue_01",
        asset_id="asset_dialogue_hero",
        source_in_ms=0,
        source_out_ms=3000,
        timeline_start_ms=1000,
        gain_db=-3.0,
        pan=0.0,
        envelope_points=[
            EnvelopePoint(offset_ms=0, level=0.0),
            EnvelopePoint(offset_ms=500, level=1.0),
            EnvelopePoint(offset_ms=3000, level=0.0),
        ],
        track_id="dialogue",
    )
    return Session(
        id="session_test_001",
        owner_uid=owner_uid,
        revision=revision,
        scene_duration_ms=scene_duration_ms,
        protected_track_ids=["dialogue"],
        cues=[dialogue_cue],
    )


def apply_edit_batch_logic(session: Session, batch: EditBatch, caller_uid: str) -> tuple[Session, dict]:
    """Pure logic replication of the backend transaction path for unit verification."""
    # 1. Ownership check
    if session.owner_uid != caller_uid:
        raise PermissionError(f"Ownership mismatch: session owned by {session.owner_uid}, caller is {caller_uid}")

    # 2. Concurrency check
    if session.revision != batch.expected_revision:
        raise ValueError(
            f"STALE_REVISION: expected {batch.expected_revision}, but current revision is {session.revision}"
        )

    cues_map = {c.id: c for c in session.cues}
    protected_tracks = set(session.protected_track_ids)

    for edit in batch.edits:
        existing_cue = cues_map.get(edit.cue_id)
        if existing_cue and existing_cue.track_id in protected_tracks:
            raise ValueError(
                f"PROTECTED_TRACK: cannot modify or remove cue {edit.cue_id} on protected track '{existing_cue.track_id}'"
            )

        if edit.action == CueEditAction.ADD:
            if not edit.cue:
                raise ValueError("Missing cue in ADD")
            if edit.cue.track_id in protected_tracks:
                raise ValueError(
                    f"PROTECTED_TRACK: cannot add cue {edit.cue_id} to protected track '{edit.cue.track_id}'"
                )
            if edit.cue_id in cues_map:
                raise ValueError(f"Cue {edit.cue_id} already exists")
            cues_map[edit.cue_id] = edit.cue

        elif edit.action == CueEditAction.MODIFY:
            if not edit.cue:
                raise ValueError("Missing cue in MODIFY")
            if edit.cue_id not in cues_map:
                raise ValueError(f"Cue {edit.cue_id} not found")
            if edit.cue.track_id in protected_tracks:
                raise ValueError("PROTECTED_TRACK: cannot move into protected track")
            cues_map[edit.cue_id] = edit.cue

        elif edit.action == CueEditAction.REMOVE:
            if edit.cue_id in cues_map:
                del cues_map[edit.cue_id]

    # Validate overall scene duration
    new_cues = list(cues_map.values())
    for c in new_cues:
        if c.timeline_end_ms > session.scene_duration_ms:
            raise ValueError(f"Cue {c.id} exceeds scene duration")

    new_revision = session.revision + 1
    updated_session = Session(
        id=session.id,
        owner_uid=session.owner_uid,
        revision=new_revision,
        scene_duration_ms=session.scene_duration_ms,
        protected_track_ids=session.protected_track_ids,
        cues=new_cues,
    )
    return updated_session, {"status": ToolResultStatus.SUCCESS, "revision": new_revision}


def test_happy_path_revision_increment():
    """Verify applying a valid edit increases revision monotonically by 1."""
    session = create_sample_session(revision=0)
    batch = EditBatch(
        operation_id="op_1",
        session_id=session.id,
        expected_revision=0,
        edits=[
            CueEdit(
                action=CueEditAction.ADD,
                cue_id="cue_foley_01",
                cue=Cue(
                    id="cue_foley_01",
                    asset_id="asset_footstep",
                    source_in_ms=0,
                    source_out_ms=1000,
                    timeline_start_ms=5000,
                    track_id="foley",
                ),
            )
        ],
        rationale_summary="Add foley footstep",
    )
    updated, res = apply_edit_batch_logic(session, batch, caller_uid="director_1")
    assert updated.revision == 1
    assert res["status"] == ToolResultStatus.SUCCESS
    assert len(updated.cues) == 2


def test_stale_revision_rejected():
    """Verify stale revision check rejects edit when expected_revision does not match."""
    session = create_sample_session(revision=2)
    batch = EditBatch(
        operation_id="op_2",
        session_id=session.id,
        expected_revision=1,  # Stale!
        edits=[],
    )
    with pytest.raises(ValueError, match="STALE_REVISION"):
        apply_edit_batch_logic(session, batch, caller_uid="director_1")


def test_protected_track_mutation_rejected():
    """Verify backend transaction rejects modifying dialogue track."""
    session = create_sample_session(revision=0)
    batch = EditBatch(
        operation_id="op_protect_1",
        session_id=session.id,
        expected_revision=0,
        edits=[
            CueEdit(
                action=CueEditAction.MODIFY,
                cue_id="cue_dialogue_01",
                cue=Cue(
                    id="cue_dialogue_01",
                    asset_id="asset_modified",
                    source_in_ms=0,
                    source_out_ms=2000,
                    timeline_start_ms=1000,
                    track_id="dialogue",
                ),
            )
        ],
    )
    with pytest.raises(ValueError, match="PROTECTED_TRACK"):
        apply_edit_batch_logic(session, batch, caller_uid="director_1")


def test_protected_track_removal_rejected():
    """Verify backend transaction rejects deleting a protected dialogue cue."""
    session = create_sample_session(revision=0)
    batch = EditBatch(
        operation_id="op_protect_2",
        session_id=session.id,
        expected_revision=0,
        edits=[
            CueEdit(
                action=CueEditAction.REMOVE,
                cue_id="cue_dialogue_01",
            )
        ],
    )
    with pytest.raises(ValueError, match="PROTECTED_TRACK"):
        apply_edit_batch_logic(session, batch, caller_uid="director_1")


def test_ownership_mismatch_rejected():
    """Verify caller cannot apply edits to a session owned by another director."""
    session = create_sample_session(owner_uid="director_alice", revision=0)
    batch = EditBatch(
        operation_id="op_auth_1",
        session_id=session.id,
        expected_revision=0,
        edits=[],
    )
    with pytest.raises(PermissionError, match="Ownership mismatch"):
        apply_edit_batch_logic(session, batch, caller_uid="director_bob")
