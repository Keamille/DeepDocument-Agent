"""Skill 扫描与召回"""

from deepdocument.skills.registry import recall_skills, scan_skills
from deepdocument.skills.proposer import propose_skill


def test_scan_skills():
    skills = scan_skills()
    assert "outline" in skills
    assert "draft-section" in skills
    assert "revise-section" in skills
    for skill in skills.values():
        assert "path" in skill
        assert "description" in skill
        assert "content" in skill
        assert "is_builtin" in skill


def test_recall_skills_returns_names():
    names = recall_skills("起草当前节 draft section", max_count=2)
    assert 1 <= len(names) <= 2
    assert all(isinstance(n, str) for n in names)


def test_propose_skill_markdown():
    md = propose_skill(["按结论归类", "按结论归类不要罗列"])
    assert md.startswith("---")
    assert "name:" in md
    assert "按结论归类" in md
