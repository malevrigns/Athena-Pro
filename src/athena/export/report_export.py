from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from athena.config import get_settings
from athena.observability import logger
from athena.schemas import FinalReport


ExportFormat = Literal["md", "html", "pdf", "docx"]


class ExportError(RuntimeError):
    pass


def available_formats() -> dict[str, bool]:
    """Report which export formats can actually be produced in this process."""
    info = {"md": True, "html": True, "pdf": False, "docx": False}
    try:
        import weasyprint  # type: ignore  # noqa: F401
        info["pdf"] = True
    except Exception:
        pass
    try:
        import pypandoc  # type: ignore
        try:
            pypandoc.get_pandoc_version()
            info["docx"] = True
        except OSError:
            info["docx"] = False
    except Exception:
        pass
    return info


_HTML_TEMPLATE = """<!doctype html>
<html lang=\"zh\">
<head>
  <meta charset=\"utf-8\" />
  <title>{title}</title>
  <style>
    @page {{ size: A4; margin: 28mm 22mm; }}
    body {{ font-family: -apple-system, 'Segoe UI', 'Source Han Sans SC', 'Noto Sans CJK SC', sans-serif; color:#1a1a1a; line-height:1.65; }}
    h1 {{ font-size: 26px; margin:0 0 8px; border-bottom:2px solid #1f6feb; padding-bottom:6px; }}
    h2 {{ font-size: 18px; margin:20px 0 8px; color:#1f6feb; }}
    h3 {{ font-size: 15px; margin:14px 0 4px; }}
    p, li {{ font-size: 12.5px; }}
    code, pre {{ font-family: 'Menlo','Consolas',monospace; background:#f6f8fa; padding:2px 4px; border-radius:4px; }}
    pre {{ padding:10px; overflow:auto; }}
    blockquote {{ border-left:3px solid #d0d7de; padding:4px 12px; color:#57606a; margin:8px 0; }}
    a {{ color:#1f6feb; text-decoration:none; }}
    .meta {{ color:#57606a; font-size:11px; margin:0 0 18px; }}
    .footer {{ margin-top:22px; padding-top:8px; border-top:1px solid #d0d7de; font-size:10.5px; color:#57606a; }}
    table {{ border-collapse:collapse; width:100%; margin:8px 0; }}
    th, td {{ border:1px solid #d0d7de; padding:6px 8px; font-size:12px; }}
    th {{ background:#f6f8fa; }}
  </style>
</head>
<body>
  <p class=\"meta\">生成时间: {generated_at} · 任务 ID: {task_id}</p>
  {body_html}
  <p class=\"footer\">由 Athena Pro 自动生成 · 仅供内部研究参考</p>
</body>
</html>
"""


def _markdown_to_html(md: str) -> str:
    try:
        from markdown_it import MarkdownIt  # type: ignore
        return MarkdownIt("commonmark", {"linkify": True, "html": False}).enable("table").render(md)
    except Exception as exc:
        logger.warning("export.markdown_render_failed err=%s", exc)
        escaped = (md or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"<pre>{escaped}</pre>"


def _slug(text: str, fallback: str) -> str:
    text = (text or fallback).strip()
    text = re.sub(r"[\s/\\:*?\"<>|]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return (text[:80] or fallback)


@dataclass
class ReportExporter:
    export_dir: Path

    def __post_init__(self) -> None:
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export(self, report: FinalReport, fmt: ExportFormat) -> Path:
        if not report:
            raise ExportError("no report to export")
        fmt_lower = fmt.lower()
        if fmt_lower not in {"md", "html", "pdf", "docx"}:
            raise ExportError(f"unsupported format: {fmt}")
        base = _slug(report.title, report.task_id)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        filename = f"{base}-{report.task_id}-{ts}.{fmt_lower}"
        out_path = self.export_dir / filename
        if fmt_lower == "md":
            out_path.write_text(report.markdown, encoding="utf-8")
            return out_path
        if fmt_lower == "html":
            out_path.write_text(self._render_html(report), encoding="utf-8")
            return out_path
        if fmt_lower == "pdf":
            self._render_pdf(report, out_path)
            return out_path
        if fmt_lower == "docx":
            self._render_docx(report, out_path)
            return out_path
        raise ExportError(f"unhandled format: {fmt}")

    def _render_html(self, report: FinalReport) -> str:
        body = _markdown_to_html(report.markdown)
        return _HTML_TEMPLATE.format(
            title=report.title or report.task_id,
            generated_at=report.generated_at.isoformat() if report.generated_at else "",
            task_id=report.task_id,
            body_html=body,
        )

    def _render_pdf(self, report: FinalReport, out_path: Path) -> None:
        try:
            from weasyprint import HTML  # type: ignore
        except Exception as exc:
            raise ExportError("weasyprint 未安装, 无法生成 PDF (请 pip install weasyprint 或使用 markdown 导出)") from exc
        html_str = self._render_html(report)
        HTML(string=html_str).write_pdf(str(out_path))

    def _render_docx(self, report: FinalReport, out_path: Path) -> None:
        try:
            import pypandoc  # type: ignore
        except Exception as exc:
            raise ExportError("pypandoc 未安装, 无法生成 DOCX") from exc
        try:
            pypandoc.convert_text(
                report.markdown,
                "docx",
                format="markdown",
                outputfile=str(out_path),
                extra_args=["--standalone"],
            )
        except OSError as exc:
            raise ExportError(f"未检测到 pandoc 可执行文件: {exc}") from exc


_exporter: ReportExporter | None = None


def get_exporter() -> ReportExporter:
    global _exporter
    if _exporter is None:
        settings = get_settings()
        assert settings.export_dir is not None
        _exporter = ReportExporter(settings.export_dir)
    return _exporter
