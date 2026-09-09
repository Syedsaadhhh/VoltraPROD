# Chunk 2 — Real Media and Editable Playback Engine Prompt Brief

Target: 120 minutes.

## Objectives
1. Implement asset inspection and manifest generation from actual audio files (`scripts/inspect_media.py`), extracting real decoded duration_ms, sample_rate, channels, and sha256 checksums.
2. Seed inspected asset metadata into ClickHouse `sound_assets` table.
3. Build browser Web Audio scheduling engine (`frontend/src/audio/engine.ts`) initialized by an explicit "Enable Audio" user gesture satisfying browser autoplay policies.
4. Implement gain envelopes, stereo panning, seek, pause, clip repositioning, and dynamic limiting for listening safety.
5. Stop and cleanly reschedule active audio nodes when edits or seeks occur to prevent ghost or duplicate playback.
6. Build `frontend/src/audio/render.ts` using `OfflineAudioContext` for WAV audition export and JSON session export.
7. Build timeline UI (`Stage.tsx`, `Timeline.tsx`, `DirectionPanel.tsx`) with VoltraPROD branding.
8. Distinguish browser-local media clearly, state that it does not survive page reloads or device transfers, and avoid raw media blobs in Firestore or ClickHouse.
