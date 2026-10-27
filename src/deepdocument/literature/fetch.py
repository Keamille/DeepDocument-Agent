"""
文献全文和摘要抓取
"""

from pathlib import Path

import httpx
from pypdf import PdfReader


def fetch_source(
    openalex_id: str,
    oa_url: str | None,
    abstract: str | None,
    project_slug: str,
) -> dict:
    """
    抓取开放获取全文或摘要，写入 sources/<id>.md

    Args:
        openalex_id: OpenAlex work ID
        oa_url: 开放获取 PDF 链接
        abstract: OpenAlex 摘要
        project_slug: 项目 slug

    Returns:
        结果字典，包含 content_source（'oa_pdf' | 'abstract' | 'unavailable'）和 excerpt_length
    """
    source_path = Path("projects") / project_slug / "sources" / f"{openalex_id}.md"
    source_path.parent.mkdir(parents=True, exist_ok=True)

    # TODO: 若 oa_url 存在，尝试下载 PDF
    # TODO: 用 pypdf 抽取文本
    # TODO: 若抽不到文本（扫描件），改用 abstract
    # TODO: 若都没有，标注「无可用文本」
    # TODO: 写入 sources/<id>.md（## card、## excerpt、## archive 三段）
    # TODO: excerpt 最多 1200 token

    return {"content_source": "unavailable", "excerpt_length": 0}


def extract_text_from_pdf(pdf_path: Path) -> str | None:
    """
    从 PDF 提取文本层

    Args:
        pdf_path: PDF 文件路径

    Returns:
        提取的文本；失败返回 None
    """
    # TODO: 用 pypdf 读取所有页
    # TODO: 扫描件会返回空或很少文本
    return None
