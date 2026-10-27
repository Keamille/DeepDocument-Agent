"""
内置 skill: 起草节
"""

SKILL = """---
name: draft-section
description: 根据摘录起草一节
---

# 触发场景

大纲已确认，当前节状态是 pending，用户要求起草。

# 做法

1. 从 meta.json 读取当前节标题
2. 从文献卡片选择 1-3 篇相关文献
3. 装入这些文献的摘录（每篇最多 1200 token）
4. 每一段都引用至少一篇摘录中的内容
5. 输出 Action: draft_section

# 示例

Action: draft_section
Action Input: {"section_id": "s01", "source_ids": ["W123", "W456"]}
"""
