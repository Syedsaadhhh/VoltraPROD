"""Preflight integration verification script for Sound Rehearsal Run 1.

Performs bounded real integration checks:
1. One real Gemini response and tool invocation.
2. Official ClickHouse MCP discovery and a real SELECT 1 query.
3. An authenticated Firestore write/read.
4. Backend health endpoint.

Reports explicit UNAVAILABLE states when credentials are missing.
Never fakes success or outputs sensitive values.
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.agent import run_gemini_smoke_test
from app.mcp_client import clickhouse_mcp
from app.firestore_store import get_firestore_client


async def check_gemini() -> dict:
    print("\n--- Gate 1: Gemini Developer API Integration ---")
    if not settings.is_gemini_configured:
        print("[UNAVAILABLE] GOOGLE_API_KEY is not set in environment or .env.")
        print("To configure: Enter your free-tier Google AI Studio API key in .env as GOOGLE_API_KEY.")
        return {"status": "UNAVAILABLE", "reason": "Missing GOOGLE_API_KEY"}

    print(f"Testing real Gemini call with model '{settings.GEMINI_MODEL}' and function calling...")
    try:
        res = await asyncio.wait_for(run_gemini_smoke_test(), timeout=30.0)
        if res.get("status") == "success":
            print(f"[SUCCESS] Gemini response received. Function calls: {res.get('function_calls')}")
            return {"status": "SUCCESS", "details": res}
        else:
            print(f"[FAIL] Gemini call failed: {res.get('error')}")
            return {"status": "FAIL", "error": res.get("error")}
    except asyncio.TimeoutError:
        print("[FAIL] Gemini smoke test timed out after 30 seconds.")
        return {"status": "FAIL", "error": "Timeout"}
    except Exception as e:
        print(f"[FAIL] Gemini test exception: {e}")
        return {"status": "FAIL", "error": str(e)}


async def check_clickhouse_mcp() -> dict:
    print("\n--- Gate 2: Official ClickHouse MCP Server Integration ---")
    if not settings.is_clickhouse_configured:
        print("[UNAVAILABLE] ClickHouse Cloud credentials are not set in environment or .env.")
        print("To configure: Set CLICKHOUSE_HOST, CLICKHOUSE_USER, and CLICKHOUSE_PASSWORD in .env.")
        return {"status": "UNAVAILABLE", "reason": "Missing CLICKHOUSE_HOST / CLICKHOUSE_PASSWORD"}

    print("Launching official mcp-clickhouse subprocess via stdio...")
    try:
        # Step A: Discover tools
        tools = await asyncio.wait_for(clickhouse_mcp.list_tools(timeout_seconds=25.0), timeout=30.0)
        tool_names = [t["name"] for t in tools]
        print(f"[SUCCESS] Discovered {len(tools)} tools from official MCP server: {tool_names}")

        # Step B: Run SELECT 1 query
        print("Executing read-only SELECT 1 query via run_query tool...")
        q_res = await asyncio.wait_for(clickhouse_mcp.execute_query("SELECT 1 AS probe", timeout_seconds=25.0), timeout=30.0)
        print(f"[SUCCESS] Query result: {q_res.get('output')}")

        return {"status": "SUCCESS", "tools": tool_names, "query_output": q_res.get("output")}
    except asyncio.TimeoutError:
        print("[FAIL] ClickHouse MCP operation timed out within bounded limit.")
        return {"status": "FAIL", "error": "MCP timeout"}
    except Exception as e:
        print(f"[FAIL] ClickHouse MCP check failed: {e}")
        return {"status": "FAIL", "error": str(e)}
    finally:
        print("Closing MCP subprocess cleanly...")
        await clickhouse_mcp.close()


async def check_firestore() -> dict:
    print("\n--- Gate 3: Authenticated Firestore Write/Read ---")
    if not settings.is_firestore_configured:
        print("[UNAVAILABLE] Firebase/Firestore credentials are not set in environment or .env.")
        print("To configure: Set FIREBASE_PROJECT_ID with service account credentials in .env.")
        return {"status": "UNAVAILABLE", "reason": "Missing Firebase credentials"}

    print("Connecting to Firestore on Spark plan...")
    try:
        db = get_firestore_client()
        if db is None:
            print("[FAIL] Could not initialize Firestore client.")
            return {"status": "FAIL", "error": "Client init failed"}

        test_id = f"preflight_test_{uuid.uuid4().hex[:8]}"
        doc_ref = db.collection("_preflight_probes").document(test_id)

        # Write
        payload = {"probe_id": test_id, "timestamp": datetime.now(timezone.utc).isoformat()}
        doc_ref.set(payload)
        print(f"Wrote test probe document: {test_id}")

        # Read
        snap = doc_ref.get()
        if not snap.exists or snap.to_dict().get("probe_id") != test_id:
            print("[FAIL] Firestore probe document verification failed.")
            return {"status": "FAIL", "error": "Data mismatch"}

        print(f"[SUCCESS] Verified roundtrip read of probe document: {test_id}")

        # Clean up test probe document
        doc_ref.delete()
        print("Deleted test probe document.")
        return {"status": "SUCCESS", "probe_id": test_id}
    except Exception as e:
        print(f"[FAIL] Firestore test failed: {e}")
        return {"status": "FAIL", "error": str(e)}


async def check_health_endpoint() -> dict:
    print("\n--- Gate 4: Backend Health Endpoint ---")
    from app.main import app
    from httpx import AsyncClient, ASGITransport

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            if resp.status_code == 200:
                print(f"[SUCCESS] /health endpoint returned 200 OK: {resp.json()}")
                return {"status": "SUCCESS", "data": resp.json()}
            else:
                print(f"[FAIL] /health returned status {resp.status_code}: {resp.text}")
                return {"status": "FAIL", "status_code": resp.status_code}
    except Exception as e:
        print(f"[FAIL] Health endpoint check exception: {e}")
        return {"status": "FAIL", "error": str(e)}


async def main():
    print("================================================================")
    print("      SOUND REHEARSAL: PREFLIGHT INTEGRATION VERIFICATION       ")
    print("================================================================")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Python: {sys.version}")

    results = {}
    results["gemini"] = await check_gemini()
    results["clickhouse_mcp"] = await check_clickhouse_mcp()
    results["firestore"] = await check_firestore()
    results["health"] = await check_health_endpoint()

    print("\n================================================================")
    print("                      PREFLIGHT SUMMARY                         ")
    print("================================================================")
    for gate, res in results.items():
        status = res.get("status")
        extra = res.get("reason") or res.get("error") or "Verified OK"
        print(f"  * {gate:18}: [{status}] - {extra}")
    print("================================================================")


if __name__ == "__main__":
    asyncio.run(main())
