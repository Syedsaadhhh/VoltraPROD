# Architecture Documentation — Sound Rehearsal

## High-Level Architecture Overview

Sound Rehearsal is a browser-based sound design rehearsal agent enabling filmmakers and directors to iteratively audition sound effects, foley, and atmospheric audio against cinematic scenes.

```text
+-------------------------------------------------------------+
|                      Browser / Frontend                     |
|  - React 19 + TypeScript (Vite Single Page Application)     |
|  - Audio Scheduling & Timeline UI                          |
|  - Idempotency & Rehearsal Session Management               |
+------------------------------+------------------------------+
                               | REST / HTTP & Static Files
                               v
+-------------------------------------------------------------+
|                   FastAPI Application Service               |
|  - Config & Domain Models (app.models, app.config)          |
|  - Firebase Auth & Ownership (app.auth)                     |
|  - Firestore Revision Transactions (app.firestore_store)    |
|  - Official ClickHouse MCP Lifecycle (app.mcp_client)       |
|  - Gemini Agent & ADK Tool Handlers (app.agent, app.tools)  |
|  - Event Ingestion Sink (app.event_sink)                    |
+---------------+-----------------------------+---------------+
                |                             |
     JSON-RPC / stdio subprocess         HTTPS (gRPC)
                |                             |
                v                             v
+-------------------------------+  +--------------------------+
|      mcp-clickhouse (0.6.0)   |  |   Google Cloud Firestore |
|  - Official MCP Server        |  |   - Authoritative State  |
|  - Read-Only Mode             |  |   - Monotonic Revisions  |
|  - Connects to ClickHouse     |  |   - Track Protection     |
+---------------+---------------+  +--------------------------+
                | Native TLS (8443)
                v
+-------------------------------+
|      ClickHouse Cloud         |
|  - sound_assets (Catalogue)   |
|  - audition_events            |
|  - playback_events            |
+-------------------------------+
```

## System Responsibilities & Boundaries

1. **Gemini & Google ADK**:
   - Semantic understanding of director's creative intention.
   - Translates artistic notes (e.g. "let the audience hear the threat before she notices") into concrete asset queries and cue placements.
   - Operates through typed tools (`find_sound_candidates`, `recall_auditions`, `inspect_session`, `apply_edit_batch`).

2. **Official mcp-clickhouse Server**:
   - Long-lived stdio subprocess managed by `ClickHouseMCPClient`.
   - Read-only execution (`CLICKHOUSE_ALLOW_WRITE_ACCESS=false`).
   - Retrieves candidates based on duration, tags, and exclusions.

3. **Firestore on Spark Free Tier**:
   - Authoritative storage of session revisions (`revision` counter).
   - Optimistic concurrency control via `expected_revision`.
   - Enforces protected track boundaries (e.g. `dialogue`).
   - Operation deduplication using `operation_id`.

4. **Event Ingestion Sink**:
   - Records director feedback decisions (`accepted`, `rejected`, `unrated`) and playback acknowledgements into ClickHouse for historical recall.
