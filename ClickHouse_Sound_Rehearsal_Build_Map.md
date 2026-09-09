# ClickHouse sound rehearsal: build map and five-chunk handoff

Prepared September 9, 2026. Architecture specification, not an implemented or tested application. Working title: Sound Rehearsal.

## Decision

Build a browser sound-design rehearsal agent for a filmmaker revising a short scene. Gemini interprets cinematic intention and chooses edits. Official mcp-clickhouse retrieves available sound candidates and prior audition outcomes. Web Audio executes placement, envelopes and panning. Firestore stores authoritative session revisions. A Python ADK/FastAPI backend serves a built React frontend on one Render free web service. Develop in Google Antigravity. No Vertex AI, Cloud Run, Firebase Storage, paid generative audio, desktop DAW or Replit dependency.

ClickHouse credits are user-provided evidence: screenshot shows $300 active trial balance, validity September 9–October 10, 2026. This does not establish that a database service exists, credentials work, compute is unlimited or service will survive trial expiry. Keep the service small; inspect its real usage and expiry conditions.

## Blockers and first-hour gates

1. Eligibility remains unresolved. Official rules require “powered by Gemini and Google Cloud Agent Builder”, accept google-adk and google-genai, and restrict AI usage broadly to Google Cloud and selected partner tools. ADK technically supports Gemini Developer API, but that does not settle this event's eligibility interpretation. Firestore usage does not by itself settle the AI restriction.
2. The same restriction explicitly mentions OpenAI tools without an explicit development-only exemption. Sol-to-Antigravity is a conditional handoff, not a certified compliant workflow. Safest execution is to give these same chunk instructions directly to Gemini in Antigravity unless organizers confirm external planning/coding assistance is permitted. Do not obscure tool usage.
3. One real Gemini request with the user's own key must succeed on an available free-tier model. Select and pin the model after inspecting account availability and testing multimodal input plus function calling. No assumed model ID or quota. No key rotation to evade quotas; no region workaround.
4. Provision ClickHouse service and dedicated database. Verify official MCP startup, tools/list and an actual read against that service from the deployment environment. Discover tool schemas from the installed server; do not invent tool names.
5. Verify an authenticated Firestore read/write on Spark, without upgrading billing. Create a separate Firebase project; do not modify COMMONS or another existing project.
6. Deploy a minimal Python web app on the user's free hosting account immediately. Render free service is a proposed route, not verified access. Test MCP subprocess startup within its memory limit. Free services sleep and have ephemeral disks. A successful localhost demo is not a hosted submission.

Organizer clarification, ready to send by the user:

“For the ClickHouse track, may we use Google ADK with Gemini Developer API through a Google AI Studio free-tier key, Firestore on Spark, and the official mcp-clickhouse server, without Vertex AI billing? Also, does the restriction on other AI tools prohibit external AI assistance during planning/development, or only AI tooling in the submitted application?”

Do not wait to specify or implement reversible components while this is unresolved, but do not call the submission fully eligible.

## Product boundary

One real 20–30-second scene; 12–24 short recordings, each with real decoded duration, sample rate and channel count. Footsteps on different surfaces, envelope handling, door movement, cloth, ambience. Self-record with phone or use redistribution-authorized sources with exact attribution. No fictitious asset counts or manufactured usage history. Recordings derived from one source must be labeled variants, not independent recordings.

Director: “Let the audience hear the threat before she notices; keep the envelope unimportant.” Agent selects actual assets, creates an editable treatment and plays it. Director can interrupt, reject an asset, protect dialogue or change an edit point. Agent queries remaining candidates and revises. This is a working audio session, not a report or a prompt-to-audio generator.

User clicks Enable Audio to satisfy browser autoplay policy. First release accepts typed directions. Voice entry is optional after all core work; no browser speech recognition service that silently introduces an outside AI provider. Do not promise uninterrupted realtime multimodal reasoning on a free quota.

## Responsibilities

Gemini: semantic understanding, candidate selection, editing plan and reconsideration. ADK: bounded tool loop. ClickHouse: catalogue and event-history retrieval through official MCP. Firestore: session revision, operation deduplication, protected tracks and durable recovery state. Browser: media decode, exact audio scheduling, audition rendering, waveform UI. Render: backend and built static frontend. Bundled demo media: public static files. User media: local browser files; clearly session-local and must be reselected after reload if unavailable. Do not store media blobs in Firestore or ClickHouse.

Use static bundled demo assets to keep a durable judge experience without paid object storage. For user video analysis, extract bounded low-resolution frames client-side and send to the backend; state clearly that sparse frames do not provide reliable exact action timing. Optional short video analysis may use Gemini Files API with deletion/expiry handling; it is not permanent asset storage. Browser offline audio rendering can export a WAV audition. Export a JSON session with asset references. Do not promise OTIO audio-envelope compatibility or video muxing in the initial release.

## Agent loop and tool contract

Observe current revision and director intention; retrieve available candidates through MCP; select an edit plan; validate bounds and protected tracks; commit a new session revision; browser applies and acknowledges; collect measured playback/decode results and director feedback; replan if needed. Listening and evaluating artistic success must never be claimed unless the rendered audio was actually supplied to Gemini. Initial reflection uses execution feedback and human preference, with optional bounded audio review later.

Proposed application tools: inspect_session, find_sound_candidates, recall_auditions, apply_edit_batch, audition_range, restore_revision. These are custom functions; find_sound_candidates and recall_auditions must actually call the official MCP server. Admin seeding and event ingestion may use a normal ClickHouse client with a separate writer credential.

Typed entities to implement in Pydantic and mirror in TypeScript:

- Asset: id, source_path, sha256, duration_ms, sample_rate, channels, tags, source_description, rights_note, available.
- Cue: id, asset_id, source_in_ms, source_out_ms, timeline_start_ms, gain_db, pan, envelope_points, track_id.
- Session: id, owner_uid, revision, scene_duration_ms, protected_track_ids, cues, status.
- DirectorInstruction: id, session_id, base_revision, text, created_at.
- EditBatch: operation_id, session_id, expected_revision, edits, rationale_summary.
- ToolResult: operation_id, status, revision, error_code, retryable, data.
- PlaybackAck: operation_id, applied_revision, status, decoded_asset_ids, error_code, observed_at.
- AuditionFeedback: event_id, session_id, revision, asset_ids, accepted_or_rejected_or_unrated, director_text, observed_at.

Constraints: finite numeric values, pan in [-1,1], gain in [-60,0] for initial UI, ordered envelope points, source range inside decoded asset duration, no negative timeline positions, cue end inside scene, no mutation of protected tracks. A conservative gain cap is not proof of safe listening level; mix headroom and output limiting belong in the engine.

Keep one active editing turn per session. Every commit uses expected_revision and a Firestore transaction. Duplicate operation_id returns the prior result. Never call Gemini, ClickHouse or browser tools from inside a retryable Firestore transaction. Store pending application state; browser acknowledges separately. Reconnect reads current state and reconciles acknowledgements. Undo creates a new revision based on an older snapshot; revisions remain monotonic.

On stale revision, reread and replan once. On MCP timeout, retry once within a bounded request deadline; otherwise preserve the current mix and say catalogue unavailable. On missing audio, mark unavailable and query another asset. On exhausted candidates, ask the director for a recording or preserve the current treatment. On Gemini 429, honor retry information, stop excessive retries, keep manual editing functional and label AI unavailable. Never substitute scripted edits and present them as live AI.

## ClickHouse design

Tables:

sound_assets(asset_id String, sha256 String, duration_ms UInt32, sample_rate UInt32, channels UInt8, tags Array(String), source_path String, rights_note String, available UInt8), MergeTree ORDER BY asset_id.

audition_events(event_id UUID, session_id String, revision UInt32, asset_id String, decision LowCardinality(String), instruction String, occurred_at DateTime64(3)), MergeTree ORDER BY (session_id, occurred_at, event_id).

playback_events(event_id UUID, session_id String, operation_id String, revision UInt32, status LowCardinality(String), error_code String, occurred_at DateTime64(3)), MergeTree ORDER BY (session_id, occurred_at, event_id).

Use idempotent seeding and deduplicate event IDs on reads because append retries can duplicate rows. Do not use ClickHouse for session locks or assume primary keys enforce uniqueness. Firestore is authoritative; event ingestion can lag. Include current-turn rejection IDs directly in retrieval constraints so an ingestion delay cannot reselect the rejected asset.

Example retrieval intent: available footsteps on a hard surface, long enough for this cue, excluding recordings rejected in this scene; then inspect prior reasons for rejection. Use bounded result limits and allowlisted read queries. The MCP database user has SELECT on only this project database and appropriate execution limits. Never give the model admin/writer credentials or expose raw unrestricted SQL to browsers.

At prototype scale, SQLite could store this catalogue. Be honest: the demonstration proves agent-directed retrieval and feedback use through ClickHouse MCP; it does not prove an OLAP scaling advantage. More credits are not a reason to fabricate millions of events.

## Repository contract

```text
sound-rehearsal/
  README.md
  LICENSE
  .env.example
  .gitignore
  Dockerfile
  render.yaml
  backend/
    pyproject.toml
    app/main.py
    app/config.py
    app/models.py
    app/auth.py
    app/agent.py
    app/tools.py
    app/mcp_client.py
    app/firestore_store.py
    app/event_sink.py
  frontend/
    package.json
    src/App.tsx
    src/api.ts
    src/types.ts
    src/audio/engine.ts
    src/audio/render.ts
    src/components/Stage.tsx
    src/components/Timeline.tsx
    src/components/DirectionPanel.tsx
    src/components/AuditionHistory.tsx
    public/demo/
  assets/manifest.json
  assets/ATTRIBUTION.md
  scripts/preflight.py
  scripts/seed_catalog.py
  scripts/inspect_media.py
  sql/001_catalog.sql
  firestore.rules
  eval/run_benchmark.py
  eval/cases.json
  tests/test_revisions.py
  tests/test_edit_constraints.py
  docs/BUILD_STATE.md
  docs/architecture.md
  docs/demo_script.md
  docs/eligibility_questions.md
  prompts/01_foundation.md
  prompts/02_media_engine.md
  prompts/03_agent_loop.md
  prompts/04_rehearsal_experience.md
  prompts/05_delivery.md
```

## Handoff protocol

The following five chunk briefs are ready for Antigravity directly. If organizer guidance permits Sol, use Sol to expand ONE brief at a time into its named prompts file; then give that file to Gemini in Antigravity to implement. Sol must not claim tool execution or write fictional test results. No repeated architecture redesign between chunks. Carry docs/BUILD_STATE.md forward: actual files changed, commands run, outcomes, unresolved blockers, dependency versions and next action. Secrets stay in local/deployment environment, never prompts or committed files. .env.example lists empty credential fields with explanatory comments, not real values. Runtime secrets include GOOGLE_API_KEY, GEMINI_MODEL, ClickHouse host/user/password/database and scoped Firebase service credentials.

Shared instruction to the implementing model: Read this map and current BUILD_STATE. Implement only the current chunk and necessary fixes to earlier integration contracts. Use Google ADK and google-genai, the actual official mcp-clickhouse distribution, and standard non-AI dependencies. Discover current APIs and pin installed versions. No other AI provider/framework. No invented assets, usage statistics, completed operations or fallback AI answers. Explain a concrete blocker while continuing independent reversible work.

### Chunk 1 — Foundation and real integrations (target 90 minutes)

Generate prompts/01_foundation.md from this brief. Scaffold FastAPI and React with one deployable service. Implement config and typed models, Firebase authentication, ownership checks, Firestore revision storage, MCP lifecycle and read-only connection. Admin-only seed script creates real catalogue schema; no fake rows. Preflight tests one real Gemini function call and one image input on an available free model, MCP tools/list and SELECT, Firestore roundtrip and public health route. Detect missing secrets without printing them. Discover exact official MCP startup arguments from its installed version. Use a long-lived subprocess connection, not installation or server startup per request. Bind web process to hosting PORT. Deploy skeleton now. Gate: all integrations work from the deployed backend, or explicitly record the unavailable service before proceeding with independent UI work.

### Chunk 2 — Real media and editable playback (target 120 minutes)

Generate prompts/02_media_engine.md. Implement asset inspection and manifest generation from actual files, seed their metadata into ClickHouse, and build browser Web Audio scheduling. A real user audio-enable gesture initializes AudioContext. Implement gain envelopes, panning, seek, pause, clip reposition, offline WAV render and JSON export. Stop/reschedule active audio when edits or seeks invalidate scheduled sources. Keep video/audio drift bounded and measure it locally; do not claim sample-accurate video synchronization. On unavailable demo recordings, provide an explicit capture/import workflow and mark the asset dependency; never replace the scene with a fake playback UI. Gate: manual edits audibly change a real scene; seek/pause do not leave ghost audio playing.

### Chunk 3 — Gemini agent and ClickHouse decisions (target 150 minutes)

Generate prompts/03_agent_loop.md. Implement a bounded ADK loop with tools described above. MCP queries must influence actual asset choices. A direction triggers inspect, retrieve, plan, apply and audition; allow tools to execute across turns rather than fixing a predetermined sequence. Use revision and idempotency enforcement. Persist execution feedback and actual director decisions. Start with at most four model requests per director instruction, bounded output, limited tool results and one bounded retry per transient service failure; tune to observed quota. Cache scene interpretation by media hash, not canned responses by prompt. Gate: reject the first sound at runtime, then observe a fresh MCP query excluding it and an audible different treatment. Test stale revision and missing asset handling.

### Chunk 4 — Rehearsal experience and resilience (target 90 minutes)

Generate prompts/04_rehearsal_experience.md. Deliver a coherent studio interface: video stage, real waveform/timeline, editable sound layers, direction box and compact audition history. Show short action summaries and actual tool statuses, never private chain-of-thought. Add protect dialogue, compare revisions, undo, reconnect and clear unavailable states. Use finite Firestore subscriptions and bounded event reads, not frame-by-frame writes. Current revision is visible; late model responses cannot overwrite manual edits. Authentication must not require organizer-specific credentials; support isolated anonymous judge sessions if Firebase anonymous auth is enabled. Gate: a new visitor opens the hosted project, enables audio, runs a direction and revises the audition without setup.

### Chunk 5 — Evidence, deployment and submission (target 90 minutes; reserve remaining time for capture/submission)

Generate prompts/05_delivery.md. Finish clean setup documentation, MIT or another deliberate OSI license for original code, separate asset licensing, architecture and a three-minute demo. Add eval/run_benchmark.py for protected dialogue, stale revision, rejected candidate, unavailable asset, MCP timeout, Gemini quota failure and ordinary creative revision. Deterministic tests cover operational correctness; creative quality is reported from actual human preference only. Live evaluation is explicit and bounded to conserve quota. Print case status, actual model/tool counts, elapsed time and measured usage; unknown costs are null, never zero. Compare a fixed first-tag-match baseline on asset choice under changing constraints, without claiming it measures artistic quality. Validate hosted runtime, real MCP queries, source accessibility and exported audition. Record limitations: free-tier rate caps, hosting sleep, trial expiry, no professional DAW integration and unresolved eligibility interpretation. Produce demo narration and submission text from actual implemented behavior only.

## Sources checked

- Official event rules: https://agentic-cinema.devpost.com/rules
- ADK Gemini integration: https://adk.dev/agents/models/google-gemini/
- Gemini free pricing and limits: https://ai.google.dev/gemini-api/docs/pricing and https://ai.google.dev/gemini-api/docs/rate-limits
- Supported regions (includes Pakistan): https://ai.google.dev/gemini-api/docs/available-regions
- Firestore/Firebase pricing: https://firebase.google.com/pricing
- Firebase Storage billing requirement: https://firebase.google.com/docs/storage/faqs-storage-changes-announced-sept-2024
- Official ClickHouse MCP: https://github.com/ClickHouse/mcp-clickhouse
- Render free service limits: https://render.com/docs/free

These sources establish documented capabilities and restrictions. No user account connectivity, quota, service provisioning or deployment has been tested in preparing this map.
