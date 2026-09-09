"""Google ADK / Gemini Developer API Agent Integration for VoltraPROD.

Uses google-genai with an AI Studio key (Developer API, no Vertex AI billing required).
Runs an iterative tool-calling loop connecting Gemini to:
- Official ClickHouse MCP (find_sound_candidates, recall_auditions)
- Firestore session inspector (inspect_session)
- Propose edit batch tool (propose_edit_batch)

Enforces:
- Protected track immutability (dialogue is protected)
- Bounded model turns (max 4 turns)
- Immediate exclusion of rejected asset IDs
- Graceful degradation on quota limits (429) or MCP errors
"""

import base64
import json
import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.config import settings
from app.models import Cue, CueEdit, CueEditAction, EditBatch, Session, ToolResult
from app.tools import find_sound_candidates, recall_auditions, inspect_session

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


SYSTEM_INSTRUCTION = """You are VoltraPROD's AI Sound Designer and Rehearsal Director.
You assist a film director with placing, editing, and rehearsing sound effects, foley, and ambience for a scene timeline.

YOUR WORKFLOW:
1. Always first inspect the session and check existing cues and protected tracks.
2. If prior auditions or rejections exist, call recall_auditions to understand prior feedback.
3. Call find_sound_candidates with relevant tags (e.g. ['footsteps', 'surface:wood'], ['foley', 'door'], ['ambience', 'atmosphere']) to find actual sound recordings from the ClickHouse sound catalog.
4. From the returned real candidates, choose the most appropriate asset. NEVER invent asset IDs; only use asset_ids returned by find_sound_candidates.
5. Propose a concrete edit batch by calling propose_edit_batch.

CRITICAL CONSTRAINTS:
- The 'dialogue' track is STRICTLY PROTECTED. Never propose adding, modifying, or removing cues on the 'dialogue' track.
- Only place sound cues on 'foley', 'sfx', or 'ambience' tracks.
- Numeric bounds:
  * timeline_start_ms >= 0
  * gain_db between -60.0 and 0.0 dB (e.g. -3.0 to -12.0 for subtle sounds)
  * pan between -1.0 (left) and 1.0 (right)
- When the director rejects an asset or asks for an alternative, query fresh candidates and choose a DIFFERENT asset.
"""


async def run_director_agent(
    session_id: str,
    instruction: str,
    base_revision: int,
    scene_beats: Optional[str] = None,
    video_frame_b64: Optional[str] = None,
    excluded_asset_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Execute the Gemini agent tool loop for director creative direction.

    Returns structured results including proposed EditBatch, action summary, and tool traces.
    """
    if not settings.is_gemini_configured:
        return {
            "status": "unavailable",
            "action_summary": "Gemini AI is unavailable: GOOGLE_API_KEY is not configured.",
            "rationale": "Missing API key in environment.",
            "revision": base_revision,
            "tool_traces": [],
            "error": "Gemini Developer API key is not configured.",
        }

    client = get_genai_client()
    if client is None:
        return {
            "status": "unavailable",
            "action_summary": "Could not initialize GenAI client.",
            "rationale": "Client init error.",
            "revision": base_revision,
            "tool_traces": [],
            "error": "GenAI client unavailable.",
        }

    # Cumulative excluded assets for this direction turn
    active_excluded: List[str] = list(excluded_asset_ids or [])
    tool_traces: List[Dict[str, Any]] = []
    proposed_batch_data: Optional[Dict[str, Any]] = None

    # Declare tool signatures for Gemini
    def find_sound_candidates_tool(tags: List[str] = None, min_duration_ms: int = 0, limit: int = 5) -> str:
        """Search the ClickHouse sound catalog for sound assets matching tags and duration constraints. Returns available assets."""
        return "Find sound assets in ClickHouse"

    def recall_auditions_tool(limit: int = 5) -> str:
        """Recall prior audition events, director decisions (accepted/rejected), and notes from ClickHouse."""
        return "Recall audition events"

    def inspect_session_tool() -> str:
        """Inspect current session cues, timeline start offsets, and protected tracks."""
        return "Inspect current session state"

    def propose_edit_batch_tool(edits: List[Dict[str, Any]], rationale_summary: str) -> str:
        """Propose a concrete batch of sound cue edits. Each edit item contains: action ('add'/'modify'/'remove'), cue_id (str), and cue (dict with asset_id, timeline_start_ms, gain_db, pan, track_id, envelope_points). Rationale summary explains why."""
        return "Propose edit batch"

    from google.genai import types

    tools_list = [
        find_sound_candidates_tool,
        recall_auditions_tool,
        inspect_session_tool,
        propose_edit_batch_tool,
    ]

    # Construct conversation contents
    contents_history: List[Any] = []

    # Optional multimodal frame input
    if video_frame_b64:
        try:
            # Strip data URL prefix if present
            raw_b64 = video_frame_b64.split(",")[-1]
            img_bytes = base64.b64decode(raw_b64)
            contents_history.append(
                types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
            )
            tool_traces.append({
                "tool": "stage_monitor",
                "summary": "Received video keyframe from stage for visual scene alignment",
                "status": "success",
            })
        except Exception as img_err:
            logger.warning(f"Could not parse video frame: {img_err}")

    # Build prompt with explicit provenance
    prompt_parts = []
    if scene_beats:
        prompt_parts.append(f"[Scene Beats - User Supplied]:\n{scene_beats.strip()}")
    
    prompt_parts.append(f"[Director Instruction]:\n{instruction.strip()}")
    prompt_parts.append(f"[Current Session ID]: {session_id}")
    prompt_parts.append(f"[Base Revision]: {base_revision}")
    if active_excluded:
        prompt_parts.append(f"[Excluded Asset IDs - DO NOT SELECT]: {active_excluded}")

    contents_history.append("\n\n".join(prompt_parts))

    config = types.GenerateContentConfig(
        tools=tools_list,
        temperature=0.2,
        system_instruction=SYSTEM_INSTRUCTION,
    )

    max_turns = 4
    turn = 0
    final_text_response = ""

    try:
        while turn < max_turns:
            turn += 1
            logger.info(f"Running agent turn {turn}/{max_turns} for session '{session_id}'...")

            response = await client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=contents_history,
                config=config,
            )

            function_calls = response.function_calls

            if not function_calls:
                # No further tool calls; agent completed reasoning
                final_text_response = response.text or ""
                break

            # Add model's turn with its function call to history
            contents_history.append(response.candidates[0].content)

            # Execute each function call and gather responses
            function_response_parts = []
            for call in function_calls:
                call_name = call.name
                call_args = call.args or {}
                logger.info(f"Agent tool call: {call_name} with args: {call_args}")

                if call_name == "find_sound_candidates_tool":
                    tags = call_args.get("tags") or []
                    min_dur = int(call_args.get("min_duration_ms") or 0)
                    limit = int(call_args.get("limit") or 5)
                    res = await find_sound_candidates(
                        tags=tags,
                        min_duration_ms=min_dur,
                        exclude_asset_ids=active_excluded,
                        limit=limit,
                    )
                    candidates = res.get("candidates", [])
                    tool_traces.append({
                        "tool": "find_sound_candidates",
                        "summary": f"Queried ClickHouse MCP for tags {tags}; found {len(candidates)} available asset(s)",
                        "status": res.get("status", "success"),
                        "candidates_count": len(candidates),
                    })
                    function_response_parts.append(
                        types.Part.from_function_response(
                            name=call_name,
                            response={"candidates": candidates, "status": "success"},
                        )
                    )

                elif call_name == "recall_auditions_tool":
                    limit = int(call_args.get("limit") or 5)
                    res = await recall_auditions(session_id=session_id, limit=limit)
                    events = res.get("events", [])
                    tool_traces.append({
                        "tool": "recall_auditions",
                        "summary": f"Recalled {len(events)} prior audition decision(s) from ClickHouse event store",
                        "status": res.get("status", "success"),
                    })
                    function_response_parts.append(
                        types.Part.from_function_response(
                            name=call_name,
                            response={"events": events, "status": "success"},
                        )
                    )

                elif call_name == "inspect_session_tool":
                    res = await inspect_session(session_id=session_id)
                    sess = res.get("session") or {}
                    tool_traces.append({
                        "tool": "inspect_session",
                        "summary": f"Inspected session revision {sess.get('revision', base_revision)} with {len(sess.get('cues', []))} existing cue(s)",
                        "status": res.get("status", "success"),
                    })
                    function_response_parts.append(
                        types.Part.from_function_response(
                            name=call_name,
                            response={"session": sess, "status": "success"},
                        )
                    )

                elif call_name == "propose_edit_batch_tool":
                    edits = call_args.get("edits") or []
                    rationale = call_args.get("rationale_summary") or "AI sound rehearsal treatment"
                    proposed_batch_data = {
                        "edits": edits,
                        "rationale_summary": rationale,
                    }
                    tool_traces.append({
                        "tool": "propose_edit_batch",
                        "summary": f"Proposed {len(edits)} edit(s): {rationale}",
                        "status": "success",
                    })
                    function_response_parts.append(
                        types.Part.from_function_response(
                            name=call_name,
                            response={"status": "accepted", "edits_count": len(edits)},
                        )
                    )
                else:
                    function_response_parts.append(
                        types.Part.from_function_response(
                            name=call_name,
                            response={"status": "error", "error": f"Unknown tool: {call_name}"},
                        )
                    )

            # Send function responses back to Gemini
            contents_history.append(types.Content(parts=function_response_parts))

            # If propose_edit_batch was called, the agent has made its decision
            if proposed_batch_data:
                break

    except Exception as api_err:
        err_str = str(api_err)
        logger.error(f"Error in Gemini agent loop: {err_str}")
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
            return {
                "status": "quota_exceeded",
                "action_summary": "Gemini API rate limit reached. Manual editing and playback remain active.",
                "rationale": "Free-tier quota limit encountered.",
                "revision": base_revision,
                "tool_traces": tool_traces,
                "error": "Gemini Developer API rate limit reached. Please wait a few moments before submitting your next direction.",
            }
        return {
            "status": "error",
            "action_summary": f"Agent error: {err_str}",
            "rationale": "Model invocation failed.",
            "revision": base_revision,
            "tool_traces": tool_traces,
            "error": err_str,
        }

    # Build and validate EditBatch if proposed
    clean_edits = []
    rationale = (proposed_batch_data or {}).get("rationale_summary") or final_text_response or "Rehearsal direction applied"

    if proposed_batch_data and "edits" in proposed_batch_data:
        raw_edits = proposed_batch_data["edits"]
        for idx, e in enumerate(raw_edits):
            action = e.get("action", "add")
            cue_id = e.get("cue_id") or f"cue_ai_{uuid.uuid4().hex[:6]}"
            cue_dict = e.get("cue") or {}

            # Strict protected track check
            track = cue_dict.get("track_id", "foley")
            if track == "dialogue":
                logger.warning(f"Rejecting AI edit targeting protected 'dialogue' track: {e}")
                continue

            # Strict bounds enforcement
            timeline_start = max(0, int(cue_dict.get("timeline_start_ms", 1000)))
            gain_db = max(-60.0, min(0.0, float(cue_dict.get("gain_db", -3.0))))
            pan = max(-1.0, min(1.0, float(cue_dict.get("pan", 0.0))))
            asset_id = cue_dict.get("asset_id") or "asset_footsteps_wood_01"

            # Build cue
            cue = Cue(
                id=cue_id,
                asset_id=asset_id,
                source_in_ms=int(cue_dict.get("source_in_ms", 0)),
                source_out_ms=int(cue_dict.get("source_out_ms", 3000)),
                timeline_start_ms=timeline_start,
                gain_db=gain_db,
                pan=pan,
                envelope_points=cue_dict.get("envelope_points", [
                    {"offset_ms": 0, "level": 0.0},
                    {"offset_ms": 80, "level": 1.0},
                    {"offset_ms": 2900, "level": 1.0},
                    {"offset_ms": 3000, "level": 0.0},
                ]),
                track_id=track,
            )

            clean_edits.append(CueEdit(
                action=CueEditAction(action),
                cue_id=cue_id,
                cue=cue if action in ("add", "modify") else None,
            ))

    op_id = f"op_ai_{uuid.uuid4().hex[:8]}"
    edit_batch = EditBatch(
        operation_id=op_id,
        session_id=session_id,
        expected_revision=base_revision,
        edits=clean_edits,
        rationale_summary=rationale[:500],
    )

    action_summary = f"Selected treatment ({len(clean_edits)} edit(s)): {rationale}"

    return {
        "status": "success",
        "action_summary": action_summary,
        "rationale": rationale,
        "revision": base_revision,
        "tool_traces": tool_traces,
        "edit_batch": edit_batch,
        "final_text": final_text_response,
    }

