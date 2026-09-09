"""Media reconciliation script for VoltraPROD Run 4.

- Inspects and decodes real recordings in assets/raw.
- Copies approved real recordings to frontend/public/demo.
- Deletes obsolete generated fixture WAVs from frontend/public/demo.
- Invalidates obsolete fixture entries in ClickHouse sound_assets table.
- Upserts the 5 real audio recordings into ClickHouse sound_assets table.
- Updates assets/manifest.json.
"""

import hashlib
import json
import os
import shutil
import sys
import wave
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.config import settings

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "assets" / "raw"
DEMO_DIR = ROOT / "frontend" / "public" / "demo"
MANIFEST_PATH = ROOT / "assets" / "manifest.json"

OBSOLETE_FIXTURE_IDS = [
    "asset_ambient_wind_hollow_01",
    "asset_cloth_rustle_jacket_01",
    "asset_dialogue_hero_01",
    "asset_door_creak_slow_01",
    "asset_footsteps_concrete_01",
    "asset_footsteps_wood_01",
    "asset_tense_drone_low_01",
]

OBSOLETE_FIXTURE_FILES = [
    "ambient_wind_hollow_01.wav",
    "cloth_rustle_jacket_01.wav",
    "dialogue_hero_01.wav",
    "door_creak_slow_01.wav",
    "footsteps_concrete_01.wav",
    "footsteps_wood_01.wav",
    "tense_drone_low_01.wav",
]


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def inspect_audio(path: Path) -> dict:
    ext = path.suffix.lower()
    sha256 = compute_sha256(path)
    if ext == ".wav":
        with wave.open(str(path), "rb") as wf:
            channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            frames = wf.getnframes()
            duration_ms = int((frames / float(sample_rate)) * 1000)
    else:
        raise ValueError(f"Unsupported audio format: {path.name}")

    stem = path.stem.lower()
    asset_id = f"asset_{stem}"

    # Tag assignments based on actual real recorded content
    tags = ["sfx"]
    desc = f"Recording: {path.stem}"
    if "footsep" in stem or "footstep" in stem:
        tags.extend(["foley", "footsteps"])
        if "heavy" in stem:
            tags.append("heavy")
            desc = "Recording: Heavy footsteps"
        elif "normal" in stem:
            tags.append("normal")
            desc = "Recording: Normal footsteps"
    elif "door" in stem:
        tags.extend(["door", "foley", "impact"])
        desc = "Recording: Door closing"
    elif "paper" in stem:
        tags.extend(["foley", "handling", "paper"])
        desc = "Recording: Paper folding"
    elif "room" in stem:
        tags.extend(["ambience", "atmosphere", "interior", "room_tone"])
        desc = "Recording: Indoor room tone"

    return {
        "id": asset_id,
        "source_path": f"demo/{path.name}",
        "sha256": sha256,
        "duration_ms": duration_ms,
        "sample_rate": sample_rate,
        "channels": channels,
        "tags": sorted(list(set(tags))),
        "source_description": desc,
        "rights_note": "User Provided / Real Recording",
        "available": True,
    }


def reconcile():
    print("=== Reconciling Media Assets ===")

    # 1. Clean obsolete fixture copies from frontend/public/demo
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    removed_count = 0
    for old_file in OBSOLETE_FIXTURE_FILES:
        target = DEMO_DIR / old_file
        if target.exists():
            target.unlink()
            print(f"Removed obsolete fixture file: {target.name}")
            removed_count += 1
    print(f"Removed {removed_count} obsolete fixture files from {DEMO_DIR}")

    # 2. Inspect real audio recordings in assets/raw
    audio_files = sorted([
        f for f in RAW_DIR.iterdir()
        if f.is_file() and f.suffix.lower() == ".wav"
    ])
    print(f"\nFound {len(audio_files)} real audio files in {RAW_DIR}")

    real_assets = []
    for af in audio_files:
        meta = inspect_audio(af)
        real_assets.append(meta)
        print(f"  - {meta['id']}: {meta['duration_ms']}ms, {meta['sample_rate']}Hz, {meta['channels']}ch, tags={meta['tags']}")

        # Copy to demo directory
        dest = DEMO_DIR / af.name
        shutil.copy2(af, dest)
        print(f"    -> Copied to {dest}")

    # 3. Copy cropped scene.mp4 to demo directory
    scene_src = RAW_DIR / "scene.mp4"
    if scene_src.exists():
        scene_dest = DEMO_DIR / "scene.mp4"
        shutil.copy2(scene_src, scene_dest)
        print(f"\nCopied cropped scene.mp4 to {scene_dest} ({scene_src.stat().st_size} bytes)")

    # 4. Save updated manifest.json
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    manifest_data = {"assets": real_assets}
    MANIFEST_PATH.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
    print(f"\nUpdated {MANIFEST_PATH} with {len(real_assets)} assets.")

    # 5. Invalidate obsolete entries and insert real assets in ClickHouse
    if not settings.is_clickhouse_configured:
        print("\n[WARN] ClickHouse not configured in settings. Skipping database sync.")
        return

    print("\nConnecting to ClickHouse Cloud to reconcile catalogue...")
    import clickhouse_connect
    admin_user = settings.CLICKHOUSE_ADMIN_USER or settings.CLICKHOUSE_USER
    admin_password = settings.CLICKHOUSE_ADMIN_PASSWORD or settings.CLICKHOUSE_PASSWORD

    client = clickhouse_connect.get_client(
        host=settings.CLICKHOUSE_HOST,
        port=settings.CLICKHOUSE_PORT,
        username=admin_user,
        password=admin_password,
        database=settings.CLICKHOUSE_DATABASE,
        secure=settings.CLICKHOUSE_SECURE,
        verify=settings.CLICKHOUSE_VERIFY,
        connect_timeout=settings.CLICKHOUSE_CONNECT_TIMEOUT,
    )

    # Invalidate obsolete fixture entries scoped to known fixture IDs
    escaped_ids = ", ".join(f"'{fid}'" for fid in OBSOLETE_FIXTURE_IDS)
    try:
        # Mark available = 0
        update_stmt = f"ALTER TABLE {settings.CLICKHOUSE_DATABASE}.sound_assets UPDATE available = 0 WHERE asset_id IN ({escaped_ids})"
        print(f"Invalidating obsolete fixtures in ClickHouse: {update_stmt}")
        client.command(update_stmt)
        print("Obsolete fixture catalogue entries marked available = 0.")
    except Exception as e:
        print(f"Note on fixture invalidation: {e}")

    # Insert new real assets
    rows = []
    for a in real_assets:
        rows.append([
            a["id"],
            a["sha256"],
            a["duration_ms"],
            a["sample_rate"],
            a["channels"],
            a["tags"],
            a["source_path"],
            a["rights_note"],
            1 if a["available"] else 0,
        ])

    client.insert(
        "sound_assets",
        rows,
        column_names=[
            "asset_id",
            "sha256",
            "duration_ms",
            "sample_rate",
            "channels",
            "tags",
            "source_path",
            "rights_note",
            "available",
        ],
    )
    print(f"[SUCCESS] Seeded {len(rows)} real assets into ClickHouse '{settings.CLICKHOUSE_DATABASE}.sound_assets'.")

    # Verify query
    probe = client.query(f"SELECT asset_id, duration_ms, sample_rate, channels, tags, available FROM {settings.CLICKHOUSE_DATABASE}.sound_assets WHERE available = 1")
    print(f"\nActive assets in ClickHouse ({len(probe.result_rows)} rows):")
    for r in probe.result_rows:
        print(f"  {r[0]}: {r[1]}ms, {r[2]}Hz, {r[3]}ch, tags={r[4]}")


if __name__ == "__main__":
    reconcile()
