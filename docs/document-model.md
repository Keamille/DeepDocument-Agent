# 文稿数据

一份文稿是 `projects/<slug>/` 下一个目录。聊天记录不是正文。字段如下。

## brief.md

```markdown
---
title: 检索增强生成在企业知识库中的应用
kind: summary
audience: 课程老师
citation_style: APA
constraints:
  - 中文
  - 先写结论再写依据
---
```

`kind` 取值：
- `summary`：总结，可以只有一节
- `report`：报告，多节结构
- `paper`：论文，需要引用格式

`citation_style` 默认为 `APA`，可选 `GB/T 7714-2015`。检索词默认来自 `title`。

## outline.md

确认后的大纲，一节一个标题。第一次可以由 `template.docx` 的标题样式生成，用户同意后才覆盖这个文件，并同步 `meta.json`。

## sections 与 meta.json

每一节一个文件：`sections/<id>.md`。状态在 `meta.json`：

```json
{
  "cursor": "summary",
  "sections": [
    {
      "id": "summary",
      "title": "总结",
      "status": "draft",
      "gist": "按两条结论归类，不逐篇罗列"
    }
  ]
}
```

`status` 取 `empty`、`outlined`、`draft`、`accepted`。`cursor` 是当前正在写的节。`gist` 在该节落盘时写成不超过 20 字的要旨，供以后的提示使用，不替代正文。一轮最多展开 10 节的要旨，其余节只留 id 和状态。

默认只动 `cursor`，或下一节 `empty`。用户点名某一节时，这一轮改为修订那一节。

## literature.jsonl

一行一条。确认卡上的候选在用户点头前不写入。点头后，勾选项为 `accepted`，未勾选项为 `rejected`。

```json
{
  "id": "W1",
  "openalex_id": "https://openalex.org/W123",
  "doi": "10.1000/example",
  "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
  "authors": ["Patrick Lewis"],
  "year": 2020,
  "venue": "NeurIPS",
  "url": "https://openalex.org/W123",
  "abstract": "...",
  "status": "accepted",
  "content_source": "fulltext"
}
```

`content_source` 取 `fulltext`、`abstract` 或 `user_file`。用户附上的本地文件可以没有 `openalex_id`，但要有 `local_path`。模型只能引用 `accepted` 条目。

模型提示里的文献卡片不是这个 JSON 的全文。卡片只有 `id`、缩短的标题、年份和 `content_source`。`abstract` 字段留在文件里，正文进入提示时走 `sources/<id>.md` 的摘录。

## sources/<id>.md

`fetch_source` 写成三截。`## card` 只在窗口右栏展示，不进入模型提示。提示中的文献卡片来自 `literature.jsonl`，只包含 id、缩短的标题、年份和 `content_source`。原文留在文件后部，不整篇送进模型。

```markdown
---
id: W1
content_source: fulltext
---

## card

两句话说明这篇材料跟题目的关系。供窗口右栏展示，不进入模型提示。

## excerpt

供当前节引用的摘录。一轮提示最多带 3 篇，每篇最多 1,200 token。超出的部分留在本文件，并在提示里注明已截断。预算见 [memory.md](memory.md)。

## archive

更长的开放获取原文。不进入提示。
```

摘要来源没有 `archive` 节，`excerpt` 就是摘要，并且 `card` 写明依据是摘要。

## decisions.jsonl

只记录这一份文稿里的逐条意见，保留原文。

```json
{"at": "2026-10-27T18:00:00+08:00", "section": "summary", "text": "按结论归类，不要逐篇罗列"}
```

原文全部保留。进入提示的是最近 5 条，每条最多 30 字。更早的意见已经收成全局用户画像。字数见 [memory.md](memory.md)。

## template.docx 与 export.docx

`template.docx` 是用户给的格式标准，导出时不修改它。`export.docx` 用 python-docx 打开模板作为底稿，沿用其中的标题和正文样式，按已确认大纲重写正文，不保留模板里的示例段落。

写入规则：

- 标题来自 `brief.md`。
- 状态为 `outlined`、`draft`、`accepted` 的节按顺序写入。
- `draft` 的标题标明草稿。
- `empty` 的节不写入。
- 文末参考文献只列 `accepted` 文献，按 `brief.md` 中的 `citation_style` 格式化（默认 APA 7th，按作者姓氏字母排序）。
- 同一路径每次覆盖。
- 没有模板时使用空白文档。
- 格式是 `.docx`，不生成旧版二进制 `.doc`。

样式映射规则：
- 一级标题 → `Heading 1` 或 `标题 1`
- 正文 → `Normal` 或 `正文`
- 若模板缺少这些样式，使用 `python-docx` 默认样式，并在导出后提示用户。

文本框、内容控件和自动目录域不保证复刻。

大纲确认写入之后、文献确认并抓到摘录之后、节草稿或修订落盘之后，都重写 `export.docx`。窗口上的「导出 Word」再合成一次并给出路径。

## 全局文件

`user_profile.md` 和 `skills_user/` 不属于某一个 slug。画像字段见 [memory.md](memory.md)，skill 字段见 [skills.md](skills.md)。
