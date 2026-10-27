"""
提示预算管理

按 docs/memory.md 的预算装入各部分内容。
"""

from deepdocument.document.store import (
    load_brief,
    load_outline,
    load_meta,
    load_section,
    load_literature,
    load_decisions,
)


# 预算分配（单位：token）
BUDGET = {
    "brief": 300,
    "outline": 200,
    "literature_cards": 400,
    "sections_gist": 500,
    "excerpts": 3600,  # 最多 3 篇，每篇 1200
    "decisions": 500,
    "profile": 400,
    "skills": 3000,  # 最多 2 个
    "observation": 200,
}


def build_prompt(project_slug: str, recalled_skills: list[str]) -> str:
    """
    组装本轮提示

    Args:
        project_slug: 项目 slug
        recalled_skills: 召回的 skill 名称列表（最多 2 个）

    Returns:
        完整提示文本
    """
    sections = []

    # 1. 前言（300 token）
    brief = load_brief(project_slug)
    if brief:
        sections.append(f"# 前言\n\n题目: {brief.title}\n种类: {brief.kind}\n")

    # 2. 大纲（200 token）
    outline = load_outline(project_slug)
    if outline:
        sections.append(f"# 大纲\n\n" + "\n".join(f"- {title}" for title in outline))

    # 3. 文献卡片（400 token，约 7 条）
    literature = load_literature(project_slug)
    accepted = [lit for lit in literature if lit.status == "accepted"][:7]
    if accepted:
        cards = []
        for lit in accepted:
            card = f"{lit.id} | {lit.title} | {lit.year} | {lit.evidence_type or 'related'}"
            cards.append(card)
        sections.append(f"# 文献卡片\n\n" + "\n".join(cards))

    # 4. 各节要旨（500 token）
    meta = load_meta(project_slug)
    if meta.get("sections"):
        gists = []
        for sec in meta["sections"]:
            status_mark = {"pending": "⏳", "draft": "📝", "accepted": "✅"}[sec["status"]]
            gists.append(f"{status_mark} {sec['title']}: {sec.get('gist', '')}")
        sections.append(f"# 各节要旨\n\n" + "\n".join(gists))

    # 5. 摘录（3600 token，最多 3 篇）
    # TODO: 根据当前动作选择相关的摘录
    sections.append(f"# 摘录\n\n（按需装入，最多 3 篇）")

    # 6. 最近反馈（500 token，最多 5 条）
    decisions = load_decisions(project_slug, limit=5)
    if decisions:
        feedback_lines = []
        for dec in decisions:
            feedback_lines.append(f"- {dec.feedback}")
        sections.append(f"# 最近反馈\n\n" + "\n".join(feedback_lines))

    # 7. 用户画像（400 token）
    # TODO: 从 user_profile.md 读取
    sections.append(f"# 用户画像\n\n（从全局文件读取）")

    # 8. Skill（最多 2 个，3000 token）
    if recalled_skills:
        sections.append(f"# Skill\n\n（已召回：{', '.join(recalled_skills)}）")

    # 9. 上一轮观察（200 token）
    sections.append(f"# Observation\n\n上一轮的结果")

    return "\n\n".join(sections)


def estimate_tokens(text: str) -> int:
    """
    估算 token 数

    按 docs/memory.md 的规则：
    - 一个中日韩统一表意文字计 2 token
    - 连续的 ASCII 每 4 个字符计 1 token
    - 其他非 ASCII 字符每个计 2 token

    Args:
        text: 文本

    Returns:
        估算的 token 数（向上取整）
    """
    cjk = 0
    other_non_ascii = 0
    ascii_chars = 0

    for ch in text:
        code = ord(ch)
        if 0x4E00 <= code <= 0x9FFF:  # 中日韩统一表意文字
            cjk += 1
        elif code < 128:
            if not ch.isspace():
                ascii_chars += 1
        else:
            other_non_ascii += 1

    # 连续的 ASCII 每 4 个字符计 1 token，不足 4 个也向上取整
    ascii_tokens = -(-ascii_chars // 4)  # 向上取整
    return cjk * 2 + other_non_ascii * 2 + ascii_tokens


def truncate_to_budget(text: str, budget: int) -> str:
    """
    裁剪文本到预算内

    Args:
        text: 原文本
        budget: token 预算

    Returns:
        裁剪后的文本
    """
    if estimate_tokens(text) <= budget:
        return text

    # 简单裁剪：按字符比例
    ratio = budget / estimate_tokens(text)
    target_len = int(len(text) * ratio * 0.9)  # 留 10% 余量
    return text[:target_len] + "..."
