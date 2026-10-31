"""
文稿存储：读写 projects/<slug>/ 下的文件

聊天和检查点不是正文真相。上层只通过本模块碰项目目录。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from deepdocument.document.model import (
    Brief,
    Decision,
    Literature,
    Section,
    Source,
)
from deepdocument.utils import (
    append_jsonl,
    format_frontmatter,
    parse_frontmatter,
    read_jsonl,
)

PROJECTS_ROOT = Path("projects")


def project_dir(project_slug: str) -> Path:
    """项目根目录"""
    return PROJECTS_ROOT / project_slug


def create_project(project_slug: str, brief: Brief) -> Path:
    """
    新建项目目录与空文件

    写入 brief.md、空 outline、空 meta、sections/、sources/。
    """
    root = project_dir(project_slug)
    (root / "sections").mkdir(parents=True, exist_ok=True)
    (root / "sources").mkdir(parents=True, exist_ok=True)
    save_brief(project_slug, brief)
    if not (root / "outline.md").exists():
        save_outline(project_slug, [])
    if not (root / "meta.json").exists():
        save_meta(project_slug, {"cursor": "", "sections": []})
    (root / "literature.jsonl").touch(exist_ok=True)
    (root / "decisions.jsonl").touch(exist_ok=True)
    return root


# ---------- brief ----------


def load_brief(project_slug: str) -> Brief | None:
    path = project_dir(project_slug) / "brief.md"
    if not path.exists():
        return None

    meta, _body = parse_frontmatter(path.read_text(encoding="utf-8"))
    kind = meta.get("kind", "report")
    if kind not in ("summary", "report", "paper"):
        kind = "report"

    return Brief(
        title=str(meta.get("title", "")),
        kind=kind,
        audience=str(meta.get("audience", "")),
        constraints=list(meta.get("constraints") or []),
        citation_style=str(meta.get("citation_style") or "APA"),
    )


def save_brief(project_slug: str, brief: Brief) -> None:
    path = project_dir(project_slug) / "brief.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "title": brief.title,
        "kind": brief.kind,
        "audience": brief.audience,
        "citation_style": brief.citation_style,
        "constraints": brief.constraints,
    }
    path.write_text(format_frontmatter(meta, ""), encoding="utf-8")


# ---------- outline / meta / sections ----------


def load_outline(project_slug: str) -> list[str]:
    path = project_dir(project_slug) / "outline.md"
    if not path.exists():
        return []

    titles: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            titles.append(stripped.lstrip("#").strip())
    return titles


def save_outline(project_slug: str, titles: list[str], *, sync_meta: bool = True) -> None:
    """
    写入大纲。默认同步 meta.json 的节列表（保留已有 status/gist）。
    """
    path = project_dir(project_slug) / "outline.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if titles:
        path.write_text("\n\n".join(f"# {t}" for t in titles) + "\n", encoding="utf-8")
    else:
        path.write_text("", encoding="utf-8")

    if sync_meta:
        sync_meta_from_outline(project_slug, titles)


def sync_meta_from_outline(project_slug: str, titles: list[str] | None = None) -> dict:
    """
    按大纲重建 meta.sections，已有 id 的 status/gist 尽量保留。
    """
    if titles is None:
        titles = load_outline(project_slug)

    meta = load_meta(project_slug)
    old_by_title = {s.get("title"): s for s in meta.get("sections", [])}
    old_by_id = {s.get("id"): s for s in meta.get("sections", [])}

    sections: list[dict] = []
    for index, title in enumerate(titles):
        section_id = _slug_id(title, index)
        previous = old_by_title.get(title) or old_by_id.get(section_id) or {}
        status = previous.get("status", "outlined" if title else "empty")
        if status not in ("empty", "outlined", "draft", "accepted"):
            status = "outlined"
        sections.append(
            {
                "id": previous.get("id") or section_id,
                "title": title,
                "status": status if previous else "outlined",
                "gist": previous.get("gist", ""),
            }
        )

    meta["sections"] = sections
    if not meta.get("cursor") and sections:
        meta["cursor"] = sections[0]["id"]
    save_meta(project_slug, meta)
    return meta


def load_meta(project_slug: str) -> dict:
    path = project_dir(project_slug) / "meta.json"
    if not path.exists():
        return {"cursor": "", "sections": []}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("cursor", "")
    data.setdefault("sections", [])
    return data


def save_meta(project_slug: str, meta: dict) -> None:
    path = project_dir(project_slug) / "meta.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")


def get_sections(project_slug: str) -> list[Section]:
    meta = load_meta(project_slug)
    result: list[Section] = []
    for item in meta.get("sections", []):
        status = item.get("status", "empty")
        if status not in ("empty", "outlined", "draft", "accepted"):
            status = "empty"
        result.append(
            Section(
                id=item["id"],
                title=item.get("title", ""),
                status=status,
                gist=item.get("gist", ""),
            )
        )
    return result


def update_section_meta(
    project_slug: str,
    section_id: str,
    *,
    status: str | None = None,
    gist: str | None = None,
    title: str | None = None,
    make_cursor: bool = False,
) -> None:
    meta = load_meta(project_slug)
    found = False
    for item in meta.get("sections", []):
        if item.get("id") != section_id:
            continue
        found = True
        if status is not None:
            item["status"] = status
        if gist is not None:
            item["gist"] = gist[:20]
        if title is not None:
            item["title"] = title
        break
    if not found:
        raise KeyError(f"未知节 id: {section_id}")
    if make_cursor:
        meta["cursor"] = section_id
    save_meta(project_slug, meta)


def load_section(project_slug: str, section_id: str) -> str:
    path = project_dir(project_slug) / "sections" / f"{section_id}.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def save_section(
    project_slug: str,
    section_id: str,
    content: str,
    *,
    status: str = "draft",
    gist: str | None = None,
) -> None:
    """写正文，并把该节 meta 标成 draft（或传入的 status）"""
    path = project_dir(project_slug) / "sections" / f"{section_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    meta = load_meta(project_slug)
    for item in meta.get("sections", []):
        if item.get("id") == section_id:
            item["status"] = status
            if gist is not None:
                item["gist"] = gist[:20]
            break
    save_meta(project_slug, meta)


# ---------- literature ----------


def load_literature(
    project_slug: str,
    *,
    status: str | None = None,
) -> list[Literature]:
    path = project_dir(project_slug) / "literature.jsonl"
    records = read_jsonl(str(path))
    items = [_literature_from_record(r) for r in records]
    if status is None:
        return items
    return [item for item in items if item.status == status]


def append_literature(project_slug: str, item: Literature) -> None:
    path = project_dir(project_slug) / "literature.jsonl"
    append_jsonl(str(path), _literature_to_record(item))


def save_literature(project_slug: str, items: list[Literature]) -> None:
    """整表覆盖写入（用于勾选后批量写入 accepted/rejected）"""
    path = project_dir(project_slug) / "literature.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(_literature_to_record(item), ensure_ascii=False) for item in items]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def update_literature(project_slug: str, literature_id: str, **fields) -> Literature:
    """按 id 更新字段后整表写回"""
    items = load_literature(project_slug)
    updated: Literature | None = None
    new_items: list[Literature] = []
    for item in items:
        if item.id != literature_id:
            new_items.append(item)
            continue
        data = _literature_to_record(item)
        data.update(fields)
        updated = _literature_from_record(data)
        new_items.append(updated)
    if updated is None:
        raise KeyError(f"未知文献 id: {literature_id}")
    save_literature(project_slug, new_items)
    return updated


def _literature_to_record(item: Literature) -> dict:
    return {
        "id": item.id,
        "openalex_id": item.openalex_id,
        "doi": item.doi,
        "title": item.title,
        "authors": item.authors,
        "year": item.year,
        "venue": item.venue,
        "url": item.url,
        "abstract": item.abstract,
        "status": item.status,
        "content_source": item.content_source,
        "local_path": item.local_path,
        "evidence_type": item.evidence_type,
    }


def _literature_from_record(record: dict) -> Literature:
    status = record.get("status", "accepted")
    if status not in ("accepted", "rejected"):
        status = "accepted"

    content_source = record.get("content_source")
    # 兼容旧骨架里的 oa_pdf
    if content_source == "oa_pdf":
        content_source = "fulltext"
    if content_source not in ("fulltext", "abstract", "user_file", "unavailable", None):
        content_source = None

    evidence = record.get("evidence_type")
    if evidence not in ("core", "related", "contrast", None):
        evidence = None

    return Literature(
        id=str(record.get("id", "")),
        title=str(record.get("title", "")),
        authors=list(record.get("authors") or []),
        year=record.get("year"),
        status=status,
        openalex_id=record.get("openalex_id"),
        doi=record.get("doi"),
        venue=record.get("venue"),
        url=record.get("url"),
        abstract=record.get("abstract"),
        content_source=content_source,
        local_path=record.get("local_path"),
        evidence_type=evidence,
    )


# ---------- sources ----------


def load_source(project_slug: str, source_id: str) -> Source | None:
    path = project_dir(project_slug) / "sources" / f"{source_id}.md"
    if not path.exists():
        return None

    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    content_source = meta.get("content_source", "abstract")
    if content_source == "oa_pdf":
        content_source = "fulltext"
    if content_source not in ("fulltext", "abstract", "user_file", "unavailable"):
        content_source = "unavailable"

    return Source(
        id=str(meta.get("id") or source_id),
        content_source=content_source,
        card=_section_body(body, "card"),
        excerpt=_section_body(body, "excerpt"),
        archive=_section_body(body, "archive"),
    )


def save_source(project_slug: str, source: Source) -> None:
    path = project_dir(project_slug) / "sources" / f"{source.id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    parts = [
        f"## card\n\n{source.card.strip()}\n",
        f"## excerpt\n\n{source.excerpt.strip()}\n",
    ]
    if source.archive.strip():
        parts.append(f"## archive\n\n{source.archive.strip()}\n")

    meta = {"id": source.id, "content_source": source.content_source}
    path.write_text(format_frontmatter(meta, "\n".join(parts)), encoding="utf-8")


def list_source_ids(project_slug: str) -> list[str]:
    root = project_dir(project_slug) / "sources"
    if not root.exists():
        return []
    return sorted(p.stem for p in root.glob("*.md"))


def _section_body(markdown: str, name: str) -> str:
    """取出 ## name 到下一个 ## 之间的正文"""
    pattern = rf"^##\s+{re.escape(name)}\s*$"
    lines = markdown.splitlines()
    start = None
    for index, line in enumerate(lines):
        if re.match(pattern, line.strip()):
            start = index + 1
            break
    if start is None:
        return ""

    end = len(lines)
    for index in range(start, len(lines)):
        if re.match(r"^##\s+\S", lines[index].strip()):
            end = index
            break
    return "\n".join(lines[start:end]).strip()


# ---------- decisions ----------


def load_decisions(project_slug: str, limit: int | None = 5) -> list[Decision]:
    path = project_dir(project_slug) / "decisions.jsonl"
    records = read_jsonl(str(path))
    if limit is not None:
        records = records[-limit:]

    decisions: list[Decision] = []
    for record in records:
        # 兼容旧字段名 timestamp/section_id/feedback
        timestamp = record.get("at") or record.get("timestamp") or ""
        section_id = record.get("section")
        if section_id is None:
            section_id = record.get("section_id")
        feedback = record.get("text") or record.get("feedback") or ""
        decisions.append(
            Decision(timestamp=timestamp, section_id=section_id, feedback=feedback)
        )
    return decisions


def append_decision(project_slug: str, decision: Decision) -> None:
    path = project_dir(project_slug) / "decisions.jsonl"
    append_jsonl(
        str(path),
        {
            "at": decision.timestamp,
            "section": decision.section_id,
            "text": decision.feedback,
        },
    )


# ---------- helpers ----------


def _slug_id(title: str, index: int) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", title).strip("-").lower()
    if not slug:
        slug = f"s{index + 1:02d}"
    # 纯中文标题用 s01 形式，避免路径怪异
    if re.fullmatch(r"[\u4e00-\u9fff\-]+", slug):
        return f"s{index + 1:02d}"
    return slug[:40]
