"""
图节点：装提示、选动作、执行白名单动作

模型动作见 llm/tools.ACTION_TOOLS。
fetch_source / export_docx / update_profile 等为运行时工具，不由 route 暴露。
需人确认的动作在节点内 interrupt(payload)；写节直接落盘。
"""

from __future__ import annotations

from datetime import datetime, timezone

from langgraph.types import interrupt

from deepdocument.document.exporter import export_docx
from deepdocument.document.model import Decision
from deepdocument.document.store import (
    append_decision,
    load_meta,
    load_section,
    save_outline,
    save_section,
    update_section_meta,
)
from deepdocument.graph.state import GraphState
from deepdocument.literature.fetch import fetch_source as fetch_literature_source
from deepdocument.literature.search import search_literature as search_openalex
from deepdocument.llm.client import chat_for_action
from deepdocument.memory.budget import build_prompt
from deepdocument.memory.profile import update_profile
from deepdocument.skills.registry import recall_skills


def load_context(state: GraphState) -> dict:
    """召回 skill，按预算现装本轮提示；不覆盖 last_observation。"""
    project_slug = state["project_slug"]
    observation = state.get("last_observation", "")
    recalled = recall_skills(observation or state.get("user_input", ""), max_count=2)
    prompt_text = build_prompt(
        project_slug,
        recalled,
        observation=observation,
    )
    return {"prompt_text": prompt_text}


def choose_action(state: GraphState) -> dict:
    """function calling 选一个白名单动作。"""
    messages = [
        {"role": "system", "content": state.get("prompt_text") or ""},
        {"role": "user", "content": state.get("user_input", "")},
    ]
    action_name, action_input = chat_for_action(messages, temperature=0.3)
    return {
        "chosen_action": action_name,
        "action_input": action_input,
    }


def route_action(state: GraphState) -> str:
    """把 chosen_action 映射到图节点名。"""
    action = state.get("chosen_action", "ask_user")
    mapping = {
        "ask_user": "ask_user",
        "search_literature": "search_literature",
        "update_outline": "update_outline",
        "draft_section": "draft_or_revise",
        "revise_section": "draft_or_revise",
        "accept_section": "accept_section",
        "record_decision": "record_decision",
        "propose_skill": "propose_skill",
    }
    return mapping.get(action, "ask_user")


def ask_user(state: GraphState) -> dict:
    """缺信息时提问；interrupt 等用户回答。"""
    question = state.get("action_input", {}).get("question", "需要更多信息")
    card = {"card_type": "question", "question": question}
    answer = interrupt(card)
    text = ""
    if isinstance(answer, dict):
        text = str(answer.get("text") or answer.get("answer") or "")
    elif isinstance(answer, str):
        text = answer
    return {
        "last_observation": f"用户回答: {text}" if text else f"已提问: {question}",
        "pending_confirmation": None,
    }


def search_literature(state: GraphState) -> dict:
    """OpenAlex 检索；interrupt 等勾选；同意后抓取 sources。"""
    query = (state.get("action_input") or {}).get("query", "")
    results = search_openalex(query, max_results=8)

    if len(results) < 3:
        return {
            "last_observation": f"只找到 {len(results)} 条文献，建议修改检索词",
            "pending_confirmation": None,
        }

    card = {
        "card_type": "literature",
        "items": [
            {
                "id": r["id"],
                "title": r["title"],
                "authors": r.get("authors", []),
                "year": r.get("year"),
                "venue": r.get("venue"),
                "url": r.get("url"),
                "oa_url": r.get("oa_url"),
                "abstract": r.get("abstract"),
                "available": bool(r.get("oa_url") or r.get("abstract")),
            }
            for r in results
        ],
    }
    selection = interrupt(card)
    if not isinstance(selection, dict) or not selection.get("accept"):
        return {
            "last_observation": "用户未确认文献候选",
            "pending_confirmation": None,
        }

    selected_ids = set(selection.get("selected_ids") or [])
    project_slug = state["project_slug"]
    fetched = 0
    for item in results:
        if item["id"] not in selected_ids:
            continue
        fetch_literature_source(
            literature_id=item["id"],
            oa_url=item.get("oa_url"),
            abstract=item.get("abstract"),
            project_slug=project_slug,
            meta={
                "title": item.get("title"),
                "authors": item.get("authors"),
                "year": item.get("year"),
                "venue": item.get("venue"),
                "url": item.get("url"),
                "openalex_id": item.get("openalex_id"),
                "doi": item.get("doi"),
            },
        )
        fetched += 1

    try:
        export_docx(project_slug)
    except FileNotFoundError:
        pass

    return {
        "last_observation": f"已确认并抓取 {fetched} 条文献摘录",
        "pending_confirmation": None,
    }


def update_outline(state: GraphState) -> dict:
    """提议大纲；interrupt 确认后写入。"""
    titles = list((state.get("action_input") or {}).get("titles") or [])
    diff = "\n".join(f"+ {t}" for t in titles)
    card = {"card_type": "outline", "diff": diff, "titles": titles}
    decision = interrupt(card)
    if not isinstance(decision, dict) or not decision.get("accept"):
        return {
            "last_observation": "用户拒绝大纲提议",
            "pending_confirmation": None,
        }

    final_titles = decision.get("titles") or titles
    project_slug = state["project_slug"]
    save_outline(project_slug, final_titles)
    try:
        export_docx(project_slug)
    except FileNotFoundError:
        pass
    return {
        "last_observation": f"大纲已写入（{len(final_titles)} 节）",
        "pending_confirmation": None,
    }


def draft_or_revise(state: GraphState) -> dict:
    """起草或修订：直接落盘，不 interrupt。"""
    action = state.get("chosen_action", "draft_section")
    action_input = state.get("action_input") or {}
    section_id = action_input.get("section_id") or state.get("cursor") or ""
    project_slug = state["project_slug"]

    if not section_id:
        return {"last_observation": "缺少 section_id，无法写节"}

    try:
        if action == "revise_section":
            content = load_section(project_slug, section_id)
            feedback = action_input.get("feedback", "")
            # TODO: 调用模型按反馈修订；骨架先标注反馈
            content = (content or "").rstrip()
            if feedback:
                content = (
                    f"{content}\n\n（修订意图: {feedback}）\n"
                    if content
                    else f"（修订意图: {feedback}）\n"
                )
            gist = feedback[:20] if feedback else None
            save_section(project_slug, section_id, content, status="draft", gist=gist)
            append_decision(
                project_slug,
                Decision(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    section_id=section_id,
                    feedback=feedback[:30] if feedback else "修订",
                ),
            )
            update_profile(feedback or "修订")
            obs = f"已修订节: {section_id}"
        else:
            # TODO: 根据 sources 摘录调用模型生成正文
            content = "（草稿占位：待根据摘录生成）\n"
            save_section(project_slug, section_id, content, status="draft", gist="草稿占位")
            obs = f"已起草节: {section_id}"
    except KeyError:
        return {"last_observation": f"未知节 id: {section_id}"}

    try:
        export_docx(project_slug)
    except FileNotFoundError:
        pass

    return {"last_observation": obs}


def accept_section(state: GraphState) -> dict:
    """把指定节标为 accepted，并尽量把 cursor 移到下一节。"""
    action_input = state.get("action_input") or {}
    section_id = action_input.get("section_id") or state.get("cursor") or ""
    project_slug = state["project_slug"]
    if not section_id:
        return {"last_observation": "缺少 section_id，无法接受"}

    try:
        update_section_meta(project_slug, section_id, status="accepted")
    except KeyError:
        return {"last_observation": f"未知节 id: {section_id}"}

    meta = load_meta(project_slug)
    sections = meta.get("sections") or []
    next_cursor = section_id
    for index, item in enumerate(sections):
        if item.get("id") == section_id and index + 1 < len(sections):
            next_cursor = sections[index + 1]["id"]
            break
    meta["cursor"] = next_cursor
    from deepdocument.document.store import save_meta

    save_meta(project_slug, meta)

    try:
        export_docx(project_slug)
    except FileNotFoundError:
        pass

    return {
        "cursor": next_cursor,
        "last_observation": f"已接受节: {section_id}，cursor={next_cursor}",
    }


def record_decision(state: GraphState) -> dict:
    """只记反馈、不改正文；并更新画像。"""
    action_input = state.get("action_input") or {}
    text = action_input.get("text") or state.get("user_input") or ""
    section_id = action_input.get("section_id") or state.get("cursor")
    project_slug = state["project_slug"]

    append_decision(
        project_slug,
        Decision(
            timestamp=datetime.now(timezone.utc).isoformat(),
            section_id=section_id,
            feedback=text[:30],
        ),
    )
    update_profile(text)
    return {"last_observation": "反馈已记录"}


def propose_skill(state: GraphState) -> dict:
    """起草 skill；interrupt 确认后写入 skills_user/。"""
    action_input = state.get("action_input") or {}
    name = action_input.get("name") or "new-skill"
    description = action_input.get("description") or ""
    body = action_input.get("body") or description
    skill_markdown = f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n"

    card = {
        "card_type": "skill",
        "name": name,
        "markdown": skill_markdown,
    }
    decision = interrupt(card)
    if not isinstance(decision, dict) or not decision.get("accept"):
        return {
            "last_observation": "用户拒绝 skill 草稿",
            "pending_confirmation": None,
        }

    final_md = decision.get("markdown") or skill_markdown
    final_name = decision.get("name") or name
    from pathlib import Path

    skill_dir = Path("skills_user") / final_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(final_md, encoding="utf-8")
    return {
        "last_observation": f"已保存 skill: {final_name}",
        "pending_confirmation": None,
    }
