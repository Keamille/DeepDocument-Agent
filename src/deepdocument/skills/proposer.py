"""
Skill 提议器

根据重复反馈生成 skill 草稿。
"""


def propose_skill(repeated_feedback: list[str]) -> str:
    """
    根据重复出现的反馈生成 skill 草稿

    Args:
        repeated_feedback: 重复的反馈列表

    Returns:
        SKILL.md 内容（包含 frontmatter）
    """
    # TODO: 调用模型生成 skill
    # TODO: frontmatter 包含 name, description
    # TODO: body 包含触发场景、做法、示例

    return """---
name: example-skill
description: 示例 skill
---

# 触发场景

当用户反馈...

# 做法

1. ...
2. ...

# 示例

...
"""
