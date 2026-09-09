-- ClickHouse Sound Rehearsal Schema
-- Idempotent table definitions for sound assets and rehearsal history.

CREATE TABLE IF NOT EXISTS sound_assets
(
    asset_id String,
    sha256 String,
    duration_ms UInt32,
    sample_rate UInt32,
    channels UInt8,
    tags Array(String),
    source_path String,
    rights_note String,
    available UInt8
)
ENGINE = MergeTree
ORDER BY asset_id;

CREATE TABLE IF NOT EXISTS audition_events
(
    event_id UUID,
    session_id String,
    revision UInt32,
    asset_id String,
    decision LowCardinality(String),
    instruction String,
    occurred_at DateTime64(3)
)
ENGINE = MergeTree
ORDER BY (session_id, occurred_at, event_id);

CREATE TABLE IF NOT EXISTS playback_events
(
    event_id UUID,
    session_id String,
    operation_id String,
    revision UInt32,
    status LowCardinality(String),
    error_code String,
    occurred_at DateTime64(3)
)
ENGINE = MergeTree
ORDER BY (session_id, occurred_at, event_id);

-- Read-only role specification for MCP client connection
CREATE ROLE IF NOT EXISTS sound_rehearsal_reader;
