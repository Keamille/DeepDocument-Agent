"""
图状态定义

与 docs/architecture.md、docs/agent-loop.md 对齐。
提示与观察分开：prompt_text 是本轮现装的系统提示，last_observation 是上一轮/本轮观察。
"""

from typing import Literal, NotRequired, TypedDict


class GraphState(TypedDict):
    """LangGraph 状态"""

    project_slug: str
    cursor: str
    last_observation: str

    pending_confirmation: NotRequired[dict | None]
    file_snapshots: NotRequired[dict[str, str]]
    user_input: NotRequired[str]
    prompt_text: NotRequired[str]
    chosen_action: NotRequired[str]
    action_input: NotRequired[dict]


class ConfirmationCard(TypedDict):
    """确认卡 payload（也可经 interrupt() 传出）"""

    card_type: Literal["question", "outline", "literature", "skill"]
    question: NotRequired[str]
    diff: NotRequired[str]
    titles: NotRequired[list[str]]
    items: NotRequired[list[dict]]
    markdown: NotRequired[str]
    name: NotRequired[str]
