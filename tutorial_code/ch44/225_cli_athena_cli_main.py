"""Athena CLI 入口"""
from __future__ import annotations
import os
import sys
from pathlib import Path

import click

from athena_cli.app import AthenaApp
from athena_cli.api import AthenaClient


CONFIG_PATH = Path.home() / ".athena" / "config.json"


@click.group(invoke_without_command=True)
@click.option("--server", default=lambda: os.environ.get(
    "ATHENA_SERVER", "https://athena.local:8000"))
@click.option("--token", default=lambda: os.environ.get("ATHENA_TOKEN"))
@click.pass_context
def cli(ctx, server, token):
    """Athena · AI Research Workstation"""
    ctx.ensure_object(dict)
    ctx.obj["server"] = server
    ctx.obj["token"] = token
    
    if ctx.invoked_subcommand is None:
        # 没子命令 → 启动 TUI
        app = AthenaApp(server_url=server, token=token)
        app.run()


@cli.command()
@click.argument("question", nargs=-1, required=True)
@click.pass_context
def ask(ctx, question):
    """快速跑一个任务,不进入 TUI(适合 piping)
    
    例:athena ask "调研 2026 Q1 半导体行业"
    """
    import asyncio
    text = " ".join(question)
    
    async def run():
        async with AthenaClient(ctx.obj["server"], ctx.obj["token"]) as client:
            resp = await client.create_task(text)
            task_id = resp["task_id"]
            click.echo(f"任务已创建: {task_id}", err=True)
            
            async for event in client.stream_task(task_id):
                if event["type"] == "token":
                    click.echo(event["content"], nl=False)
                elif event["type"] == "done":
                    click.echo()
                    return
                elif event["type"] == "error":
                    click.echo(f"错误: {event['error']}", err=True)
                    sys.exit(1)
    
    asyncio.run(run())


@cli.command()
@click.argument("task_id")
@click.pass_context
def resume(ctx, task_id):
    """续接一个之前的任务(回放 + 接实时流)"""
    app = AthenaApp(server_url=ctx.obj["server"], token=ctx.obj["token"])
    app.initial_resume_task = task_id
    app.run()


@cli.command()
@click.option("--limit", default=20, help="最多显示几条")
@click.option("--status", default=None,
              type=click.Choice(["running", "done", "failed", "aborted"]))
@click.pass_context
def history(ctx, limit, status):
    """列出最近的任务"""
    import asyncio
    from rich.console import Console
    from rich.table import Table
    
    async def run():
        async with AthenaClient(ctx.obj["server"], ctx.obj["token"]) as client:
            tasks = await client.list_tasks(limit=limit, status=status)
            
            console = Console()
            table = Table(title="Athena · 任务历史", border_style="dim")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("状态")
            table.add_column("问题")
            table.add_column("成本", justify="right")
            table.add_column("创建时间", style="dim")
            
            for t in tasks:
                status_style = {
                    "done": "green",
                    "running": "yellow",
                    "failed": "red",
                    "aborted": "dim",
                }.get(t["status"], "white")
                
                table.add_row(
                    t["task_id"][:8],
                    f"[{status_style}]{t['status']}[/]",
                    t["question"][:60] + ("..." if len(t["question"]) > 60 else ""),
                    f"${t['cost_usd']:.3f}",
                    t["created_at"][:16],
                )
            
            console.print(table)
            console.print(f"\n[dim]共 {len(tasks)} 条 · "
                          f"使用 [bold]athena resume [/] 继续任务[/]")
    
    asyncio.run(run())


@cli.command()
@click.argument("task_id")
@click.option("--format", "fmt", default="markdown",
              type=click.Choice(["markdown", "pdf", "html", "json"]))
@click.option("--output", "-o", type=click.Path(), default=None,
              help="保存路径(默认输出到 stdout)")
@click.pass_context
def export(ctx, task_id, fmt, output):
    """导出任务报告"""
    import asyncio
    
    async def run():
        async with AthenaClient(ctx.obj["server"], ctx.obj["token"]) as client:
            data = await client.export_task(task_id, fmt=fmt)
            
            if output:
                Path(output).write_bytes(data if isinstance(data, bytes)
                                          else data.encode())
                click.echo(f"已导出到 {output}", err=True)
            else:
                if isinstance(data, bytes):
                    sys.stdout.buffer.write(data)
                else:
                    click.echo(data)
    
    asyncio.run(run())


@cli.command()
@click.pass_context
def cost(ctx):
    """查看本月累计成本"""
    import asyncio
    from rich.console import Console
    
    async def run():
        async with AthenaClient(ctx.obj["server"], ctx.obj["token"]) as client:
            info = await client.get_monthly_cost()
            
            console = Console()
            console.print(f"\n[bold]本月累计:[/] [orange1]${info['total']:.2f}[/]")
            console.print(f"[dim]预算:[/] ${info['budget']:.2f} "
                          f"([yellow]{info['percent_used']:.0f}%[/])")
            console.print(f"[dim]剩余:[/] [green]${info['remaining']:.2f}[/]")
            console.print(f"\n[bold]按模型分布:[/]")
            for m, c in info["by_model"].items():
                console.print(f"  {m:24s} ${c:.3f}")
    
    asyncio.run(run())


@cli.command()
@click.argument("subcommand", type=click.Choice(["list", "revoke", "clear"]))
@click.argument("decision_id", required=False)
@click.pass_context
def permissions(ctx, subcommand, decision_id):
    """管理权限授权"""
    import asyncio
    
    async def run():
        async with AthenaClient(ctx.obj["server"], ctx.obj["token"]) as client:
            if subcommand == "list":
                decisions = await client.list_permissions()
                for d in decisions:
                    click.echo(f"{d['id']:8s} {d['scope']:10s} "
                               f"{d['tool_name']:30s} {d['created_at']}")
            elif subcommand == "revoke" and decision_id:
                await client.revoke_permission(decision_id)
                click.echo(f"已撤回 {decision_id}")
            elif subcommand == "clear":
                if click.confirm("确认清空所有 session 级授权?"):
                    await client.clear_session_permissions()
                    click.echo("已清空")
    
    asyncio.run(run())


if __name__ == "__main__":
    cli()