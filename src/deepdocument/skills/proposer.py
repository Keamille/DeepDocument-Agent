"""
Skill 提议器：根据重复反馈起草 SKILL.md 文本（不直接写盘）。
"""

from __future__ import annotations

import re


def propose_skill(
    repeated_feedback: list[str],
    *,
    name: str | None = None,
    description: str | None = None,
) -> str:
    """
    生成 skill 草稿 Markdown（含 frontmatter）。

    真实落盘由 graph 的 propose_skill 节点在用户确认后完成。
    """
    samples = [f.strip() for f in repeated_feedback if f and f.strip()]
    if not samples:
        samples = ["（待补充的重复反馈）"]

    slug = name or _slug_from_text(samples[0])
    desc = description or f"当出现与「{samples[0][:40]}」类似的反馈时使用"

    bullets = "\n".join(f"- {s}" for s in samples[:5])
    return (
        f"---\nname: {slug}\ndescription: {desc}\n---\n\n"
        f"# 触发场景\n\n以下反馈重复出现：\n\n{bullets}\n\n"
        f"# 做法\n\n1. 确认用户仍要同一类改法\n"
        f"2. 只改点名的节，不重写全文\n"
        f"3. 把该偏好记入画像，避免下轮再犯\n\n"
        f"# 示例\n\n用户：{samples[0]}\n助手：按该偏好修订对应节并记录决策。\n"
    )


def _slug_from_text(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", text).strip("-").lower()
    slug = re.sub(r"[\u4e00-\u9fff]+", "pref", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return (slug or "user-pref")[:40]
