# DeepDocument

本机桌面窗口客户端。它按用户的题目检索真实文献，读取开放获取全文或摘要，再写成总结、文档或论文，并导出 Word。用户改过的写法会留下，下一次少犯同样的错。

这一版是开发说明，还没有实现代码。阅读顺序：

1. [docs/architecture.md](docs/architecture.md)：进程、目录、模块（先看全貌）
2. [docs/document-model.md](docs/document-model.md)：磁盘上的字段（理解数据）
3. [docs/agent-loop.md](docs/agent-loop.md)：工具、ReAct、一轮如何结束（理解循环）
4. [docs/memory.md](docs/memory.md)：五类记忆，以及上下文窗口里每个数字的取值（理解预算）
5. [docs/skills.md](docs/skills.md)：可复用做法如何生成和装载（理解扩展）
6. [docs/gui.md](docs/gui.md)：窗口里的两屏和确认卡（理解交互）
7. [docs/stack.md](docs/stack.md)：技术栈选型（理解选型）

## 四条需求

1. **搜索真实文献。** 只使用 OpenAlex 索引中的记录。确认卡展示 OpenAlex id、标题、作者、年份、出处和链接。用户勾选后，有开放获取全文就抽取文本，没有则只用摘要，并标明依据。用户附上的本地文件同样进入确认。模型不编造文献，不抓付费墙后的 PDF。
2. **自生成可复用的 skill。** 用户说「记住这个做法」，或同类修改在决策日志里出现两次，就起草一份 `SKILL.md`。同意后写入 `skills_user/`，所有文稿项目共用。描述匹配时才把正文装进提示。
3. **按检索到的内容生成总结、报告或论文。** `brief.md` 的 `kind` 为 `summary`、`report` 或 `paper`。正文只依据 `sources/` 里的摘录。给了 `template.docx` 就用它的样式导出；没给就用空白文档。每次落盘重写 `export.docx`。
4. **按反馈修改。** 用户点名某一节，这一轮只改那一节，Word 跟着更新。意见写入该项目的 `decisions.jsonl`，并收成全局 `user_profile.md`。同一类意见再次出现时提议变成 skill。

这里的「项目」是窗口里的一份文稿，不扫描外部代码仓库。一次用户消息只推进一个动作。关掉窗口再打开，停在同一次确认上。

## 范围边界

实现时不包含：

- 不使用 LangGraph Platform 或 `langgraph dev`
- 不绕过付费墙，不编造文献
- 不做向量检索，摘录按节装入提示
- 一次消息推进一个动作，不交出终稿

## 运行时（实现阶段）

技术栈见 [docs/stack.md](docs/stack.md)。模型密钥放在实现阶段的 `.env`，不写入仓库。
