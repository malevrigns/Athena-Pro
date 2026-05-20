"""Knowledge base CRUD.

A minimal CRUD on top of two SQLite tables: knowledge_collections and
knowledge_items. The first request to /overview also seeds a small set of
default collections so the UI is not empty on a fresh install.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import csv
import io

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from athena.config import get_settings
from athena.persistence import get_store


router = APIRouter(prefix="/v1/knowledge", tags=["knowledge"])


_DEFAULT_COLLECTIONS = [
    {"id": "industry",  "name": "行业报告库",   "icon": "📄", "color": "blue",   "description": "覆盖全球主要行业的研究报告与市场洞察"},
    {"id": "company",   "name": "公司与财报库", "icon": "🏢", "color": "green",  "description": "上市公司资料、财报、公告与分析"},
    {"id": "policy",    "name": "政策法规库",   "icon": "⚖", "color": "purple", "description": "国内外政策法规、标准与监管文件"},
    {"id": "paper",     "name": "技术论文库",   "icon": "📕", "color": "orange", "description": "学术论文、预印本与技术白皮书"},
    {"id": "template",  "name": "研究模板库",   "icon": "📋", "color": "pink",   "description": "研究方法、分析框架与报告模板"},
    {"id": "history",   "name": "历史项目沉淀", "icon": "📦", "color": "cyan",   "description": "历史项目中的结构化知识与结论沉淀"},
]


async def _seed_collections_if_empty() -> None:
    store = get_store()
    existing = await store.list_knowledge_collections()
    if existing:
        return
    for c in _DEFAULT_COLLECTIONS:
        await store.upsert_knowledge_collection(c)


class CollectionIn(BaseModel):
    id: str | None = None
    name: str
    icon: str | None = None
    color: str | None = None
    description: str | None = None


class ItemIn(BaseModel):
    id: str | None = None
    collection_id: str | None = None
    name: str = Field(min_length=1)
    summary: str | None = None
    type: str | None = None
    source: str | None = None
    tags: list[str] = []
    status: str = "pending"


@router.get("/collections")
async def list_collections():
    await _seed_collections_if_empty()
    return {"items": await get_store().list_knowledge_collections()}


@router.post("/collections")
async def create_collection(body: CollectionIn):
    payload = body.model_dump()
    payload["id"] = body.id or f"col_{uuid4().hex[:8]}"
    await get_store().upsert_knowledge_collection(payload)
    return {"id": payload["id"]}


@router.get("/items")
async def list_items(
    collection_id: str | None = Query(None),
    search: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    items, total = await get_store().list_knowledge_items(
        collection_id=collection_id, search=search, status=status,
        limit=limit, offset=offset,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("/items")
async def create_item(body: ItemIn):
    payload = body.model_dump()
    payload["id"] = body.id or f"kn_{uuid4().hex[:8]}"
    await get_store().upsert_knowledge_item(payload)
    return {"id": payload["id"]}


@router.post("/items/{item_id}/verify")
async def verify_item(item_id: str):
    store = get_store()
    items, _ = await store.list_knowledge_items()
    target = next((i for i in items if i["id"] == item_id), None)
    if not target:
        raise HTTPException(404, "item not found")
    target["status"] = "verified"
    await store.upsert_knowledge_item(target)
    return {"id": item_id, "status": "verified"}


@router.get("/overview")
async def overview():
    await _seed_collections_if_empty()
    return await get_store().knowledge_overview()


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), collection_id: str | None = None):
    """Persist an uploaded file under ATHENA_DATA_DIR/knowledge/ and register a
    knowledge_item entry referencing it. The first 1 KB of plain-text content is
    stored as the summary for searchability."""
    settings = get_settings()
    assert settings.data_dir is not None
    target_dir = Path(settings.data_dir) / "knowledge"
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = (file.filename or f"upload_{uuid4().hex[:6]}").replace("/", "_").replace("\\", "_")
    target = target_dir / f"{uuid4().hex[:8]}_{safe_name}"
    contents = await file.read()
    target.write_bytes(contents)
    # quick text peek
    summary = ""
    try:
        summary = contents[:1024].decode("utf-8", errors="ignore").strip()
    except Exception:
        pass
    payload = {
        "id": f"kn_{uuid4().hex[:8]}",
        "collection_id": collection_id,
        "name": safe_name,
        "summary": summary or f"上传文件 · {len(contents)} bytes",
        "type": (Path(safe_name).suffix.lstrip(".") or "file").upper(),
        "source": "上传",
        "tags": [],
        "status": "pending",
    }
    await get_store().upsert_knowledge_item(payload)
    return {"id": payload["id"], "filename": safe_name, "bytes": len(contents), "stored_at": str(target)}


@router.delete("/items/{item_id}")
async def delete_item(item_id: str):
    store = get_store()
    await store.connect()
    assert store._conn is not None
    async with store._lock:
        cursor = await store._conn.execute("DELETE FROM knowledge_items WHERE id = ?", (item_id,))
        await store._conn.commit()
        changes = cursor.rowcount
        await cursor.close()
    if not changes:
        raise HTTPException(404, "item not found")
    return {"deleted": item_id}


@router.get("/tags")
async def list_tags(limit: int = Query(20, ge=1, le=200)):
    """Return tags ranked by usage count."""
    overview = await get_store().knowledge_overview()
    return {"items": overview.get("hot_tags", [])[:limit]}


@router.get("/items.csv")
async def export_items_csv(
    collection_id: str | None = Query(None),
    search: str | None = Query(None),
    status: str | None = Query(None),
):
    """Stream all matching items as a UTF-8 CSV. The Excel BOM is prepended so
    Microsoft Excel renders Chinese characters correctly without manual decode."""
    items, _ = await get_store().list_knowledge_items(
        collection_id=collection_id, search=search, status=status,
        limit=10_000, offset=0,
    )
    buf = io.StringIO()
    buf.write("﻿")
    writer = csv.writer(buf)
    writer.writerow(["id", "collection_id", "name", "type", "source", "tags", "usage_count", "status", "summary", "updated_at"])
    for it in items:
        writer.writerow([
            it["id"], it.get("collection_id") or "", it["name"], it.get("type") or "",
            it.get("source") or "", ";".join(it.get("tags", [])),
            it.get("usage_count", 0), it.get("status", ""),
            (it.get("summary") or "").replace("\n", " ")[:500],
            it.get("updated_at") or "",
        ])
    buf.seek(0)
    filename = f"knowledge-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    return StreamingResponse(
        iter([buf.getvalue().encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
