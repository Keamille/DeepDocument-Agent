"""
LLM 客户端

OpenAI 兼容接口封装，以及一轮一个 tool call 的解析。

这一层只管两件事：把 messages 和 tools 发出去，把返回的第一个
tool call 解析成 (action, action_input)。不碰业务状态，也不写文件。

工具 schema 见 tools.py。
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError
from openai import APIStatusError

from deepdocument.llm.tools import ACTION_TOOLS, ACTION_WHITELIST

# 上下文至少 16,384 token，见 docs/memory.md
MIN_CONTEXT_TOKENS = 16_384
# 输出预留 2,048 token
MAX_OUTPUT_TOKENS = 2_048

DEFAULT_TIMEOUT = 60.0

# 方便 `from deepdocument.llm.client import ACTION_TOOLS` 的旧写法
__all__ = [
    "ACTION_TOOLS",
    "ACTION_WHITELIST",
    "LLMError",
    "chat",
    "chat_for_action",
    "get_client",
    "get_model",
    "parse_tool_calls",
]


class LLMError(RuntimeError):
    """接口调用失败，且重试后仍未成功"""


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    """
    获取 OpenAI 客户端

    进程内复用同一个实例。base_url 留空时用 SDK 默认值。

    Returns:
        OpenAI 客户端实例
    """
    base_url = os.getenv("OPENAI_BASE_URL") or None
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise LLMError("缺少环境变量 OPENAI_API_KEY")

    return OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=float(os.getenv("OPENAI_TIMEOUT", DEFAULT_TIMEOUT)),
        max_retries=0,  # 重试由本模块控制，便于记录日志
    )


def get_model() -> str:
    """读取模型名，缺省值直接报错，避免悄悄用一个猜的名字"""
    model = os.getenv("OPENAI_MODEL")
    if not model:
        raise LLMError("缺少环境变量 OPENAI_MODEL")
    return model


def chat(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = MAX_OUTPUT_TOKENS,
    retries: int = 2,
    client: OpenAI | None = None,
) -> str:
    """
    调用聊天接口（纯文本，不带 tools）

    起草节正文等需要自由文本时使用。选动作请用 chat_for_action。

    Args:
        messages: 消息列表
        temperature: 采样温度
        max_tokens: 输出上限
        retries: 可重试错误的重试次数
        client: 测试时注入的假客户端

    Returns:
        模型回复文本

    Raises:
        LLMError: 重试耗尽或遇到不可重试的错误
    """
    response = _create_completion(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        retries=retries,
        client=client,
    )
    if not response.choices:
        return ""
    return response.choices[0].message.content or ""


def chat_for_action(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = MAX_OUTPUT_TOKENS,
    retries: int = 2,
    client: OpenAI | None = None,
    tools: list[dict] | None = None,
) -> tuple[str, dict]:
    """
    让模型从白名单里选一个动作（function calling）

    每轮只取第一个 tool call。没有 call、名字不在白名单、或参数不是
    JSON 对象时，退回 ask_user，让调用方本轮不写入。

    Args:
        messages: 消息列表，通常含系统上下文和本轮用户话
        temperature: 选动作宜偏低
        max_tokens: 输出上限
        retries: 可重试错误的重试次数
        client: 测试时注入的假客户端
        tools: 默认 ACTION_TOOLS；测试可传入子集

    Returns:
        (action_name, action_input_dict)
        可选理由在 action_input["reason"]，来自工具参数或 message.content
    """
    response = _create_completion(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        retries=retries,
        client=client,
        tools=tools if tools is not None else ACTION_TOOLS,
        tool_choice="required",
        parallel_tool_calls=False,
    )
    return parse_tool_calls(response)


def parse_tool_calls(response: Any) -> tuple[str, dict]:
    """
    从 Chat Completions 响应里取出第一个 tool call

    Args:
        response: SDK 返回的 ChatCompletion，或带同样字段的假对象

    Returns:
        (action_name, action_input_dict)
    """
    if response is None or not getattr(response, "choices", None):
        return _fallback("模型没有返回 choices")

    message = response.choices[0].message
    content_reason = (getattr(message, "content", None) or "").strip()
    tool_calls = getattr(message, "tool_calls", None) or []

    if not tool_calls:
        return _fallback("模型没有调用工具")

    # 一轮只执行一个动作；若接口仍返回多个，只取第一个
    call = tool_calls[0]
    function = getattr(call, "function", None)
    if function is None:
        return _fallback("tool call 缺少 function")

    action = (getattr(function, "name", None) or "").strip()
    if action not in ACTION_WHITELIST:
        return _fallback(f"未知的 Action: {action or '(空)'}")

    raw_args = getattr(function, "arguments", None) or ""
    if not str(raw_args).strip():
        payload: dict = {}
    else:
        try:
            parsed = json.loads(raw_args)
        except json.JSONDecodeError:
            return _fallback(f"工具参数不是合法 JSON: {str(raw_args).strip()[:80]}")
        if not isinstance(parsed, dict):
            return _fallback("工具参数不是 JSON 对象")
        payload = parsed

    if content_reason and "reason" not in payload:
        payload["reason"] = content_reason

    return action, payload


def _create_completion(
    messages: list[dict],
    *,
    temperature: float,
    max_tokens: int,
    retries: int,
    client: OpenAI | None,
    tools: list[dict] | None = None,
    tool_choice: str | None = None,
    parallel_tool_calls: bool | None = None,
):
    if not messages:
        raise LLMError("messages 不能为空")

    api = client or get_client()
    model = get_model()

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools is not None:
        kwargs["tools"] = tools
    if tool_choice is not None:
        kwargs["tool_choice"] = tool_choice
    if parallel_tool_calls is not None:
        kwargs["parallel_tool_calls"] = parallel_tool_calls

    last_error: Exception | None = None
    for _attempt in range(retries + 1):
        try:
            return api.chat.completions.create(**kwargs)
        except (APITimeoutError, APIConnectionError, RateLimitError) as exc:
            last_error = exc
        except APIStatusError as exc:
            # 4xx 里只有 429 值得重试，其余是请求本身的问题
            if exc.status_code != 429 and exc.status_code < 500:
                raise LLMError(f"接口返回 {exc.status_code}: {exc.message}") from exc
            last_error = exc
        except TypeError as exc:
            # 部分兼容接口不认 parallel_tool_calls，去掉后再试一次
            if "parallel_tool_calls" in kwargs and "parallel_tool_calls" in str(exc):
                kwargs.pop("parallel_tool_calls", None)
                last_error = exc
                continue
            raise

    raise LLMError(f"接口调用失败，已重试 {retries} 次: {last_error}") from last_error


def _fallback(reason: str) -> tuple[str, dict]:
    """解析失败时退回提问，理由写进 question 供窗口显示"""
    return "ask_user", {"question": reason}
