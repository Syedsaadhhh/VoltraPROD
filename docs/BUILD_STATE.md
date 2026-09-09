# VoltraPROD Build State — Run 1, Run 2, Run 3 & Run 4 Complete

Date: September 9, 2026  
Status: Run 1 Complete (Live Integrations Verified), Run 2 Complete (Media Engine & Editable Playback Operational), Run 3 Complete (Gemini Agent Loop & ClickHouse MCP), Run 4 Complete (Real Media Replacement, End-to-End Workflow Proof, Offline Audio Export & Render Deployment)  
Current State: Run 4 Complete  
Deployment Destination: https://github.com/Syedsaadhhh/VoltraPROD (Render Free Web Service Ready)

---

## 1. Executive Summary

VoltraPROD is an AI-directed sound rehearsal studio running on Google ADK / Gemini Developer API (`gemini-3.1-flash-lite`), official ClickHouse MCP, and Google Cloud Firestore (Spark plan).
- **Run 1**: Established the backend architecture, typed domain models, Firebase Firestore optimistic revision store, Google GenAI Developer API client, and official `mcp-clickhouse` server connectivity over HTTPS port 8443.
- **Run 2**: Built the deterministic browser Web Audio playback scheduler, offline 16-bit PCM WAV / JSON session exporters, interactive multi-track stage and timeline UI, and session-local media isolation architecture.
- **Run 3**: Implemented the Gemini agent loop with ClickHouse MCP sound candidate retrieval, bounded tool turns, protected track safeguards (`dialogue` track locked), audition feedback ingestion, dark-mode UI workstation styling (`#09090B`, `#18181B`, `#27272A`, `#3B82F6`), and video framing analysis.
- **Run 4**: Reconciled and decoded real sound recordings, replaced all synthetic sound fixtures with real Foley/ambience assets, invalidated obsolete fixtures in ClickHouse (`available = 0`), removed the audio synthesizer script, updated the cropped video specifications, proved the complete 2-turn rehearsal workflow end-to-end with live Gemini and ClickHouse MCP, generated offline audition WAV and session JSON exports, and finalized production deployment artifacts (`Dockerfile`, `render.yaml`).

The entire test suite passes with 100% success (17/17 tests), and the frontend builds cleanly into a production bundle (402 kB) with 0 errors.

---

## 2. Reconciled Real Media Specifications

All obsolete synthesized fixtures have been permanently removed from the demo bundle (`frontend/public/demo/`) and marked `available = 0` in ClickHouse. Real audio recordings and the cropped video are active and verified.

### Real Audio Assets Table

| Asset ID | Filename | Duration (ms) | Sample Rate | Channels | Format | SHA-256 (Truncated) | Tags | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- | :--- | :---: |
| `asset_door_close` | `door_close.wav` | 3,000 | 48,000 Hz | 2 (stereo) | 16-bit PCM | `2aea089c9a61...` | `['door', 'foley', 'impact', 'sfx']` | Active (`available = 1`) |
| `asset_footseps_heavy` | `footseps_heavy.wav` | 6,000 | 24,000 Hz | 2 (stereo) | 16-bit PCM | `7ebed0aba546...` | `['foley', 'footsteps', 'heavy', 'sfx']` | Active (`available = 1`) |
| `asset_footsteps_normal`| `footsteps_normal.wav`| 6,000 | 48,000 Hz | 2 (stereo) | 16-bit PCM | `909c81f16bed...` | `['foley', 'footsteps', 'normal', 'sfx']` | Active (`available = 1`) |
| `asset_paper_fold` | `paper_fold.wav` | 6,000 | 44,100 Hz | 1 (mono) | 16-bit PCM | `7a46f04f6805...` | `['foley', 'handling', 'paper', 'sfx']` | Active (`available = 1`) |
| `asset_room_tone` | `room_tone.wav` | 14,920 | 48,000 Hz | 2 (stereo) | 16-bit PCM | `4cb60ac3452f...` | `['ambience', 'atmosphere', 'interior', 'room_tone', 'sfx']` | Active (`available = 1`) |

### Cropped Video Analysis (`assets/raw/scene.mp4` & `frontend/public/demo/scene.mp4`)
- **Container / Timescale**: ISO BMFF MP4, timescale 30,000.
- **Duration**: Exactly **10.034 seconds** (301,020 timescale units = **10,034 ms**).
- **Video Track**: AVC / H.264, **792x362** pixels (cropped from original 848x478), ~30.10 fps (302 frames, keyframes: [1, 129, 257]).
- **Audio Track**: AAC stereo, 10.027 seconds (470 audio frames).
- **Scene Timeline Alignment**: Session `scene_duration_ms` is set to **10,034 ms** across backend domain validation, frontend timeline canvas, and offline bounce.

### Invalidation of Synthetic Fixtures
- **ClickHouse Cloud**: Executed scoped mutation `ALTER TABLE default.sound_assets UPDATE available = 0 WHERE asset_id IN ('asset_ambient_wind_hollow_01', 'asset_cloth_rustle_jacket_01', 'asset_dialogue_hero_01', 'asset_door_creak_slow_01', 'asset_footsteps_concrete_01', 'asset_footsteps_wood_01', 'asset_tense_drone_low_01')`.
- **Filesystem Cleanliness**: Removed all 7 synthesized WAVs from `frontend/public/demo/` and `assets/raw/`.
- **Generator Deletion**: Deleted `scripts/generate_demo_audio.py` from repository tracking.
- **Frontend Stale Cue Protection**: Added detection banner in `frontend/src/App.tsx` warning users if obsolete synthetic fixture IDs are present in a restored session, with a one-click "Start Fresh Demo Session" button.

---

## 3. Proven End-to-End Workflow Execution

The live rehearsal workflow was executed end-to-end via `scripts/prove_workflow.py` connecting live Gemini Developer API (`gemini-3.1-flash-lite`), official ClickHouse MCP, and Google Cloud Firestore.

### Workflow Execution Summary

```
================================================================================
VOLTRAPROD PHASE 2: END-TO-END AGENT WORKFLOW & REAL MEDIA REHEARSAL
================================================================================

--- Step 1: Active Catalogue in ClickHouse MCP ---
Discovered 5 active candidate(s) via ClickHouse MCP:
  [asset_door_close] 3000ms, tags=['door', 'foley', 'impact', 'sfx'], path=/demo/door_close.wav
  [asset_footseps_heavy] 6000ms, tags=['foley', 'footsteps', 'heavy', 'sfx'], path=/demo/footseps_heavy.wav
  [asset_footsteps_normal] 6000ms, tags=['foley', 'footsteps', 'normal', 'sfx'], path=/demo/footsteps_normal.wav
  [asset_paper_fold] 6000ms, tags=['foley', 'handling', 'paper', 'sfx'], path=/demo/paper_fold.wav
  [asset_room_tone] 14920ms, tags=['ambience', 'atmosphere', 'interior', 'room_tone', 'sfx'], path=/demo/room_tone.wav

--- Step 2: Creating Fresh Session 'voltra_rehearsal_7a1950' (10034 ms) in Firestore ---
Session created. Revision: 0, Protected: ['dialogue'], Cues: 0

--- Step 3: Turn 1 Creative Direction ---
Prompt: "Build suspense with heavy footsteps before the character turns toward the doorway. Keep paper handling subtle. Do not add music or a door sound."
Agent tool call: inspect_session -> revision 0, 0 cues
Agent tool call: find_sound_candidates -> tags=['paper', 'handling'] -> found asset_paper_fold
Agent tool call: find_sound_candidates -> tags=['footsteps', 'heavy'] -> found asset_footseps_heavy
Agent tool call: propose_edit_batch ->
  - [ADD] Cue 'cue_paper_001': asset='asset_paper_fold', start=0ms, dur=4000ms, gain=-18.0dB, track='foley'
  - [ADD] Cue 'cue_footsteps_001': asset='asset_footseps_heavy', start=3000ms, dur=1500ms, gain=-6.0dB, track='foley'
Applied Batch 1. New Session Revision: 1, Total cues: 2

Director auditions treatment 1: identifies asset_footseps_heavy as too aggressive.

--- Step 4: Turn 2 Revision Direction ---
Prompt: "Those footsteps are too aggressive. Replace them with the normal footsteps and make the approach quieter. Keep the paper cue."
Excluding asset: [asset_footseps_heavy]
Agent tool call: inspect_session -> revision 1, 2 cues
Agent tool call: recall_auditions -> 0 prior decisions
Agent tool call: find_sound_candidates -> tags=['footsteps', 'normal'], NOT IN ('asset_footseps_heavy') -> found asset_footsteps_normal
Agent tool call: propose_edit_batch ->
  - [REMOVE] Cue 'cue_footsteps_001'
  - [ADD] Cue 'cue_footsteps_normal_001': asset='asset_footsteps_normal', start=3000ms, dur=1500ms, gain=-16.0dB, track='foley'
  - Preserves Cue 'cue_paper_001' (start=0ms, gain=-18.0dB)
Applied Batch 2. New Session Revision: 2, Total cues: 2

--- Step 5: Final Timeline Layout ---
  - Track [foley] Cue 'cue_paper_001': asset='asset_paper_fold', start=0ms to 4000ms, gain=-18.0dB
  - Track [foley] Cue 'cue_footsteps_normal_001': asset='asset_footsteps_normal', start=3000ms to 4500ms, gain=-16.0dB

--- Step 6: Rendering Offline Audition WAV & Session JSON ---
Saved session JSON to: docs/exports/voltra_rehearsal_7a1950_rev2.json
Rendered Audition WAV (1,926,572 bytes, 10034ms, 48kHz stereo) to: docs/exports/voltra_rehearsal_7a1950_audition_rev2.wav
================================================================================
[SUCCESS] WORKFLOW PROVEN
================================================================================
```

### Key Verification Metrics
1. **Model & Retrieval**: Gemini `gemini-3.1-flash-lite` successfully selected candidate IDs strictly returned by ClickHouse MCP queries. It never invented nonexistent IDs.
2. **Turn 2 Revision Accuracy**: Correctly generated a `REMOVE` action for the heavy footsteps cue, retrieved the alternative `asset_footsteps_normal`, lowered its gain by -10dB (from -6dB down to -16dB) for a quieter approach, and left the paper handling cue untouched.
3. **Optimistic Locking**: Firestore transactional updates strictly incremented revisions `0 -> 1 -> 2` with idempotency recording.
4. **Offline Export**: Produced `voltra_rehearsal_7a1950_rev2.json` and 16-bit 48kHz stereo WAV bounce (`voltra_rehearsal_7a1950_audition_rev2.wav`) mixed according to the timeline.

---

## 4. Audition & Browser Environment Disclosure

> [!WARNING]
> **Headless Execution Disclosure**:
> The automated agent runs in a headless environment without physical audio output transducers (speakers/headphones) or interactive browser rendering.
> Consequently:
> 1. **Audible Quality**: Sonic balance, timbre, and aesthetic feel cannot be acoustically judged by the agent and are marked **untested by human ears**.
> 2. **Browser Interaction**: Physical clicks, mouse drags on canvas timeline cue handles, and live Web Audio playback in a user agent could not be visually observed.
> 
> A complete manual verification protocol is provided below for user testing.

### Manual Verification Checklist for Browser UI

1. **Launch Stack Locally**:
   ```bash
   # In terminal 1 (backend):
   .venv\Scripts\python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
   
   # In terminal 2 (frontend):
   npm --prefix frontend run dev
   ```
2. **Open Browser**: Navigate to `http://localhost:5173`.
3. **Verify Demo Video Playback**:
   - Check that the cropped 10.034s video (`/demo/scene.mp4`) renders smoothly in the Stage monitor (792x362 framing, aspect ratio preserved).
   - Verify play/pause synchronization between the timeline cursor and the video player.
4. **Verify Live Rehearsal Turn 1**:
   - Type into the Direction prompt: *"Build suspense with heavy footsteps before the character turns toward the doorway. Keep paper handling subtle. Do not add music or a door sound."*
   - Click **Rehearse Direction**.
   - Watch the **Tool Execution** drawer show `find_sound_candidates` and `propose_edit_batch`.
   - Verify that 2 cue blocks appear on the Timeline (`foley` track).
   - Click **Audition Treatment**: listen for subtle paper handling and heavy footsteps approaching from the right.
5. **Verify Live Rehearsal Turn 2**:
   - Type into the Direction prompt: *"Those footsteps are too aggressive. Replace them with the normal footsteps and make the approach quieter. Keep the paper cue."*
   - Click **Rehearse Direction**.
   - Verify that the heavy footsteps cue disappears and is replaced by a quieter normal footstep cue at lower volume, while paper handling remains.
   - Click **Audition Treatment**: confirm quieter footsteps and preserved paper folding.

---

## 5. Deployment Configuration & Hardening

### Multi-Stage Dockerfile (`Dockerfile`)
- **Stage 1 (`frontend-builder`)**: Node 22 Alpine, runs `npm ci` and `npm run build`.
- **Stage 2 (`runner`)**: Python 3.12 slim, installs exact locked dependencies from `backend/requirements.lock`. Copies backend app, SQL migrations, `assets/raw`, `frontend/public`, and `frontend/dist`.
- **Static Assets Mount**: FastAPI serves `/demo` from `frontend/public/demo` (or `assets/raw`) and serves the SPA from `frontend/dist`.

### Render Blueprint (`render.yaml`)
- **Runtime**: Docker Web Service on free plan.
- **Port**: 10000.
- **Health Check Path**: `/health`.
- **Environment Variables**:
  - `GEMINI_MODEL`: Pinned to `gemini-3.1-flash-lite`.
  - `GOOGLE_API_KEY`: Secret (AI Studio key, no billing required).
  - `CLICKHOUSE_HOST`: Cloud hostname (without protocol or port).
  - `CLICKHOUSE_PORT`: `8443` (HTTPS TLS).
  - `CLICKHOUSE_USER`: Restricted reader user.
  - `CLICKHOUSE_PASSWORD`: Secret.
  - `CLICKHOUSE_ADMIN_USER` & `CLICKHOUSE_ADMIN_PASSWORD`: Secret admin credentials for event writes and DDL.
  - `CLICKHOUSE_DATABASE`: `default`.
  - `FIREBASE_PROJECT_ID`, `FIREBASE_CLIENT_EMAIL`, `FIREBASE_PRIVATE_KEY`: Secret service account credentials (Firestore Spark plan).
  - Public Vite config (`frontend/src/firebase/config.ts`) strictly uses mock/public auth credentials and never contains server private keys.

---

## 6. Automated Test Matrix

| Test Module | Command | Result |
| :--- | :--- | :---: |
| `tests/test_agent_and_mcp.py` | `pytest tests/test_agent_and_mcp.py` | 5 / 5 PASS |
| `tests/test_media_and_playback.py` | `pytest tests/test_media_and_playback.py` | 4 / 4 PASS |
| `tests/test_models_and_constraints.py` | `pytest tests/test_models_and_constraints.py` | 3 / 3 PASS |
| `tests/test_revisions.py` | `pytest tests/test_revisions.py` | 5 / 5 PASS |
| **Full Pytest Suite** | `pytest tests/` | **17 / 17 PASS (8.86s)** |
| **Frontend Production Build** | `npm --prefix frontend run build` | **0 errors (402 kB)** |
| **End-to-End Workflow Proof** | `python scripts/prove_workflow.py` | **PASS (Turn 1 & 2 verified)** |

---

## 7. Next Actions for User
1. Push git commits to `https://github.com/Syedsaadhhh/VoltraPROD`.
2. Connect the repository in the Render dashboard and create a "Web Service from Blueprint" (`render.yaml`).
3. Enter the environment variables in Render's UI (`GOOGLE_API_KEY`, `CLICKHOUSE_PASSWORD`, `FIREBASE_PRIVATE_KEY`, etc.).
4. Test live browser playback following the checklist in Section 4.
