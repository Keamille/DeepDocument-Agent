"""
窗口 API

pywebview 的 js_api，连接前端和图。
"""

from pathlib import Path

from deepdocument.graph.builder import build_graph


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
        """
        项目切换时才重新编译图

        Args:
            project_slug: 项目 slug
        """
        if not project_slug or project_slug == self.current_project:
            return
        self.current_project = project_slug
        self._graph = self._build_graph(project_slug)
        self.pending_confirmation = None

    def list_projects(self) -> list[dict]:
        """
        列出所有项目

        Returns:
            项目列表，每项包含 slug 和 title
        """
        projects_dir = Path("projects")
        if not projects_dir.exists():
            return []

        result = []
        for proj_dir in projects_dir.iterdir():
            if not proj_dir.is_dir():
                continue
            # TODO: 从 brief.md 读取 title
            result.append({"slug": proj_dir.name, "title": proj_dir.name})
        return sorted(result, key=lambda p: p["slug"])

    def load_project(self, slug: str) -> dict:
        """
        加载项目数据

        Args:
            slug: 项目 slug

        Returns:
            项目数据字典
        """
        self._ensure_graph(slug)

        # TODO: 从磁盘读取 outline, sections, literature, profile
        return {
            "outline": [],
            "sections": [],
            "literature": [],
            "profile": "",
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
