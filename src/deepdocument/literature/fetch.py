"""
文献全文 / 摘要 → sources/<id>.md

优先开放获取 PDF 文本层；失败则用摘要；都没有则 content_source=unavailable。
写入走 document.store.save_source，并同步 literature.jsonl 中的 content_source。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import httpx
from pypdf import PdfReader

from deepdocument.document.model import Literature, Source
from deepdocument.document.store import (
    append_literature,
    load_literature,
    save_source,
    update_literature,
)
from deepdocument.memory.budget import EXCERPT_PER_SOURCE, estimate_tokens, truncate_to_budget


def fetch_source(
    literature_id: str,
    oa_url: str | None,
    abstract: str | None,
    project_slug: str,
    *,
    meta: dict | None = None,
) -> dict:
    """
    抓取并写入 sources/<literature_id>.md。

    Returns:
        {"content_source": fulltext|abstract|unavailable, "excerpt_length": int}
    """
    meta = meta or {}
    fulltext = _download_pdf_text(oa_url) if oa_url else None

    if fulltext and estimate_tokens(fulltext) >= 40:
        content_source = "fulltext"
        excerpt = truncate_to_budget(fulltext, EXCERPT_PER_SOURCE)
        archive = fulltext
        card = "依据开放获取全文抽取摘录。"
    elif abstract and abstract.strip():
        content_source = "abstract"
        excerpt = truncate_to_budget(abstract.strip(), EXCERPT_PER_SOURCE)
        archive = ""
        card = "无可用全文文本层，依据摘要。"
    else:
        content_source = "unavailable"
        excerpt = ""
        archive = ""
        card = "无可用文本（无开放获取全文且无摘要）。"

    save_source(
        project_slug,
        Source(
            id=literature_id,
            content_source=content_source,
            card=card,
            excerpt=excerpt,
            archive=archive,
        ),
    )
    _upsert_literature(
        project_slug,
        literature_id,
        content_source=content_source,
        abstract=abstract,
        meta=meta,
    )

    return {
        "content_source": content_source,
        "excerpt_length": estimate_tokens(excerpt),
    }


def extract_text_from_pdf(pdf_path: Path) -> str | None:
    """抽取 PDF 文本层；扫描件或失败返回 None。"""
    try:
        reader = PdfReader(str(pdf_path))
        chunks: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                chunks.append(text)
        joined = "\n".join(chunks).strip()
        return joined or None
    except Exception:
        return None


def _download_pdf_text(oa_url: str) -> str | None:
    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            resp = client.get(oa_url)
            resp.raise_for_status()
            content_type = (resp.headers.get("content-type") or "").lower()
            # 非 PDF Content-Type / 扩展名时，再用魔数确认是否真是 PDF
            if (
                "pdf" not in content_type
                and not oa_url.lower().endswith(".pdf")
                and not resp.content.startswith(b"%PDF")
            ):
                return None
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(resp.content)
                tmp_path = Path(tmp.name)
        try:
            return extract_text_from_pdf(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)
    except (httpx.HTTPError, OSError):
        return None


def _upsert_literature(
    project_slug: str,
    literature_id: str,
    *,
    content_source: str,
    abstract: str | None,
    meta: dict,
) -> None:
    existing = {item.id: item for item in load_literature(project_slug)}
    if literature_id in existing:
        update_literature(
            project_slug,
            literature_id,
            content_source=content_source,
            status="accepted",
            abstract=abstract if abstract is not None else existing[literature_id].abstract,
        )
        return

    append_literature(
        project_slug,
        Literature(
            id=literature_id,
            title=str(meta.get("title") or literature_id),
            authors=list(meta.get("authors") or []),
            year=meta.get("year"),
            status="accepted",
            openalex_id=meta.get("openalex_id"),
            doi=meta.get("doi"),
            venue=meta.get("venue"),
            url=meta.get("url"),
            abstract=abstract,
            content_source=content_source,  # type: ignore[arg-type]
        ),
    )
