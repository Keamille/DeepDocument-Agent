"""
Word 导出

以 template.docx 为底稿，套入节正文，输出 export.docx。
"""

from pathlib import Path

from docx import Document
from docx.shared import Pt
from docx.enum.style import WD_STYLE_TYPE

from deepdocument.document.store import load_meta, load_section, load_literature
from deepdocument.document.model import Brief


def export_docx(project_slug: str, brief: Brief):
    """
    导出 Word 文档

    Args:
        project_slug: 项目 slug
        brief: Brief 对象，包含 citation_style
    """
    template_path = Path("projects") / project_slug / "template.docx"
    export_path = Path("projects") / project_slug / "export.docx"

    # 加载模板或创建空白文档
    if template_path.exists():
        doc = Document(str(template_path))
    else:
        doc = Document()

    # 清空现有内容（保留样式）
    for element in doc.element.body:
        doc.element.body.remove(element)

    # 添加标题
    heading_style = _find_style(doc, ["Heading 1", "标题 1"])
    if heading_style:
        doc.add_heading(brief.title, level=1).style = heading_style
    else:
        doc.add_heading(brief.title, level=1)

    # 添加各节正文
    meta = load_meta(project_slug)
    for section in meta.get("sections", []):
        if section["status"] != "accepted":
            continue

        # 节标题
        section_heading_style = _find_style(doc, ["Heading 2", "标题 2"])
        if section_heading_style:
            doc.add_heading(section["title"], level=2).style = section_heading_style
        else:
            doc.add_heading(section["title"], level=2)

        # 节正文
        content = load_section(project_slug, section["id"])
        normal_style = _find_style(doc, ["Normal", "正文"])
        for para_text in content.split("\n\n"):
            p = doc.add_paragraph(para_text.strip())
            if normal_style:
                p.style = normal_style

    # 添加参考文献
    _add_references(doc, project_slug, brief.citation_style)

    # 保存
    doc.save(str(export_path))


def _find_style(doc: Document, names: list[str]) -> str | None:
    """
    查找第一个存在的样式名称

    Args:
        doc: Document 对象
        names: 候选样式名称列表

    Returns:
        存在的样式名称；都不存在返回 None
    """
    styles = {s.name for s in doc.styles if s.type == WD_STYLE_TYPE.PARAGRAPH}
    for name in names:
        if name in styles:
            return name
    return None


def _add_references(doc: Document, project_slug: str, citation_style: str):
    """
    添加参考文献列表

    Args:
        doc: Document 对象
        project_slug: 项目 slug
        citation_style: 引用格式（默认 APA 7th）
    """
    literature = load_literature(project_slug)
    accepted = [lit for lit in literature if lit.status == "accepted"]
    if not accepted:
        return

    # 添加参考文献标题
    doc.add_heading("参考文献", level=1)

    # 按作者姓氏排序
    accepted.sort(key=lambda lit: lit.authors[0] if lit.authors else "")

    # 格式化每条文献
    for lit in accepted:
        ref_text = _format_citation(lit, citation_style)
        doc.add_paragraph(ref_text)


def _format_citation(lit, style: str) -> str:
    """
    格式化单条引用

    Args:
        lit: Literature 对象
        style: 引用格式

    Returns:
        格式化的引用文本
    """
    # TODO: 支持 APA 7th、GB/T 7714-2015 等格式
    # 第一版简单拼接：作者. (年份). 标题. DOI
    authors_str = ", ".join(lit.authors[:3])
    if len(lit.authors) > 3:
        authors_str += ", et al."

    parts = [f"{authors_str}. ({lit.year}). {lit.title}."]
    if lit.doi:
        parts.append(f"https://doi.org/{lit.doi}")

    return " ".join(parts)
