"""
从 template.docx 标题样式提出大纲候选。

骨架：接口先定；完整样式遍历与中英文标题样式匹配后续补。
"""

from __future__ import annotations

from pathlib import Path

from deepdocument.document.store import project_dir


def extract_outline_from_template(project_slug: str) -> list[str]:
    """
    读取 projects/<slug>/template.docx 中的标题，返回候选节标题列表。

    无模板或解析失败时返回空列表（不抛错）。
    """
    path = project_dir(project_slug) / "template.docx"
    if not path.is_file():
        return []

    try:
        from docx import Document
    except ImportError:
        return []

    # TODO: 识别 Heading 1/标题 1 等；过滤正文与目录域
    try:
        doc = Document(str(path))
    except Exception:
        return []

    titles: list[str] = []
    for para in doc.paragraphs:
        style_name = (para.style.name if para.style is not None else "") or ""
        text = (para.text or "").strip()
        if not text:
            continue
        lowered = style_name.lower()
        if "heading 1" in lowered or style_name in ("标题 1", "Heading 1"):
            titles.append(text)
    return titles


def suggest_outline(project_slug: str, fallback: list[str] | None = None) -> list[str]:
    """优先模板标题；否则用 fallback（例如 kind=summary → ['总结']）。"""
    from_template = extract_outline_from_template(project_slug)
    if from_template:
        return from_template
    return list(fallback or [])
