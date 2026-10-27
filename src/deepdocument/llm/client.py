"""
LLM 客户端

OpenAI 兼容接口封装。
"""

import os
from openai import OpenAI


def get_client() -> OpenAI:
    """
    获取 OpenAI 客户端

    Returns:
        OpenAI 客户端实例
    """
    return OpenAI(
        base_url=os.getenv("OPENAI_BASE_URL"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )


def chat(messages: list[dict], temperature: float = 0.7) -> str:
    """
    调用聊天接口

    Args:
        messages: 消息列表
        temperature: 采样温度

    Returns:
        模型回复
    """
    client = get_client()
    model = os.getenv("OPENAI_MODEL", "gpt-4")

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )

    return response.choices[0].message.content


def parse_react(response: str) -> tuple[str, dict]:
    """
    解析 ReAct 格式输出

    容忍 Action Input 前后有 ```json``` 标记

    Args:
        response: 模型回复

    Returns:
        (action_name, action_input_dict)
    """
    # TODO: 用正则提取 Action: 和 Action Input:
    # TODO: 清理 JSON 前后的 Markdown 代码块标记
    # TODO: 解析 JSON，失败时返回 ("ask_user", {"question": "解析失败"})

    return ("ask_user", {"question": "未实现"})
