"""
文稿数据模型
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class Brief:
    """brief.md 的结构"""

    title: str
    kind: Literal["summary", "report", "paper"]
    audience: str = ""
    constraints: list[str] = None
    citation_style: str = "APA 7th"

    def __post_init__(self):
        if self.constraints is None:
            self.constraints = []


@dataclass
class Section:
    """一节的元数据"""

    id: str
    title: str
    status: Literal["pending", "draft", "accepted"]
    gist: str = ""  # 要旨，最多 20 字


@dataclass
class Literature:
    """一条文献记录"""

    id: str  # OpenAlex work ID
    title: str
    authors: list[str]
    year: int
    doi: str | None
    oa_url: str | None
    status: Literal["candidate", "accepted", "rejected"]
    content_source: Literal["oa_pdf", "abstract", "user_file", "unavailable"] | None
    evidence_type: Literal["core", "related", "contrast"] | None


@dataclass
class Decision:
    """一条反馈"""

    timestamp: str
    section_id: str | None
    feedback: str  # 用户的意见，最多 30 字进入提示


@dataclass
class Profile:
    """用户画像"""

    language: str = "中文"
    tone: str = ""
    structure: str = ""
    citation: str = ""
    rejects: list[str] = None

    def __post_init__(self):
        if self.rejects is None:
            self.rejects = []
