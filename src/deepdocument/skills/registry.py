"""
Skill 注册表：扫描内置与 skills_user/，按 description 关键词召回。
"""

from __future__ import annotations

import re
from pathlib import Path

from deepdocument.utils import parse_frontmatter


def scan_skills() -> dict[str, dict]:
    """
    扫描所有 skill。

    Returns:
        {name: {path, description, content, is_builtin}}
    """
    skills: dict[str, dict] = {}

    builtin_dir = Path(__file__).parent / "builtin"
    if builtin_dir.exists():
        for skill_dir in builtin_dir.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    meta, _ = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
                    skills[skill_dir.name] = {
                        "path": skill_md,
                        "description": str(meta.get("description") or ""),
                        "content": skill_md.read_text(encoding="utf-8"),
                        "is_builtin": True,
                    }

    user_dir = Path("skills_user")
    if user_dir.exists():
        for skill_dir in user_dir.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    meta, _ = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
                    skills[skill_dir.name] = {
                        "path": skill_md,
                        "description": str(meta.get("description") or ""),
                        "content": skill_md.read_text(encoding="utf-8"),
                        "is_builtin": False,
                    }

    return skills


def recall_skills(action_context: str, max_count: int = 2) -> list[str]:
    """
    按 description / 名称与上下文的关键词重叠召回。

    同分时用户 skill 优先于内置。无匹配时回退前 max_count 个（用户优先排序）。
    """
    skills = scan_skills()
    if not skills or max_count <= 0:
        return []

    context_tokens = _tokens(action_context)
    scored: list[tuple[int, int, str]] = []
    for name, skill in skills.items():
        desc_tokens = _tokens(f"{name} {skill.get('description', '')}")
        overlap = len(context_tokens & desc_tokens) if context_tokens else 0
        user_boost = 0 if skill.get("is_builtin") else 1
        scored.append((overlap, user_boost, name))

    scored.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    matched = [name for overlap, _, name in scored if overlap > 0]
    if matched:
        return matched[:max_count]

    # 无关键词命中：仍给内置写作相关 skill 一个稳定默认
    preferred = ["draft-section", "outline", "revise-section"]
    ordered = [n for n in preferred if n in skills]
    ordered.extend(n for _, _, n in scored if n not in ordered)
    return ordered[:max_count]


def _tokens(text: str) -> set[str]:
    text = (text or "").lower()
    parts = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", text)
    return {p for p in parts if len(p) >= 2}
