"""
图构建器

组装 LangGraph，并按项目持有 SQLite 检查点连接。

人机确认用节点内的 interrupt()，不靠 interrupt_before 猜暂停点。
SqliteSaver.from_conn_string() 返回的是上下文管理器，不能直接交给
compile()，所以这里自己持有 sqlite3 连接。
连接开了 check_same_thread=False，因为 pywebview 的 js_api 在另一线程调用。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from deepdocument.graph import nodes
from deepdocument.graph.state import GraphState

_connections: dict[str, sqlite3.Connection] = {}
_savers: dict[str, SqliteSaver] = {}


def build_workflow() -> StateGraph:
    """组装未编译的图：load → choose → 单一动作 → END。"""
    workflow = StateGraph(GraphState)

    workflow.add_node("load_context", nodes.load_context)
    workflow.add_node("choose_action", nodes.choose_action)
    workflow.add_node("ask_user", nodes.ask_user)
    workflow.add_node("search_literature", nodes.search_literature)
    workflow.add_node("update_outline", nodes.update_outline)
    workflow.add_node("draft_or_revise", nodes.draft_or_revise)
    workflow.add_node("accept_section", nodes.accept_section)
    workflow.add_node("record_decision", nodes.record_decision)
    workflow.add_node("propose_skill", nodes.propose_skill)

    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "choose_action")
    workflow.add_conditional_edges(
        "choose_action",
        nodes.route_action,
        {
            "ask_user": "ask_user",
            "search_literature": "search_literature",
            "update_outline": "update_outline",
            "draft_or_revise": "draft_or_revise",
            "accept_section": "accept_section",
            "record_decision": "record_decision",
            "propose_skill": "propose_skill",
        },
    )

    for name in (
        "ask_user",
        "search_literature",
        "update_outline",
        "draft_or_revise",
        "accept_section",
        "record_decision",
        "propose_skill",
    ):
        workflow.add_edge(name, END)

    return workflow


def build_graph(project_slug: str):
    """编译某个项目的图；thread_id 由调用方用 slug 配置。"""
    return build_workflow().compile(checkpointer=get_checkpointer(project_slug))


def get_checkpointer(project_slug: str) -> SqliteSaver:
    """每个项目一个 projects/<slug>/checkpoints.sqlite，进程内复用连接。"""
    if project_slug in _savers:
        return _savers[project_slug]

    db_path = Path("projects") / project_slug / "checkpoints.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    saver = SqliteSaver(conn)

    _connections[project_slug] = conn
    _savers[project_slug] = saver
    return saver


def close_checkpointers() -> None:
    """退出窗口时关闭全部检查点连接。"""
    for project_slug, conn in list(_connections.items()):
        conn.close()
        _connections.pop(project_slug, None)
        _savers.pop(project_slug, None)
