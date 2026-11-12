"""
文稿文件快照：检测确认恢复前是否被外部修改。

快照存内容 sha256（相对项目根路径 → 哈希）。
中断时记下快照；用户确认前与磁盘比对，若有变更则给出冲突报告，
由窗口决定 keep_disk（以当前磁盘为准继续）或 abort（取消本次确认）。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from deepdocument.document.store import project_dir

ChangeKind = Literal["modified", "added", "deleted"]

# 参与快照的相对路径模式（正文真相；不含 checkpoints / export / template）
TRACKED_GLOBS = (
    "brief.md",
    "outline.md",
    "meta.json",
    "sections/*.md",
    "literature.jsonl",
    "sources/*.md",
    "decisions.jsonl",
)


@dataclass(frozen=True)
class FileChange:
    """单个文件相对上一份快照的变更。"""

    path: str
    kind: ChangeKind


@dataclass
class SnapshotDiff:
    """快照与当前磁盘的差异。"""

    changes: list[FileChange] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.changes)

    @property
    def paths(self) -> list[str]:
        return [c.path for c in self.changes]

    @property
    def modified(self) -> list[str]:
        return [c.path for c in self.changes if c.kind == "modified"]

    @property
    def added(self) -> list[str]:
        return [c.path for c in self.changes if c.kind == "added"]

    @property
    def deleted(self) -> list[str]:
        return [c.path for c in self.changes if c.kind == "deleted"]

    def to_dict(self) -> dict:
        return {
            "changed": bool(self.changes),
            "paths": self.paths,
            "modified": self.modified,
            "added": self.added,
            "deleted": self.deleted,
            "summary": summarize_diff(self),
            "changes": [{"path": c.path, "kind": c.kind} for c in self.changes],
        }


def capture_file_snapshots(project_slug: str) -> dict[str, str]:
    """
    记录项目关键文件的内容哈希。

    Returns:
        {相对路径: sha256 hex}；目录不存在或无可读文件时为空 dict
    """
    root = project_dir(project_slug)
    if not root.is_dir():
        return {}

    snapshots: dict[str, str] = {}
    for pattern in TRACKED_GLOBS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            rel = _relpath(root, path)
            digest = _hash_file(path)
            if digest is not None:
                snapshots[rel] = digest
    return snapshots


def diff_snapshots(
    previous: dict[str, str] | None,
    current: dict[str, str] | None,
) -> SnapshotDiff:
    """纯比对两份快照，不读盘。"""
    prev = previous or {}
    curr = current or {}
    changes: list[FileChange] = []

    for rel, digest in prev.items():
        if rel not in curr:
            changes.append(FileChange(path=rel, kind="deleted"))
        elif curr[rel] != digest:
            changes.append(FileChange(path=rel, kind="modified"))

    for rel in curr:
        if rel not in prev:
            changes.append(FileChange(path=rel, kind="added"))

    changes.sort(key=lambda c: (c.kind, c.path))
    return SnapshotDiff(changes=changes)


def detect_external_changes(
    project_slug: str,
    previous: dict[str, str] | None,
) -> SnapshotDiff:
    """
    对比当前磁盘与 previous 快照。

    previous 为空时视为无冲突（尚未建快照）。
    """
    if not previous:
        return SnapshotDiff()
    current = capture_file_snapshots(project_slug)
    return diff_snapshots(previous, current)


def summarize_diff(diff: SnapshotDiff) -> str:
    """给人看的冲突摘要。"""
    if not diff:
        return "文件未发生外部修改"
    parts: list[str] = []
    if diff.modified:
        parts.append(f"已修改: {', '.join(diff.modified)}")
    if diff.added:
        parts.append(f"新增: {', '.join(diff.added)}")
    if diff.deleted:
        parts.append(f"删除: {', '.join(diff.deleted)}")
    return "；".join(parts)


def build_conflict_report(
    project_slug: str,
    previous: dict[str, str] | None,
    *,
    pending_confirmation: dict | None = None,
) -> dict | None:
    """
    若有外部修改，返回给窗口的冲突 payload；否则 None。

    窗口可展示后让用户选择：
      - keep_disk：以当前磁盘为准，刷新快照后继续 confirm
      - abort：取消本次确认，保留确认卡
    """
    diff = detect_external_changes(project_slug, previous)
    if not diff:
        return None
    return {
        "card_type": "conflict",
        "project_slug": project_slug,
        "diff": diff.to_dict(),
        "pending_confirmation": pending_confirmation,
        "choices": ["keep_disk", "abort"],
        "message": (
            "确认恢复前检测到文稿文件被外部修改。"
            "选择「保留磁盘」以当前文件继续，或「取消」回到确认卡。"
        ),
    }


def _relpath(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _hash_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None
