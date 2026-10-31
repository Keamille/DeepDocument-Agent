"""
图节点：各个处理步骤
"""

from datetime import datetime
from pathlib import Path
import json

from deepdocument.graph.state import GraphState
from deepdocument.memory.budget import build_prompt
from deepdocument.skills.registry import recall_skills
from deepdocument.llm.client import chat_for_action
from deepdocument.document.store import (
    load_meta,
    save_meta,
    load_section,
    save_section,
    append_decision,
)
from deepdocument.document.model import Decision
from deepdocument.literature.search import search_literature as search_openalex
from deepdocument.literature.fetch import fetch_source as fetch_literature_source


def load_context(state: GraphState) -> dict:
    """
    加载上下文

    召回 skill、组装提示
    """
    project_slug = state["project_slug"]

    # 召回 skill（最多 2 个）
    action_context = state.get("last_observation", "")
    recalled = recall_skills(action_context, max_count=2)

    # 组装提示
    prompt_text = build_prompt(project_slug, recalled)

    return {
        "last_observation": prompt_text,
    }


def choose_action(state: GraphState) -> dict:
    """
    模型选择动作

    通过 function calling 从白名单里选一个 tool，解析为动作名和参数。
    """
    messages = [
        {"role": "system", "content": state["last_observation"]},
        {"role": "user", "content": state.get("user_input", "")},
    ]

    action_name, action_input = chat_for_action(messages, temperature=0.3)

    return {
        "chosen_action": action_name,
        "action_input": action_input,
    }


def route_action(state: GraphState) -> str:
    """
    路由到对应的动作节点

    Returns:
        下一个节点的名称
    """
    action = state.get("chosen_action", "ask_user")

    # 映射到节点名称
    if action == "ask_user":
        return "ask_user"
    elif action == "search_literature":
        return "search_literature"
    elif action == "fetch_source":
        return "fetch_source"
    elif action == "update_outline":
        return "update_outline"
    elif action in ("draft_section", "revise_section"):
        return "draft_or_revise"
    elif action == "propose_skill":
        return "propose_skill"
    else:
        # 未知动作，回退到 ask_user
        return "ask_user"


def ask_user(state: GraphState) -> dict:
    """
    向用户提问

    不中断，只返回观察
    """
    question = state.get("action_input", {}).get("question", "需要更多信息")
    return {
        "last_observation": f"Question: {question}",
    }


def search_literature(state: GraphState) -> dict:
    """
    检索文献

    调用 OpenAlex，返回最多 8 条候选
    弹出确认卡让用户选择
    """
    query = state["action_input"]["query"]
    results = search_openalex(query, max_results=8)

    if len(results) < 3:
        return {
            "last_observation": f"只找到 {len(results)} 条文献，建议修改检索词",
        }

    # 构造确认卡
    card = {
        "card_type": "literature",
        "items": [
            {
                "id": r["id"],
                "title": r["title"],
                "year": r["year"],
                "available": r.get("oa_url") or r.get("abstract"),
            }
            for r in results
        ],
    }

    return {
        "pending_confirmation": card,
        "last_observation": f"找到 {len(results)} 条文献",
    }


def fetch_source(state: GraphState) -> dict:
    """
    抓取文献全文或摘要
    """
    lit_id = state["action_input"]["literature_id"]
    oa_url = state["action_input"].get("oa_url")
    abstract = state["action_input"].get("abstract")
    project_slug = state["project_slug"]

    result = fetch_literature_source(lit_id, oa_url, abstract, project_slug)

    return {
        "last_observation": f"抓取完成，来源: {result['content_source']}",
    }


def update_outline(state: GraphState) -> dict:
    """
    更新大纲

    弹出确认卡
    """
    titles = state["action_input"]["titles"]
    project_slug = state["project_slug"]

    # TODO: 生成 diff
    diff = "\n".join(f"+ {t}" for t in titles)

    card = {
        "card_type": "outline",
        "diff": diff,
    }

    return {
        "pending_confirmation": card,
        "last_observation": f"提议大纲（{len(titles)} 节）",
    }


def draft_or_revise(state: GraphState) -> dict:
    """
    起草或修订节

    弹出确认卡
    """
    action = state["chosen_action"]
    section_id = state["action_input"]["section_id"]
    project_slug = state["project_slug"]

    if action == "draft_section":
        # TODO: 调用模型生成正文
        content = "（草稿）"
    else:
        # revise_section
        # TODO: 读取现有正文，根据反馈修订
        content = load_section(project_slug, section_id)
        feedback = state["action_input"].get("feedback", "")
        # TODO: 调用模型修订
        content += f"\n\n（根据反馈修订: {feedback}）"

    card = {
        "card_type": "section",
        "markdown": content,
    }

    return {
        "pending_confirmation": card,
        "last_observation": f"{'起草' if action == 'draft_section' else '修订'}节: {section_id}",
    }


def propose_skill(state: GraphState) -> dict:
    """
    提议 skill

    弹出确认卡
    """
    name = state["action_input"].get("name", "new-skill")
    description = state["action_input"].get("description", "")
    body = state["action_input"].get("body") or description

    skill_markdown = (
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n"
    )

    card = {
        "card_type": "skill",
        "markdown": skill_markdown,
    }

    return {
        "pending_confirmation": card,
        "last_observation": "提议保存为 skill",
    }


def record_feedback(state: GraphState) -> dict:
    """
    记录反馈到 decisions.jsonl 和 user_profile.md
    """
    project_slug = state["project_slug"]
    feedback = state.get("user_input", "")
    section_id = state.get("cursor")

    decision = Decision(
        timestamp=datetime.now().isoformat(),
        section_id=section_id,
        feedback=feedback[:30],  # 最多 30 字
    )

    append_decision(project_slug, decision)

    # TODO: 更新画像
    return {
        "last_observation": "反馈已记录",
    }
