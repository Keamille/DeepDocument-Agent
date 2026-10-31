"""
提示预算管理

按 docs/memory.md 的 32k 窗口 / 16k 提示预算装入各部分内容。
"""

from __future__ import annotations

from deepdocument.document.store import (
    load_brief,
    load_decisions,
    load_literature,
    load_meta,
    load_outline,
)

# 模型上下文下限与提示总预算（见 docs/memory.md）
MIN_CONTEXT_TOKENS = 32_768
PROMPT_TOKEN_BUDGET = 16_000
MAX_OUTPUT_TOKENS = 4_096

# 各切片上限，合计必须等于 PROMPT_TOKEN_BUDGET
BUDGET = {
    "system": 1_000,
    "brief": 800,
    "outline": 400,
    "sections_gist": 800,
    "literature_cards": 800,
    "profile": 1_200,
    "decisions": 600,
    "skills": 1_200,
    "observation": 400,
    "current_section": 2_000,
    "excerpts": 6_800,  # 最多 3 篇；单篇裁剪上限见 EXCERPT_PER_SOURCE
}

EXCERPT_PER_SOURCE = 2_400
MAX_EXCERPT_SOURCES = 3
MAX_LITERATURE_CARDS = 12
MAX_SECTION_GISTS = 20
MAX_DECISIONS = 10
MAX_SKILL_BODY_TOKENS = 600

assert sum(BUDGET.values()) == PROMPT_TOKEN_BUDGET


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

    # 1. brief
    brief = load_brief(project_slug)
    if brief:
        text = (
            f"# 前言\n\n题目: {brief.title}\n种类: {brief.kind}\n"
            f"读者: {brief.audience}\n约束: {', '.join(brief.constraints)}"
        )
        sections.append(truncate_to_budget(text, BUDGET["brief"]))

    # 2. 大纲
    outline = load_outline(project_slug)
    if outline:
        text = "# 大纲\n\n" + "\n".join(f"- {title}" for title in outline)
        sections.append(truncate_to_budget(text, BUDGET["outline"]))

    # 3. 文献卡片
    literature = load_literature(project_slug, status="accepted")[:MAX_LITERATURE_CARDS]
    if literature:
        cards = []
        for lit in literature:
            source = lit.content_source or lit.evidence_type or "unknown"
            cards.append(f"{lit.id} | {lit.title} | {lit.year} | {source}")
        text = "# 文献卡片\n\n" + "\n".join(cards)
        sections.append(truncate_to_budget(text, BUDGET["literature_cards"]))

    # 4. 各节要旨
    meta = load_meta(project_slug)
    if meta.get("sections"):
        marks = {
            "empty": "·",
            "outlined": "○",
            "draft": "✎",
            "accepted": "✓",
        }
        gists = []
        for sec in meta["sections"][:MAX_SECTION_GISTS]:
            status_mark = marks.get(sec.get("status", "empty"), "?")
            gists.append(f"{status_mark} {sec['title']}: {sec.get('gist', '')}")
        extra = len(meta["sections"]) - MAX_SECTION_GISTS
        if extra > 0:
            gists.append(f"…另有 {extra} 节仅保留 id/状态，未展开要旨")
        text = "# 各节要旨\n\n" + "\n".join(gists)
        sections.append(truncate_to_budget(text, BUDGET["sections_gist"]))

    # 5. 摘录（按需装入；此处占位，由调用方或后续实现填入）
    sections.append(
        truncate_to_budget(
            f"# 摘录\n\n（按需装入，最多 {MAX_EXCERPT_SOURCES} 篇，每篇 ≤ {EXCERPT_PER_SOURCE} token）",
            BUDGET["excerpts"],
        )
    )

    # 6. 最近反馈
    decisions = load_decisions(project_slug, limit=MAX_DECISIONS)
    if decisions:
        feedback_lines = [f"- {dec.feedback[:30]}" for dec in decisions]
        text = "# 最近反馈\n\n" + "\n".join(feedback_lines)
        sections.append(truncate_to_budget(text, BUDGET["decisions"]))

    # 7. 用户画像
    # TODO: 从 user_profile.md 读取后按 BUDGET["profile"] 裁剪
    sections.append(
        truncate_to_budget("# 用户画像\n\n（从全局文件读取）", BUDGET["profile"])
    )

    # 8. Skill
    if recalled_skills:
        text = f"# Skill\n\n（已召回：{', '.join(recalled_skills)}；每份正文 ≤ {MAX_SKILL_BODY_TOKENS} token）"
        sections.append(truncate_to_budget(text, BUDGET["skills"]))

    # 9. 上一轮观察
    sections.append(
        truncate_to_budget("# Observation\n\n上一轮的结果", BUDGET["observation"])
    )

    return "\n\n".join(sections)


def estimate_tokens(text: str) -> int:
    """
    估算 token 数

    按 docs/memory.md 的规则：
    - 一个中日韩统一表意文字计 2 token
    - 连续的 ASCII 每 4 个字符计 1 token
    - 其他非 ASCII 字符每个计 2 token
    """
    cjk = 0
    other_non_ascii = 0
    ascii_chars = 0

    for ch in text:
        code = ord(ch)
        if 0x4E00 <= code <= 0x9FFF:
            cjk += 1
        elif code < 128:
            if not ch.isspace():
                ascii_chars += 1
        else:
            other_non_ascii += 1

    ascii_tokens = -(-ascii_chars // 4)
    return cjk * 2 + other_non_ascii * 2 + ascii_tokens


def truncate_to_budget(text: str, budget: int) -> str:
    """裁剪文本到预算内；超限时末尾加省略说明。"""
    if estimate_tokens(text) <= budget:
        return text

    suffix = "…（已截断，全文在文件中）"
    suffix_tokens = estimate_tokens(suffix)
    if suffix_tokens >= budget:
        # 预算极小时只保留能放下的前缀
        out = ""
        for ch in text:
            if estimate_tokens(out + ch) > budget:
                break
            out += ch
        return out

    body_budget = budget - suffix_tokens
    out = ""
    for ch in text:
        if estimate_tokens(out + ch) > body_budget:
            break
        out += ch
    return out + suffix
