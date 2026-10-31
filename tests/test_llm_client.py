"""
测试：LLM 客户端与 function calling 解析
"""

import json

import pytest
from openai import APIConnectionError, APIStatusError, RateLimitError

from deepdocument.llm import client as llm
from deepdocument.llm.client import chat, chat_for_action, parse_tool_calls
from deepdocument.llm.tools import ACTION_TOOLS, ACTION_WHITELIST


# ---------- tool call 解析 ----------


def test_parse_tool_calls_basic():
    """标准单个 tool call"""
    response = _tool_response(
        "search_literature",
        {"query": "检索增强生成在企业知识库中的应用"},
    )
    action, payload = parse_tool_calls(response)
    assert action == "search_literature"
    assert payload == {"query": "检索增强生成在企业知识库中的应用"}


def test_parse_tool_calls_attaches_content_as_reason():
    """message.content 可作为 reason，不覆盖参数里已有的 reason"""
    response = _tool_response(
        "ask_user",
        {"question": "题目是什么？"},
        content="缺 brief 里的题目",
    )
    action, payload = parse_tool_calls(response)
    assert action == "ask_user"
    assert payload["question"] == "题目是什么？"
    assert payload["reason"] == "缺 brief 里的题目"

    response2 = _tool_response(
        "ask_user",
        {"question": "题目是什么？", "reason": "参数里的理由"},
        content="content 里的理由",
    )
    _, payload2 = parse_tool_calls(response2)
    assert payload2["reason"] == "参数里的理由"


def test_parse_tool_calls_empty_arguments_gives_empty_dict():
    """arguments 为空字符串时给空对象"""
    response = _tool_response("accept_section", raw_arguments="")
    # accept_section 需要 section_id，但解析层只保证是 dict；缺字段由节点处理
    action, payload = parse_tool_calls(response)
    assert action == "accept_section"
    assert payload == {}


def test_parse_tool_calls_takes_first_of_many():
    """若仍返回多个 call，只取第一个"""
    response = _Response(
        [
            _ToolCall("draft_section", {"section_id": "s01"}),
            _ToolCall("search_literature", {"query": "不该执行"}),
        ]
    )
    action, payload = parse_tool_calls(response)
    assert action == "draft_section"
    assert payload == {"section_id": "s01"}


def test_parse_tool_calls_unknown_action_falls_back():
    """白名单外的工具名退回 ask_user"""
    response = _tool_response("delete_everything", {"path": "C:/"})
    action, payload = parse_tool_calls(response)
    assert action == "ask_user"
    assert "delete_everything" in payload["question"]


def test_parse_tool_calls_missing_tool_falls_back():
    """没有 tool_calls"""
    action, payload = parse_tool_calls(_Response([]))
    assert action == "ask_user"
    assert "工具" in payload["question"]


def test_parse_tool_calls_bad_json_falls_back():
    """arguments 不是合法 JSON"""
    response = _tool_response("draft_section", raw_arguments="{section_id: s01")
    action, payload = parse_tool_calls(response)
    assert action == "ask_user"
    assert "JSON" in payload["question"]


def test_parse_tool_calls_non_object_json_falls_back():
    """arguments 是数组时退回 ask_user"""
    response = _tool_response("draft_section", raw_arguments='["s01", "s02"]')
    action, payload = parse_tool_calls(response)
    assert action == "ask_user"


def test_parse_tool_calls_empty_response():
    """没有 choices"""
    action, payload = parse_tool_calls(_EmptyResponse())
    assert action == "ask_user"
    assert payload["question"]


def test_action_tools_cover_whitelist():
    """ACTION_TOOLS 与白名单一致，且不含运行时专用动作"""
    names = {t["function"]["name"] for t in ACTION_TOOLS}
    assert names == ACTION_WHITELIST
    assert "fetch_source" not in names
    assert "export_docx" not in names


# ---------- 接口调用 ----------


class _FakeCompletions:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FakeClient:
    def __init__(self, outcomes):
        self.chat = type("Chat", (), {"completions": _FakeCompletions(outcomes)})()


class _Function:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _ToolCall:
    def __init__(self, name, arguments=None, *, raw_arguments=None):
        if raw_arguments is not None:
            args = raw_arguments
        elif arguments is None:
            args = ""
        else:
            args = json.dumps(arguments, ensure_ascii=False)
        self.function = _Function(name, args)


class _Msg:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class _Choice:
    def __init__(self, message):
        self.message = message


class _Response:
    def __init__(self, tool_calls, content=None):
        self.choices = [_Choice(_Msg(content=content, tool_calls=tool_calls))]


class _EmptyResponse:
    choices = []


class _TextResponse:
    def __init__(self, content):
        self.choices = [_Choice(_Msg(content=content))]


def _tool_response(name, arguments=None, *, raw_arguments=None, content=None):
    return _Response(
        [_ToolCall(name, arguments, raw_arguments=raw_arguments)],
        content=content,
    )


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def test_chat_returns_content():
    """纯文本 chat 仍可用"""
    fake = _FakeClient([_TextResponse("一段正文")])
    result = chat([{"role": "user", "content": "hi"}], client=fake)

    assert result == "一段正文"
    call = fake.chat.completions.calls[0]
    assert call["model"] == "test-model"
    assert call["max_tokens"] == llm.MAX_OUTPUT_TOKENS
    assert "tools" not in call


def test_chat_for_action_sends_tools():
    """选动作时带上 tools，并解析返回"""
    fake = _FakeClient(
        [_tool_response("search_literature", {"query": "RAG"})]
    )
    action, payload = chat_for_action(
        [{"role": "user", "content": "搜文献"}],
        client=fake,
    )

    assert action == "search_literature"
    assert payload == {"query": "RAG"}

    call = fake.chat.completions.calls[0]
    assert call["tools"] == ACTION_TOOLS
    assert call["tool_choice"] == "required"
    assert call["parallel_tool_calls"] is False


def test_chat_for_action_retries_without_parallel_flag():
    """兼容接口不认 parallel_tool_calls 时去掉再试"""
    outcomes = [
        TypeError("got an unexpected keyword argument 'parallel_tool_calls'"),
        _tool_response("ask_user", {"question": "ok"}),
    ]
    fake = _FakeClient(outcomes)
    action, payload = chat_for_action(
        [{"role": "user", "content": "hi"}],
        client=fake,
        retries=1,
    )

    assert action == "ask_user"
    assert payload["question"] == "ok"
    assert len(fake.chat.completions.calls) == 2
    assert "parallel_tool_calls" not in fake.chat.completions.calls[1]


def test_chat_retries_on_rate_limit():
    """429 重试后成功"""
    fake = _FakeClient(
        [
            RateLimitError("rate limited", response=_mock_response(429), body=None),
            _TextResponse("第二次成功"),
        ]
    )
    result = chat([{"role": "user", "content": "hi"}], client=fake, retries=1)

    assert result == "第二次成功"
    assert len(fake.chat.completions.calls) == 2


def test_chat_raises_after_retries_exhausted():
    """重试耗尽后抛 LLMError"""
    fake = _FakeClient(
        [
            APIConnectionError(request=_mock_request()),
            APIConnectionError(request=_mock_request()),
        ]
    )
    with pytest.raises(llm.LLMError):
        chat([{"role": "user", "content": "hi"}], client=fake, retries=1)


def test_chat_does_not_retry_on_400():
    """400 是请求本身的问题，不重试"""
    fake = _FakeClient([APIStatusError("bad request", response=_mock_response(400), body=None)])
    with pytest.raises(llm.LLMError):
        chat([{"role": "user", "content": "hi"}], client=fake, retries=2)

    assert len(fake.chat.completions.calls) == 1


def test_chat_empty_choices_returns_empty_string():
    """没有 choices 时返回空串"""
    fake = _FakeClient([_EmptyResponse()])
    assert chat([{"role": "user", "content": "hi"}], client=fake) == ""


def test_chat_rejects_empty_messages():
    """messages 为空直接报错，不发请求"""
    with pytest.raises(llm.LLMError):
        chat([], client=_FakeClient([]))


def test_chat_requires_model_env(monkeypatch):
    """没有 OPENAI_MODEL 时报错，不猜模型名"""
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    with pytest.raises(llm.LLMError):
        chat([{"role": "user", "content": "hi"}], client=_FakeClient([_TextResponse("x")]))


def test_get_client_requires_api_key(monkeypatch):
    """没有 OPENAI_API_KEY 时报错"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    llm.get_client.cache_clear()
    with pytest.raises(llm.LLMError):
        llm.get_client()
    llm.get_client.cache_clear()


# ---------- 辅助 ----------


def _mock_response(status_code: int):
    import httpx

    return httpx.Response(
        status_code,
        request=httpx.Request("POST", "https://example.invalid/v1/chat/completions"),
    )


def _mock_request():
    import httpx

    return httpx.Request("POST", "https://example.invalid/v1/chat/completions")
