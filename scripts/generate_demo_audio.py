import math
import struct
import wave
from pathlib import Path

def generate_wav(filepath: Path, duration_sec: float, sample_rate: int = 44100, generator_fn=None):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(sample_rate * duration_sec)
    with wave.open(str(filepath), 'wb') as wf:
        wf.setnchannels(2)  # Stereo
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(sample_rate)
        
        frames = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            left_val, right_val = generator_fn(t, duration_sec) if generator_fn else (0.0, 0.0)
            
            # Clamp to [-1.0, 1.0] and convert to 16-bit integer
            left_val = max(-1.0, min(1.0, left_val))
            right_val = max(-1.0, min(1.0, right_val))
            
            left_int = int(left_val * 32767)
            right_int = int(right_val * 32767)
            frames.extend(struct.pack('<hh', left_int, right_int))
            
        wf.writeframes(frames)
    print(f"Generated {filepath.name} ({duration_sec}s, {sample_rate}Hz, stereo)")

def footstep_wood(t, dur):
    # Short wooden tap with resonance around 180Hz and harmonic at 360Hz
    # Repeating step pattern every 0.6s
    step_time = t % 0.6
    if step_time < 0.12:
        env = math.exp(-step_time * 40.0)
        sig = math.sin(2 * math.pi * 180 * step_time) * 0.7 + math.sin(2 * math.pi * 360 * step_time) * 0.3
        val = sig * env * 0.7
        return val, val * 0.85
    return 0.0, 0.0

def footstep_concrete(t, dur):
    # Sharp, gritty transient with higher frequency clatter around 800Hz and 1600Hz
    step_time = t % 0.6
    if step_time < 0.1:
        env = math.exp(-step_time * 50.0)
        sig = math.sin(2 * math.pi * 820 * step_time) * 0.5 + math.sin(2 * math.pi * 1640 * step_time) * 0.4
        noise = (((t * 100000) % 2.0) - 1.0) * 0.15
        val = (sig + noise) * env * 0.7
        return val * 0.9, val
    return 0.0, 0.0

def door_creak(t, dur):
    # Frequency modulated groaning squeak (250Hz - 420Hz)
    freq = 280 + 120 * math.sin(2 * math.pi * 0.8 * t)
    env = math.sin(math.pi * (t / dur))  # Smooth arc
    jitter = math.sin(2 * math.pi * 12 * t) * 0.2
    val = math.sin(2 * math.pi * (freq + jitter) * t) * env * 0.5
    return val * 0.7, val

def cloth_rustle(t, dur):
    # Filtered mid-frequency noise burst mimicking jacket movement
    env = (math.sin(2 * math.pi * 1.5 * t) ** 2) * 0.4
    noise = math.sin(2 * math.pi * 1200 * t) * 0.3 + math.sin(2 * math.pi * 2400 * t) * 0.2
    val = noise * env
    return val, val * 0.8

def ambient_wind(t, dur):
    # Low ambient hollow wind with slow pitch drift (90Hz - 140Hz)
    drift = 110 + 25 * math.sin(2 * math.pi * 0.15 * t)
    env = 0.35 + 0.15 * math.sin(2 * math.pi * 0.3 * t)
    val = math.sin(2 * math.pi * drift * t) * env
    return val, val * 0.95

def tense_drone(t, dur):
    # Deep cinematic sub drone (55Hz / A1) with slight beating detuning (55.5Hz)
    osc1 = math.sin(2 * math.pi * 55.0 * t)
    osc2 = math.sin(2 * math.pi * 55.6 * t) * 0.5
    osc3 = math.sin(2 * math.pi * 110.0 * t) * 0.2
    val = (osc1 + osc2 + osc3) * 0.45
    return val * 0.9, val

def dialogue_hero(t, dur):
    # Formant synthesized vocal carrier simulating speech cadence
    formant1 = math.sin(2 * math.pi * 300 * t) * 0.4
    formant2 = math.sin(2 * math.pi * 850 * t) * 0.3
    cadence = 0.5 + 0.5 * math.sin(2 * math.pi * 2.2 * t)
    val = (formant1 + formant2) * cadence * 0.5
    return val, val

def main():
    root = Path(__file__).resolve().parent.parent
    targets = [root / "assets" / "raw", root / "frontend" / "public" / "demo"]
    
    samples = [
        ("footsteps_wood_01.wav", 3.0, footstep_wood),
        ("footsteps_concrete_01.wav", 3.0, footstep_concrete),
        ("door_creak_slow_01.wav", 2.5, door_creak),
        ("cloth_rustle_jacket_01.wav", 2.0, cloth_rustle),
        ("ambient_wind_hollow_01.wav", 8.0, ambient_wind),
        ("tense_drone_low_01.wav", 6.0, tense_drone),
        ("dialogue_hero_01.wav", 4.0, dialogue_hero),
    ]
    
    for target_dir in targets:
        print(f"\nWriting audio files to {target_dir}...")
        for name, dur, fn in samples:
            generate_wav(target_dir / name, dur, 44100, fn)
            
    print("\n[SUCCESS] All 7 real demo audio files generated in assets/raw and frontend/public/demo!")

if __name__ == "__main__":
    main()
