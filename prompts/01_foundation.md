# Chunk 1 — Foundation and Real Integrations Prompt Brief

Target: 90 minutes.

## Objectives
1. Scaffold FastAPI and React with one deployable service targeting Render free web tier.
2. Implement typed configuration (`Settings`) and Pydantic domain models (`Asset`, `Cue`, `Session`, `DirectorInstruction`, `EditBatch`, `ToolResult`, `PlaybackAck`, `AuditionFeedback`) with strict numerical bounds and track protections.
3. Establish Firebase authentication and session ownership verification.
4. Implement Firestore session revision storage with optimistic revision checks (`expected_revision`), atomic transactions, and `operation_id` deduplication.
5. Implement the official `mcp-clickhouse` lifecycle client using stdio JSON-RPC subprocess connection, tool discovery, and read-only query execution with a 60-second bounded timeout.
6. Admin-only seed script creates real ClickHouse catalogue schema from `sql/001_catalog.sql`; no fake rows.
7. Preflight verification testing four distinct gates:
   - Real Gemini function call test (Developer API on AI Studio key).
   - Official ClickHouse MCP tool listing and SELECT 1 query.
   - Authenticated Firestore write/read.
   - Backend health endpoint (`/health`).
8. Explicitly record unavailable services when credentials are not configured; never fake success.
