"""
测试：图节点
"""

import pytest
from deepdocument.graph.state import GraphState
from deepdocument.graph import nodes


def test_route_action():
    """测试动作路由"""
    state = {"chosen_action": "ask_user"}
    assert nodes.route_action(state) == "ask_user"

    state = {"chosen_action": "draft_section"}
    assert nodes.route_action(state) == "draft_or_revise"

    state = {"chosen_action": "unknown"}
    assert nodes.route_action(state) == "ask_user"


def test_load_context():
    """测试上下文加载"""
    state = {
        "project_slug": "test-project",
        "cursor": "",
        "pending_confirmation": None,
        "last_observation": "",
        "file_snapshots": {},
        "user_input": "测试",
    }

    result = nodes.load_context(state)
    assert "last_observation" in result
