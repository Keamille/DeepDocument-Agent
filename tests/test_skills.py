"""
测试：Skill 注册表
"""

from pathlib import Path
from deepdocument.skills.registry import scan_skills, _parse_skill_meta


def test_scan_skills():
    """测试 skill 扫描"""
    skills = scan_skills()

    # 应该至少有 3 个内置 skill
    assert "outline" in skills
    assert "draft-section" in skills
    assert "revise-section" in skills

    # 每个 skill 都有必需字段
    for name, skill in skills.items():
        assert "path" in skill
        assert "description" in skill
        assert "content" in skill
        assert "is_builtin" in skill


def test_parse_skill_meta():
    """测试 frontmatter 解析"""
    # TODO: 创建临时 SKILL.md 文件测试
    pass
