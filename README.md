# VoltraPROD

> **AI-Directed Sound Rehearsal Studio**  
> VoltraPROD is an intelligent sound rehearsal and audio-post production platform designed for dialogue, sound effects, foley, and ambient score placement against video and audio timelines.  
> **Live Hosted Deployment**: [https://sound-rehearsal.onrender.com](https://sound-rehearsal.onrender.com)

---

## System Architecture

```mermaid
graph TD
    User([Sound Designer / Director]) <--> Frontend[VoltraPROD Web Shell (React 19 + Web Audio Engine)]
    Frontend <-->|REST API / Bearer Token| Backend[FastAPI Backend (Python 3.12)]
    Backend <-->|google-genai SDK Loop| Gemini[Gemini Developer API (gemini-3.1-flash-lite)]
    Backend <-->|FastMCP stdio| MCP[Official mcp-clickhouse Server]
    MCP <-->|Port 8443 HTTPS| ClickHouse[(ClickHouse Cloud Catalog & Analytics)]
    Backend <-->|google-cloud-firestore| Firestore[(Firebase Firestore Revision Store)]
```

### Core Architecture Highlights
- **Web Audio Scheduling Engine**: Browser-native deterministic playback scheduler, volume envelopes, stereo panning, dynamic compression, immediate cancellation on seek/pause/edit, offline 16-bit stereo PCM WAV rendering, and JSON session interchange.
- **Session-Local Media Isolation**: Raw audio and video files remain strictly local to the user's browser session. Only bounded metadata, audio hashes, and cue timings are transmitted to backend and ClickHouse, ensuring low latency and privacy.
- **Google GenAI Agent Loop**: Uses `google-genai` Python SDK with `gemini-3.1-flash-lite` in an iterative tool-calling loop using explicit `FunctionDeclaration` bindings to ClickHouse MCP, Firestore revision inspection, and atomic edit batch proposals.
- **Official ClickHouse MCP**: Uses `mcp-clickhouse` (FastMCP) over stdio connecting to ClickHouse Cloud on port 8443 (HTTPS) with a dedicated read-only role (`sound_rehearsal_reader`).
- **Firestore Session Revisions**: Spark free plan compatibility with atomic monotonic revisions, optimistic locking (`expected_revision`), and protected dialogue track safeguards.
- **Audition & Verification Scope**: Automated proof scripts (`scripts/prove_workflow.py`) execute scripted programmatic feedback turns; acoustic balance and audible quality require human audition via physical speakers or headphones.

---

## Project Structure

`
VoltraPROD/
├── assets/                  # Media attribution and session assets
├── backend/
│   ├── app/
│   │   ├── config.py        # Settings loader and credential validator
│   │   ├── models.py        # Pydantic schemas and domain bounds
│   │   ├── auth.py          # Firebase Bearer token verification
│   │   ├── firestore_store.py # Monotonic revision store
│   │   ├── mcp_client.py    # Official ClickHouse MCP client
│   │   ├── agent.py         # Google GenAI model integration
│   │   ├── tools.py         # Catalog lookup and rehearsal tools
│   │   ├── event_sink.py    # ClickHouse telemetry sink
│   │   └── main.py          # FastAPI application & SPA static server
│   ├── pyproject.toml       # Backend dependencies
│   └── requirements.lock    # 125 exact pinned dependencies
├── frontend/
│   ├── src/
│   │   ├── audio/
│   │   │   ├── engine.ts    # Web Audio API playback scheduler
│   │   │   └── render.ts    # Offline WAV renderer & JSON export
│   │   ├── components/
│   │   │   ├── Stage.tsx    # Video & audio preview with A/V drift
│   │   │   ├── Timeline.tsx # Multi-track timeline & cue inspector
│   │   │   └── DirectionPanel.tsx # Import & revision management
│   │   ├── api.ts           # Backend client
│   │   ├── firebase.ts      # Firebase Auth client
│   │   └── App.tsx          # Studio dashboard
│   └── dist/                # Production build artifacts
├── docs/
│   ├── BUILD_STATE.md       # Authoritative build state & run log
│   ├── architecture.md      # High-level architecture map
│   └── eligibility_questions.md # System requirements
├── sql/
│   └── 001_catalog.sql      # ClickHouse schema DDL
├── scripts/
│   ├── preflight.py         # 4-gate integration test
│   ├── seed_catalog.py      # ClickHouse table seeder
│   └── inspect_media.py     # Audio metadata & manifest generator
├── tests/                   # Pytest test suite (11 unit tests)
├── Dockerfile               # Production multi-stage Docker build
└── render.yaml              # Render Blueprint specification
`

---

## Quick Start (Local Development)

### 1. Prerequisites
- Python 3.12+
- Node.js 20+
- uv (recommended package manager) or pip

### 2. Environment Setup
Copy the example environment configuration and fill in your keys:
`ash
cp .env.example .env
`

Required variables:
- GOOGLE_API_KEY: Google AI Studio API key.
- CLICKHOUSE_HOST: ClickHouse Cloud host (e.g. xyz.region.clickhouse.cloud).
- CLICKHOUSE_PASSWORD: ClickHouse Cloud password.
- FIREBASE_PROJECT_ID, FIREBASE_CLIENT_EMAIL, FIREBASE_PRIVATE_KEY: Firebase Service Account credentials.

### 3. Backend Setup
`ash
# Create virtual environment and install dependencies
uv venv .venv --python 3.12
.venv/Scripts/activate       # On Windows (.venv/bin/activate on Linux/macOS)
uv pip install -r backend/requirements.lock

# Run test suite
python -m pytest tests/

# Run integration preflight check
python scripts/preflight.py
`

### 4. Frontend Setup
`ash
cd frontend
npm install
npm run build
cd ..
`

### 5. Launch Application
To launch the FastAPI server (which automatically serves the compiled frontend):
`ash
.venv/Scripts/python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
`
Navigate to http://localhost:8000 to open VoltraPROD.

For frontend hot-reload development:
`ash
cd frontend
npm run dev
`

---

## Deployment (Render)

VoltraPROD includes a production-ready Dockerfile and 
ender.yaml blueprint targeted for Render's free tier.

1. Push your repository to GitHub.
2. In the [Render Dashboard](https://dashboard.render.com/), select **New +** -> **Blueprint**.
3. Connect your VoltraPROD repository.
4. Set the required environment variables under the service settings.
5. Deploy. Render will execute the multi-stage Docker build and serve the FastAPI application with /health preflight checks.

---

## Testing

Run the automated backend test suite:
`ash
.venv/Scripts/python.exe -m pytest tests -v
`

Verification covers:
- Asset, Cue, and Session domain constraints.
- Monotonic revision increments, optimistic lock rejection, and protected track validation.
- Audio manifest generation and clickhouse catalog payload compatibility.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
