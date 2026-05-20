from athena.security.permissions import PermissionEngine
from athena.security.guarded_tool_node import GuardedToolNode

# 全局单例
permission_engine = PermissionEngine(rules_path=Path("config/permissions.yaml"))

# 在图里替换原来的 ToolNode(tools, handle_tool_errors=True)
g.add_node(
    "tools",
    GuardedToolNode(tools=[bash_tool, file_write, ...], engine=permission_engine),
)