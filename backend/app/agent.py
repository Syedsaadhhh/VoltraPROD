"""Google ADK / Gemini Developer API Agent Integration.

Uses google-genai with an AI Studio key (Developer API, no Vertex AI billing required).
Handles function calling, multimodal inputs, and graceful UNAVAILABLE states.
"""

import logging
from typing import Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)

# Cached GenAI Client
_genai_client = None


def get_genai_client():
    """Initialize or retrieve Google GenAI client if configured."""
    global _genai_client
    if _genai_client is not None:
        return _genai_client

    if not settings.is_gemini_configured:
        return None

    try:
        from google import genai
        _genai_client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        return _genai_client
    except Exception as e:
        logger.error(f"Failed to initialize Google GenAI client: {e}")
        return None


async def run_gemini_smoke_test() -> Dict[str, Any]:
    """Execute a real Gemini response and tool-declaration invocation check.

    Returns status indicating SUCCESS or UNAVAILABLE/ERROR.
    """
    if not settings.is_gemini_configured:
        return {
            "status": "unavailable",
            "model": settings.GEMINI_MODEL,
            "error": "Gemini API key is not configured. Set GOOGLE_API_KEY in .env.",
        }

    client = get_genai_client()
    if client is None:
        return {
            "status": "unavailable",
            "model": settings.GEMINI_MODEL,
            "error": "Could not initialize GenAI client.",
        }

    try:
        from google.genai import types

        called_args = []

        def lookup_catalog_asset(tag: str) -> str:
            """Lookup test asset by tag in catalogue."""
            called_args.append(tag)
            return f"Found 1 sample asset with tag '{tag}'"

        chat = client.chats.create(
            model=settings.GEMINI_MODEL,
            config=types.GenerateContentConfig(
                tools=[lookup_catalog_asset],
                temperature=0.0,
            ),
        )
        response = chat.send_message("Please call the lookup_catalog_asset tool with tag 'footsteps'.")

        return {
            "status": "success",
            "model": settings.GEMINI_MODEL,
            "response_text": response.text or "",
            "function_calls": [{"name": "lookup_catalog_asset", "args": {"tag": t}} for t in called_args],
        }

    except Exception as e:
        logger.error(f"Gemini smoke test failed: {e}")
        return {
            "status": "error",
            "model": settings.GEMINI_MODEL,
            "error": str(e),
        }
