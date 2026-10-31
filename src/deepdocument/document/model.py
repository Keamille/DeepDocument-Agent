"""
文稿数据模型

字段与 docs/document-model.md 对齐。磁盘序列化由 store 负责。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SectionStatus = Literal["empty", "outlined", "draft", "accepted"]
DocKind = Literal["summary", "report", "paper"]
LiteratureStatus = Literal["accepted", "rejected"]
ContentSource = Literal["fulltext", "abstract", "user_file", "unavailable"]
EvidenceType = Literal["core", "related", "contrast"]


@dataclass
class Brief:
    """brief.md"""

    title: str
    kind: DocKind = "report"
    audience: str = ""
    constraints: list[str] = field(default_factory=list)
    citation_style: str = "APA"


@dataclass
class Section:
    """meta.json 里一节的元数据；正文在 sections/<id>.md"""

    id: str
    title: str
    status: SectionStatus = "empty"
    gist: str = ""  # 要旨，提示里最多约 20 字


@dataclass
class Literature:
    """literature.jsonl 一行"""

    id: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    status: LiteratureStatus = "accepted"
    openalex_id: str | None = None
    doi: str | None = None
    venue: str | None = None
    url: str | None = None
    abstract: str | None = None
    content_source: ContentSource | None = None
    local_path: str | None = None
    evidence_type: EvidenceType | None = None


@dataclass
class Source:
    """sources/<id>.md 三截"""

    id: str
    content_source: ContentSource
    card: str = ""
    excerpt: str = ""
    archive: str = ""


@dataclass
class Decision:
    """decisions.jsonl 一条；磁盘字段为 at / section / text"""

    timestamp: str
    feedback: str
    section_id: str | None = None


@dataclass
class Profile:
    """全局 user_profile.md 的内存形状（读写在 memory/profile）"""

    language: str = "中文"
    tone: str = ""
    structure: str = ""
    citation: str = ""
    rejects: list[str] = field(default_factory=list)
