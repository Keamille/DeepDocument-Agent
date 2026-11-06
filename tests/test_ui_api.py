"""窗口 API：list_projects / load_project / confirm_action"""

from pathlib import Path
from typing import TypedDict

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from deepdocument.document.model import Brief, Literature, Source
from deepdocument.document import store
from deepdocument.memory import profile as profile_mod
from deepdocument.ui.api import WindowAPI


class _ConfirmState(TypedDict, total=False):
    last_observation: str
    project_slug: str
    cursor: str
    user_input: str


def _build_confirm_graph(slug: str):
    """测试用小图：interrupt 一次大纲卡，resume 后写 observation。"""

    def propose(state: _ConfirmState) -> dict:
        decision = interrupt(
            {"card_type": "outline", "diff": "+ 总结", "titles": ["总结"]}
        )
        if isinstance(decision, dict) and decision.get("accept"):
            titles = decision.get("titles") or ["总结"]
            return {"last_observation": f"大纲已写入（{len(titles)} 节）"}
        return {"last_observation": "用户拒绝大纲提议"}

    workflow = StateGraph(_ConfirmState)
    workflow.add_node("propose", propose)
    workflow.add_edge(START, "propose")
    workflow.add_edge("propose", END)
    return workflow.compile(checkpointer=MemorySaver())


def _build_message_graph(slug: str):
    """按用户输入决定：含「大纲」则 interrupt，否则直接结束。"""

    def step(state: _ConfirmState) -> dict:
        text = state.get("user_input") or ""
        if "大纲" in text:
            decision = interrupt(
                {"card_type": "outline", "diff": "+ 总结", "titles": ["总结"]}
            )
            if isinstance(decision, dict) and decision.get("accept"):
                return {"last_observation": "大纲已写入（1 节）"}
            return {"last_observation": "用户拒绝大纲提议"}
        if "提问" in text:
            answer = interrupt({"card_type": "question", "question": "题目是什么？"})
            reply = ""
            if isinstance(answer, dict):
                reply = str(answer.get("text") or "")
            return {"last_observation": f"用户回答: {reply}"}
        return {"last_observation": f"收到: {text}"}

    workflow = StateGraph(_ConfirmState)
    workflow.add_node("step", step)
    workflow.add_edge(START, "step")
    workflow.add_edge("step", END)
    return workflow.compile(checkpointer=MemorySaver())


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(store, "PROJECTS_ROOT", tmp_path / "projects")
    monkeypatch.setattr(profile_mod, "PROFILE_PATH", tmp_path / "user_profile.md")
    return WindowAPI(build_graph_fn=lambda slug: f"graph:{slug}")


@pytest.fixture
def confirm_api(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(store, "PROJECTS_ROOT", tmp_path / "projects")
    monkeypatch.setattr(profile_mod, "PROFILE_PATH", tmp_path / "user_profile.md")
    store.create_project(
        "demo",
        Brief(title="演示", kind="summary", audience="老师"),
    )
    return WindowAPI(build_graph_fn=_build_confirm_graph)


def test_list_projects_reads_brief_title(api, tmp_path):
    store.create_project(
        "alpha",
        Brief(title="阿尔法文稿", kind="summary", audience="老师"),
    )
    store.create_project(
        "beta",
        Brief(title="贝塔报告", kind="report", audience=""),
    )
    (tmp_path / "projects" / ".gitkeep").write_text("", encoding="utf-8")

    projects = api.list_projects()
    assert [p["slug"] for p in projects] == ["alpha", "beta"]
    assert projects[0]["title"] == "阿尔法文稿"
    assert projects[0]["kind"] == "summary"
    assert projects[1]["title"] == "贝塔报告"


def test_list_projects_empty(api):
    assert api.list_projects() == []


def test_load_project_payload(api):
    store.create_project(
        "demo",
        Brief(title="演示", kind="summary", audience="老师", constraints=["中文"]),
    )
    store.save_outline("demo", ["总结", "局限"])
    meta = store.load_meta("demo")
    s0 = meta["sections"][0]["id"]
    store.save_section("demo", s0, "结论一段。\n", status="draft", gist="按结论归类")
    store.save_literature(
        "demo",
        [
            Literature(
                id="W1",
                title="RAG Paper",
                authors=["Alice"],
                year=2020,
                status="accepted",
                content_source="abstract",
            ),
            Literature(
                id="W2",
                title="Rejected",
                authors=["Bob"],
                year=2021,
                status="rejected",
            ),
        ],
    )
    store.save_source(
        "demo",
        Source(id="W1", content_source="abstract", card="c", excerpt="摘录"),
    )
    profile_mod.update_profile("按结论归类，不要逐篇罗列")

    data = api.load_project("demo")
    assert data["slug"] == "demo"
    assert data["title"] == "演示"
    assert data["outline"] == ["总结", "局限"]
    assert len(data["sections"]) == 2
    assert data["sections"][0]["id"] == s0
    assert data["sections"][0]["status"] == "draft"
    assert "结论一段" in data["sections"][0]["content"]
    assert len(data["literature"]) == 1
    assert data["literature"][0]["id"] == "W1"
    assert data["literature"][0]["content_source"] == "abstract"
    assert "结论" in data["profile"]
    assert api.current_project == "demo"
    assert api._graph == "graph:demo"


def test_load_project_missing_raises(api):
    with pytest.raises(FileNotFoundError):
        api.load_project("nope")


def test_confirm_action_without_pending(api):
    result = api.confirm_action(True)
    assert result["type"] == "message"
    assert "没有待确认" in result["content"]


def test_confirm_action_accept_resumes_graph(confirm_api):
    api = confirm_api
    api._ensure_graph("demo")
    paused = api._graph.invoke(
        {"project_slug": "demo", "last_observation": ""},
        api._thread_config(),
    )
    card = paused["__interrupt__"][0].value
    api.pending_confirmation = card

    result = api.confirm_action(True)
    assert result["type"] == "update"
    assert "大纲已写入" in result["content"]
    assert api.pending_confirmation is None


def test_confirm_action_reject(confirm_api):
    api = confirm_api
    api._ensure_graph("demo")
    paused = api._graph.invoke(
        {"project_slug": "demo", "last_observation": ""},
        api._thread_config(),
    )
    api.pending_confirmation = paused["__interrupt__"][0].value

    result = api.confirm_action(False)
    assert result["type"] == "update"
    assert "拒绝" in result["content"]


def test_build_resume_payload_literature_defaults():
    api = WindowAPI(build_graph_fn=lambda slug: None)
    api.pending_confirmation = {
        "card_type": "literature",
        "items": [
            {"id": "W1", "available": True},
            {"id": "W2", "available": False},
            {"id": "W3", "available": True},
        ],
    }
    resume = api._build_resume_payload(True, None)
    assert resume["accept"] is True
    assert resume["selected_ids"] == ["W1", "W3"]

    resume_custom = api._build_resume_payload(True, {"selected_ids": ["W2"]})
    assert resume_custom["selected_ids"] == ["W2"]


@pytest.fixture
def message_api(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(store, "PROJECTS_ROOT", tmp_path / "projects")
    monkeypatch.setattr(profile_mod, "PROFILE_PATH", tmp_path / "user_profile.md")
    store.create_project(
        "demo",
        Brief(title="演示", kind="summary", audience="老师"),
    )
    return WindowAPI(build_graph_fn=_build_message_graph)


def test_send_message_completes_with_observation(message_api):
    result = message_api.send_message("你好", "demo")
    assert result["type"] == "message"
    assert "收到: 你好" in result["content"]
    assert message_api.pending_confirmation is None


def test_send_message_returns_confirmation(message_api):
    result = message_api.send_message("请给大纲", "demo")
    assert result["type"] == "confirmation"
    assert result["data"]["card_type"] == "outline"
    assert message_api.pending_confirmation["card_type"] == "outline"

    # 未确认前再发普通消息，提示先处理确认卡
    blocked = message_api.send_message("继续", "demo")
    assert blocked["type"] == "confirmation"
    assert "确认卡" in blocked["content"]


def test_send_message_answers_pending_question(message_api):
    paused = message_api.send_message("需要提问", "demo")
    assert paused["type"] == "confirmation"
    assert paused["data"]["card_type"] == "question"

    answered = message_api.send_message("题目是 RAG", "demo")
    assert answered["type"] == "update"
    assert "RAG" in answered["content"]
    assert message_api.pending_confirmation is None


def test_send_message_validation(message_api):
    assert "选择项目" in message_api.send_message("hi", "")["content"]
    assert "不能为空" in message_api.send_message("  ", "demo")["content"]
    assert "不存在" in message_api.send_message("hi", "missing")["content"]


def test_create_project_and_export(api, tmp_path):
    created = api.create_project("骨架演示", "summary", "老师")
    assert created["ok"] is True
    assert created["slug"]
    assert store.project_dir(created["slug"]).is_dir()
    brief = store.load_brief(created["slug"])
    assert brief is not None and brief.title == "骨架演示"
    assert store.load_outline(created["slug"]) == ["总结"]

    exported = api.export_word(created["slug"])
    assert exported["ok"] is True
    assert Path(exported["path"]).exists()


def test_load_project_includes_pending_and_skills(confirm_api):
    api = confirm_api
    api._ensure_graph("demo")
    paused = api._graph.invoke(
        {"project_slug": "demo", "last_observation": "", "user_input": ""},
        api._thread_config(),
    )
    api.pending_confirmation = paused["__interrupt__"][0].value
    data = api.load_project("demo")
    assert data["pending_confirmation"]["card_type"] == "outline"
    assert isinstance(data["skills"], list)
