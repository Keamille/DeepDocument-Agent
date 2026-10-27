"""
图构建器

组装 LangGraph，并按项目持有 SQLite 检查点连接。

SqliteSaver.from_conn_string() 返回的是上下文管理器，不能直接交给
compile()，所以这里自己持有 sqlite3 连接，再交给 SqliteSaver 构造。
连接开了 check_same_thread=False，因为 pywebview 的 js_api 在另一个线程调用。
"""

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from deepdocument.graph import nodes
from deepdocument.graph.state import GraphState

# 每个项目一份连接和一个 saver，进程内复用
_connections: dict[str, sqlite3.Connection] = {}
_savers: dict[str, SqliteSaver] = {}


def build_workflow() -> StateGraph:
    """
    组装未编译的图

    拆成两步，是为了让调用方按项目传入 checkpointer。

    Returns:
        未编译的 StateGraph
    """
    workflow = StateGraph(GraphState)

    workflow.add_node("load_context", nodes.load_context)
    workflow.add_node("choose_action", nodes.choose_action)
    workflow.add_node("ask_user", nodes.ask_user)
    workflow.add_node("search_literature", nodes.search_literature)
    workflow.add_node("fetch_source", nodes.fetch_source)
    workflow.add_node("update_outline", nodes.update_outline)
    workflow.add_node("draft_or_revise", nodes.draft_or_revise)
    workflow.add_node("propose_skill", nodes.propose_skill)
    workflow.add_node("record_feedback", nodes.record_feedback)

    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "choose_action")

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

    for action_node in [
        "ask_user",
        "search_literature",
        "fetch_source",
        "update_outline",
        "draft_or_revise",
        "propose_skill",
    ]:
        workflow.add_edge(action_node, "record_feedback")

    workflow.add_edge("record_feedback", END)

    return workflow


def build_graph(project_slug: str):
    """
    编译某个项目的图

    Args:
        project_slug: 项目 slug，同时作为 thread_id

    Returns:
        编译后的图
    """
    return build_workflow().compile(
        checkpointer=get_checkpointer(project_slug),
        interrupt_before=[
            "update_outline",
            "draft_or_revise",
            "propose_skill",
        ],
    )


def get_checkpointer(project_slug: str) -> SqliteSaver:
    """
    获取项目的检查点存储

    每个项目一个 projects/<slug>/checkpoints.sqlite，连接在进程内复用。

    Args:
        project_slug: 项目 slug

    Returns:
        SqliteSaver 实例
    """
    if project_slug in _savers:
        return _savers[project_slug]

    db_path = Path("projects") / project_slug / "checkpoints.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    saver = SqliteSaver(conn)

    _connections[project_slug] = conn
    _savers[project_slug] = saver
    return saver


def close_checkpointers():
    """
    关闭所有检查点连接

    退出窗口时调用，避免 sqlite 文件残留 -wal 或连接未释放。
    """
    for project_slug, conn in list(_connections.items()):
        conn.close()
        _connections.pop(project_slug, None)
        _savers.pop(project_slug, None)
