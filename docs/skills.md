# Skills

Skill 是一份说明书，不是可执行代码。内置 skill 和用户 skill 使用同一格式。用户 skill 放在全局 `skills_user/<name>/SKILL.md`，所有文稿项目都能用。

## 格式

```markdown
---
name: related-work-by-claim
description: 用户要求相关工作按主张而不是按年份组织时使用
---

先列 3 条主张，每条下再放文献，不要写成年表。
```

`name` 是目录名，使用小写英文和连字符。`description` 是装载依据，写明什么情况下使用。正文是做法。进入提示时，每份 skill 正文最多 300 token，两份合计不超过 600 token。超出的步骤仍留在文件里。预算见 [memory.md](memory.md)。

## 内置三条

实现时放在 `skills/builtin/`：

| name | 何时使用 |
| --- | --- |
| `outline` | 要从格式文件或题目整理大纲时 |
| `draft-section` | 要根据摘录写当前节时 |
| `revise-section` | 要按用户意见改某一节时 |

内置 skill 保证第一次没有用户 skill 时仍能写。它们可以被用户 skill 补上更具体的做法，但不能被用户 skill 覆盖成可执行脚本。

## 装载

优先级：用户 skill > 内置 skill

装载规则：
1. 若用户 skill 的 description 与这一轮相符，只装该用户 skill
2. 若没有匹配的用户 skill，装载与当前动作对应的内置 skill
3. 若多个用户 skill 匹配，按最近创建时间排序，取第一个
4. 两份合计不超过 600 token

不做向量检索。description 匹配使用关键词或模式匹配。

## 生成

两种触发：

- 用户说「记住这个做法」。
- 同一类修改在当前项目的 `decisions.jsonl` 里出现两次。

`propose_skill` 只起草文本。确认卡展示完整的 `SKILL.md`。用户可以同意、拒绝，或改完再同意。同意后才写入 `skills_user/<name>/SKILL.md`。拒绝不写文件。

下一份文稿，只要 `description` 匹配，就会装上这份 skill。这就是越用越顺：做法留在全局目录里，而不是留在某一次聊天里。

## 和用户画像的分工

画像里的一句可能是「相关工作按主张组织」。对应的 skill 才写明先列主张、再放文献。画像整份常驻。skill 正文只在命中时出现。提议 skill 时不要把画像里的短句原样再存一份更长的重复说明，除非里面有可执行的步骤。

Skill 示例里应写明要调用的**工具名**和 JSON 参数，不要再写 `Thought` / `Action` / `Action Input` 三段文本。动作契约以 [agent-loop.md](agent-loop.md) 与 [`llm/tools.py`](../src/deepdocument/llm/tools.py) 的 `ACTION_TOOLS` 为准。
