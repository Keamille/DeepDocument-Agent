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
    load_brief,
    load_meta,
    load_section,
    load_source,
    save_outline,
    save_section,
    update_section_meta,
)
from deepdocument.graph.state import GraphState
from deepdocument.literature.fetch import fetch_source as fetch_literature_source
from deepdocument.literature.search import search_literature as search_openalex
from deepdocument.llm.client import LLMError, chat, chat_for_action
from deepdocument.memory.budget import (
    EXCERPT_PER_SOURCE,
    MAX_EXCERPT_SOURCES,
    build_prompt,
    truncate_to_budget,
)
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
            return _run_revise_section(project_slug, section_id, action_input)
        return _run_draft_section(project_slug, section_id, action_input)
    except KeyError:
        return {"last_observation": f"未知节 id: {section_id}"}


def _run_draft_section(
    project_slug: str,
    section_id: str,
    action_input: dict,
) -> dict:
    """根据 sources 摘录调用模型起草一节并落盘。"""
    title = _section_title(project_slug, section_id)
    source_ids = list(action_input.get("source_ids") or [])[:MAX_EXCERPT_SOURCES]
    excerpts = _collect_excerpts(project_slug, source_ids)
    if not excerpts:
        return {
            "last_observation": (
                f"无法起草 {section_id}：需要 1～{MAX_EXCERPT_SOURCES} 篇有效摘录"
                "（先确认文献并抓取 sources）"
            ),
        }

    brief = load_brief(project_slug)
    try:
        drafted = _draft_section_text(
            title=title,
            excerpts=excerpts,
            kind=brief.kind if brief else "report",
            audience=brief.audience if brief else "",
            constraints=list(brief.constraints) if brief else [],
        )
    except LLMError as exc:
        return {"last_observation": f"起草失败（模型错误）: {exc}"}

    drafted = (drafted or "").strip()
    if not drafted:
        return {"last_observation": f"起草失败: 模型未返回正文（{section_id}）"}

    gist = _gist_from_text(drafted)
    save_section(project_slug, section_id, drafted + "\n", status="draft", gist=gist)

    try:
        export_docx(project_slug)
    except FileNotFoundError:
        pass

    return {"last_observation": f"已起草节: {section_id}"}


def _run_revise_section(
    project_slug: str,
    section_id: str,
    action_input: dict,
) -> dict:
    """按反馈调用模型修订一节，落盘后记决策与画像。"""
    feedback = (action_input.get("feedback") or "").strip()
    if not feedback:
        return {"last_observation": "缺少 feedback，无法修订"}

    current = load_section(project_slug, section_id)
    title = _section_title(project_slug, section_id)
    source_ids = list(action_input.get("source_ids") or [])[:MAX_EXCERPT_SOURCES]
    excerpts = _collect_excerpts(project_slug, source_ids)

    try:
        revised = _revise_section_text(
            title=title,
            content=current,
            feedback=feedback,
            excerpts=excerpts,
        )
    except LLMError as exc:
        return {"last_observation": f"修订失败（模型错误）: {exc}"}

    revised = (revised or "").strip()
    if not revised:
        return {"last_observation": f"修订失败: 模型未返回正文（{section_id}）"}

    gist = feedback[:20]
    save_section(project_slug, section_id, revised + "\n", status="draft", gist=gist)
    append_decision(
        project_slug,
        Decision(
            timestamp=datetime.now(timezone.utc).isoformat(),
            section_id=section_id,
            feedback=feedback[:30],
        ),
    )
    update_profile(feedback)

    try:
        export_docx(project_slug)
    except FileNotFoundError:
        pass

    return {"last_observation": f"已修订节: {section_id}"}


def _section_title(project_slug: str, section_id: str) -> str:
    for item in load_meta(project_slug).get("sections") or []:
        if item.get("id") == section_id:
            return str(item.get("title") or section_id)
    return section_id


def _collect_excerpts(project_slug: str, source_ids: list[str]) -> list[tuple[str, str]]:
    """装入最多 3 篇摘录；(id, excerpt_text)。"""
    collected: list[tuple[str, str]] = []
    for source_id in source_ids:
        source = load_source(project_slug, source_id)
        if source is None or not source.excerpt.strip():
            continue
        excerpt = truncate_to_budget(source.excerpt.strip(), EXCERPT_PER_SOURCE)
        collected.append((source_id, excerpt))
        if len(collected) >= MAX_EXCERPT_SOURCES:
            break
    return collected


def _format_excerpt_block(excerpts: list[tuple[str, str]]) -> str:
    if not excerpts:
        return "（本轮未提供摘录；不要新增无依据的断言。）"
    return "\n\n".join(f"### {sid}\n\n{text}" for sid, text in excerpts)


def _gist_from_text(text: str, limit: int = 20) -> str:
    for line in text.splitlines():
        cleaned = line.strip().lstrip("#").strip()
        if cleaned:
            return cleaned[:limit]
    return text.strip()[:limit]


def _draft_section_text(
    *,
    title: str,
    excerpts: list[tuple[str, str]],
    kind: str,
    audience: str,
    constraints: list[str],
) -> str:
    """调用 chat() 根据摘录起草一节；只返回正文。"""
    constraint_line = "、".join(constraints) if constraints else "无"
    messages = [
        {
            "role": "system",
            "content": (
                "你是文稿起草助手。只根据提供的文献摘录写这一节的 Markdown 正文。"
                "每一段主张都要能对上至少一篇摘录；没有摘录支撑的断言不要写。"
                "不要编造文献或页码。不要输出节标题、前言或写作说明，只输出正文。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"文稿种类: {kind}\n"
                f"读者: {audience or '未指定'}\n"
                f"约束: {constraint_line}\n"
                f"节标题: {title}\n\n"
                f"相关摘录:\n{_format_excerpt_block(excerpts)}\n"
            ),
        },
    ]
    return chat(messages, temperature=0.4).strip()


def _revise_section_text(
    *,
    title: str,
    content: str,
    feedback: str,
    excerpts: list[tuple[str, str]],
) -> str:
    """调用 chat() 按反馈改写一节；只返回正文。"""
    messages = [
        {
            "role": "system",
            "content": (
                "你是文稿修订助手。只按用户反馈修改给定节的正文。"
                "保留未被指出问题的段落；不要扩写无关内容。"
                "没有摘录支撑的新断言不要写。"
                "只输出修订后的 Markdown 正文，不要前言、标题或解释。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"节标题: {title}\n\n"
                f"用户反馈:\n{feedback}\n\n"
                f"现有正文:\n{content.strip() or '（空）'}\n\n"
                f"相关摘录:\n{_format_excerpt_block(excerpts)}\n"
            ),
        },
    ]
    return chat(messages, temperature=0.3).strip()


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
