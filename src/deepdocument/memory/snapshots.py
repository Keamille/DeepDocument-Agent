"""
文稿文件快照：检测确认恢复前是否被外部修改。

骨架：接口与约定先就位；完整哈希比对与冲突 UI 后续补。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from deepdocument.document.store import project_dir

# 参与快照的相对路径模式
TRACKED_GLOBS = (
    "brief.md",
    "outline.md",
    "meta.json",
    "sections/*.md",
    "literature.jsonl",
    "sources/*.md",
    "decisions.jsonl",
)


def capture_file_snapshots(project_slug: str) -> dict[str, str]:
    """
    记录项目关键文件的内容哈希。

    Returns:
        {相对路径: sha256 hex}
    """
    root = project_dir(project_slug)
    if not root.is_dir():
        return {}

    snapshots: dict[str, str] = {}
    for pattern in TRACKED_GLOBS:
        for path in root.glob(pattern):
            if not path.is_file():
                continue
            rel = str(path.relative_to(root)).replace("\\", "/")
            snapshots[rel] = _hash_file(path)
    return snapshots


def detect_external_changes(
    project_slug: str,
    previous: dict[str, str] | None,
) -> list[str]:
    """
    对比当前磁盘与 previous 快照，返回已变更的相对路径列表。

    TODO: 与确认卡冲突 UI 联动（保留检查点 / 保留磁盘）。
    """
    if not previous:
        return []
    current = capture_file_snapshots(project_slug)
    changed: list[str] = []
    for rel, digest in previous.items():
        if current.get(rel) != digest:
            changed.append(rel)
    for rel in current:
        if rel not in previous:
            changed.append(rel)
    return sorted(set(changed))


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
