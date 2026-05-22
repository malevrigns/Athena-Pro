from __future__ import annotations

import asyncio

import pytest

from athena.research.tools import PermissionLevel, ToolResult, ToolRouter, ToolSpec


async def _ok_handler(arguments: dict):
    return ToolResult(
        ok=True,
        summary="ok",
        structured_output={"echo": arguments},
    )


def test_tool_router_registers_and_lists_specs_for_llm():
    router = ToolRouter()
    router.register(
        ToolSpec(
            name="paper_search",
            description="Search papers",
            parameters_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            permission_level=PermissionLevel.network_read,
            handler=_ok_handler,
        )
    )

    assert router.names() == ["paper_search"]
    assert router.get("paper_search").permission_level is PermissionLevel.network_read
    assert router.specs_for_llm() == [
        {
            "type": "function",
            "function": {
                "name": "paper_search",
                "description": "Search papers",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        }
    ]


def test_tool_router_rejects_duplicate_names():
    spec = ToolSpec(
        name="paper_search",
        description="Search papers",
        parameters_schema={"type": "object"},
        handler=_ok_handler,
    )
    router = ToolRouter([spec])

    with pytest.raises(ValueError, match="already registered"):
        router.register(spec)


@pytest.mark.asyncio
async def test_tool_router_executes_async_handler():
    router = ToolRouter([
        ToolSpec(
            name="echo",
            description="Echo arguments",
            parameters_schema={"type": "object"},
            handler=_ok_handler,
        )
    ])

    result = await router.execute("echo", {"query": "rag"})

    assert result.ok is True
    assert result.summary == "ok"
    assert result.structured_output == {"echo": {"query": "rag"}}


@pytest.mark.asyncio
async def test_tool_router_executes_sync_handler():
    def handler(arguments: dict):
        return {"ok": True, "summary": "sync", "structured_output": arguments}

    router = ToolRouter([
        ToolSpec(
            name="sync_tool",
            description="Sync tool",
            parameters_schema={"type": "object"},
            handler=handler,
        )
    ])

    result = await router.execute("sync_tool", {"x": 1})

    assert result.ok is True
    assert result.summary == "sync"
    assert result.structured_output == {"x": 1}


@pytest.mark.asyncio
async def test_tool_router_unknown_tool_raises():
    router = ToolRouter()

    with pytest.raises(KeyError, match="unknown tool"):
        await router.execute("missing", {})


@pytest.mark.asyncio
async def test_tool_router_converts_handler_exception_to_failed_result():
    async def handler(_arguments: dict):
        raise RuntimeError("boom")

    router = ToolRouter([
        ToolSpec(
            name="bad",
            description="Bad tool",
            parameters_schema={"type": "object"},
            handler=handler,
        )
    ])

    result = await router.execute("bad", {})

    assert result.ok is False
    assert result.summary == "boom"
    assert result.error == "RuntimeError"


@pytest.mark.asyncio
async def test_tool_router_times_out_slow_handler():
    async def handler(_arguments: dict):
        await asyncio.sleep(0.2)
        return ToolResult(ok=True, summary="late")

    router = ToolRouter([
        ToolSpec(
            name="slow",
            description="Slow tool",
            parameters_schema={"type": "object"},
            handler=handler,
            timeout_seconds=0.01,
        )
    ])

    result = await router.execute("slow", {})

    assert result.ok is False
    assert result.error == "timeout"


def test_tool_result_default_output_is_isolated():
    a = ToolResult(ok=True, summary="a")
    b = ToolResult(ok=True, summary="b")

    a.structured_output["x"] = 1

    assert b.structured_output == {}

