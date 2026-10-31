# 代理循环

LangGraph 负责暂停、恢复，以及把唯一的动作接到运行时工具。模型每轮通过 **function calling** 只调用一个白名单工具，不在内部连续调用多个工具。

## 记忆层

五类记忆放什么、保留多久、其中多少进入模型，都写在 [memory.md](memory.md)。这里只定循环怎么用它们。

`load_memory` 每轮按该文档的 8,000 token 预算从磁盘现装提示，不把历史推理文本累积进模型。检查点只保留恢复确认卡所需的状态和上一条 Observation。画像是短偏好，skill 是步骤，两者不互相替代。

## 工具层

模型能通过 function calling 点名的只有下面这些（与 `llm/tools.py` 里的 `ACTION_TOOLS` 一致）：

| 工具名 | 作用 | 是否暂停 |
| --- | --- | --- |
| `ask_user` | 缺题目、种类或格式文件时提问 | 是 |
| `search_literature` | 用题目向 OpenAlex 要真实记录（可能少于 8 条） | 是，等勾选 |
| `update_outline` | 给出大纲 diff | 是 |
| `draft_section` | 只根据 `sources/` 写当前节 | 否 |
| `revise_section` | 只按本轮反馈改点名的节 | 否 |
| `accept_section` | 把当前节标为 `accepted`，并移动 `cursor` | 否 |
| `record_decision` | 追加一条反馈 | 否 |
| `propose_skill` | 起草 skill | 是 |

运行时工具不由模型点名：

| 工具 | 何时运行 |
| --- | --- |
| `fetch_source` | 用户勾选文献之后，写入 `sources/<id>.md`。若既无开放获取全文也无摘要，标注「无可用文本」 |
| `export_docx` | 大纲、摘录或某一节落盘之后，以及用户点击导出 |
| `load_memory` | 每轮拼提示之前 |
| `recall_skills` | 每轮按 description 选择最多 2 个 skill（优先级见 skills.md） |
| `update_profile` | `revise_section` 或 `record_decision` 之后 |

`draft_section` 和 `revise_section` 的提示里只放摘录和已确认文献的短卡片。没有对应摘录的断言不写进正文。

`revise_section` 落盘后，图的节点自动调用 `record_decision` 和 `update_profile`。这样一次修订不会再占一轮。`record_decision` 单独使用时，只用于没有改动正文的意见。

## Function calling

`choose_action` 调用聊天接口时带上全部 `ACTION_TOOLS`，并设置：

- `tool_choice="required"`：本轮必须选一个工具
- `parallel_tool_calls=False`：禁止一次返回多个 call（兼容接口若不支持该参数则省略）

运行时只取**第一个** `tool_call`，解析 `function.name` 与 `function.arguments`（JSON 对象）。

可选的简短理由放在工具参数的 `reason` 字段，或写在 `message.content` 里；窗口可用来展示，不进入下一轮提示预算。

解析失败、没有 tool call、或名字不在白名单时，这一轮改为 `ask_user`，不执行写入。

运行时执行该动作，得到 Observation。需要人看的 Observation 变成确认卡。已经落盘的 Observation 写成文件变更。下一轮提示只带上一条 Observation。

提示各切片的 token 上限见 [memory.md](memory.md)。

## 一轮怎么结束

写节、修订、接受和记录反馈在落盘后结束本轮，并触发 `export_docx`。修订和记录反馈都会触发 `update_profile`。

提问、大纲、文献勾选和 skill 草稿停在 `interrupt`。用户的选择作为 `Command(resume=...)` 进入下一步：同意则写入，拒绝则保持原文件，并可以把拒绝本身记入反馈。
