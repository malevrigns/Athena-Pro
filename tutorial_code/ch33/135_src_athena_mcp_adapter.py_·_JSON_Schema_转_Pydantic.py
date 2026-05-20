"""
把 MCPTool 包装成 LangChain BaseTool,无缝塞进 ToolNode。
"""
from __future__ import annotations
from typing import Any, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, create_model

from athena.mcp.client import MCPStdioClient, MCPTool


def _schema_to_pydantic_model(name: str, schema: dict) -> Type[BaseModel]:
    """
    把 MCP 工具的 JSON Schema 转成 Pydantic 模型,
    LangChain 用这个做参数验证 + 给 LLM 看的 schema。
    """
    fields: dict[str, tuple] = {}
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    
    for prop_name, prop_schema in properties.items():
        # 简化的类型映射(生产应支持更多类型)
        json_type = prop_schema.get("type", "string")
        py_type = {
            "string": str, "number": float, "integer": int,
            "boolean": bool, "array": list, "object": dict,
        }.get(json_type, str)
        
        description = prop_schema.get("description", "")
        default = ... if prop_name in required else None
        fields[prop_name] = (py_type, Field(default=default, description=description))
    
    return create_model(name + "Input", **fields)