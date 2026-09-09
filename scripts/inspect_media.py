"""Inspects real audio files, extracts metadata, generates assets/manifest.json,
and optionally seeds records into ClickHouse sound_assets table.
"""

import argparse
import hashlib
import json
import os
import sys
import wave
from pathlib import Path
from typing import Dict, Any, List

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.config import settings


def compute_sha256(file_path: Path) -> str:
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def inspect_audio_file(file_path: Path) -> Dict[str, Any]:
    """Inspect WAV or generic audio file to obtain duration_ms, sample_rate, channels."""
    ext = file_path.suffix.lower()
    sha256 = compute_sha256(file_path)

    sample_rate = 44100
    channels = 2
    duration_ms = 1000

    if ext == ".wav":
        try:
            with wave.open(str(file_path), "rb") as wf:
                channels = wf.getnchannels()
                sample_rate = wf.getframerate()
                frames = wf.getnframes()
                duration_ms = int((frames / float(sample_rate)) * 1000)
        except Exception as e:
            print(f"Warning: Could not parse WAV header for {file_path.name}: {e}")
    else:
        # Generic heuristic based on file size if header parser unavailable
        stat = file_path.stat()
        duration_ms = max(1000, int((stat.st_size / (44100 * 2 * 2)) * 1000))

    asset_id = f"asset_{file_path.stem.lower().replace(' ', '_').replace('-', '_')}"

    # Infer reasonable default tags from name
    stem = file_path.stem.lower()
    tags = ["sfx"]
    if "footstep" in stem or "walk" in stem or "step" in stem:
        tags.extend(["foley", "footsteps"])
        if "wood" in stem:
            tags.append("surface:wood")
        elif "concrete" in stem:
            tags.append("surface:concrete")
    elif "door" in stem or "creak" in stem:
        tags.extend(["foley", "door"])
    elif "wind" in stem or "ambient" in stem or "room" in stem:
        tags.extend(["ambience", "atmosphere"])
    elif "cloth" in stem or "movement" in stem:
        tags.extend(["foley", "cloth"])

    return {
        "id": asset_id,
        "source_path": f"demo/{file_path.name}",
        "sha256": sha256,
        "duration_ms": duration_ms,
        "sample_rate": sample_rate,
        "channels": channels,
        "tags": sorted(list(set(tags))),
        "source_description": f"Recording: {file_path.stem}",
        "rights_note": "User Provided / Public Domain",
        "available": True,
    }


def seed_to_clickhouse(assets: List[Dict[str, Any]]):
    """Seed asset metadata rows into ClickHouse sound_assets table."""
    if not settings.is_clickhouse_configured:
        print("[FAIL] Cannot seed ClickHouse: credentials are not configured in .env.")
        return

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
    )

    rows = []
    for a in assets:
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
    print(f"[SUCCESS] Seeded {len(rows)} real asset rows into ClickHouse '{settings.CLICKHOUSE_DATABASE}.sound_assets'.")


def main():
    parser = argparse.ArgumentParser(description="Inspect audio assets and generate manifest.json")
    parser.add_argument("--dir", default="assets/raw", help="Directory containing audio files")
    parser.add_argument("--seed", action="store_true", help="Seed inspected assets into ClickHouse Cloud")
    args = parser.parse_args()

    audio_dir = Path(__file__).resolve().parent.parent / args.dir
    audio_dir.mkdir(parents=True, exist_ok=True)

    audio_extensions = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}
    files = [f for f in audio_dir.iterdir() if f.is_file() and f.suffix.lower() in audio_extensions]

    print(f"Inspecting directory: {audio_dir} (found {len(files)} audio files)")

    assets = []
    for f in files:
        asset_meta = inspect_audio_file(f)
        assets.append(asset_meta)
        print(f"  - {asset_meta['id']}: {asset_meta['duration_ms']}ms, {asset_meta['sample_rate']}Hz, {asset_meta['channels']}ch, tags={asset_meta['tags']}")

    manifest_path = Path(__file__).resolve().parent.parent / "assets" / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({"assets": assets}, indent=2), encoding="utf-8")
    print(f"Saved manifest to {manifest_path} ({len(assets)} assets)")

    if args.seed and assets:
        seed_to_clickhouse(assets)


if __name__ == "__main__":
    main()
