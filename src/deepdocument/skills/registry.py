"""
Skill 注册表

扫描内置 skill 和 skills_user/，按 description 匹配。
"""

from pathlib import Path

import yaml


def scan_skills() -> dict[str, dict]:
    """
    扫描所有 skill

    Returns:
        {skill_name: {"path": Path, "description": str, "content": str}}
    """
    skills = {}

    # 扫描内置 skill
    builtin_dir = Path(__file__).parent / "builtin"
    if builtin_dir.exists():
        for skill_dir in builtin_dir.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    meta = _parse_skill_meta(skill_md)
                    skills[skill_dir.name] = {
                        "path": skill_md,
                        "description": meta.get("description", ""),
                        "content": skill_md.read_text(encoding="utf-8"),
                        "is_builtin": True,
                    }

    # 扫描用户 skill
    user_dir = Path("skills_user")
    if user_dir.exists():
        for skill_dir in user_dir.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    meta = _parse_skill_meta(skill_md)
                    # 用户 skill 优先级更高，会覆盖同名内置 skill
                    skills[skill_dir.name] = {
                        "path": skill_md,
                        "description": meta.get("description", ""),
                        "content": skill_md.read_text(encoding="utf-8"),
                        "is_builtin": False,
                    }

    return skills


def recall_skills(action_context: str, max_count: int = 2) -> list[str]:
    """
    召回与当前动作相关的 skill

    优先级：用户 skill > 内置 skill
    若多个匹配，按 description 相似度排序，取前 max_count 个

    Args:
        action_context: 当前动作的上下文描述
        max_count: 最多召回数量

    Returns:
        skill 名称列表
    """
    skills = scan_skills()

    # TODO: 按 description 与 action_context 的相似度排序
    # TODO: 简单实现：关键词匹配
    # TODO: 高级实现：嵌入向量相似度

    return []


def _parse_skill_meta(skill_path: Path) -> dict:
    """
    解析 SKILL.md 的 frontmatter

    Args:
        skill_path: SKILL.md 路径

    Returns:
        frontmatter 字典
    """
    content = skill_path.read_text(encoding="utf-8")
    if not content.startswith("---\n"):
        return {}

    # 提取 frontmatter
    parts = content.split("---\n", 2)
    if len(parts) < 3:
        return {}

    try:
        return yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {}
