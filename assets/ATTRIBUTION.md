# Sound Rehearsal / VoltraPROD Asset Attributions & Rights

## Asset Policy
- Real recordings imported by the filmmaker/director remain user-owned and session-local.
- Bundled demo recordings must use redistribution-authorized sources (Creative Commons 0 / Public Domain or user-recorded audio) with exact attribution.
- No synthetic or invented asset names, waveforms, or metadata are introduced into the catalog.
- If no media is provided in `assets/raw`, the interface exposes an explicit user import workflow rather than mocking playback.

## Licensing Categories
1. **User Imported Media**: Retained locally in browser storage (IndexedDB / Blob URLs). Never transmitted as raw media blobs to Firestore or ClickHouse.
2. **Bundled Demo Media**: Static files served under `/demo/` with verified permissive open-source licenses.
