"""
图构建器

组装 LangGraph，配置 interrupt。
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from deepdocument.graph.state import GraphState
from deepdocument.graph import nodes


def build_graph():
    """
    构建 LangGraph

    Returns:
        编译后的图
    """
    # 创建图
    workflow = StateGraph(GraphState)

    # 添加节点
    workflow.add_node("load_context", nodes.load_context)
    workflow.add_node("choose_action", nodes.choose_action)
    workflow.add_node("ask_user", nodes.ask_user)
    workflow.add_node("search_literature", nodes.search_literature)
    workflow.add_node("fetch_source", nodes.fetch_source)
    workflow.add_node("update_outline", nodes.update_outline)
    workflow.add_node("draft_or_revise", nodes.draft_or_revise)
    workflow.add_node("propose_skill", nodes.propose_skill)
    workflow.add_node("record_feedback", nodes.record_feedback)

    # 设置入口
    workflow.set_entry_point("load_context")

    # 添加边
    workflow.add_edge("load_context", "choose_action")

    # 条件路由
    workflow.add_conditional_edges(
        "choose_action",
        nodes.route_action,
        {
            "ask_user": "ask_user",
            "search_literature": "search_literature",
            "fetch_source": "fetch_source",
            "update_outline": "update_outline",
            "draft_or_revise": "draft_or_revise",
            "propose_skill": "propose_skill",
        },
    )

    # 所有动作节点都回到记录反馈
    for action_node in [
        "ask_user",
        "search_literature",
        "fetch_source",
        "update_outline",
        "draft_or_revise",
        "propose_skill",
    ]:
        workflow.add_edge(action_node, "record_feedback")

    # 记录反馈后结束
    workflow.add_edge("record_feedback", END)

    # 编译（带 checkpointer）
    checkpointer = get_checkpointer()
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=[
            "update_outline",
            "draft_or_revise",
            "propose_skill",
        ],
    )


def get_checkpointer():
    """
    获取 checkpointer

    使用 SQLite 存储检查点

    Returns:
        SqliteSaver 实例
    """
    from pathlib import Path

    db_path = Path("checkpoints.db")
    return SqliteSaver.from_conn_string(str(db_path))
