"""
OpenAlex 文献检索
"""

import httpx


def search_literature(query: str, max_results: int = 10) -> list[dict]:
    """
    在 OpenAlex 中检索文献

    Args:
        query: 检索词
        max_results: 最多返回条数（默认 10，实际可能更少）

    Returns:
        文献列表，每条包含 id, title, authors, year, doi, oa_url 等字段
        可能少于 max_results 条
    """
    # TODO: 请求 https://api.openalex.org/works?search=<query>
    # TODO: 过滤出有摘要或开放获取链接的条目
    # TODO: 返回最多 max_results 条
    # TODO: 若少于 3 条，在返回值中标注建议修改检索词
    return []


def get_work_details(openalex_id: str) -> dict | None:
    """
    获取单条文献的详细信息

    Args:
        openalex_id: OpenAlex 的 work ID

    Returns:
        文献详情，包含完整的摘要、引用数等；失败返回 None
    """
    # TODO: 请求 https://api.openalex.org/works/<id>
    return None
