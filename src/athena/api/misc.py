"""Lightweight ancillary endpoints (announcements, quick-start links).

These endpoints are intentionally open (no auth) since they only return public
product information used by the home page.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter


router = APIRouter(prefix="/v1", tags=["misc"])


_ANNOUNCEMENTS = [
    {
        "id": "2026-05-08",
        "date": "2026-05-08",
        "title": "Cost / Citation / Knowledge API 上线",
        "desc": "成本看板、引用验证、知识库 API 已实装,前端从硬编码切换到真实数据。",
    },
    {
        "id": "2026-05-07",
        "date": "2026-05-07",
        "title": "报告导出支持 PDF / DOCX",
        "desc": "已接入 WeasyPrint + Pandoc。在「报告与引用」一键导出。",
    },
    {
        "id": "2026-05-05",
        "date": "2026-05-05",
        "title": "Gemma / 自托管 vLLM 接入",
        "desc": "通过 ATHENA_LLM_PROVIDER=gemma + ATHENA_GEMMA_BASE_URL 即可接入。",
    },
]


_QUICK_START = [
    {"label": "如何创建高质量研究问题",     "url": "https://docs.athena.dev/research-question"},
    {"label": "了解研究流程与阶段",         "url": "https://docs.athena.dev/pipeline"},
    {"label": "如何解读研究报告",           "url": "https://docs.athena.dev/report"},
    {"label": "查看最佳实践案例",           "url": "https://docs.athena.dev/best-practices"},
]


@router.get("/announcements")
async def announcements(limit: int = 5):
    return {"items": _ANNOUNCEMENTS[:limit]}


@router.get("/quick-start")
async def quick_start():
    return {"items": _QUICK_START}


@router.get("/now")
async def server_now():
    return {"now": datetime.now(timezone.utc).isoformat()}
