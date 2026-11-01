"""
OpenAlex 文献检索

只返回索引中的真实记录；不做向量检索、不编造条目。
"""

from __future__ import annotations

import re

import httpx

OPENALEX_WORKS = "https://api.openalex.org/works"
# 礼貌池标识；无真实邮箱时用本地占位
MAILTO = "deepdocument@localhost"


def search_literature(query: str, max_results: int = 8) -> list[dict]:
    """
    按题目/检索词查 OpenAlex，默认最多 8 条。

    每条字段：id, openalex_id, title, authors, year, doi, venue, url, oa_url, abstract
    """
    query = (query or "").strip()
    if not query or max_results <= 0:
        return []

    params = {
        "search": query,
        "per_page": min(max_results, 25),
        "mailto": MAILTO,
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(OPENALEX_WORKS, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, ValueError):
        return []

    results: list[dict] = []
    for work in payload.get("results") or []:
        item = _normalize_work(work)
        if item:
            results.append(item)
        if len(results) >= max_results:
            break
    return results


def get_work_details(openalex_id: str) -> dict | None:
    """拉取单条 work；失败返回 None。"""
    openalex_id = (openalex_id or "").strip()
    if not openalex_id:
        return None
    if openalex_id.startswith("http"):
        url = openalex_id
    else:
        wid = openalex_id if openalex_id.startswith("W") else f"W{openalex_id}"
        url = f"{OPENALEX_WORKS}/{wid}"

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, params={"mailto": MAILTO})
            resp.raise_for_status()
            return _normalize_work(resp.json())
    except (httpx.HTTPError, ValueError):
        return None


def _normalize_work(work: dict) -> dict | None:
    openalex_id = work.get("id") or ""
    short_id = openalex_id.rsplit("/", 1)[-1] if openalex_id else ""
    if not short_id:
        return None

    title = (work.get("display_name") or work.get("title") or "").strip()
    if not title:
        return None

    authors: list[str] = []
    for authorship in work.get("authorships") or []:
        author = authorship.get("author") or {}
        name = author.get("display_name")
        if name:
            authors.append(name)

    primary = work.get("primary_location") or {}
    source = primary.get("source") or {}
    venue = source.get("display_name")

    oa = work.get("open_access") or {}
    oa_url = oa.get("oa_url") or primary.get("pdf_url") or primary.get("landing_page_url")

    abstract = _invert_abstract_index(work.get("abstract_inverted_index"))

    doi = work.get("doi")
    if isinstance(doi, str) and doi.startswith("https://doi.org/"):
        doi = doi.removeprefix("https://doi.org/")

    return {
        "id": short_id,
        "openalex_id": openalex_id,
        "title": title,
        "authors": authors,
        "year": work.get("publication_year"),
        "doi": doi,
        "venue": venue,
        "url": openalex_id,
        "oa_url": oa_url,
        "abstract": abstract,
    }


def _invert_abstract_index(index: dict | None) -> str | None:
    """OpenAlex 摘要是倒排索引，还原成纯文本。"""
    if not index or not isinstance(index, dict):
        return None
    positions: list[tuple[int, str]] = []
    for word, places in index.items():
        if not isinstance(places, list):
            continue
        for pos in places:
            if isinstance(pos, int):
                positions.append((pos, word))
    if not positions:
        return None
    positions.sort(key=lambda x: x[0])
    text = " ".join(w for _, w in positions)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None
