# 技术栈选型

运行环境是本仓库已有的 Python 3.14。一个进程里同时有桌面窗口和 LangGraph。不另起网站，不引入 Node 构建，也不把数据放进数据库服务。

## 选定

| 层 | 选定 | 理由 |
| --- | --- | --- |
| 语言 | Python 3.14 | 本机虚拟环境已是 3.14。代码只用 3.11 及以上就有的语法，便于以后换解释器 |
| 图与暂停 | `langgraph` | `interrupt()` 和检查点正好对应确认卡、关窗再开。一轮一个动作由我们自己的节点完成 |
| 会话存储 | `langgraph-checkpoint-sqlite` | 每个文稿项目一个 `checkpoints.sqlite`，不需要单独安装数据库 |
| 模型调用 | `openai` 官方 SDK | 节点自己组提示；选动作用 Chat Completions 的 function calling（`tools` / `tool_choice`）。不使用 LangChain 的 Agent 或 Retriever |
| 窗口 | `pywebview` | 打开的是系统窗口。Windows 上用 WebView2。Python 与页面通过 `js_api` 调用，不监听端口 |
| 窗口内页面 | HTML、CSS、少量 JavaScript | 左栏对话、右栏 Markdown、确认卡用静态页面就够。不引入 React、Vue，也不需要 Node |
| Markdown 预览 | 仓库内的 `marked` 单文件 | 右栏要把 `sections/*.md` 显示出来。单文件放进仓库，窗口不访问外网 CDN |
| Word | `python-docx` | 用用户的 `template.docx` 当底稿，沿用其中的标题和正文样式，写出 `export.docx` |
| 文献检索 | OpenAlex `https://api.openalex.org/works?search=` | 返回真实存在的作品 id、题名、作者、年份和开放获取链接，不需要密钥 |
| HTTP | `httpx` | 检索和下载开放获取 PDF 需要超时和状态码。同步接口和同步的图节点一致 |
| PDF 文本 | `pypdf` | 只抽取 PDF 的文本层，供摘录使用。纯 Python，不带原生库 |
| 前言 | `PyYAML` | `brief.md` 和 `SKILL.md` 的前言就是一小段 YAML |
| 配置 | 标准库读环境变量，`python-dotenv` 读 `.env` | 只需要模型地址、密钥和模型名 |
| 大纲 diff | 标准库 `difflib` | 确认卡上的大纲差异不必再依赖一个 diff 库 |
| 测试 | `pytest` | 用假的模型客户端验证一轮动作、确认门和预算裁剪 |

`langgraph` 会带入 `langchain-core`。这是图的依赖，不在业务代码里使用 LangChain 的代理封装。

## 模型与 token

`.env` 只放这三项：

```text
OPENAI_BASE_URL=
OPENAI_API_KEY=
OPENAI_MODEL=
```

模型上下文至少 32,768 token。提示仍按 [memory.md](memory.md) 装到 16,000 token，不因为换了更长窗口就多放原文。

不使用 `tiktoken`。它只对部分 OpenAI 模型准确，换到其他兼容接口就会数错。有该模型自己的 tokenizer 时用它，否则用 `memory.md` 里的估算。

## PDF 抽不到文本时

`pypdf` 只读文本层。扫描件、图片型 PDF 不进行 OCR。开放获取 PDF 抽不到文本时，改为使用 OpenAlex 的摘要，`content_source` 写成 `abstract`，并在界面上标明。用户附上的 PDF 同样用 `pypdf`；抽不到文本时不能假装有摘要，这一条材料不进入 `accepted`，并请用户换文件或改为检索。`.docx` 附件只作为 `template.docx`，不作为文献正文。

不下载付费墙后的文件。没有开放获取链接时同样只用摘要。

## 不选这些

| 不选 | 原因 |
| --- | --- |
| LangGraph Platform、`langgraph dev` | 那是带网址的服务。这个客户端要关窗之后靠本地 sqlite 恢复 |
| LangChain Agent、LlamaIndex、向量库 | 文献来自一次检索和用户勾选，摘录按节装进提示，不需要再做相似度检索 |
| PySide、Electron、Tauri | 窗口只承载对话、确认卡和 Markdown。pywebview 足够，且不必再维护一套前端工程 |
| FastAPI 或本机网站 | 页面和 Python 在同一进程里通过 `js_api` 通信 |
| `python-doc` 或其他旧式 `.doc` 库 | 交稿格式是 `.docx` |
| OCR、版面分析、`unstructured` | 摘录不需要还原栏位和页眉。文本层失败时退回摘要 |
| PostgreSQL、MongoDB | 文稿是文件，会话是一个 sqlite 文件 |
