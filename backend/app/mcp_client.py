"""Official ClickHouse MCP Client Lifecycle Management.

Communicates with the official mcp-clickhouse server over stdio using JSON-RPC.
Enforces:
- 60-second bounded timeout on operations
- Read-only execution safety
- Subprocess cleanup on close
- Explicit UNAVAILABLE reporting when credentials are not configured
"""

import asyncio
import logging
import os
import sys
from typing import Dict, Any, List, Optional
from app.config import settings

logger = logging.getLogger(__name__)


class ClickHouseMCPClient:
    """Manages the official mcp-clickhouse subprocess lifecycle and tool calls."""

    def __init__(self):
        self.server_process = None
        self._session = None
        self._exit_stack = None
        self._lock = asyncio.Lock()
        self._discovered_tools: Dict[str, Any] = {}

    @property
    def is_configured(self) -> bool:
        return settings.is_clickhouse_configured

    def _get_server_env(self) -> Dict[str, str]:
        """Construct isolated environment variables for mcp-clickhouse subprocess."""
        env = os.environ.copy()
        if settings.CLICKHOUSE_HOST:
            env["CLICKHOUSE_HOST"] = settings.CLICKHOUSE_HOST
        if settings.CLICKHOUSE_PORT:
            env["CLICKHOUSE_PORT"] = str(settings.CLICKHOUSE_PORT)
        if settings.CLICKHOUSE_USER:
            env["CLICKHOUSE_USER"] = settings.CLICKHOUSE_USER
        if settings.CLICKHOUSE_PASSWORD:
            env["CLICKHOUSE_PASSWORD"] = settings.CLICKHOUSE_PASSWORD
        if settings.CLICKHOUSE_DATABASE:
            env["CLICKHOUSE_DATABASE"] = settings.CLICKHOUSE_DATABASE

        env["CLICKHOUSE_SECURE"] = "true" if settings.CLICKHOUSE_SECURE else "false"
        env["CLICKHOUSE_VERIFY"] = "true" if settings.CLICKHOUSE_VERIFY else "false"
        env["CLICKHOUSE_ALLOW_WRITE_ACCESS"] = "false"
        env["CLICKHOUSE_CONNECT_TIMEOUT"] = str(settings.CLICKHOUSE_CONNECT_TIMEOUT)
        return env

    async def _start_session(self, timeout_seconds: float = 60.0):
        """Start initialized session with official mcp-clickhouse server."""
        if not self.is_configured:
            raise RuntimeError(
                "ClickHouse is UNAVAILABLE: CLICKHOUSE_HOST or CLICKHOUSE_PASSWORD is not set."
            )

        from contextlib import AsyncExitStack
        from fastmcp import Client
        import mcp_clickhouse.mcp_server as s

        # Inject configured ClickHouse environment variables
        for k, v in self._get_server_env().items():
            os.environ[k] = v

        self._exit_stack = AsyncExitStack()
        self._session = await self._exit_stack.enter_async_context(Client(s.mcp))

        # Discover available tools
        tool_list = await asyncio.wait_for(self._session.list_tools(), timeout=timeout_seconds)
        self._discovered_tools = {tool.name: tool for tool in tool_list}
        logger.info(f"Connected to mcp-clickhouse. Discovered tools: {list(self._discovered_tools.keys())}")

    async def get_session(self, timeout_seconds: float = 60.0):
        """Ensure active initialized session with mcp-clickhouse server."""
        async with self._lock:
            if self._session is None:
                await self._start_session(timeout_seconds=timeout_seconds)
            return self._session

    async def list_tools(self, timeout_seconds: float = 60.0) -> List[Dict[str, Any]]:
        """Retrieve list of discovered MCP tools and input schemas."""
        if not self.is_configured:
            return []

        session = await self.get_session(timeout_seconds=timeout_seconds)
        res = await asyncio.wait_for(session.list_tools(), timeout=timeout_seconds)
        tools_info = []
        for t in res:
            tools_info.append({
                "name": t.name,
                "description": getattr(t, "description", ""),
                "input_schema": getattr(t, "inputSchema", getattr(t, "parameters", {})),
            })
        return tools_info

    async def execute_query(self, query: str, timeout_seconds: float = 60.0) -> Dict[str, Any]:
        """Execute a read-only SQL query via the official run_query tool."""
        if not self.is_configured:
            return {
                "status": "unavailable",
                "error": "ClickHouse is not configured. Missing CLICKHOUSE_HOST or CLICKHOUSE_PASSWORD.",
            }

        session = await self.get_session(timeout_seconds=timeout_seconds)
        if "run_query" not in self._discovered_tools:
            # Refresh tools
            t_res = await asyncio.wait_for(session.list_tools(), timeout=timeout_seconds)
            self._discovered_tools = {tool.name: tool for tool in t_res}

        if "run_query" not in self._discovered_tools:
            raise RuntimeError(f"'run_query' tool not found among {list(self._discovered_tools.keys())}")

        result = await asyncio.wait_for(
            session.call_tool("run_query", arguments={"query": query}),
            timeout=timeout_seconds,
        )

        content_output = []
        if hasattr(result, "content") and result.content:
            for c in result.content:
                if hasattr(c, "text"):
                    content_output.append(c.text)
                else:
                    content_output.append(str(c))
        elif hasattr(result, "data"):
            content_output.append(str(result.data))
        else:
            content_output.append(str(result))

        return {
            "status": "success",
            "is_error": getattr(result, "is_error", getattr(result, "isError", False)),
            "output": "\n".join(content_output),
        }

    async def close(self):
        """Gracefully terminate MCP session and close subprocess."""
        async with self._lock:
            if self._exit_stack is not None:
                try:
                    await self._exit_stack.aclose()
                except Exception as e:
                    logger.warning(f"Error while closing MCP client exit stack: {e}")
                finally:
                    self._exit_stack = None
                    self._session = None
                    self._discovered_tools.clear()


# Global MCP client instance
clickhouse_mcp = ClickHouseMCPClient()
