"""
测试：图节点路由与装提示
"""

from deepdocument.document.model import Brief
from deepdocument.document import store
from deepdocument.graph import nodes


def test_route_action_whitelist():
    assert nodes.route_action({"chosen_action": "ask_user"}) == "ask_user"
    assert nodes.route_action({"chosen_action": "search_literature"}) == "search_literature"
    assert nodes.route_action({"chosen_action": "update_outline"}) == "update_outline"
    assert nodes.route_action({"chosen_action": "draft_section"}) == "draft_or_revise"
    assert nodes.route_action({"chosen_action": "revise_section"}) == "draft_or_revise"
    assert nodes.route_action({"chosen_action": "accept_section"}) == "accept_section"
    assert nodes.route_action({"chosen_action": "record_decision"}) == "record_decision"
    assert nodes.route_action({"chosen_action": "propose_skill"}) == "propose_skill"
    assert nodes.route_action({"chosen_action": "fetch_source"}) == "ask_user"
    assert nodes.route_action({"chosen_action": "unknown"}) == "ask_user"


def test_load_context_sets_prompt_text(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(store, "PROJECTS_ROOT", tmp_path / "projects")
    store.create_project(
        "demo",
        Brief(title="测试文稿", kind="summary", audience="老师"),
    )

    state = {
        "project_slug": "demo",
        "cursor": "",
        "last_observation": "上一轮完成大纲",
        "user_input": "继续",
    }
    result = nodes.load_context(state)
    assert "prompt_text" in result
    assert "上一轮完成大纲" in result["prompt_text"]
    assert "last_observation" not in result
