"""
测试：预算管理
"""

import pytest

from deepdocument.memory.budget import estimate_tokens, truncate_to_budget


def test_estimate_tokens_cjk():
    """一个汉字计 2 token"""
    assert estimate_tokens("你好") == 4
    assert estimate_tokens("总结") == 4


def test_estimate_tokens_ascii():
    """连续的 ASCII 每 4 个字符计 1 token，向上取整，不计空白"""
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2
    assert estimate_tokens("hello") == 2
    # 空格不算字符：hello world = 10 个字符 → 3 token
    assert estimate_tokens("hello world") == 3


def test_estimate_tokens_mixed():
    """中英混合分别计算"""
    # "hello" 5 个 ASCII 字符 → 2 token；"世界" 2 个汉字 → 4 token
    assert estimate_tokens("hello 世界") == 6


def test_estimate_tokens_empty():
    """空文本为 0"""
    assert estimate_tokens("") == 0
    assert estimate_tokens("   ") == 0


def test_estimate_tokens_monotonic():
    """文本越长，估算不会变小"""
    texts = ["", "短", "短文本", "这是一段更长的文本"]
    values = [estimate_tokens(t) for t in texts]
    assert values == sorted(values)


def test_truncate_to_budget():
    """超出预算时截断并加省略号"""
    text = "这是一段很长的文本" * 100
    truncated = truncate_to_budget(text, 100)

    assert len(truncated) < len(text)
    assert truncated.endswith("...")


def test_truncate_within_budget_keeps_text():
    """未超预算时原样返回"""
    text = "短文"
    assert truncate_to_budget(text, 1000) == text


def test_truncate_result_fits_budget():
    """截断后的估算仍不超过预算"""
    text = "这是一段很长的文本" * 200
    truncated = truncate_to_budget(text, 200)
    assert estimate_tokens(truncated) <= 200
