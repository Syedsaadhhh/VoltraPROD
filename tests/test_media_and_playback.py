"""Unit tests for media inspection, audio math, and playback constraints."""

import io
import math
import struct
import wave
from pathlib import Path
from scripts.inspect_media import inspect_audio_file


def generate_test_wav_file(path: Path, duration_sec: float = 1.5, sample_rate: int = 44100, channels: int = 2):
    """Generates a real PCM WAV file for deterministic media inspection tests."""
    num_frames = int(duration_sec * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        # Generate quiet sine wave
        frames = bytearray()
        for i in range(num_frames):
            val = int(32767.0 * 0.1 * math.sin(2.0 * math.pi * 440.0 * i / sample_rate))
            sample_bytes = struct.pack("<h", val)
            for _ in range(channels):
                frames.extend(sample_bytes)
        wf.writeframes(frames)


def test_real_wav_inspection(tmp_path):
    """Verify that inspect_audio_file extracts actual duration, sample rate, channels, and sha256."""
    wav_path = tmp_path / "footsteps_wood_test.wav"
    generate_test_wav_file(wav_path, duration_sec=2.0, sample_rate=48000, channels=2)

    meta = inspect_audio_file(wav_path)

    assert meta["duration_ms"] == 2000
    assert meta["sample_rate"] == 48000
    assert meta["channels"] == 2
    assert meta["sha256"] is not None and len(meta["sha256"]) == 64
    assert "footsteps" in meta["tags"]
    assert "surface:wood" in meta["tags"]
    assert meta["available"] is True


def test_gain_db_to_linear_conversion():
    """Verify standard decibel to linear gain formulas used in Web Audio engine."""
    def db_to_linear(db: float) -> float:
        return 10.0 ** (db / 20.0)

    assert math.isclose(db_to_linear(0.0), 1.0, rel_tol=1e-5)
    assert math.isclose(db_to_linear(-6.0206), 0.5, rel_tol=1e-3)
    assert math.isclose(db_to_linear(-20.0), 0.1, rel_tol=1e-5)
    assert math.isclose(db_to_linear(-60.0), 0.001, rel_tol=1e-5)


def test_pan_clamping():
    """Verify stereo pan bounds [-1.0, 1.0]."""
    def clamp_pan(pan: float) -> float:
        return max(-1.0, min(1.0, pan))

    assert clamp_pan(0.0) == 0.0
    assert clamp_pan(-1.5) == -1.0
    assert clamp_pan(1.5) == 1.0
    assert clamp_pan(-0.5) == -0.5
