"""
从 template.docx 标题样式提出大纲候选。
"""

from __future__ import annotations

import re

from deepdocument.document.store import project_dir

# 一级标题样式名（中英文、有无空格）
_HEADING1_NAMES = frozenset(
    {
        "heading 1",
        "heading1",
        "标题 1",
        "标题1",
        "title",  # 少数模板把文章题名外的章题也叫 Title；仅作弱匹配见下方
    }
)

_TOC_TITLES = frozenset({"目录", "目 录", "contents", "table of contents", "toc"})


def extract_outline_from_template(project_slug: str) -> list[str]:
    """
    读取 projects/<slug>/template.docx 中的一级标题，返回候选节标题列表。

    无模板或解析失败时返回空列表（不抛错）。
    """
    path = project_dir(project_slug) / "template.docx"
    if not path.is_file():
        return []

    try:
        from docx import Document
    except ImportError:
        return []

    try:
        doc = Document(str(path))
    except Exception:
        return []

    titles: list[str] = []
    for para in doc.paragraphs:
        text = _clean_heading_text(para.text or "")
        if not text or _is_toc_heading(text):
            continue
        if _looks_like_toc_entry(text):
            continue
        if not _is_heading1(para):
            continue
        titles.append(text)

    return _dedupe_preserve_order(titles)


def suggest_outline(project_slug: str, fallback: list[str] | None = None) -> list[str]:
    """优先模板标题；否则用 fallback（例如 kind=summary → ['总结']）。"""
    from_template = extract_outline_from_template(project_slug)
    if from_template:
        return from_template
    return list(fallback or [])


def _is_heading1(para) -> bool:
    """判断段落是否为一级标题（样式名或 outline level 0）。"""
    style = getattr(para, "style", None)
    style_name = (style.name if style is not None else "") or ""
    normalized = _normalize_style_name(style_name)

    if normalized in {"heading 1", "heading1", "标题 1", "标题1"}:
        return True
    # 「标题」且带 1
    if normalized.startswith("标题") and "1" in normalized:
        return True
    if normalized.startswith("heading") and normalized.endswith("1"):
        return True

    # outlineLvl = 0 → 一级大纲
    try:
        ppr = para._element.pPr  # noqa: SLF001 — python-docx 惯例
        if ppr is not None and ppr.outlineLvl is not None:
            return int(ppr.outlineLvl.val) == 0
    except Exception:
        pass

    return False


def _normalize_style_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def _clean_heading_text(text: str) -> str:
    text = text.replace("\t", " ").strip()
    text = re.sub(r"\s+", " ", text)
    # 去掉末尾页码残留
    text = re.sub(r"\s+\d+\s*$", "", text).strip()
    return text


def _is_toc_heading(text: str) -> bool:
    return text.strip().lower() in _TOC_TITLES


def _looks_like_toc_entry(text: str) -> bool:
    """目录项常见形态：标题……12 或 标题\\t12。"""
    if "\t" in text and re.search(r"\d+\s*$", text):
        return True
    if re.search(r".+\.{2,}\s*\d+\s*$", text):
        return True
    return False


def _dedupe_preserve_order(titles: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for title in titles:
        key = title.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(title)
    return out
