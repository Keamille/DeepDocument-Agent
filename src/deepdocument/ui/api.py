"""
窗口 API

pywebview 的 js_api，连接前端和图。
"""

from __future__ import annotations

from typing import Any

from langgraph.types import Command

from deepdocument.document import store
from deepdocument.graph.builder import build_graph
from deepdocument.memory.profile import profile_to_prompt


class WindowAPI:
    """窗口暴露给 JavaScript 的 API"""

    def __init__(self, build_graph_fn=build_graph):
        """
        Args:
            build_graph_fn: 按项目 slug 编译图的函数
        """
        self._build_graph = build_graph_fn
        self.current_project = None
        self._graph = None
        self.pending_confirmation = None

    def _thread_config(self) -> dict:
        """LangGraph 配置：thread_id = 项目 slug。"""
        return {"configurable": {"thread_id": self.current_project}}

    def _ensure_graph(self, project_slug: str):
        """项目切换时才重新编译图。"""
        if not project_slug:
            return
        if project_slug == self.current_project and self._graph is not None:
            return
        self.current_project = project_slug
        self._graph = self._build_graph(project_slug)
        self.pending_confirmation = None

    def list_projects(self) -> list[dict]:
        """
        列出 projects/ 下已有项目。

        Returns:
            [{slug, title, kind}]，按 slug 排序；title 来自 brief.md，缺省用 slug
        """
        root = store.PROJECTS_ROOT
        if not root.exists():
            return []

        result: list[dict] = []
        for proj_dir in root.iterdir():
            if not proj_dir.is_dir() or proj_dir.name.startswith("."):
                continue
            slug = proj_dir.name
            brief = store.load_brief(slug)
            result.append(
                {
                    "slug": slug,
                    "title": (brief.title if brief and brief.title else slug),
                    "kind": brief.kind if brief else "report",
                }
            )
        return sorted(result, key=lambda p: p["slug"])

    def load_project(self, slug: str) -> dict:
        """
        加载项目右栏数据：大纲、各节、已确认文献、全局画像。

        Raises:
            FileNotFoundError: 项目目录不存在
        """
        slug = (slug or "").strip()
        if not slug:
            raise ValueError("project slug 不能为空")

        root = store.project_dir(slug)
        if not root.is_dir():
            raise FileNotFoundError(f"项目不存在: {slug}")

        self._ensure_graph(slug)

        meta = store.load_meta(slug)
        outline = store.load_outline(slug)
        sections = []
        for sec in store.get_sections(slug):
            sections.append(
                {
                    "id": sec.id,
                    "title": sec.title,
                    "status": sec.status,
                    "gist": sec.gist,
                    "content": store.load_section(slug, sec.id),
                }
            )

        literature = []
        for lit in store.load_literature(slug, status="accepted"):
            literature.append(
                {
                    "id": lit.id,
                    "title": lit.title,
                    "authors": list(lit.authors or []),
                    "year": lit.year,
                    "venue": lit.venue,
                    "url": lit.url,
                    "content_source": lit.content_source,
                }
            )

        brief = store.load_brief(slug)
        return {
            "slug": slug,
            "title": brief.title if brief else slug,
            "kind": brief.kind if brief else "report",
            "cursor": meta.get("cursor") or "",
            "outline": outline,
            "sections": sections,
            "literature": literature,
            "profile": profile_to_prompt(),
        }

    def send_message(self, message: str, project_slug: str) -> dict:
        """
        发送用户消息

        Args:
            message: 用户输入
            project_slug: 项目 slug

        Returns:
            响应字典，包含 type 和 content/data
        """
        self._ensure_graph(project_slug)

        # TODO: 调用图，检查是否停在 interrupt
        # TODO: 若有，返回 {"type": "confirmation", "data": ...}
        # TODO: 若无，返回 {"type": "message", "content": ...}

        return {"type": "message", "content": "未实现"}

    def confirm_action(self, accept: bool, payload: dict | None = None) -> dict:
        """
        确认或拒绝当前 interrupt 确认卡，并以 Command(resume=...) 恢复图。

        Args:
            accept: 是否接受
            payload: 可选补充字段。文献可传 selected_ids；提问可传 text；
                大纲可传 titles；skill 可传 markdown / name。

        Returns:
            与 send_message 相同形态的响应：message / confirmation / update
        """
        if not self.pending_confirmation:
            return {"type": "message", "content": "没有待确认的动作"}
        if not self._graph or not self.current_project:
            return {"type": "message", "content": "没有打开的项目"}

        resume = self._build_resume_payload(bool(accept), payload)
        card = self.pending_confirmation
        self.pending_confirmation = None

        try:
            result = self._graph.invoke(Command(resume=resume), self._thread_config())
        except Exception as exc:  # noqa: BLE001 — 窗口侧统一成消息
            self.pending_confirmation = card
            return {"type": "message", "content": f"确认失败: {exc}"}

        return self._response_from_result(result)

    def _build_resume_payload(self, accept: bool, payload: dict | None) -> dict:
        """按确认卡类型组装 interrupt() 的返回值。"""
        extra = dict(payload or {})
        card = self.pending_confirmation or {}
        card_type = card.get("card_type")
        resume: dict[str, Any] = {"accept": accept}

        if card_type == "literature":
            if "selected_ids" in extra:
                resume["selected_ids"] = list(extra.get("selected_ids") or [])
            elif accept:
                resume["selected_ids"] = [
                    item.get("id")
                    for item in (card.get("items") or [])
                    if item.get("id") and item.get("available", True)
                ]
            else:
                resume["selected_ids"] = []
        elif card_type == "outline":
            if "titles" in extra:
                resume["titles"] = list(extra.get("titles") or [])
            elif card.get("titles"):
                resume["titles"] = list(card["titles"])
        elif card_type == "skill":
            if extra.get("markdown"):
                resume["markdown"] = extra["markdown"]
            elif card.get("markdown"):
                resume["markdown"] = card["markdown"]
            if extra.get("name"):
                resume["name"] = extra["name"]
            elif card.get("name"):
                resume["name"] = card["name"]
        elif card_type == "question":
            text = extra.get("text") or extra.get("answer") or ""
            resume["text"] = text
            resume["answer"] = text

        return resume

    def _response_from_result(self, result: Any) -> dict:
        """把图 invoke 结果变成前端响应；若再次 interrupt 则挂起确认卡。"""
        card = _interrupt_value(result)
        if card is not None:
            self.pending_confirmation = card
            return {"type": "confirmation", "data": card}

        observation = ""
        if isinstance(result, dict):
            observation = str(result.get("last_observation") or "").strip()
        return {
            "type": "update",
            "content": observation or "已更新",
        }


def _interrupt_value(result: Any) -> dict | None:
    """从 invoke 返回值取出第一个 interrupt payload。"""
    if not isinstance(result, dict):
        return None
    interrupts = result.get("__interrupt__") or []
    if not interrupts:
        return None
    first = interrupts[0]
    value = getattr(first, "value", None)
    if value is None and isinstance(first, dict):
        value = first.get("value")
    return value if isinstance(value, dict) else None
