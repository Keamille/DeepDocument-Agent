"""LLM 客户端与动作工具 schema。"""

from deepdocument.llm.client import (
    LLMError,
    chat,
    chat_for_action,
    get_client,
    get_model,
    parse_tool_calls,
)
from deepdocument.llm.tools import ACTION_TOOLS, ACTION_WHITELIST

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
