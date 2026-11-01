"""OpenAlex 检索与开放获取/摘要落盘。"""

from deepdocument.literature.fetch import extract_text_from_pdf, fetch_source
from deepdocument.literature.search import get_work_details, search_literature

__all__ = [
    "extract_text_from_pdf",
    "fetch_source",
    "get_work_details",
    "search_literature",
]
