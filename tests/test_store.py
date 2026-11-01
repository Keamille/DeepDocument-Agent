"""
测试：文稿磁盘存储与导出
"""

from datetime import datetime, timezone

import pytest

from deepdocument.document.exporter import export_docx
from deepdocument.document.model import Brief, Decision, Literature, Source
from deepdocument.document import store


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(store, "PROJECTS_ROOT", tmp_path / "projects")
    brief = Brief(
        title="检索增强生成",
        kind="summary",
        audience="课程老师",
        constraints=["中文"],
        citation_style="APA",
    )
    store.create_project("demo", brief)
    return "demo"


def test_create_project_layout(project, tmp_path):
    root = tmp_path / "projects" / "demo"
    assert (root / "brief.md").exists()
    assert (root / "outline.md").exists()
    assert (root / "meta.json").exists()
    assert (root / "sections").is_dir()
    assert (root / "sources").is_dir()

    brief = store.load_brief(project)
    assert brief is not None
    assert brief.title == "检索增强生成"
    assert brief.kind == "summary"
    assert brief.citation_style == "APA"


def test_outline_syncs_meta(project):
    store.save_outline(project, ["总结", "局限"])
    meta = store.load_meta(project)

    assert len(meta["sections"]) == 2
    assert meta["sections"][0]["title"] == "总结"
    assert meta["sections"][0]["status"] == "outlined"
    assert meta["cursor"] == meta["sections"][0]["id"]

    titles = store.load_outline(project)
    assert titles == ["总结", "局限"]


def test_save_section_marks_draft_and_gist(project):
    store.save_outline(project, ["总结"])
    section_id = store.load_meta(project)["sections"][0]["id"]

    store.save_section(
        project,
        section_id,
        "第一段结论。\n\n第二段依据。",
        gist="按结论归类不逐篇罗列多余字会被截断",
    )

    assert "第一段结论" in store.load_section(project, section_id)
    meta = store.load_meta(project)
    sec = meta["sections"][0]
    assert sec["status"] == "draft"
    assert len(sec["gist"]) <= 20


def test_save_section_unknown_id_raises(project, tmp_path):
    store.save_outline(project, ["总结"])
    with pytest.raises(KeyError, match="未知节 id"):
        store.save_section(project, "no-such-section", "不应落盘")
    assert not (tmp_path / "projects" / "demo" / "sections" / "no-such-section.md").exists()


def test_literature_roundtrip_and_filter(project):
    items = [
        Literature(
            id="W1",
            title="RAG Paper",
            authors=["Alice"],
            year=2020,
            status="accepted",
            openalex_id="https://openalex.org/W1",
            doi="10.1000/x",
            content_source="fulltext",
            evidence_type="core",
        ),
        Literature(
            id="W2",
            title="Other",
            authors=["Bob"],
            year=2021,
            status="rejected",
        ),
    ]
    store.save_literature(project, items)

    accepted = store.load_literature(project, status="accepted")
    assert len(accepted) == 1
    assert accepted[0].doi == "10.1000/x"
    assert accepted[0].content_source == "fulltext"

    store.update_literature(project, "W1", content_source="abstract", venue="NeurIPS")
    updated = store.load_literature(project, status="accepted")[0]
    assert updated.content_source == "abstract"
    assert updated.venue == "NeurIPS"


def test_source_card_excerpt_archive(project):
    source = Source(
        id="W1",
        content_source="fulltext",
        card="与题目相关的两句话。",
        excerpt="可供引用的摘录。",
        archive="更长的原文在这里。",
    )
    store.save_source(project, source)

    loaded = store.load_source(project, "W1")
    assert loaded is not None
    assert loaded.card == "与题目相关的两句话。"
    assert loaded.excerpt == "可供引用的摘录。"
    assert loaded.archive == "更长的原文在这里。"
    assert "W1" in store.list_source_ids(project)


def test_source_without_archive(project):
    store.save_source(
        project,
        Source(
            id="W2",
            content_source="abstract",
            card="依据是摘要",
            excerpt="摘要正文",
            archive="",
        ),
    )
    text = (store.project_dir(project) / "sources" / "W2.md").read_text(encoding="utf-8")
    assert "## archive" not in text
    loaded = store.load_source(project, "W2")
    assert loaded.archive == ""


def test_decisions_disk_format(project):
    store.append_decision(
        project,
        Decision(
            timestamp="2026-10-27T18:00:00+08:00",
            section_id="summary",
            feedback="按结论归类，不要逐篇罗列",
        ),
    )
    raw = (store.project_dir(project) / "decisions.jsonl").read_text(encoding="utf-8")
    assert '"at"' in raw
    assert '"section"' in raw
    assert '"text"' in raw

    decisions = store.load_decisions(project, limit=10)
    assert len(decisions) == 1
    assert decisions[0].feedback.startswith("按结论归类")
    assert decisions[0].section_id == "summary"


def test_package_exports_section_helpers():
    from deepdocument.document import (
        get_sections,
        list_source_ids,
        update_literature,
        update_section_meta,
    )

    assert callable(get_sections)
    assert callable(list_source_ids)
    assert callable(update_literature)
    assert callable(update_section_meta)


def test_export_includes_draft_marks_and_skips_empty(project):
    store.save_outline(project, ["总结", "附录"])
    meta = store.load_meta(project)
    s0, s1 = meta["sections"][0]["id"], meta["sections"][1]["id"]

    store.save_section(project, s0, "总结正文。", status="draft")
    store.update_section_meta(project, s1, status="empty")

    store.append_literature(
        project,
        Literature(
            id="W1",
            title="A Study",
            authors=["Zhang"],
            year=2022,
            status="accepted",
            doi="10.1/abc",
        ),
    )

    path = export_docx(project)
    assert path.exists()
    assert path.name == "export.docx"

    from docx import Document

    doc = Document(str(path))
    texts = [p.text for p in doc.paragraphs]
    joined = "\n".join(texts)
    assert "检索增强生成" in joined
    assert "总结（草稿）" in joined
    assert "附录" not in joined  # empty 不导出
    assert "参考文献" in joined
    assert "Zhang" in joined
