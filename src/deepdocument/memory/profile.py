"""
全局用户画像 user_profile.md

不属于某一个项目 slug；字段约定见 docs/memory.md。
"""

from __future__ import annotations

import re
from pathlib import Path

from deepdocument.document.model import Profile
from deepdocument.utils import format_frontmatter, parse_frontmatter

PROFILE_PATH = Path("user_profile.md")
MAX_REJECTS = 15


def load_profile() -> Profile:
    """读取全局画像；文件不存在时返回默认值。"""
    if not PROFILE_PATH.exists():
        return Profile()

    meta, _body = parse_frontmatter(PROFILE_PATH.read_text(encoding="utf-8"))
    rejects = meta.get("rejects") or []
    if isinstance(rejects, str):
        rejects = [rejects]
    return Profile(
        language=str(meta.get("language") or "中文"),
        tone=str(meta.get("tone") or ""),
        structure=str(meta.get("structure") or ""),
        citation=str(meta.get("citation") or ""),
        rejects=[str(r) for r in rejects][:MAX_REJECTS],
    )


def save_profile(profile: Profile | dict) -> None:
    """写回 user_profile.md（YAML frontmatter）。"""
    if isinstance(profile, dict):
        profile = Profile(
            language=str(profile.get("language") or "中文"),
            tone=str(profile.get("tone") or ""),
            structure=str(profile.get("structure") or ""),
            citation=str(profile.get("citation") or ""),
            rejects=list(profile.get("rejects") or [])[:MAX_REJECTS],
        )

    meta = {
        "language": profile.language,
        "tone": profile.tone,
        "structure": profile.structure,
        "citation": profile.citation,
        "rejects": profile.rejects[:MAX_REJECTS],
    }
    PROFILE_PATH.write_text(format_frontmatter(meta, ""), encoding="utf-8")


def update_profile(feedback: str) -> Profile:
    """
    根据一条反馈更新画像。

    第一版：去掉标点后精确去重；「不要/别/拒绝」类写入 rejects，其余追加到 structure。
    """
    text = (feedback or "").strip()
    profile = load_profile()
    if not text:
        return profile

    normalized = _normalize(text)
    existing = {_normalize(x) for x in [profile.tone, profile.structure, profile.citation, *profile.rejects] if x}
    if normalized in existing:
        return profile

    if _looks_like_reject(text):
        profile.rejects.append(text[:80])
        profile.rejects = profile.rejects[:MAX_REJECTS]
    elif not profile.structure:
        profile.structure = text[:120]
    elif text not in profile.rejects:
        # 已有 structure 时，额外偏好放进 rejects 旁的备注式追加：仍归 structure 用分号连接过长则截断
        merged = f"{profile.structure}；{text}"
        profile.structure = merged[:120]

    save_profile(profile)
    return profile


def profile_to_prompt(profile: Profile | None = None) -> str:
    """拼进提示的短文本。"""
    profile = profile or load_profile()
    lines = [
        f"language: {profile.language}",
        f"tone: {profile.tone}",
        f"structure: {profile.structure}",
        f"citation: {profile.citation}",
        "rejects:",
    ]
    if profile.rejects:
        lines.extend(f"  - {r}" for r in profile.rejects)
    else:
        lines.append("  - （无）")
    return "\n".join(lines)


def _normalize(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE).lower()


def _looks_like_reject(text: str) -> bool:
    return bool(re.search(r"不要|别|拒绝|禁止|避免", text))
