"""
模型可选的动作工具定义

与 docs/agent-loop.md 白名单一一对应。每轮只应触发其中一个。
运行时工具（fetch_source、export_docx 等）不在这里。
"""

from __future__ import annotations

from typing import Any

ACTION_WHITELIST = frozenset(
    {
        "ask_user",
        "search_literature",
        "update_outline",
        "draft_section",
        "revise_section",
        "accept_section",
        "record_decision",
        "propose_skill",
    }
)


def _tool(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str] | None = None,
) -> dict:
    """构造一条 OpenAI function tool 定义"""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
                "additionalProperties": False,
            },
        },
    }


ACTION_TOOLS: list[dict] = [
    _tool(
        "ask_user",
        "信息不够时向用户提问，不编造章节或文献。",
        {
            "question": {"type": "string", "description": "要问用户的问题"},
            "reason": {"type": "string", "description": "可选：选择该动作的简短理由"},
        },
        ["question"],
    ),
    _tool(
        "search_literature",
        "用题目向 OpenAlex 检索真实文献，结果需用户勾选后才进入正文。",
        {
            "query": {"type": "string", "description": "检索词，通常来自 brief 的题目"},
            "reason": {"type": "string", "description": "可选：选择该动作的简短理由"},
        },
        ["query"],
    ),
    _tool(
        "update_outline",
        "提议或更新大纲。写入前会弹出 diff 确认卡。",
        {
            "titles": {
                "type": "array",
                "items": {"type": "string"},
                "description": "按顺序的节标题列表",
            },
            "reason": {"type": "string", "description": "可选：选择该动作的简短理由"},
        },
        ["titles"],
    ),
    _tool(
        "draft_section",
        "只根据 sources/ 摘录起草当前节。没有摘录支撑的断言不要写。",
        {
            "section_id": {"type": "string", "description": "节 id，对应 meta.json"},
            "source_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "本轮要用的文献 id，最多 3 个",
                "maxItems": 3,
            },
            "reason": {"type": "string", "description": "可选：选择该动作的简短理由"},
        },
        ["section_id"],
    ),
    _tool(
        "revise_section",
        "只按本轮反馈修订用户点名的那一节。",
        {
            "section_id": {"type": "string", "description": "要修订的节 id"},
            "feedback": {"type": "string", "description": "用户的修改意见"},
            "source_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "本轮要用的文献 id，最多 3 个",
                "maxItems": 3,
            },
            "reason": {"type": "string", "description": "可选：选择该动作的简短理由"},
        },
        ["section_id", "feedback"],
    ),
    _tool(
        "accept_section",
        "用户明确接受后，把当前节标为 accepted 并移动 cursor。",
        {
            "section_id": {"type": "string", "description": "要接受的节 id"},
            "reason": {"type": "string", "description": "可选：选择该动作的简短理由"},
        },
        ["section_id"],
    ),
    _tool(
        "record_decision",
        "追加一条不改动正文的反馈意见到 decisions.jsonl。",
        {
            "text": {"type": "string", "description": "反馈原文"},
            "section_id": {"type": "string", "description": "相关节 id，可空"},
            "reason": {"type": "string", "description": "可选：选择该动作的简短理由"},
        },
        ["text"],
    ),
    _tool(
        "propose_skill",
        "起草一份可复用的 SKILL.md，写入前需用户确认。",
        {
            "name": {
                "type": "string",
                "description": "skill 目录名，小写英文和连字符",
            },
            "description": {
                "type": "string",
                "description": "何时使用该 skill",
            },
            "body": {
                "type": "string",
                "description": "skill 正文做法，可选；没有则由节点再生成",
            },
            "reason": {"type": "string", "description": "可选：选择该动作的简短理由"},
        },
        ["name", "description"],
    ),
]
