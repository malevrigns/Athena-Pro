"""Cost dashboard aggregation endpoints.

Pulls usage events from the persisted SQLite event log so every row reflects
real Token consumption. Falls back to empty arrays when no data is recorded
yet — the front-end is expected to show its empty states in that case.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import aiosqlite
from fastapi import APIRouter, Query

from athena.persistence import get_store


router = APIRouter(prefix="/v1/cost", tags=["cost"])


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _range_window(value: str) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    if value == "all":
        return datetime(2020, 1, 1, tzinfo=timezone.utc), now
    if value == "7d":
        return now - timedelta(days=7), now
    if value == "30d":
        return now - timedelta(days=30), now
    if value == "last-month":
        last = (now.replace(day=1) - timedelta(days=1))
        return last.replace(day=1, hour=0, minute=0, second=0, microsecond=0), last.replace(hour=23, minute=59, second=59)
    # default: this month
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0), now


async def _all_usage_rows(start: datetime, end: datetime, task_id: str | None = None) -> list[dict[str, Any]]:
    store = get_store()
    await store.connect()
    assert store._conn is not None
    sql = "SELECT task_id, payload_json, ts FROM events WHERE type = 'usage' AND ts >= ? AND ts <= ?"
    args: list[Any] = [_iso(start), _iso(end)]
    if task_id:
        sql += " AND task_id = ?"
        args.append(task_id)
    sql += " ORDER BY ts ASC"
    async with store._lock:
        cursor = await store._conn.execute(sql, args)
        rows = await cursor.fetchall()
        await cursor.close()
    out: list[dict[str, Any]] = []
    for task_id, payload_json, ts in rows:
        try:
            payload = json.loads(payload_json)
            usage = payload.get("usage", {})
            out.append({
                "task_id": task_id,
                "node": usage.get("node", ""),
                "model": usage.get("model", ""),
                "input_tokens": int(usage.get("input_tokens", 0) or 0),
                "output_tokens": int(usage.get("output_tokens", 0) or 0),
                "cost_usd": float(usage.get("cost_usd", 0) or 0.0),
                "ts": ts,
            })
        except Exception:
            continue
    return out


@router.get("/summary")
async def cost_summary(range: str = Query("this-month"), task_id: str | None = Query(None)) -> dict[str, Any]:
    start, end = _range_window(range)
    rows = await _all_usage_rows(start, end, task_id)
    total_cost = sum(r["cost_usd"] for r in rows)
    input_tok = sum(r["input_tokens"] for r in rows)
    output_tok = sum(r["output_tokens"] for r in rows)
    tasks = {r["task_id"] for r in rows}
    return {
        "range": range,
        "start": _iso(start),
        "end": _iso(end),
        "total_cost_usd": round(total_cost, 6),
        "input_tokens": input_tok,
        "output_tokens": output_tok,
        "total_tokens": input_tok + output_tok,
        "task_count": len(tasks),
        "avg_cost_per_task": round(total_cost / len(tasks), 6) if tasks else 0.0,
    }


@router.get("/trend")
async def cost_trend(
    range: str = Query("this-month"),
    mode: Literal["day", "week"] = Query("day"),
    task_id: str | None = Query(None),
) -> dict[str, Any]:
    start, end = _range_window(range)
    rows = await _all_usage_rows(start, end, task_id)
    buckets: dict[str, float] = defaultdict(float)
    for r in rows:
        d = datetime.fromisoformat(r["ts"].replace("Z", "+00:00"))
        if mode == "week":
            iso = d.isocalendar()
            key = f"{iso[0]}-W{iso[1]:02d}"
        else:
            key = d.strftime("%Y-%m-%d")
        buckets[key] += r["cost_usd"]
    series = sorted(buckets.items())
    return {
        "mode": mode,
        "labels": [k for k, _ in series],
        "values": [round(v, 6) for _, v in series],
    }


@router.get("/by-model")
async def cost_by_model(range: str = Query("this-month"), task_id: str | None = Query(None)) -> dict[str, Any]:
    start, end = _range_window(range)
    rows = await _all_usage_rows(start, end, task_id)
    bucket: dict[str, float] = defaultdict(float)
    for r in rows:
        bucket[r["model"] or "unknown"] += r["cost_usd"]
    total = sum(bucket.values()) or 1.0
    items = [
        {"model": k, "cost_usd": round(v, 6), "pct": round(v / total * 100, 1)}
        for k, v in sorted(bucket.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return {"total_cost_usd": round(sum(bucket.values()), 6), "items": items}


@router.get("/by-node")
async def cost_by_node(range: str = Query("this-month"), top: int = Query(6, ge=1, le=50), task_id: str | None = Query(None)) -> dict[str, Any]:
    start, end = _range_window(range)
    rows = await _all_usage_rows(start, end, task_id)
    bucket: dict[str, dict[str, float]] = defaultdict(lambda: {"cost": 0.0, "in": 0.0, "out": 0.0, "calls": 0.0})
    for r in rows:
        node = r["node"] or "unknown"
        bucket[node]["cost"] += r["cost_usd"]
        bucket[node]["in"]   += r["input_tokens"]
        bucket[node]["out"]  += r["output_tokens"]
        bucket[node]["calls"] += 1
    sorted_items = sorted(bucket.items(), key=lambda kv: kv[1]["cost"], reverse=True)[:top]
    return {
        "items": [
            {
                "node": node, "cost_usd": round(v["cost"], 6),
                "input_tokens": int(v["in"]), "output_tokens": int(v["out"]),
                "calls": int(v["calls"]),
            }
            for node, v in sorted_items
        ]
    }


@router.get("/tasks")
async def cost_by_task(range: str = Query("this-month"), limit: int = Query(20, ge=1, le=200), task_id: str | None = Query(None)) -> dict[str, Any]:
    start, end = _range_window(range)
    rows = await _all_usage_rows(start, end, task_id)
    store = get_store()
    # Lookup task questions
    task_ids = list({r["task_id"] for r in rows})
    qmap: dict[str, str] = {}
    for tid in task_ids:
        row = await store.fetch_task_json(tid)
        if row: qmap[tid] = row["question"]
    # Aggregate by (task, node, model)
    bucket: dict[tuple[str, str, str], dict[str, float]] = defaultdict(
        lambda: {"cost": 0.0, "in": 0.0, "out": 0.0, "calls": 0.0, "last_ts": ""}
    )
    for r in rows:
        key = (r["task_id"], r["node"], r["model"])
        bucket[key]["cost"]  += r["cost_usd"]
        bucket[key]["in"]    += r["input_tokens"]
        bucket[key]["out"]   += r["output_tokens"]
        bucket[key]["calls"] += 1
        if r["ts"] > bucket[key]["last_ts"]:
            bucket[key]["last_ts"] = r["ts"]
    total_cost = sum(v["cost"] for v in bucket.values()) or 1.0
    items = []
    for (tid, node, model), v in sorted(bucket.items(), key=lambda kv: kv[1]["cost"], reverse=True)[:limit]:
        items.append({
            "task_id": tid,
            "task_name": qmap.get(tid, tid),
            "node": node, "model": model,
            "calls": int(v["calls"]),
            "input_tokens": int(v["in"]), "output_tokens": int(v["out"]),
            "cost_usd": round(v["cost"], 6),
            "pct": round(v["cost"] / total_cost * 100, 1),
            "updated_at": v["last_ts"],
        })
    return {"items": items}


@router.get("/tips")
async def cost_tips() -> dict[str, Any]:
    """Heuristic optimisation hints based on the live usage profile."""
    start, end = _range_window("this-month")
    rows = await _all_usage_rows(start, end)
    by_node = defaultdict(lambda: {"cost": 0.0, "calls": 0})
    for r in rows:
        by_node[r["node"]]["cost"] += r["cost_usd"]
        by_node[r["node"]]["calls"] += 1
    total = sum(v["cost"] for v in by_node.values()) or 1.0
    tips: list[dict[str, str]] = []
    for node, v in by_node.items():
        share = v["cost"] / total
        if share > 0.35:
            tips.append({
                "title": f"{node} 占比 {share*100:.1f}%",
                "desc": f"该节点累计 ${v['cost']:.4f},尝试将其切到更便宜的模型可节省成本",
                "ico": "✦", "color": "blue",
            })
    if not rows:
        tips.append({"title": "暂无数据", "desc": "完成一次研究任务后将出现优化建议", "ico": "·", "color": "gray"})
    tips.append({"title": "查看完整成本日志", "desc": "下载明细以做更深入的分析", "ico": "📋", "color": "gray"})
    return {"items": tips}
