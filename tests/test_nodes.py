"""
测试：图节点路由与装提示
"""

from deepdocument.document.model import Brief, Source
from deepdocument.document import store
from deepdocument.graph import nodes
from deepdocument.llm.client import LLMError
from deepdocument.memory import profile as profile_mod


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


def test_draft_section_calls_model_and_saves(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(store, "PROJECTS_ROOT", tmp_path / "projects")

    store.create_project(
        "demo",
        Brief(title="测试文稿", kind="summary", audience="老师", constraints=["中文"]),
    )
    store.save_outline("demo", ["总结"])
    section_id = store.load_meta("demo")["sections"][0]["id"]
    store.save_source(
        "demo",
        Source(
            id="W1",
            content_source="abstract",
            card="相关",
            excerpt="检索增强生成把外部知识接入语言模型。",
        ),
    )

    captured: dict = {}

    def fake_chat(messages, temperature=0.7, **_kwargs):
        captured["messages"] = messages
        captured["temperature"] = temperature
        return "RAG 将外部知识接入语言模型，便于企业知识库问答。"

    monkeypatch.setattr(nodes, "chat", fake_chat)
    monkeypatch.setattr(nodes, "export_docx", lambda *_a, **_k: tmp_path / "export.docx")

    result = nodes.draft_or_revise(
        {
            "project_slug": "demo",
            "cursor": section_id,
            "last_observation": "",
            "chosen_action": "draft_section",
            "action_input": {"section_id": section_id, "source_ids": ["W1"]},
        }
    )

    assert result["last_observation"] == f"已起草节: {section_id}"
    body = store.load_section("demo", section_id)
    assert "RAG" in body
    assert "草稿占位" not in body
    assert captured["temperature"] == 0.4
    assert "检索增强生成" in captured["messages"][1]["content"]
    meta = store.load_meta("demo")["sections"][0]
    assert meta["status"] == "draft"
    assert meta["gist"]


def test_draft_section_requires_excerpts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(store, "PROJECTS_ROOT", tmp_path / "projects")
    store.create_project(
        "demo",
        Brief(title="测试文稿", kind="summary", audience="老师"),
    )
    store.save_outline("demo", ["总结"])
    section_id = store.load_meta("demo")["sections"][0]["id"]

    result = nodes.draft_or_revise(
        {
            "project_slug": "demo",
            "cursor": section_id,
            "last_observation": "",
            "chosen_action": "draft_section",
            "action_input": {"section_id": section_id, "source_ids": []},
        }
    )
    assert "无法起草" in result["last_observation"]
    assert store.load_section("demo", section_id) == ""


def test_revise_section_calls_model_and_saves(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(store, "PROJECTS_ROOT", tmp_path / "projects")
    monkeypatch.setattr(profile_mod, "PROFILE_PATH", tmp_path / "user_profile.md")

    store.create_project(
        "demo",
        Brief(title="测试文稿", kind="summary", audience="老师"),
    )
    store.save_outline("demo", ["总结"])
    section_id = store.load_meta("demo")["sections"][0]["id"]
    store.save_section("demo", section_id, "原有很长的引言段落。\n")
    store.save_source(
        "demo",
        Source(
            id="W1",
            content_source="abstract",
            card="相关",
            excerpt="RAG 将检索与生成结合。",
        ),
    )

    captured: dict = {}

    def fake_chat(messages, temperature=0.7, **_kwargs):
        captured["messages"] = messages
        captured["temperature"] = temperature
        return "缩短后的引言。依据摘录说明 RAG。"

    monkeypatch.setattr(nodes, "chat", fake_chat)
    monkeypatch.setattr(nodes, "export_docx", lambda *_a, **_k: tmp_path / "export.docx")

    state = {
        "project_slug": "demo",
        "cursor": section_id,
        "last_observation": "",
        "chosen_action": "revise_section",
        "action_input": {
            "section_id": section_id,
            "feedback": "引言太长，缩短到两百字",
            "source_ids": ["W1"],
        },
    }
    result = nodes.draft_or_revise(state)

    assert result["last_observation"] == f"已修订节: {section_id}"
    assert "缩短后的引言" in store.load_section("demo", section_id)
    assert "修订意图" not in store.load_section("demo", section_id)
    assert captured["temperature"] == 0.3
    user_msg = captured["messages"][1]["content"]
    assert "引言太长" in user_msg
    assert "RAG 将检索与生成结合" in user_msg
    decisions = store.load_decisions("demo")
    assert decisions and "引言太长" in decisions[-1].feedback


def test_revise_section_model_error_keeps_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(store, "PROJECTS_ROOT", tmp_path / "projects")

    store.create_project(
        "demo",
        Brief(title="测试文稿", kind="summary", audience="老师"),
    )
    store.save_outline("demo", ["总结"])
    section_id = store.load_meta("demo")["sections"][0]["id"]
    store.save_section("demo", section_id, "原文不动。\n")

    def boom(*_a, **_k):
        raise LLMError("超时")

    monkeypatch.setattr(nodes, "chat", boom)

    result = nodes.draft_or_revise(
        {
            "project_slug": "demo",
            "cursor": section_id,
            "last_observation": "",
            "chosen_action": "revise_section",
            "action_input": {
                "section_id": section_id,
                "feedback": "改短一点",
            },
        }
    )
    assert "修订失败" in result["last_observation"]
    assert store.load_section("demo", section_id) == "原文不动。\n"
