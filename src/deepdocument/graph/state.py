"""
图状态定义
"""

from typing import TypedDict, Literal, NotRequired


class GraphState(TypedDict):
    """
    LangGraph 状态

    按 docs/architecture.md 的定义
    """

    # 项目标识
    project_slug: str

    # 当前处理的节 id
    cursor: str

    # 待确认的动作（interrupt 时设置）
    pending_confirmation: NotRequired[dict | None]

    # 文件快照（用于检测外部修改）
    file_snapshots: NotRequired[dict[str, dict]]

    # 上一轮的观察结果
    last_observation: str

    # 用户输入
    user_input: NotRequired[str]

    # 模型选择的动作
    chosen_action: NotRequired[str]

    # 动作参数
    action_input: NotRequired[dict]


class ConfirmationCard(TypedDict):
    """确认卡数据"""

    card_type: Literal["outline", "literature", "section", "skill"]
    diff: NotRequired[str]  # outline 的 diff
    items: NotRequired[list[dict]]  # literature 的列表
    markdown: NotRequired[str]  # section 或 skill 的内容
