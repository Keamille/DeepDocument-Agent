"""
窗口 API

pywebview 的 js_api，连接前端和图。
"""

from __future__ import annotations

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

    def _ensure_graph(self, project_slug: str):
        """项目切换时才重新编译图。"""
        if not project_slug or project_slug == self.current_project:
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

    def confirm_action(self, accept: bool) -> dict:
        """
        确认或拒绝动作

        Args:
            accept: 是否接受

        Returns:
            响应字典
        """
        if not self.pending_confirmation:
            return {"type": "message", "content": "没有待确认的动作"}

        # TODO: 用 Command(resume=accept) 恢复图
        # TODO: 清除 pending_confirmation

        return {"type": "update"}
