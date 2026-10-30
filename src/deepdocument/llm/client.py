"""
LLM 客户端

OpenAI 兼容接口封装，以及 ReAct 输出的解析。

这一层只管两件事：把 messages 发出去拿回文本，把文本解析成
(action, action_input)。不碰业务状态，也不写文件。
"""

import json
import os
import re
from functools import lru_cache
from typing import Any

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError
from openai import APIStatusError

# 允许 ReAct 点名的动作。其余一律按无效处理，退回 ask_user。
ACTION_WHITELIST = frozenset(
    {
        "ask_user",
        "search_literature",
        "update_outline",
        "draft_section",
        "revise_section",
        "accept_section",
        "record_decision",
        "propose_skill",
    }
)

# 上下文至少 16,384 token，见 docs/memory.md
MIN_CONTEXT_TOKENS = 16_384
# 输出预留 2,048 token
MAX_OUTPUT_TOKENS = 2_048

DEFAULT_TIMEOUT = 60.0


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
    调用聊天接口

    Args:
        messages: 消息列表，形如 [{"role": "system", "content": "..."}]
        temperature: 采样温度
        max_tokens: 输出上限，默认 2,048，与 docs/memory.md 的输出预留一致
        retries: 可重试错误（超时、连接失败、429、5xx）的重试次数
        client: 测试时注入的假客户端；为空则用 get_client()

    Returns:
        模型回复文本，无内容时返回空串

    Raises:
        LLMError: 重试耗尽或遇到不可重试的错误
    """
    if not messages:
        raise LLMError("messages 不能为空")

    api = client or get_client()
    model = get_model()

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = api.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except (APITimeoutError, APIConnectionError, RateLimitError) as exc:
            last_error = exc
        except APIStatusError as exc:
            # 4xx 里只有 429 值得重试，其余是请求本身的问题
            if exc.status_code != 429 and exc.status_code < 500:
                raise LLMError(f"接口返回 {exc.status_code}: {exc.message}") from exc
            last_error = exc
        else:
            if not response.choices:
                return ""
            return response.choices[0].message.content or ""

    raise LLMError(f"接口调用失败，已重试 {retries} 次: {last_error}") from last_error


def parse_react(response: str) -> tuple[str, dict]:
    """
    解析 ReAct 格式输出

    只接受 docs/agent-loop.md 规定的这段：

        Thought: ...
        Action: draft_section
        Action Input: {"section_id": "s01", "source_ids": ["W1"]}

    容忍 Action Input 前后带 ```json``` 或 ``` 围栏。解析失败、
    Action 为空或不在白名单内时，返回 ask_user，让调用方本轮不写入。

    Args:
        response: 模型回复

    Returns:
        (action_name, action_input_dict)
    """
    if not response or not response.strip():
        return _fallback("模型没有输出")

    action_match = re.search(r"^\s*Action\s*[:：]\s*(.+?)\s*$", response, re.MULTILINE)
    if not action_match:
        return _fallback("没有找到 Action 行")

    action = action_match.group(1).strip().strip("`").strip()
    if action not in ACTION_WHITELIST:
        return _fallback(f"未知的 Action: {action}")

    present, raw_input = _extract_action_input(response)
    if not present:
        # 整行 Action Input 都没有：这类动作允许无参数，给空对象
        return action, {}

    if raw_input is None:
        # 写了 Action Input，但后面没有对象（数组、字符串、空围栏）
        return _fallback("Action Input 没有给出 JSON 对象")

    parsed = _parse_json_object(raw_input)
    if parsed is None:
        return _fallback(f"Action Input 不是合法的 JSON 对象: {raw_input.strip()[:80]}")
    if not isinstance(parsed, dict):
        return _fallback("Action Input 不是 JSON 对象")

    return action, parsed


def parse_thought(response: str) -> str:
    """
    取出 Thought 行

    Thought 不进下一轮提示（见 docs/memory.md），只在窗口里展示。

    Args:
        response: 模型回复

    Returns:
        Thought 文本；没有则返回空串
    """
    match = re.search(r"^\s*Thought\s*[:：]\s*(.+?)\s*$", response, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _fallback(reason: str) -> tuple[str, dict]:
    """解析失败时退回提问，理由写进 question 供窗口显示"""
    return "ask_user", {"question": reason}


def _extract_action_input(response: str) -> tuple[bool, str | None]:
    """
    取出 Action Input 之后的文本

    先定位 Action Input 行，再在该行之后寻找第一个 '{'，交给
    _parse_json_object 做括号配对。返回原始文本，不是解析结果。

    Args:
        response: 模型回复

    Returns:
        (是否有 Action Input 行, 以第一个 '{' 起始的原始文本)
        没有该行 → (False, None)；有该行但没有对象 → (True, None)
    """
    match = re.search(
        r"^\s*Action\s*Input\s*[:：]\s*(.*)$", response, re.MULTILINE | re.DOTALL
    )
    if not match:
        return False, None

    tail = match.group(1)
    start = tail.find("{")
    if start == -1:
        return True, None
    return True, tail[start:]


def _parse_json_object(text: str) -> Any | None:
    """
    从文本里取出第一个完整的 JSON 对象

    逐个 '{' 尝试括号配对（跳过字符串内的括号和转义），配对成功就交给
    json.loads。这样模型在 JSON 后面多写一句话也不影响。

    Args:
        text: 以 '{' 开头的原始文本

    Returns:
        解析出的对象；失败返回 None
    """
    decoder = json.JSONDecoder()

    for index, char in enumerate(text):
        if char != "{":
            continue
        end = _find_object_end(text, index)
        if end is None:
            continue
        try:
            value, _ = decoder.raw_decode(text[index:end])
        except json.JSONDecodeError:
            continue
        return value

    return None


def _find_object_end(text: str, start: int) -> int | None:
    """
    找出从 start 处的 '{' 起配对的 '}' 位置

    字符串里的括号不算数，反斜杠转义要跳过。

    Args:
        text: 原始文本
        start: '{' 的下标

    Returns:
        配对的 '}' 的下标 + 1（可直接切片）；不配对返回 None
    """
    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index + 1

    return None
