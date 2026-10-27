"""
用户画像管理

把反馈收成 user_profile.md，去重。
"""

from pathlib import Path


def load_profile() -> dict:
    """
    读取全局用户画像

    Returns:
        画像字典，包含 language, tone, structure, citation, rejects 等字段
    """
    profile_path = Path("user_profile.md")
    if not profile_path.exists():
        return {
            "language": "中文",
            "tone": "",
            "structure": "",
            "citation": "",
            "rejects": [],
        }

    # TODO: 解析 Markdown，提取各字段
    return {}


def update_profile(feedback: str):
    """
    根据反馈更新画像，去重

    去重规则：
    - 精确匹配（去掉标点后比较）
    - 未来可用嵌入向量计算相似度（阈值 > 0.9）

    Args:
        feedback: 用户反馈
    """
    profile = load_profile()

    # TODO: 分类反馈（语言/语气/结构/引用/拒绝）
    # TODO: 检查是否已存在（精确匹配）
    # TODO: 若不存在，追加到对应字段
    # TODO: 写回 user_profile.md

    pass


def save_profile(profile: dict):
    """
    写入画像文件

    Args:
        profile: 画像字典
    """
    profile_path = Path("user_profile.md")

    # TODO: 格式化为 Markdown
    # TODO: 写入文件

    pass
