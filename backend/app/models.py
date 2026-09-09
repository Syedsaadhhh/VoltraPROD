"""Typed domain models and validation rules for Sound Rehearsal.

Enforces strict domain constraints:
- pan in [-1.0, 1.0]
- gain_db in [-60.0, 0.0]
- non-negative timeline positions
- ordered envelope points
- finite numeric values
- protected track mutation restrictions
"""

import math
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Tuple, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator


def ensure_finite(val: float, field_name: str) -> float:
    if not math.isfinite(val):
        raise ValueError(f"{field_name} must be a finite numeric value, got {val}")
    return val


class Asset(BaseModel):
    """Sound asset in catalogue."""
    id: str = Field(description="Unique asset identifier")
    source_path: str = Field(description="Relative path or URI to audio file")
    sha256: str = Field(description="SHA-256 digest of media content")
    duration_ms: int = Field(ge=1, description="Decoded media duration in milliseconds")
    sample_rate: int = Field(ge=8000, description="Sample rate in Hz (e.g. 44100, 48000)")
    channels: int = Field(ge=1, le=8, description="Number of audio channels (1=mono, 2=stereo)")
    tags: List[str] = Field(default_factory=list, description="Categorical tags (e.g. footsteps, surface:wood)")
    source_description: str = Field(default="", description="Descriptive label or origin")
    rights_note: str = Field(default="", description="Attribution / license notice")
    available: bool = Field(default=True, description="Whether asset is presently accessible")


class EnvelopePoint(BaseModel):
    """Envelope control point (time offset relative to cue start, normalized level 0.0-1.0)."""
    offset_ms: int = Field(ge=0, description="Time offset from cue start in milliseconds")
    level: float = Field(ge=0.0, le=1.0, description="Normalized volume multiplier [0.0, 1.0]")

    @field_validator("level")
    @classmethod
    def check_level_finite(cls, v: float) -> float:
        return ensure_finite(v, "EnvelopePoint.level")


class Cue(BaseModel):
    """Audio cue placed on the rehearsal timeline."""
    id: str = Field(description="Unique cue ID")
    asset_id: str = Field(description="Referenced sound asset ID")
    source_in_ms: int = Field(ge=0, description="In-point inside the source asset")
    source_out_ms: int = Field(ge=0, description="Out-point inside the source asset")
    timeline_start_ms: int = Field(ge=0, description="Timeline position in milliseconds")
    gain_db: float = Field(default=0.0, ge=-60.0, le=0.0, description="Cue gain in dB [-60.0, 0.0]")
    pan: float = Field(default=0.0, ge=-1.0, le=1.0, description="Stereo panning [-1.0 = left, 1.0 = right]")
    envelope_points: List[EnvelopePoint] = Field(default_factory=list, description="Ordered envelope points")
    track_id: str = Field(default="sfx", description="Track or layer ID (e.g. dialogue, foley, ambience, sfx)")

    @field_validator("gain_db")
    @classmethod
    def check_gain_finite(cls, v: float) -> float:
        return ensure_finite(v, "Cue.gain_db")

    @field_validator("pan")
    @classmethod
    def check_pan_finite(cls, v: float) -> float:
        return ensure_finite(v, "Cue.pan")

    @model_validator(mode="after")
    def check_source_bounds_and_envelope(self) -> "Cue":
        if self.source_out_ms <= self.source_in_ms:
            raise ValueError(
                f"source_out_ms ({self.source_out_ms}) must be strictly greater than source_in_ms ({self.source_in_ms})"
            )
        # Check envelope ordering
        for i in range(1, len(self.envelope_points)):
            if self.envelope_points[i].offset_ms < self.envelope_points[i - 1].offset_ms:
                raise ValueError("Envelope points must be monotonically ordered by offset_ms")
        return self

    @property
    def duration_ms(self) -> int:
        return self.source_out_ms - self.source_in_ms

    @property
    def timeline_end_ms(self) -> int:
        return self.timeline_start_ms + self.duration_ms


class SessionStatus(str, Enum):
    IDLE = "idle"
    REHEARSING = "rehearsing"
    PLAYING = "playing"
    ERROR = "error"


class Session(BaseModel):
    """Authoritative rehearsal session state stored in Firestore."""
    id: str = Field(description="Unique session ID")
    owner_uid: str = Field(description="Firebase Auth UID of session owner")
    revision: int = Field(ge=0, default=0, description="Monotonically increasing revision counter")
    scene_duration_ms: int = Field(default=30000, ge=1000, description="Scene timeline duration in ms")
    protected_track_ids: List[str] = Field(default_factory=lambda: ["dialogue"], description="Tracks protected from AI edits")
    cues: List[Cue] = Field(default_factory=list, description="Timeline cues")
    status: SessionStatus = Field(default=SessionStatus.IDLE, description="Session lifecycle status")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of last update")

    @model_validator(mode="after")
    def validate_cues_within_scene(self) -> "Session":
        for cue in self.cues:
            if cue.timeline_end_ms > self.scene_duration_ms:
                raise ValueError(
                    f"Cue {cue.id} ends at {cue.timeline_end_ms}ms which exceeds scene duration {self.scene_duration_ms}ms"
                )
        return self


class DirectorInstruction(BaseModel):
    """Director artistic intent or revision direction."""
    id: str = Field(description="Instruction ID")
    session_id: str = Field(description="Target session ID")
    base_revision: int = Field(ge=0, description="Session revision upon which direction is based")
    text: str = Field(min_length=1, max_length=2000, description="Director feedback or creative prompt")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CueEditAction(str, Enum):
    ADD = "add"
    MODIFY = "modify"
    REMOVE = "remove"


class CueEdit(BaseModel):
    """Single cue modification action."""
    action: CueEditAction
    cue_id: str
    cue: Optional[Cue] = None  # Required for ADD and MODIFY


class EditBatch(BaseModel):
    """Atomic batch of timeline edits proposed by agent or user."""
    operation_id: str = Field(description="Idempotency key for this edit batch")
    session_id: str = Field(description="Target session ID")
    expected_revision: int = Field(ge=0, description="Expected base revision for optimistic concurrency")
    edits: List[CueEdit] = Field(default_factory=list, description="Ordered list of cue edits")
    rationale_summary: str = Field(default="", description="Summary of creative or technical rationale")


class ToolResultStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    UNAVAILABLE = "unavailable"


class ToolResult(BaseModel):
    """Outcome of an agent or backend tool operation."""
    operation_id: str
    status: ToolResultStatus
    revision: int
    error_code: Optional[str] = None
    retryable: bool = False
    data: Dict[str, Any] = Field(default_factory=dict)


class PlaybackStatus(str, Enum):
    APPLIED = "applied"
    FAILED = "failed"
    REJECTED = "rejected"


class PlaybackAck(BaseModel):
    """Client acknowledgement following timeline cue application and media decode."""
    operation_id: str
    applied_revision: int
    status: PlaybackStatus
    decoded_asset_ids: List[str] = Field(default_factory=list)
    error_code: Optional[str] = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditionDecision(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNRATED = "unrated"


class AuditionFeedback(BaseModel):
    """Director reaction to an auditioned candidate or arrangement."""
    event_id: str
    session_id: str
    revision: int
    asset_ids: List[str]
    accepted_or_rejected_or_unrated: AuditionDecision
    director_text: Optional[str] = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
