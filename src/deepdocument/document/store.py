"""
文稿存储：读写项目目录下的文件
"""

import json
from pathlib import Path
from datetime import datetime

import yaml

from deepdocument.document.model import Brief, Section, Literature, Decision
from deepdocument.utils import parse_frontmatter, format_frontmatter, read_jsonl, append_jsonl


def load_brief(project_slug: str) -> Brief | None:
    """
    读取 brief.md

    Args:
        project_slug: 项目 slug

    Returns:
        Brief 对象；不存在返回 None
    """
    brief_path = Path("projects") / project_slug / "brief.md"
    if not brief_path.exists():
        return None

    content = brief_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(content)

    return Brief(
        title=meta.get("title", ""),
        kind=meta.get("kind", "report"),
        audience=meta.get("audience", ""),
        constraints=meta.get("constraints", []),
        citation_style=meta.get("citation_style", "APA 7th"),
    )


def save_brief(project_slug: str, brief: Brief):
    """
    写入 brief.md

    Args:
        project_slug: 项目 slug
        brief: Brief 对象
    """
    brief_path = Path("projects") / project_slug / "brief.md"
    brief_path.parent.mkdir(parents=True, exist_ok=True)

    meta = {
        "title": brief.title,
        "kind": brief.kind,
        "audience": brief.audience,
        "constraints": brief.constraints,
        "citation_style": brief.citation_style,
    }

    # body 留空或放项目描述
    content = format_frontmatter(meta, "")
    brief_path.write_text(content, encoding="utf-8")


def load_outline(project_slug: str) -> list[str]:
    """
    读取 outline.md

    Args:
        project_slug: 项目 slug

    Returns:
        标题列表
    """
    outline_path = Path("projects") / project_slug / "outline.md"
    if not outline_path.exists():
        return []

    content = outline_path.read_text(encoding="utf-8")
    titles = []
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("#"):
            # 去掉 # 标记
            title = line.lstrip("#").strip()
            titles.append(title)
    return titles


def save_outline(project_slug: str, titles: list[str]):
    """
    写入 outline.md

    Args:
        project_slug: 项目 slug
        titles: 标题列表
    """
    outline_path = Path("projects") / project_slug / "outline.md"
    outline_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [f"# {title}" for title in titles]
    outline_path.write_text("\n\n".join(lines) + "\n", encoding="utf-8")


def load_meta(project_slug: str) -> dict:
    """
    读取 meta.json（节状态、cursor）

    Args:
        project_slug: 项目 slug

    Returns:
        元数据字典
    """
    meta_path = Path("projects") / project_slug / "meta.json"
    if not meta_path.exists():
        return {"sections": [], "cursor": ""}
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_meta(project_slug: str, meta: dict):
    """
    写入 meta.json

    Args:
        project_slug: 项目 slug
        meta: 元数据字典
    """
    meta_path = Path("projects") / project_slug / "meta.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def load_section(project_slug: str, section_id: str) -> str:
    """
    读取节正文

    Args:
        project_slug: 项目 slug
        section_id: 节 id

    Returns:
        Markdown 正文
    """
    section_path = Path("projects") / project_slug / "sections" / f"{section_id}.md"
    if not section_path.exists():
        return ""
    return section_path.read_text(encoding="utf-8")


def save_section(project_slug: str, section_id: str, content: str):
    """
    写入节正文

    Args:
        project_slug: 项目 slug
        section_id: 节 id
        content: Markdown 正文
    """
    section_path = Path("projects") / project_slug / "sections" / f"{section_id}.md"
    section_path.parent.mkdir(parents=True, exist_ok=True)
    section_path.write_text(content, encoding="utf-8")


def load_literature(project_slug: str) -> list[Literature]:
    """
    读取 literature.jsonl

    Args:
        project_slug: 项目 slug

    Returns:
        文献列表
    """
    lit_path = Path("projects") / project_slug / "literature.jsonl"
    records = read_jsonl(str(lit_path))
    return [
        Literature(
            id=r["id"],
            title=r["title"],
            year=r["year"],
            authors=r.get("authors", []),
            kind=r["kind"],
            status=r["status"],
        )
        for r in records
    ]


def append_literature(project_slug: str, item: Literature):
    """
    追加文献记录

    Args:
        project_slug: 项目 slug
        item: 文献对象
    """
    lit_path = Path("projects") / project_slug / "literature.jsonl"
    record = {
        "id": item.id,
        "title": item.title,
        "year": item.year,
        "authors": item.authors,
        "kind": item.kind,
        "status": item.status,
    }
    append_jsonl(str(lit_path), record)


def load_decisions(project_slug: str, limit: int = 5) -> list[Decision]:
    """
    读取最近的反馈

    Args:
        project_slug: 项目 slug
        limit: 最多读取条数

    Returns:
        反馈列表
    """
    dec_path = Path("projects") / project_slug / "decisions.jsonl"
    records = read_jsonl(str(dec_path))

    # 取最后 N 条
    records = records[-limit:] if len(records) > limit else records

    return [
        Decision(
            timestamp=r["timestamp"],
            section_id=r.get("section_id"),
            feedback=r["feedback"],
        )
        for r in records
    ]


def append_decision(project_slug: str, decision: Decision):
    """
    追加反馈

    Args:
        project_slug: 项目 slug
        decision: 反馈对象
    """
    decision_path = Path("projects") / project_slug / "decisions.jsonl"
    decision_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {
            "timestamp": decision.timestamp,
            "section_id": decision.section_id,
            "feedback": decision.feedback,
        },
        ensure_ascii=False,
    )
    with open(decision_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
