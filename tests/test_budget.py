"""
测试：预算管理
"""

from deepdocument.memory.budget import estimate_tokens, truncate_to_budget


def test_estimate_tokens():
    """测试 token 估算"""
    # 1 英文单词 = 1 token
    assert estimate_tokens("hello world") == 2

    # 1 汉字 = 2 token
    assert estimate_tokens("你好") == 4

    # 混合
    assert estimate_tokens("hello 世界") == 1 + 4


def test_truncate_to_budget():
    """测试预算裁剪"""
    text = "这是一段很长的文本" * 100
    truncated = truncate_to_budget(text, 100)

    assert len(truncated) < len(text)
    assert truncated.endswith("...")
