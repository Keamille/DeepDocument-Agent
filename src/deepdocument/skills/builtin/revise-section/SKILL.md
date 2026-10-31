---
name: revise-section
description: 根据用户反馈修订一节
---

# 触发场景

用户对某一节提出修改意见。

# 做法

1. 读取该节的现有正文
2. 读取用户的反馈
3. 装入相关摘录（若需要补充引用）
4. 只修改必要部分，保留未被指出问题的段落
5. 调用工具 `revise_section`
6. 落盘后自动记录反馈到 decisions.jsonl 和 user_profile.md

# 示例

调用 `revise_section`，参数：

```json
{"section_id": "s02", "feedback": "引言太长，缩短到 200 字", "source_ids": ["W123"], "reason": "按用户意见压缩引言"}
```
