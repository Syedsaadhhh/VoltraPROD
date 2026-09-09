import sys, time
from pathlib import Path

backend_dir = Path("backend").resolve()
sys.path.insert(0, str(backend_dir))
from app.config import settings
from google import genai

client = genai.Client(api_key=settings.GOOGLE_API_KEY)

video_path = Path("assets/raw/scene.mp4")
print(f"Uploading {video_path.name} ({video_path.stat().st_size} bytes) to Gemini Files API...")

video_file = client.files.upload(file=str(video_path))
print(f"Uploaded file name: {video_file.name}, state: {video_file.state}")

# Wait for processing if needed
while video_file.state.name == "PROCESSING":
    print("Waiting for video processing...")
    time.sleep(2)
    video_file = client.files.get(name=video_file.name)

print(f"File ready with state: {video_file.state.name}")

prompt = """Analyze this 10-second silent video clip in detail.
Provide:
1. Overall visual description and setting.
2. Exact action timings (e.g. 0.0s - X.Xs, X.Xs - Y.Ys): what happens at each second.
3. Framing changes: camera movements (pan, tilt, zoom, dolly), shot types (wide, medium, close-up), and framing adjustments.
4. Specific opportunities for sound placement (foley footsteps, cloth, door, ambience).
"""

response = client.models.generate_content(
    model=settings.GEMINI_MODEL,
    contents=[video_file, prompt]
)

print("\n=== VISUAL SCENE ANALYSIS ===")
print(response.text)

# Clean up uploaded file per privacy & temporary storage guidelines
try:
    client.files.delete(name=video_file.name)
    print("\n[CLEANUP] Deleted temporary video from Gemini Files API.")
except Exception as e:
    print(f"Cleanup note: {e}")
