---
name: outline
description: 根据题目和文献起草大纲
---

# 触发场景

用户提供了题目和文献，但还没有大纲。

# 做法

1. 从 brief.md 读取题目、种类、受众
2. 从文献卡片读取已接受的文献标题和年份
3. 根据种类确定结构：
   - summary: 总结（单节）
   - report: 引言、主体若干节、结论
   - paper: 摘要、引言、方法、结果、讨论、结论
4. 调用工具 `update_outline`

# 示例

调用 `update_outline`，参数：

```json
{"titles": ["引言", "主要发现", "局限", "结论"], "reason": "按报告结构列出四节"}
```
